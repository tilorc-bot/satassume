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
- the plants (relkeys.rs RS_PLANT0, 269-277) each move the digest; the counters (rk:*, rs:*, 350-358) are read out;
- two equal classes (`_twin`, its own process): one query holding `f(0)` under two `==` `Function("f")` classes keys it once,
  as Python's sets did; the plant `class-is` (661) gives the second class's object its own key and is caught by the
  answer and by the sets' digest against Python.
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
        # A session that outlives its query (the two tests/test_scope.py failures on the bar of 1a6d38a): the next query's
        # table is allocated at the dead table's address, and each table gives its symbol the same term id. RelKeys must
        # see a second table (by its serial) and go dict-only, not read `a`'s id as `b`'s.
        import gc
        import convert
        a, b = Symbol('a'), Symbol('b')
        ca = convert.convert(Q.positive(a + pi), True, eng)
        cb = convert.convert(Q.positive(b + pi), True, eng)
        qa = term_live._Query(ca)
        term_live.stack().append(qa)
        s2 = Session(eng)
        rel2 = Relations(s2, eng._relation_specs)
        rel2._xcand.add(a)
        addr, before = id(qa.table), sa_solver.session_counts()['rk:outlive']
        term_live.stack().pop()
        del qa
        gc.collect()
        held = []
        for _ in range(50):
            qb = term_live._Query(cb)
            if id(qb.table) == addr:
                break
            held.append(qb)
        term_live.stack().append(qb)
        out['alias'] = {'same_address': id(qb.table) == addr, 'ids': [ca.ids.get(a), cb.ids.get(b)],
                        'b_in': b in rel2._xcand, 'a_in': a in rel2._xcand, 'len': len(rel2._xcand),
                        'outlive': sa_solver.session_counts()['rk:outlive'] - before}
        term_live.stack().pop()
    del out['rows']
    print(json.dumps(out))


def _twin(mode):
    """One query that meets `f(u)` and `f(0)` under two equal `Function("f")` classes, the suite's order in small
    (tests/test_history.py::test_fixed_repro_stays_fixed[T1-transfer-congruent-application] before
    tests/test_ref.py::test_zero_under_an_application_is_an_equality[T1-transfer-congruent-application]).
    Class A's query is built first and held, as test_ref's module constants are. SymPy's cache is then emptied (in the suite
    the lru cache evicts `Function("f")`), so `Function("f")` is a second class B, `==` to A and hashing alike. B's query is
    asked between a registry snapshot and its restore, as harness.checker.execute does: the restore is a new registry
    version, and process-wide memos keep B's objects. Then A's held query is asked on a fresh engine: its session meets
    A's objects from the query and B's from the memos."""
    if mode == 'rust':
        from test_relations_core import _rust
        _rust()
        import sa_solver
    from sympy import Function, Q, Symbol
    from sympy.core.cache import clear_cache
    from satassume import sympy_api
    from satassume.engine import DictCache, Engine
    from satassume.knowledge.extensions import extensions
    from satassume.relations import Relations
    u = Symbol('u')
    fa = Function('f')
    pa, aa = Q.positive(fa(u)), Q.zero(u) & Q.positive(fa(0))
    clear_cache()
    fb = Function('f')
    pb, ab = Q.positive(fb(u)), Q.zero(u) & Q.positive(fb(0))
    out = dict(two_classes=[fa is not fb, fa == fb, hash(fa) == hash(fb), pa == pb, aa == ab,
                            type(pa.arguments[0]) is fa, type(pb.arguments[0]) is fb])
    snap = extensions.snapshot()
    out['first'] = sympy_api.ask(pb, ab, engine=Engine(cache=DictCache(), uninterpreted='none'))
    extensions.restore(snap)
    made = []
    init = Relations.__init__

    def tracked(self, *a, **k):
        r = init(self, *a, **k)
        made.append((self, getattr(getattr(a[0], 'table', None), 'core', None) if mode == 'rust' else None))
        return r
    Relations.__init__ = tracked
    before = dict(sa_solver.session_counts()) if mode == 'rust' else {}
    out['answer'] = sympy_api.ask(pa, aa, engine=Engine(cache=DictCache(), uninterpreted='none'))
    Relations.__init__ = init
    # the nine sets, and the fifteen dicts' keys in insertion order (test_rd_core.py's snapshot)
    import test_rd_core
    rows = []
    for rel, core in made:
        if mode == 'rust':
            sets = [d for r, d in core.rs_snapshot() if r is rel][0]
            dicts = [d for r, d in core.rd_snapshot() if r is rel][0]
        else:
            sets = {n: rel.__dict__[n] for n in NAMES}
            dicts = {n: list(rel.__dict__[n].items()) for n in test_rd_core.NAMES}
        rows.append([[_norm(sets[n]) for n in NAMES], [[test_rd_core._r(k) for k, _ in dicts[n]] for n in test_rd_core.NAMES]])
    out['rows'] = rows
    out['filled'] = [sum(bool(x) for row in rows for x in row[i]) for i in (0, 1)]
    if mode == 'rust':
        after = dict(sa_solver.session_counts())
        out['counts'] = {k: after.get(k, 0) - before.get(k, 0) for k in ('join', 'cls:eq', 'link:none', 'rel:plant_fired')}
    print(json.dumps(out))


