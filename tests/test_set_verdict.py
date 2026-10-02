"""One complete, three-valued consistency verdict per assumption set (#73).

Whether an assumption set raises must not depend on the query nor on what
ran before: every set gets one complete check (``Engine._complete_check``)
when its session is built, memoized per set.  Only an ``inconsistent``
verdict raises; ``unknown`` (a theory gave up, a cone over the discovery budget) never does.
"""
import itertools

import pytest
from sympy import Q, cos, sin, symbols

from satassume import P
from satassume.engine import CONSISTENT, INCONSISTENT, UNKNOWN
from satassume.sympy_api import DictCache, Engine, ask


def _issue73():
    p, q, r = symbols('p q r', real=True)
    a = Q.lt(p, 0) & Q.ne(p + 2*r, 1) & Q.eq(-p - 2*r, -1)
    return a, [Q.lt(p, 0), Q.gt(r, 0), Q.gt(q, 0)]


def _k5():
    x, y = symbols('x y')
    c = cos(1)**2 + sin(1)**2 - 1
    return x, Q.gt(x, 1) & Q.eq(y, c)


@pytest.mark.parametrize("i", range(3))
def test_issue73_raises_in_a_fresh_engine(i):
    a, queries = _issue73()
    with pytest.raises(ValueError):
        ask(queries[i], a, Engine(cache=DictCache()))


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_issue73_raises_in_one_engine_in_every_order(order):
    a, queries = _issue73()
    eng = Engine(cache=DictCache())
    for i in order:
        with pytest.raises(ValueError):
            ask(queries[i], a, eng)


def test_unknown_verdict_does_not_raise():
    # LRA gives up on the undecidable constant (K5): no conflict found, so
    # the set is not inconsistent and its queries answer (asked under the
    # whole set: with relevance, x's component answers alone, see below)
    x, a = _k5()
    eng = Engine(relevance=False)
    assert ask(Q.gt(x, 0), a, eng) is None
    assert ask(Q.gt(x, 0), a, eng) is None


def test_k5_set_answers_under_its_part():
    # the whole set's verdict is unknown, which does not raise, and x's
    # component answers as it does alone (#53 R2)
    from satassume.sympy_api import _formula
    x, a = _k5()
    eng = Engine()
    assert ask(Q.gt(x, 0), a, eng) is True
    assert eng.verdict(_formula(a, True, True)) is UNKNOWN
    assert ask(Q.gt(x, 0), Q.gt(x, 1), Engine()) is True


def test_verdicts():
    from satassume.sympy_api import _formula
    x, y = symbols('x y')
    eng = Engine()
    assert eng.verdict(_formula(Q.gt(x, 1), True)) is CONSISTENT
    assert eng.verdict(_formula(Q.gt(x, 1) & Q.lt(x, 0), True)) is INCONSISTENT
    assert eng.verdict(_formula(_issue73()[0], True)) is INCONSISTENT
    assert eng.verdict(_formula(_k5()[1], True)) is UNKNOWN


def test_one_set_check_per_query():
    # was test_one_set_check_for_many_queries: the set's session, and its
    # complete check, are built for every contextual query (#97 P1); the
    # verdict is memoized once per set
    x, y, z = symbols('x y z')
    # one component (every query is answered under the whole set)
    a = Q.positive(x) & Q.negative(y) & Q.gt(z, 1) & Q.lt(y, x) & Q.lt(x, z)
    eng = Engine(cache=DictCache())
    props = (Q.positive(x), Q.negative(y), Q.positive(z), Q.real(x*y),
             Q.negative(x*y), Q.gt(z, 0), Q.zero(x + z), Q.positive(x + z))
    for p in props:
        ask(p, a, eng)
    assert eng.stats["set_checks"] == len(props)
    assert not eng._context_sessions and len(eng._verdict) == 1


def test_setting_change_drops_the_verdict_memo():
    """A verdict depends on the engine's settings (``discovery_budget``,
    ``templates``, ``transfer``, ``uninterpreted``, ...): a setting change
    drops the memoized verdicts with the other caches (S, #79), and the
    next query checks the set again, as a fresh engine with the new
    setting does."""
    from satassume.sympy_api import _formula
    x, y = symbols('x y')
    g = _formula(Q.positive(x) & Q.gt(x*y, 1), True, True)
    eng = Engine()
    v = eng.verdict(g)
    assert eng._verdict.get(g) is v and eng.stats["set_checks"] == 1
    eng.discovery_budget = 200
    assert not eng._verdict and eng.stats["version_clears"] == 1
    assert eng.verdict(g) is Engine(discovery_budget=200).verdict(g)
    assert eng.stats["set_checks"] == 2
    # a budget below the set's cone: unknown, without a check (#53 task 6)
    eng.discovery_budget = 1
    assert eng.verdict(g) is UNKNOWN is Engine(discovery_budget=1).verdict(g)
    assert eng.stats["set_checks"] == 2


