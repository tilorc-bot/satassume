"""`ad:cbm_noid` cause read (issue 323, results/cbm-noid-cause.md). Two `Function('f')` are one class to SymPy (`==`, same hash)
and two class objects. Process-wide memos keyed by `==` hand back whichever object came first, so a query can hold `f(1)` of
one class object while the engine's atoms hold `f(1)` of the other. A row then counts for both; before the fix the term had
no id and Python read it, counted as `ad:cbm_noid`, by test order. Run on the suite's plugin:
`run_suite.sh WORK rust rust-spike/slice/test_cbm_noid.py` (on `python` the answers are checked and the counts skipped).

The fix (sa-port-243): every site that takes a row for a term asks `same_class` (term_live.py, and formula.rs for Rust's
sites), which reads the query's own class table (`_Query.classes`, keyed by the classes' hash and `==` at conversion), never
a process-wide one. Plant 660 (`ad-lra-class-is`) puts the identity compare back in adapters.rs `Reader.id` alone; plant 661
(`class-is`) puts it back at every site. Both must fire and be seen here."""
import sys

import pytest
from sympy import Function, Q, S, Symbol
from sympy.core.cache import clear_cache

#: Python's answers (the same list on both backends, before and after the fix)
WANT = dict(first=None, second=None, mixed=[True, True, False, None, True, False])


def _counts():
    sl = sys.modules.get('session_live')
    return sl.counts() if sl else None


def _ask(p, a=True):
    from satassume import Engine
    from satassume.engine import DictCache
    from satassume.sympy_api import ask
    return ask(p, a, engine=Engine(cache=DictCache()))


def _leaves(x, out):
    """Every SymPy object a reader's result holds, containers opened."""
    from sympy import Basic
    if isinstance(x, dict):
        for k, v in x.items():
            _leaves(k, out), _leaves(v, out)
    elif isinstance(x, (tuple, list)):
        for y in x:
            _leaves(y, out)
    elif isinstance(x, Basic):
        out.append(x)
    return out


def _applied(t, out):
    from sympy.core.function import AppliedUndef
    if isinstance(t, AppliedUndef):
        out.append(t)
    for a in t.args:
        _applied(a, out)
    return out


def _run(watch=None):
    """`watch(tag, f1, f2)` is called before each group of queries and returns a function called after it."""
    watch = watch or (lambda *a: (lambda: None))
    a, b = Symbol('a'), Symbol('b')
    f1 = Function('f')
    t1 = f1(S(1))
    clear_cache()                   # else SymPy's own cache hands `f1`'s object back for `f2(1)`
    f2 = Function('f')
    t2 = f2(S(1))
    assert t1 == t2 and hash(t1) == hash(t2) and type(t1) is not type(t2) and type(t1) == type(t2)
    c0 = _counts()
    done = watch('first', f1, f2)
    got = dict(first=_ask(Q.eq(S(1), t1), Q.ne(b, a)))      # the memos now hold `f1`'s `f(1)` ...
    done()
    done = watch('second', f1, f2)
    got['second'] = _ask(Q.eq(S(1), t2), Q.ne(b, a))        # ... and this query's rows hold `f2`'s
    done()
    clear_cache()
    x1 = f1(a)
    clear_cache()
    x2, y2 = f2(a), f2(b)
    assert type(x1) is not type(x2)
    # both class objects inside one query; the first two answers need them to be one function
    mixed = [(Q.eq(x1, x2), True), (Q.eq(x1, y2), Q.eq(a, b)), (Q.lt(x1, x2), True), (Q.gt(x1 + 1, x2), True),
             (Q.le(x1, 3), Q.lt(x2, 2) & Q.real(x2)), (Q.eq(t1, 2), Q.eq(t2, 3))]
    got['mixed'] = []
    for n, (p, asm) in enumerate(mixed):
        done = watch(f'mixed{n}', f1, f2)
        got['mixed'].append(_ask(p, asm))
        done()
    c1 = _counts()
    d = None if c0 is None else {k: c1.get(k, 0) - c0.get(k, 0)
                                 for k in ('ad:cbm_noid', 'ad:lra_native', 'rel:plant_fired', 'cls:eq', 'cls:differs')}
    return got, d


def test_equal_classes_take_the_row():
    got, d = _run()
    assert got == WANT
    if d is None:
        pytest.skip('Python backend: answers checked, no session counts')
    assert d['ad:lra_native'] > 0, 'the adapter was never asked: the zero below would prove nothing'
    assert d['ad:cbm_noid'] == 0 and d['rel:plant_fired'] == 0, d
    assert d['cls:eq'] > 0, 'no row was taken across two class objects: the zero above would prove nothing'


