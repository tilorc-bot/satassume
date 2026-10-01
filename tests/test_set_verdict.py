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
    # the set is not inconsistent and its queries answer
    x, a = _k5()
    eng = Engine()
    assert ask(Q.gt(x, 0), a, eng) is None
    assert ask(Q.gt(x, 0), a, eng) is None


@pytest.mark.xfail(strict=True, reason="needs R2")
def test_k5_set_answers_under_its_part():
    x, a = _k5()
    assert ask(Q.gt(x, 0), a, Engine()) is True


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
    a = Q.positive(x) & Q.negative(y) & Q.gt(z, 1)
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
    from sympy import Symbol
    from satassume.sympy_api import _formula
    x = Symbol('x')
    A = Symbol('A', commutative=False)
    f = _formula(Q.algebraic(x + A), True)
    assert Engine(cache=DictCache(), discovery_budget=2).verdict(f) is UNKNOWN
    assert Engine(cache=DictCache(), discovery_budget=3).verdict(f) is INCONSISTENT


def test_check_runs_in_the_query_session():
    # no session of its own for the check: the set's contextual session
    # is the only one built, and Engine.verdict builds that very session
    from satassume.sympy_api import _formula
    x, y = symbols('x y')
    f = _formula(Q.positive(x) & Q.gt(y, 1), True)
    eng = Engine(cache=DictCache())
    assert eng.verdict(f) is CONSISTENT
    assert eng.stats["sessions"] == 1
    s, _ = eng._context_session(f)
    assert eng.stats["sessions"] == 1 and s.verdict is CONSISTENT


def test_setting_change_recomputes_a_memoized_verdict():
    # the verdict memoized under discovery_budget=3 (inconsistent) is not
    # kept when the budget becomes 2, which truncates the cone (unknown)
    from sympy import Symbol
    from satassume.sympy_api import _formula
    x = Symbol('x')
    A = Symbol('A', commutative=False)
    f = _formula(Q.algebraic(x + A), True, True)
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
    eng = Engine(cache=DictCache(), cone_threshold=0)
    a = Q.positive(x) & Q.gt(y, 1)
    assert eng.verdict(_formula(a, True)) is CONSISTENT
    ask(Q.positive(z*w + 1), a, eng)  # pollutes the session
    ask(Q.negative(x*y), a, eng)
    assert eng.stats["cone_searches"] >= 1
    assert eng.verdict(_formula(a, True)) is CONSISTENT