def _run(mode, plant=None, child='child'):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    env.pop('SLICE_SESSION_PLANT', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    r = subprocess.run([sys.executable, os.path.abspath(__file__), child, mode], env=env, capture_output=True, text=True,
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


def test_a_later_table_at_a_dead_tables_address_is_a_second_table(rust):
    """Found by the bar of 1a6d38a (tests/test_scope.py::test_answers_agree_with_the_lazy_order and
    ::test_zero_twins_are_in_the_scope answered None for True in the suite's order): RelKeys compared the query table by
    address, so a session outliving its query read the dead table's term ids as the next table's. On 1a6d38a this gives
    b_in True and a_in False."""
    al = rust['alias']
    assert al['same_address'] and al['ids'][0] == al['ids'][1] is not None, al    # the control: the alias is reached
    assert al == dict(al, b_in=False, a_in=True, len=1, outlive=1), al


def test_two_equal_function_classes_key_as_one():
    """Found by the bar of 0576370 (eight zero-twin ids of tests/test_scope.py, tests/test_ref.py and tests/test_zero_glue.py
    answered None in the suite's order): `f(0)` of a second, equal `Function("f")` class has no row of its own class in the
    query's table, so RelKeys interned it by hash beside the first class's term-id key, and the moved sets held as two
    members what Python's sets held as one. On 0576370 the answer here is None and the rows differ from Python's."""
    py, rust = _run('py', child='twin'), _run('rust', child='twin')
    assert all(py['two_classes']) and all(rust['two_classes']), (py['two_classes'], rust['two_classes'])
    assert rust['counts']['join'] > 0, rust['counts']    # the control: the session met both classes
    assert py['first'] is True and py['answer'] is True and min(py['filled']) > 0, py
    assert (rust['first'], rust['answer']) == (py['first'], py['answer']), (py['answer'], rust['answer'], rust['counts'])
    assert rust['rows'] == py['rows'], (py['rows'], rust['rows'])
    # by the query's own class table: the second class's object takes the first's row (term_live.py `same_class`)
    assert rust['counts']['cls:eq'] > 0, rust['counts']


def test_class_split_plant_is_caught():
    """The second class's object keyed apart (plant `class-is`, 661: a row counts only for its own class object again, so
    RelKeys interns the object by hash beside the first's term-id key) loses the answer and moves the sets' digest off
    Python's. Until the formula step this was plant `rk-class-split` (409) on relkeys.rs's `twin_row`, which the query's class
    table made unreachable."""
    py, got = _run('py', child='twin'), _run('rust', 'class-is', child='twin')
    assert got['counts']['cls:eq'] == 0 and got['counts']['join'] > 0 and got['counts']['rel:plant_fired'] > 0, got['counts']
    assert got['answer'] != py['answer'], got
    assert got['rows'] != py['rows'], got['rows']
    # `_tv` (the transfer's values) is where the two keys show: `f(u)` and `f(0)` twice
    import test_rd_core
    tv = got['rows'][0][1][test_rd_core.NAMES.index('_tv')]
    assert len(tv) > len(set(tv)), tv


@pytest.mark.parametrize('plant', PLANTS)
def test_plant_moves_the_digest(rust, plant):
    got = _run('rust', plant)
    assert (got['digest'], got['bounded']) != (rust['digest'], rust['bounded']), plant


if __name__ == '__main__' and sys.argv[1:2] == ['child']:
    _child(sys.argv[2])
elif __name__ == '__main__' and sys.argv[1:2] == ['twin']:
    _twin(sys.argv[2])