def test_plant_660_fires_and_is_seen():
    if _counts() is None:
        pytest.skip('Python backend: no plant')
    import sa_solver
    sa_solver.formula_plant('ad-lra-class-is')
    try:
        got, d = _run()
    finally:
        sa_solver.formula_plant(None)
    assert d['rel:plant_fired'] > 0, 'plant 660 no longer fires'
    assert d['ad:cbm_noid'] > 0, d       # what test_equal_classes_take_the_row asserts is 0
    assert got == WANT                   # Python reads the term then, so the answers stay Python's


def test_plant_661_fires_and_is_seen():
    if _counts() is None:
        pytest.skip('Python backend: no plant')
    import sa_solver
    sa_solver.formula_plant('class-is')
    try:
        got, d = _run()
    finally:
        sa_solver.formula_plant(None)
    assert d['rel:plant_fired'] > 0, 'plant 661 no longer fires'
    assert d['cls:eq'] == 0 and d['ad:cbm_noid'] > 0, d
    assert got == WANT


def _held(plant=None):
    """Per group of queries, which class object each `f(...)` in a native reader result is of, and whether the object is
    one of the query's own rows. Rust only (`sa_solver.ad_lra_export`: every slot entry as it is stored)."""
    import sa_solver
    rows = []

    def watch(tag, f1, f2):
        sa_solver.ad_lra_export(True)

        def done():
            for q, k, arg, flag, r in sa_solver.ad_lra_export(False):
                for t in _leaves(r, []):
                    for u in _applied(t, []):
                        rows.append((tag, k, str(arg), 'f1' if type(u) is f1 else 'f2' if type(u) is f2 else '?',
                                     any(u is o for o in q.objects)))
        return done
    return _run(watch), rows


def _not_first(rows):
    """The rule's violations in `_held`'s rows. The rule (planner, 10 Nov, RULINGS.md 5, the one named exception to
    "results hold Python's objects"): **an equal class is represented by its first occurrence in the query's input.**"""
    bad = [r for r in rows if not r[-1]]                # an object that is not one of the query's own rows
    # The two cases where Python's result holds the atom's own `f2` object (`_memoized`'s results on the Python backend,
    # ~/sa-rust-ids-work/sa-port-243/explore-python; its choice follows the process-wide `_INTERPRETED` memo) and the
    # native one holds the row's, `f1`'s, the first the query's input shows:
    for tag, arg in (('mixed3', 'Q.lt(f(a), f(a) + 1)'), ('mixed4', 'Q.lt(f(a), 2)')):
        held = {c for t, k, a, c, _ in rows if t == tag and a == arg and k == 0}
        if held != {'f1'}:
            bad.append((tag, arg, held))
    return bad


def test_native_results_hold_the_querys_own_rows():
    """A native result holds the query's own row object for a term, whichever equal object the atom came with: the first
    equal object the query's input shows, a function of the query alone. Python's own choice follows its process-wide
    memo, so in the two cases of `_not_first` it holds another object; the planner ruled the native choice the rule."""
    if _counts() is None:
        pytest.skip('Python backend: no native results')
    (got, d), rows = _held()
    assert got == WANT and rows
    assert _not_first(rows) == []


def test_plant_662_fires_and_is_caught():
    """Plant 662 (`ad-lra-atom-object`): the result is built from the atom's own object, a later equal one."""
    if _counts() is None:
        pytest.skip('Python backend: no plant')
    import sa_solver
    sa_solver.formula_plant('ad-lra-atom-object')
    try:
        (got, d), rows = _held()
    finally:
        sa_solver.formula_plant(None)
    assert d['rel:plant_fired'] > 0, 'plant 662 no longer fires'
    assert got == WANT                  # the answers don't read which object is held
    bad = _not_first(rows)
    assert any(len(r) == 5 for r in bad) and any(len(r) == 3 for r in bad), bad[:4]     # both halves of the check see it


_SERIAL = [0]


def _twins():
    """Two equal, distinct objects that no memo of the process holds yet: a symbol made twice (SymPy's cache cleared
    between) and an `f(a)` of two `Function` classes, under names used once."""
    _SERIAL[0] += 1
    name = f'q1same{_SERIAL[0]}'
    x1 = Symbol(name)
    clear_cache()
    x2 = Symbol(name)
    g1 = Function(name)(Symbol('a'))
    clear_cache()
    g2 = Function(name)(Symbol('a'))
    assert x1 is not x2 and x1 == x2 and g1 is not g2 and g1 == g2 and type(g1) is not type(g2)
    return (x1, x2), (g1, g2)


def _kept():
    import term_live
    return term_live.COUNTS.get('kept:args-eq-not-is', 0) if term_live.installed() else None


def _same_base(count=('same:eq', 'rel:plant_fired')):
    """`b**b` with the base and the exponent equal, distinct objects. Only the Pow rule of the 'same' shape (wiring.py
    `matches`; `x**x` is positive for `x >= 0`) gives the answers, and it read the two by identity before ruling Q1 (b)."""
    from sympy import Pow
    c0 = _counts()
    got = []
    for b, e in _twins():
        p = Pow(b, e, evaluate=False)
        assert p.args[0] is b and p.args[1] is e
        got.append(_ask(Q.extended_positive(p), Q.extended_nonnegative(b)))
    c1 = _counts()
    return got, None if c0 is None else {k: c1.get(k, 0) - c0.get(k, 0) for k in count}


