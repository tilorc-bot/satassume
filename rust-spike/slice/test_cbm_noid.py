"""`ad:cbm_noid` cause read (issue 323, results/cbm-noid-cause.md). Two `Function('f')` are one class to SymPy (`==`, same hash)
and two class objects. Process-wide memos keyed by `==` hand back whichever object came first, so a query can hold `f(1)` of
one class object while the engine's atoms hold `f(1)` of the other. A row then counts for both; before the fix the term had
no id and Python read it, counted as `ad:cbm_noid`, by test order. Run on the suite's plugin:
`run_suite.sh WORK rust rust-spike/slice/test_cbm_noid.py` (on `python` the answers are checked and the counts skipped).
Plant 660 (`ad-lra-class-is`, adapters.rs `Reader.id`) puts the identity compare back; it must fire and be seen here."""
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


def _run():
    a, b = Symbol('a'), Symbol('b')
    f1 = Function('f')
    t1 = f1(S(1))
    clear_cache()                   # else SymPy's own cache hands `f1`'s object back for `f2(1)`
    f2 = Function('f')
    t2 = f2(S(1))
    assert t1 == t2 and hash(t1) == hash(t2) and type(t1) is not type(t2) and type(t1) == type(t2)
    c0 = _counts()
    got = dict(first=_ask(Q.eq(S(1), t1), Q.ne(b, a)))      # the memos now hold `f1`'s `f(1)` ...
    got['second'] = _ask(Q.eq(S(1), t2), Q.ne(b, a))        # ... and this query's rows hold `f2`'s
    clear_cache()
    x1 = f1(a)
    clear_cache()
    x2, y2 = f2(a), f2(b)
    assert type(x1) is not type(x2)
    # both class objects inside one query; the first two answers need them to be one function
    got['mixed'] = [_ask(Q.eq(x1, x2)), _ask(Q.eq(x1, y2), Q.eq(a, b)), _ask(Q.lt(x1, x2)), _ask(Q.gt(x1 + 1, x2)),
                    _ask(Q.le(x1, 3), Q.lt(x2, 2) & Q.real(x2)), _ask(Q.eq(t1, 2), Q.eq(t2, 3))]
    c1 = _counts()
    d = None if c0 is None else {k: c1.get(k, 0) - c0.get(k, 0) for k in ('ad:cbm_noid', 'ad:lra_native', 'rel:plant_fired')}
    return got, d


def test_equal_classes_take_the_row():
    got, d = _run()
    assert got == WANT
    if d is None:
        pytest.skip('Python backend: answers checked, no session counts')
    assert d['ad:lra_native'] > 0, 'the adapter was never asked: the zero below would prove nothing'
    assert d['ad:cbm_noid'] == 0 and d['rel:plant_fired'] == 0, d


def test_plant_660_fires_and_is_seen():
    if _counts() is None:
        pytest.skip('Python backend: no plant')
    import sa_solver
    sa_solver.rel_plant('ad-lra-class-is')
    try:
        got, d = _run()
    finally:
        sa_solver.rel_plant(None)
    assert d['rel:plant_fired'] > 0, 'plant 660 no longer fires'
    assert d['ad:cbm_noid'] > 0, d       # what test_equal_classes_take_the_row asserts is 0
    assert got == WANT                   # Python reads the term then, so the answers stay Python's
