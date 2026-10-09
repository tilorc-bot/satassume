"""Transfer through arguments that are value-equal numbers written
differently (a Float and a Rational, two spellings of an irrational):
EUF may merge them through a common side, so applications over them are
congruence candidates.  Regression for the landing review of the stage 2
tuning (``Relations._congruent`` excluded every pair of numbers)."""
from sympy import Function, Q, Rational, Symbol, sqrt

from satassume.engine import Engine
from satassume.sympy_api import ask

f = Function("f")
x = Symbol("x")


def _ask(prop, assumptions):
    return ask(prop, assumptions, engine=Engine())


def test_float_and_rational_argument():
    half = Rational(1, 2)
    a = Q.eq(half, f(half)) & Q.eq(0.5, f(half))
    assert _ask(Q.finite(f(0.5)), a) is True
    assert _ask(~Q.negative(f(0.5)), a) is True


def test_float_side_merges_with_integer():
    a = Q.eq(x, 1.0) & Q.eq(x, 1) & Q.positive(f(1.0))
    assert _ask(Q.positive(f(1)), a) is True


def test_two_spellings_of_an_irrational():
    a = Q.eq(x, (1 + sqrt(2))**2) & Q.eq(x, 3 + 2*sqrt(2)) & Q.positive(f(3 + 2*sqrt(2)))
    assert _ask(Q.positive(f((1 + sqrt(2))**2)), a) is True


def test_is_many_matches_is_and_leaves_the_same_cache():
    # Engine.is_many answers the predicates of a node from one session; it
    # must agree with a loop of Engine.is_ and store what the loop stores,
    # under every harness preset (the budget presets send some of these
    # over the budget), for numbers and for non-numbers
    from sympy import S, Rational, Float, pi, E, I, oo, zoo, nan, sqrt
    from harness.state import PRESETS
    from satassume.knowledge.rules import PREDICATES
    nums = (S.Zero, S.One, S(-3), Rational(1, 2), Rational(-5, 10**20 + 1),
            S(10)**30, Float("0.5"), pi, E - 2, I, 1 + I, oo, zoo, nan,
            sqrt(2) - 1, x, x + 1)
    for cfg in PRESETS.values():
        for c in nums:
            a, b = cfg.make(), cfg.make()
            want = [a.is_(c, p) for p in PREDICATES]
            assert b.is_many(c, PREDICATES) == want, (cfg.name, c)
            assert b.cache.facts(c) == a.cache.facts(c), (cfg.name, c)
            assert b.last_budget_limited == a.last_budget_limited, (cfg.name, c)
            if a.stats["budget_limited"] == 0 and None not in want:
                assert b.stats["sessions"] == 1
            # a second call reads the cache (an open predicate, never
            # cached, is asked again, as is_ asks it again)
            assert b.is_many(c, PREDICATES) == want


def test_reference_is_many_is_its_is_loop():
    from sympy import Rational
    from satassume.ref import _RefEngine
    from satassume.relations import default_specs
    from satassume.knowledge.rules import PREDICATES
    from satassume.knowledge.extensions import extensions
    import satassume.knowledge.templates  # noqa: F401 (registers the templates)
    e = _RefEngine(extensions, default_specs(), True, "free")
    c = Rational(3, 7)
    assert e.is_many(c, PREDICATES) == [e.is_(c, p) for p in PREDICATES]