def test_same_shape_is_equality_not_identity():
    """Both backends, and on both it is wiring.py that answers: conversion keeps a query holding a term with two equal,
    distinct arguments (convert.py R12, `args-eq-not-is`), so Python reads it under Rust too. On the reference before the
    ruling (`a is not args[j]`, `b is e`) both answers were None in a fresh process, and True once an identical `b**b`
    of the same name had been asked: the mutant that puts `is` back fails here (results/cbm-noid-cause.md)."""
    k0 = _kept()
    got, d = _same_base()
    assert got == [True, True]
    if d is not None:
        assert _kept() - k0 == 2, 'such a query is no longer kept: plant 663 below must now fire and be caught'
        assert d == {'same:eq': 0, 'rel:plant_fired': 0}, d


def test_plant_663_is_void_while_such_queries_are_kept():
    """Plant 663 (`same-is`): rows_tpl.rs `same_term` by identity again. Rust's site holds the same `==` as wiring.py, but
    R12 lets no input term with equal, distinct arguments reach it, so the plant cannot fire on a query: void by that rule,
    and a footnote in the report. If R12 goes, this test fails and the plant gets its catch."""
    if _counts() is None:
        pytest.skip('Python backend: no plant')
    import sa_solver
    sa_solver.formula_plant('same-is')
    try:
        got, d = _same_base()
    finally:
        sa_solver.formula_plant(None)
    assert got == [True, True] and d == {'same:eq': 0, 'rel:plant_fired': 0}, (got, d)


def test_cache_store_key_is_the_first_equal_object():
    """Ruling Q1 (c): a term that becomes a key of `Engine.cache.store` (a user can read the store). Two equal, distinct
    constants in one query: the store gets one key, `==` to both, with the same facts on both backends; under Rust the
    key is the first the query's input shows (rule (a)). The writer reached here is `Engine.is_(u, 'extended_real')` for a
    constant side; **relations.py:1116's `is_(u, 'real')` is not reached by this or by 14 other crafted queries**
    (results/cbm-noid-cause.md), only by test_relations_core.py's direct case `guard-real-at-root`."""
    from sympy import log, sin
    from satassume import Engine
    from satassume.engine import DictCache
    from satassume.sympy_api import ask
    x, y = Symbol('x'), Symbol('y')
    _SERIAL[0] += 1
    k = 7919 + _SERIAL[0]
    for mk in (lambda: sin(S(k)), lambda: log(S(k))):
        n1 = mk()
        clear_cache()
        n2 = mk()
        assert n1 is not n2 and n1 == n2
        e = Engine(cache=DictCache())
        assert ask(Q.lt(x, y), Q.lt(x, n1) & Q.gt(y, n2), engine=e) is True
        held = [(key, facts) for key, facts in e.cache.store.items() if key == n1]
        assert [facts for _, facts in held] == [{'extended_real': True}]
        if _counts() is not None:
            assert held[0][0] is n1


_CLS = '''import atexit, json, runpy, sys
sys.path.insert(0, sys.argv[1])
import sa_solver
atexit.register(lambda: print('NOID %d' % sa_solver.session_counts()['ad:cbm_noid']))
sys.argv = [sys.argv[1] + '/live.py', 'cls', 'rust', sys.argv[2], '--check', 'plain']
runpy.run_path(sys.argv[0], run_name='__main__')
'''


def test_cbm_noid_is_zero_on_cls_and_the_class_plants_flip_it(tmp_path):
    """Item 4b: `ad:cbm_noid == 0` on workload cls, exact. Plants 660 (`ad-lra-class-is`) and 661 (`class-is`) send the
    reads back to Python (264 each on cls at b18b064, answers unchanged); 662 does not route anything to Python (it changes
    which object a native result holds: test_native_results_hold_the_querys_own_rows is its check)."""
    import os
    import subprocess
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    got = {}
    for plant in (None, 'ad-lra-class-is', 'class-is'):
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([here, os.environ.get('PYTHONPATH', '')]), SLICE_MOVED='0')
        env.pop('SLICE_SESSION_PLANT', None)
        if plant:
            env['SLICE_SESSION_PLANT'] = plant
        r = subprocess.run([sys.executable, '-c', _CLS, here, str(tmp_path / ('%s.jsonl' % plant))], env=env,
                           capture_output=True, text=True, timeout=900)
        assert r.returncode == 0, r.stderr[-3000:]
        got[plant] = int([x for x in r.stdout.splitlines() if x.startswith('NOID ')][-1].split()[1])
    assert got[None] == 0 and got['ad-lra-class-is'] > 0 and got['class-is'] > 0, got
