"""One complete, three-valued consistency verdict per assumption set (#73).

Whether an assumption set raises must not depend on the query nor on what
ran before: every set gets one complete check (``Engine._complete_check``)
when its session is built, memoized per set.  Only an ``inconsistent``
verdict raises; ``unknown`` (a theory gave up, a truncated cone) never does.
"""
import itertools

import pytest
from sympy import Q, cos, sin, symbols

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


def test_one_set_check_for_many_queries():
    x, y, z = symbols('x y z')
    # one component (every query is answered under the whole set)
    a = Q.positive(x) & Q.negative(y) & Q.gt(z, 1) & Q.lt(y, x) & Q.lt(x, z)
    eng = Engine()
    for p in (Q.positive(x), Q.negative(y), Q.positive(z), Q.real(x*y),
              Q.negative(x*y), Q.gt(z, 0), Q.zero(x + z), Q.positive(x + z)):
        ask(p, a, eng)
    assert eng.stats["set_checks"] == 1


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
    eng.discovery_budget = 1
    assert not eng._verdict and eng.stats["version_clears"] == 1
    assert eng.verdict(g) is Engine(discovery_budget=1).verdict(g)
    assert eng.stats["set_checks"] == 2


def test_truncated_cone_is_unknown():
    # the discovery budget drops frontier nodes (Session.truncated): a
    # check over the cut cone finds no conflict, which proves nothing
    from sympy import Symbol, exp
    from satassume.sympy_api import _formula
    x = Symbol('x')
    f = _formula(Q.negative(exp(x) + x**2) & Q.real(x), True)
    assert Engine(cache=DictCache(), discovery_budget=2).verdict(f) is UNKNOWN
    assert Engine(cache=DictCache(), discovery_budget=3).verdict(f) is INCONSISTENT
    # a non-commutative argument is out of scope: an opaque atom, no raise
    A = Symbol('A', commutative=False)
    g = _formula(Q.algebraic(x + A), True, True)
    assert Engine(cache=DictCache(), discovery_budget=3).verdict(g) is CONSISTENT


def test_verdict_keeps_no_session():
    # Engine.verdict builds the set's session as a query would
    # (_build_context) but keeps only the verdict: the relevance layer asks
    # it for sets it then answers under a part, whose sessions a
    # never-queried whole session would evict.  A query under the whole
    # set builds its session then, with the same verdict; later verdicts
    # come from the memo
    from satassume.sympy_api import _formula
    x, y = symbols('x y')
    f = _formula(Q.positive(x) & Q.gt(y, 1), True)
    eng = Engine(cache=DictCache())
    assert eng.verdict(f) is CONSISTENT
    assert eng.stats["sessions"] == 1 and not eng._context_sessions
    s, _ = eng._context_session(f)
    assert eng.stats["sessions"] == 2 and s.verdict is CONSISTENT
    assert eng.verdict(f) is CONSISTENT and eng.stats["sessions"] == 2
    # a session's verdict answers when the memo has none
    eng._verdict.clear()
    assert eng.verdict(f) is CONSISTENT and eng.stats["sessions"] == 2


def test_setting_change_recomputes_a_memoized_verdict():
    # the verdict memoized under discovery_budget=3 (inconsistent) is not
    # kept when the budget becomes 2, which truncates the cone (unknown)
    from sympy import Symbol, exp
    from satassume.sympy_api import _formula
    x = Symbol('x')
    A = Symbol('A', commutative=False)
    # out of scope (non-commutative): opaque, consistent at any budget
    g = _formula(Q.algebraic(x + A), True, True)
    assert Engine(cache=DictCache(), discovery_budget=3).verdict(g) is CONSISTENT
    f = _formula(Q.negative(exp(x) + x**2) & Q.real(x), True, True)
    eng = Engine(cache=DictCache(), discovery_budget=3)
    assert eng.verdict(f) is INCONSISTENT
    eng.discovery_budget = 2
    assert eng.verdict(f) is UNKNOWN
    eng.discovery_budget = 3
    assert eng.verdict(f) is INCONSISTENT
    assert eng.stats["version_clears"] == 2


def test_cone_search_keeps_the_verdict():
    # the cone session that replaces a polluted one carries the set's verdict
    from satassume.sympy_api import _formula
    x, y, z, w = symbols('x y z w')
    # (relevance off: the queries are asked under the whole set)
    eng = Engine(cache=DictCache(), cone_threshold=0, relevance=False)
    a = Q.positive(x) & Q.gt(y, 1)
    g = _formula(a, True, True)
    assert eng.verdict(g) is CONSISTENT
    ask(Q.positive(z*w + 1), a, eng)  # pollutes the session
    ask(Q.negative(x*y), a, eng)
    assert eng.stats["cone_searches"] >= 1
    assert eng._context_sessions[g][0].verdict is CONSISTENT
    assert eng.verdict(g) is CONSISTENT
