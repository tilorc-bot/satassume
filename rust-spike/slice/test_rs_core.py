"""State step, part 2 (iii)(b), rest: RelKeys and Relations' nine sets held in the session core (relkeys.rs, session.rs `RelS`).

`linked`, `_bounded`, `_user_eq`, `_xpairs`, `_aux_eq`, `_link_eq`, `_xpart`, `_xcounted` and `_xcand` were Python sets on each
`Relations`, read and written by relations_core.rs through the C API. The core now holds them as `HashSet<u32>` over RelKeys
(a key with a term id in the query's table takes it; others are interned by hash, counted rk:intern:input / rk:intern:engine).
Here, one process per run:
- the switch: the same queries on Python (each `Relations`' own sets, the old state) and on Rust (the core's test-only snapshot
  export `rs_snapshot`), after every query; the digests (each set's members, sorted by repr, since no set is iterated) must be
  equal, and the sets must fill;
- the class join (the state rule): a Python set joins `==`-equal members of different classes (`2` and `Integer(2)`); Rust's
  sets must never hold two `==` members, on the workloads and on a seeded case;
- the record method: Python's writes through the views (`add`, `update`, `in`, `len`) read back as Python's would;
- the plants (relkeys.rs RS_PLANT0, 269-277) each move the digest; the counters (rk:*, rs:*, 350-358) are read out.
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ('linked', '_bounded', '_user_eq', '_xpairs', '_aux_eq', '_link_eq', '_xpart', '_xcounted', '_xcand')
PLANTS = tuple('rs-%s-drop' % n.lstrip('_') for n in NAMES)
WLS = ('transfer:7:60', 'transfer2:3:40', 'fuzz:200', 'scope')


def _queries(wl):
    import live
    if wl.startswith('fuzz:'):
        return list(live.load('fuzz'))[:int(wl.split(':')[1])]
    return list(live.load(wl))


def _norm(xs):
    return sorted(repr(x) for x in xs)


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
    out = dict(rows=[], filled={n: 0 for n in NAMES}, in_dict=0, joined=0, rk={})
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
                    snap = [d for r, d in core.rs_snapshot() if r is rel]
                    out['in_dict'] += any(n in rel.__dict__ for n in NAMES)
                    sets = snap[0] if snap else None
                    if sets is not None:
                        # two `==` members in one set: a join Python's set would have made
                        out['joined'] += sum(len(set(sets[n])) != len(sets[n]) for n in NAMES)
                else:
                    sets = {n: rel.__dict__[n] for n in NAMES} if 'linked' in rel.__dict__ else None
                if sets is not None:
                    for n in NAMES:
                        out['filled'][n] += bool(sets[n])
                row.append(None if sets is None else [_norm(sets[n]) for n in NAMES])
            out['rows'].append([wl, i, row])
        if mode == 'rust':
            after = dict(sa_solver.session_counts())
            out['rk'][wl] = {k: after[k] - before.get(k, 0) for k in after if k.startswith(('rk:', 'rs:core', 'rs:view',
                                                                                            'rs:record'))}
    Relations.__init__ = init
    out['digest'] = hashlib.blake2b(json.dumps(out['rows']).encode(), digest_size=8).hexdigest()
    out['n'] = len(out['rows'])
    if mode == 'rust':
        # The record method and the class join, through the views.
        from sympy import Float, Integer, S, Symbol
        from satassume.engine import Engine, Session
        import term_live
        from sympy import Q, pi
        eng = Engine()
        x = Symbol('x')
        term_live.stack().append(term_live._convert(Q.positive(x + pi + 2), True, eng))   # x has a term id; 2.0, True don't
        s = Session(eng)
        rel = Relations(s, eng._relation_specs)

        def core_of(r):
            return [d for q, d in s.table.core.rs_snapshot() if q is r][0]
        first = [len(getattr(rel, n)) for n in NAMES]
        rel._xcand.add(x)
        rel._xcand.update([x, x + 1])
        rel._xpart.add(Integer(2))
        rel._xpart.add(2)
        rel._xpart.add(2.0)
        rel._xpart.add(Float(2))
        rel._xpart.add(True)
        rel._xpart.add(S.true)
        py = set()
        for y in (Integer(2), 2, 2.0, Float(2), True, S.true):
            py.add(y)
        # `_bounded`: no workload reaches `_bound` (port-c2b.md), so `_guard` is called directly, as test_relations_core's
        # `_direct` does: a closed term twice in a guarded adapter's term list.
        s.relations = rel
        ad = next(a for a in map(rel._adapter, eng._relation_specs) if hasattr(a, 'register_bounds'))
        s.solver.attach_theory(ad.theory)
        rel._guard(ad, [pi])
        rel._guard(ad, [pi, x])
        out['bounded'] = _norm(core_of(rel)['_bounded'])
        out['record'] = [first == [0] * 9, len(rel._xcand) == 2, x in rel._xcand, (x + 1) in rel._xcand,
                         (x + 2) not in rel._xcand, len(rel._xpart) == len(py), 2 in rel._xpart, Integer(2) in rel._xpart,
                         not any(n in rel.__dict__ for n in NAMES)]
        term_live.stack().pop()
        out['counts'] = {k: v for k, v in sa_solver.session_counts().items() if k.startswith(('rk:', 'rs:core', 'rs:view',
                                                                                              'rs:record'))}
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
    assert py['n'] == rust['n'] and all(py['filled'][n] > 0 for n in ('linked', '_xcand', '_aux_eq')), py['filled']
    assert rust['digest'] == py['digest'], (py, rust)
    assert rust['filled'] == py['filled'] and rust['in_dict'] == 0


def test_no_set_misses_a_class_join(rust):
    assert rust['joined'] == 0


def test_record_method_and_counters(rust):
    assert all(rust['record']), rust['record']
    assert rust['bounded'] == ['pi'], rust['bounded']
    c = rust['counts']
    assert all(c[k] > 0 for k in ('rk:intern:input', 'rk:intern:engine', 'rk:term', 'rs:core', 'rs:view', 'rs:record')), c


@pytest.mark.parametrize('plant', PLANTS)
def test_plant_moves_the_digest(rust, plant):
    got = _run('rust', plant)
    assert (got['digest'], got['bounded']) != (rust['digest'], rust['bounded']), plant


if __name__ == '__main__' and sys.argv[1:2] == ['child']:
    _child(sys.argv[2])