def test_set_over_the_budget_is_unknown():
    # a set whose structural cone outweighs the discovery budget is not
    # checked (#53 task 6): unknown, never raising, and every query under
    # it is over the budget too (None); at its weight the check runs
    from sympy import Symbol, exp
    from satassume.sympy_api import _formula
    x = Symbol('x')
    a = Q.negative(exp(x) + x**2) & Q.real(x)
    f = _formula(a, True)
    # cone: exp(x) + x**2, exp(x), x**2, x
    eng = Engine(cache=DictCache(), discovery_budget=3)
    assert eng.verdict(f) is UNKNOWN and eng.stats["sessions"] == 0
    assert ask(Q.positive(x), a, eng) is None and eng.last_budget_limited
    assert eng.ask(P('positive', x), f) is None and eng.last_budget_limited
    assert eng.stats["sessions"] == 0
    assert Engine(cache=DictCache(), discovery_budget=4).verdict(f) is INCONSISTENT
    # a non-commutative argument is out of scope: an opaque atom, no raise
    A = Symbol('A', commutative=False)
    g = _formula(Q.algebraic(x + A), True, True)
    assert Engine(cache=DictCache(), discovery_budget=3).verdict(g) is CONSISTENT


def test_verdict_keeps_no_session():
    # Engine.verdict builds the set's session as a query would
    # (_build_context) but keeps only the verdict: the relevance layer asks
    # it for sets it then answers under a part.  A query under the whole
    # set builds its own session, with the same verdict; later verdicts
    # come from the memo
    from satassume.sympy_api import _formula
    x, y = symbols('x y')
    f = _formula(Q.positive(x) & Q.gt(y, 1), True)
    eng = Engine(cache=DictCache())
    assert eng.verdict(f) is CONSISTENT
    # the set's session is the only one: an order atom alone does not
    # engage predicate transfer (an equality or a _trichotomy pair does,
    # Relations.wants_transfer), so no context-free Engine.is_ query for
    # the facts of a number side runs.  The point: no context session is
    # kept
    n = eng.stats["sessions"]
    assert n == 1 and not eng._context_sessions
    s, _ = eng._context_session(f)
    assert eng.stats["sessions"] == n + 1 and s.verdict is CONSISTENT
    assert not eng._context_sessions           # a query's session is not kept either
    assert eng.verdict(f) is CONSISTENT and eng.stats["sessions"] == n + 1
    # with no memo (and no kept session) the verdict is recomputed by one
    # more build, with the same result
    eng._verdict.clear()
    assert eng.verdict(f) is CONSISTENT and eng.stats["sessions"] == n + 2


def test_setting_change_recomputes_a_memoized_verdict():
    # the verdict memoized under discovery_budget=4 (inconsistent) is not
    # kept when the budget becomes 3, below the set's cone (unknown)
    from sympy import Symbol, exp
    from satassume.sympy_api import _formula
    x = Symbol('x')
    A = Symbol('A', commutative=False)
    # out of scope (non-commutative): opaque, consistent at any budget
    g = _formula(Q.algebraic(x + A), True, True)
    assert Engine(cache=DictCache(), discovery_budget=3).verdict(g) is CONSISTENT
    f = _formula(Q.negative(exp(x) + x**2) & Q.real(x), True, True)
    eng = Engine(cache=DictCache(), discovery_budget=4)
    assert eng.verdict(f) is INCONSISTENT
    eng.discovery_budget = 3
    assert eng.verdict(f) is UNKNOWN
    eng.discovery_budget = 4
    assert eng.verdict(f) is INCONSISTENT
    assert eng.stats["version_clears"] == 2


def test_search_keeps_the_verdict():
    # was test_cone_search_keeps_the_verdict: a query that searches under
    # the set (which once polluted a kept session and made the next search
    # run in a cone session) leaves the set's verdict as it is, and the
    # session built for the next query carries it
    from satassume.sympy_api import _formula
    x, y, z, w = symbols('x y z w')
    # (relevance off: the queries are asked under the whole set;
    # cone_threshold is accepted and changes nothing)
    eng = Engine(cache=DictCache(), cone_threshold=0, relevance=False)
    a = Q.positive(x) & Q.gt(y, 1)
    g = _formula(a, True, True)
    assert eng.verdict(g) is CONSISTENT
    ask(Q.positive(z*w + 1), a, eng)  # searches under the set
    assert eng.stats["searches"] >= 1 and "cone_searches" not in eng.stats
    ask(Q.negative(x*y), a, eng)
    assert not eng._context_sessions
    s, _ = eng._context_session(g)
    assert s.verdict is CONSISTENT
    assert eng.verdict(g) is CONSISTENT
