"""State step, part 2 (iii)(b), rest: Relations' four work lists held in the session core (relkeys.rs `RelListView`, session.rs
`RelS.l`).

`queue`, `_pending_links`, `_xextra` and `_xpend` were Python lists on each `Relations`, read and written by relations_core.rs
through the C API. The core now holds them as `Vec`s of Python objects. `specs` stays Python's list (configuration: never written
after `__init__`). Here, one process per run:
- the switch: the same queries on Python (each `Relations`' own lists, the old state) and on Rust (the core's test-only snapshot
  export `rl_snapshot`); the lists are drained by the end of a query, so they're sampled at every `_interpret` and `_link` call
  (each a point where Python can read them) and at the end, beside the moved dicts and sets at the end. The digests must be
  equal, and each list must be seen non-empty;
- the record method: Python's writes through the views read back as a list would, and `rel.X = xs` goes through `set_rl`;
- the plants (relkeys.rs RL_PLANT0, 405-408) each move the digest; the counters (rl:*, 523-525) are read out.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ('queue', '_pending_links', '_xextra', '_xpend')
DNAMES = ('adapters', 'status', '_guards', '_link_lt', 'top', 'link_sel', 'atom_sel', 'num_sel', '_roles', '_info', '_link_of',
          '_tv', '_tsrc', '_xside', '_xheads')
SNAMES = ('linked', '_bounded', '_user_eq', '_xpairs', '_aux_eq', '_link_eq', '_xpart', '_xcounted', '_xcand')
PLANTS = tuple('rl-%s-drop' % n.lstrip('_') for n in NAMES)
WLS = ('transfer:7:60', 'transfer2:3:40', 'fuzz:200', 'scope')
_ADDR = re.compile(r' at 0x[0-9a-f]+')
_CLS = re.compile(r'<[\w.]*\.(\w+Adapter) object>')


def _r(x):
    return _CLS.sub(r'<\1>', _ADDR.sub('', repr(x)))


def _queries(wl):
    import live
    if wl.startswith('fuzz:'):
        return list(live.load('fuzz'))[:int(wl.split(':')[1])]
    return list(live.load(wl))


def _child(mode):
    if mode == 'rust':
        from test_relations_core import _rust
        _rust()
        import sa_solver
    from satassume import sympy_api
    from satassume.relations import Relations
    rust = mode == 'rust'
    made = []
    seen = {n: 0 for n in NAMES}

    def lists(rel, core=None):
        if rust:
            snap = [d for r, d in (core or rel.session.table.core).rl_snapshot() if r is rel]
            return snap[0] if snap else None
        return {n: list(rel.__dict__[n]) for n in NAMES} if 'queue' in rel.__dict__ else None

    def sample(rel, at):
        ls = lists(rel)
        if ls is not None:
            for n in NAMES:
                seen[n] += bool(ls[n])
            mid.append([at] + [[_r(x) for x in ls[n]] for n in NAMES])
    init, interp, link = Relations.__init__, Relations._interpret, Relations._link

    def tracked(self, *a, **k):
        r = init(self, *a, **k)
        made.append((self, getattr(getattr(a[0], 'table', None), 'core', None) if rust else None))
        return r

    def t_interp(self, atom):
        sample(self, 'interpret')
        return interp(self, atom)

    def t_link(self, e):
        sample(self, 'link')
        return link(self, e)
    Relations.__init__, Relations._interpret, Relations._link = tracked, t_interp, t_link
    out = dict(rows=[], in_dict=0, rl={})
    for wl in WLS:
        before = dict(sa_solver.session_counts()) if rust else {}
        for i, (p, a) in enumerate(_queries(wl)):
            del made[:]
            mid = []
            try:
                sympy_api.ask(p, a)
            except Exception:
                pass
            row = []
            for rel, core in made:
                ls = lists(rel, core)
                if rust:
                    out['in_dict'] += any(n in rel.__dict__ for n in NAMES)
                    ds = [d for r, d in core.rd_snapshot() if r is rel]
                    ss = [d for r, d in core.rs_snapshot() if r is rel]
                    ds, ss = (ds[0] if ds else None), (ss[0] if ss else None)
                else:
                    has = 'status' in rel.__dict__
                    ds = {n: list(rel.__dict__[n].items()) for n in DNAMES} if has else None
                    ss = {n: rel.__dict__[n] for n in SNAMES} if has else None
                row.append([None if ls is None else [[_r(x) for x in ls[n]] for n in NAMES],
                            None if ds is None else [[[_r(k), _r(v)] for k, v in ds[n]] for n in DNAMES],
                            None if ss is None else [sorted(map(repr, ss[n])) for n in SNAMES]])
            out['rows'].append([wl, i, mid, row])
        if rust:
            after = dict(sa_solver.session_counts())
            out['rl'][wl] = {k: after[k] - before.get(k, 0) for k in after if k.startswith('rl:')}
    Relations.__init__, Relations._interpret, Relations._link = init, interp, link
    out['seen'] = seen
    out['digest'] = hashlib.blake2b(json.dumps(out['rows']).encode(), digest_size=8).hexdigest()
    out['n'] = len(out['rows'])
    if rust:
        # The record method, through the views (with any plant off: the plants are for the digest above).
        sa_solver.rel_plant(None)
        from sympy import Q, Symbol, pi
        from satassume.engine import Engine, Session
        import term_live
        eng = Engine()
        x, y = Symbol('x'), Symbol('y')
        term_live.stack().append(term_live._convert(Q.positive(x + pi + 2), True, eng))
        s = Session(eng)
        rel = Relations(s, eng._relation_specs)
        first = [len(getattr(rel, n)) for n in NAMES]
        q = rel.queue
        q.append(x)
        q.extend([y, pi])
        got = [q.pop(), len(q), bool(q), list(q), q[0], q[-1]]
        rel._xpend[:] = [(x, 0), (y, 4)]
        keep = [e for e in rel._xpend if e[1]]
        rel._xpend[:] = keep
        rel._xextra = [x]                                     # the record method
        new = [y]
        new.extend(rel._xextra)
        rel._xextra.clear()
        try:
            rel._pending_links.pop()
            empty_pop = False
        except IndexError:
            empty_pop = True
        out['record'] = [first == [0] * 4, got == [pi, 2, True, [x, y], x, y], list(rel._xpend) == [(y, 4)],
                         new == [y, x] and not rel._xextra, empty_pop, isinstance(rel.specs, list),
                         not any(n in rel.__dict__ for n in NAMES)]
        term_live.stack().pop()
        out['counts'] = {k: v for k, v in sa_solver.session_counts().items() if k.startswith('rl:')}
    if os.environ.get('RL_DUMP'):
        with open(os.environ['RL_DUMP'] + '.' + mode, 'w') as f:
            json.dump(out['rows'], f)
    del out['rows']
    print(json.dumps(out))


def _run(mode, plant=None):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    env.pop('SLICE_SESSION_PLANT', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    r = subprocess.run([sys.executable, os.path.abspath(__file__), 'child', mode], env=env, capture_output=True, text=True,
                       timeout=1800)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope='module')
def py():
    return _run('py')


@pytest.fixture(scope='module')
def rust():
    return _run('rust')


def test_snapshot_digest_equal_at_the_switch(py, rust):
    assert py['n'] == rust['n'] and all(py['seen'][n] > 0 for n in NAMES), py['seen']
    assert rust['digest'] == py['digest'], (py, rust)
    assert rust['seen'] == py['seen'] and rust['in_dict'] == 0


def test_record_method_and_counters(rust):
    assert all(rust['record']), rust['record']
    c = rust['counts']
    assert all(c[k] > 0 for k in ('rl:core', 'rl:view', 'rl:record')), c


@pytest.mark.parametrize('plant', PLANTS)
def test_plant_moves_the_digest(rust, plant):
    got = _run('rust', plant)
    assert got['digest'] != rust['digest'], plant


if __name__ == '__main__' and sys.argv[1:2] == ['child']:
    _child(sys.argv[2])
