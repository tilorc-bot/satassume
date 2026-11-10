"""State step, part 2 (iii)(b), rest: Relations' fifteen dicts held in the session core (relkeys.rs `OrdMap`, session.rs `RelS.d`).

`adapters`, `status`, `_guards`, `_link_lt`, `top`, `link_sel`, `atom_sel`, `num_sel`, `_roles`, `_info`, `_link_of`, `_tv`,
`_tsrc`, `_xside` and `_xheads` were Python dicts on each `Relations`, read and written by relations_core.rs through the C API.
The core now holds them as insertion-ordered maps over RelKeys (values stay Python objects). Here, one process per run:
- the switch: the same queries on Python (each `Relations`' own dicts, the old state) and on Rust (the core's test-only snapshot
  export `rd_snapshot`), after every query; the digests (each dict's items in insertion order, since `_xheads` and `top` are
  iterated, values by repr with addresses masked) must be equal, and the dicts must fill;
- the record method: Python's writes through the views read back as a dict would, and `rel.X = d` goes through `set_rd`;
- the plants (relkeys.rs RD_PLANT0, 390-404) each move the digest, or are named void; the counters (rd:*, 520-522) are read out.
"""
import hashlib
import json
import os
import subprocess
import sys

import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ('adapters', 'status', '_guards', '_link_lt', 'top', 'link_sel', 'atom_sel', 'num_sel', '_roles', '_info', '_link_of',
         '_tv', '_tsrc', '_xside', '_xheads')
PLANTS = tuple('rd-%s-drop' % n.lstrip('_') for n in NAMES)
WLS = ('transfer:7:60', 'transfer2:3:40', 'fuzz:200', 'scope')


def _queries(wl):
    import live
    if wl.startswith('fuzz:'):
        return list(live.load('fuzz'))[:int(wl.split(':')[1])]
    return list(live.load(wl))


_ADDR = re.compile(r' at 0x[0-9a-f]+')
# Default specs hold the Rust adapters (the RelKeys ruling, (3)): an adapter compares by its class's own name.
_CLS = re.compile(r'<[\w.]*\.(\w+Adapter) object>')


def _r(x):
    return _CLS.sub(r'<\1>', _ADDR.sub('', repr(x)))


def _norm(items):
    return [[_r(k), _r(v)] for k, v in items]


def _child(mode):
    if mode == 'rust':
        from test_relations_core import _rust
        _rust()
        import sa_solver
    from satassume import sympy_api
    from satassume.relations import Relations
    made = []
    init = Relations.__init__

    def tracked(self, *a, **k):
        r = init(self, *a, **k)
        t = getattr(a[0], 'table', None) if mode == 'rust' else None
        made.append((self, getattr(t, 'core', None)))    # the session goes with its query; its core is kept here
        return r
    Relations.__init__ = tracked
    out = dict(rows=[], filled={n: 0 for n in NAMES}, in_dict=0, rd={})
    for wl in WLS:
        before = dict(sa_solver.session_counts()) if mode == 'rust' else {}
        for i, (p, a) in enumerate(_queries(wl)):
            del made[:]
            try:
                sympy_api.ask(p, a)
            except Exception:
                pass
            row = []
            for rel, core in made:
                if mode == 'rust':
                    snap = [d for r, d in core.rd_snapshot() if r is rel]
                    out['in_dict'] += any(n in rel.__dict__ for n in NAMES)
                    ds = snap[0] if snap else None
                else:
                    ds = {n: list(rel.__dict__[n].items()) for n in NAMES} if 'status' in rel.__dict__ else None
                if ds is not None:
                    for n in NAMES:
                        out['filled'][n] += bool(ds[n])
                row.append(None if ds is None else [_norm(ds[n]) for n in NAMES])
            out['rows'].append([wl, i, row])
        if mode == 'rust':
            after = dict(sa_solver.session_counts())
            out['rd'][wl] = {k: after[k] - before.get(k, 0) for k in after if k.startswith('rd:')}
    Relations.__init__ = init
    out['digest'] = hashlib.blake2b(json.dumps(out['rows']).encode(), digest_size=8).hexdigest()
    out['n'] = len(out['rows'])
    if mode == 'rust':
        # The record method, through the views.
        from sympy import Integer, Q, Symbol, pi
        from satassume.engine import Engine, Session
        import term_live
        eng = Engine()
        x = Symbol('x')
        term_live.stack().append(term_live._convert(Q.positive(x + pi + 2), True, eng))
        s = Session(eng)
        rel = Relations(s, eng._relation_specs)
        first = [len(getattr(rel, n)) for n in NAMES]
        d = rel._xheads
        d[(x, 1)] = []
        d.setdefault((x, 1), []).append(x)
        d.setdefault((x + 1, 0), []).append(pi)
        rel.num_sel[Integer(2)] = 5
        rel.num_sel[2] = 6                                   # joins Integer(2), as a dict does
        rel.top[x] = None
        rel.top[pi] = None
        taken = list(rel.top)
        rel.top.clear()
        rel._tv = {x: [1, 2]}                                # the record method
        rel.status[x] = False
        out['record'] = [first[1:] == [0] * 14, list(d.items()) == [((x, 1), [x]), ((x + 1, 0), [pi])],
                         rel.num_sel.get(2) == 6 and len(rel.num_sel) == 1, rel.num_sel.get(x, 'dflt') == 'dflt',
                         taken == [x, pi] and not rel.top and len(rel.top) == 0, dict(rel._tv) == {x: [1, 2]},
                         rel.status.get(x) is False and x in rel.status, (x, 2) not in d,
                         not any(n in rel.__dict__ for n in NAMES)]
        term_live.stack().pop()
        out['counts'] = {k: v for k, v in sa_solver.session_counts().items() if k.startswith('rd:')}
    if os.environ.get('RD_DUMP'):
        with open(os.environ['RD_DUMP'] + '.' + mode, 'w') as f:
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
    assert py['n'] == rust['n'] and all(py['filled'][n] > 0 for n in ('status', 'link_sel', '_roles')), py['filled']
    assert rust['digest'] == py['digest'], (py, rust)
    assert rust['filled'] == py['filled'] and rust['in_dict'] == 0


def test_record_method_and_counters(rust):
    assert all(rust['record']), rust['record']
    c = rust['counts']
    assert all(c[k] > 0 for k in ('rd:core', 'rd:view', 'rd:record')), c


@pytest.mark.parametrize('plant', PLANTS)
def test_plant_moves_the_digest(rust, plant):
    got = _run('rust', plant)
    assert got['digest'] != rust['digest'], plant


if __name__ == '__main__' and sys.argv[1:2] == ['child']:
    _child(sys.argv[2])
