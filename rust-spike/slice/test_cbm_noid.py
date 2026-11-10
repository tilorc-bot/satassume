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


def test_native_results_hold_the_querys_own_rows():
    """What the fix does about objects: a native result holds the query's own row object for a term, whichever equal object
    the atom came with. That is a function of the query alone. **It is not always the object Python's result holds** (the
    two cases below), which is open with the planner (port-formula.md, "Q1")."""
    if _counts() is None:
        pytest.skip('Python backend: no native results')
    (got, d), rows = _held()
    assert got == WANT and rows
    assert all(own for *_, own in rows), [r for r in rows if not r[-1]][:3]
    # The two cases where Python's result holds the atom's own `f2` object (`_memoized`'s results on the Python backend,
    # ~/sa-rust-ids-work/sa-port-243/explore-python) and this holds the row's, `f1`'s, the first the query's input shows:
    for tag, arg in (('mixed3', 'Q.lt(f(a), f(a) + 1)'), ('mixed4', 'Q.lt(f(a), 2)')):
        assert {c for t, k, a, c, _ in rows if t == tag and a == arg and k == 0} == {'f1'}, (tag, arg)
