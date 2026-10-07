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


def test_number_values_match_is_and_leave_the_same_cache():
    # relations._number_values answers every predicate of a number from one
    # session; it must agree with Engine.is_ and store what is_ stores
    from sympy import S, Rational
    from satassume.engine import Engine
    from satassume.relations import _number_values
    from satassume.rules import PREDICATES
    for c in (S.Zero, S.One, S(2), S(-3), Rational(1, 2), S(7)):
        a, b = Engine(), Engine()
        want = [a.is_(c, p) for p in PREDICATES]
        assert _number_values(b, c) == want
        assert b.cache.facts(c) == a.cache.facts(c)
        assert b.stats["sessions"] == 1
        # a second call reads the cache (an open predicate, never cached,
        # is asked again, as is_ asks it again)
        assert _number_values(b, c) == want
        assert b.stats["sessions"] == (1 if None not in want else 2)
