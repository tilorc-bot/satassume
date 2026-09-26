"""The ``combinatorial`` rule table: every row fires where v3's rule does,
agrees numerically with the input (poles included: both sides ``zoo``), and
the v3 refusals stay refusals.

``values=`` puts integers, half-integers and complex points in reach of the
harness where the defaults would not satisfy the assumptions.
"""
from __future__ import annotations

import pytest
from sympy import I, Q, Rational, S, binomial, factorial, ff, gamma, rf, oo, symbols, zoo

from satrefine import refine
from satrefine.testing.harness import assert_refinement_valid

n, k, x = symbols('n k x')
HALF = Rational(1, 2)
INTS = [S(v) for v in range(-5, 7)]
MIXED = INTS + [HALF, Rational(-3, 2), Rational(7, 3), I, 1 + 2*I]

POSITIVE = [  # (expr, assumptions, expected, values)
    # shared by binomial, rf, ff: k == 0 -> 1, k == 1 -> first argument
    (binomial(n, k), Q.zero(k), S.One, {n: MIXED}),
    (binomial(n, k), Q.eq(k, 0), S.One, {n: MIXED, k: INTS}),
    (binomial(n, k), Q.eq(k, 1), n, {n: MIXED, k: INTS}),
    (rf(x, k), Q.zero(k), S.One, {x: MIXED}),
    (rf(x, k), Q.eq(k, 1), x, {x: MIXED, k: INTS}),
    (ff(x, k), Q.zero(k), S.One, {x: MIXED}),
    (ff(x, k), Q.eq(k, 1), x, {x: MIXED, k: INTS}),
    # factorial
    (factorial(n), Q.zero(n), S.One, None),
    (factorial(n), Q.eq(n, 0), S.One, {n: INTS}),
    (factorial(n), Q.eq(n, 1), S.One, {n: INTS}),
    (factorial(n - 1), Q.zero(n - 1), S.One, {n: INTS}),
    (factorial(n), Q.integer(n) & Q.negative(n), zoo, None),
    (factorial(n), Q.positive_infinite(n), oo, {n: [oo]}),
    # gamma
    (gamma(n), Q.integer(n) & Q.positive(n), factorial(n - 1), None),
    (gamma(n + 1), Q.integer(n) & Q.nonnegative(n), factorial(n), None),
    (gamma(n), Q.integer(n) & Q.nonpositive(n), zoo, None),
    (gamma(n + 3), Q.integer(n) & Q.nonpositive(n + 3), zoo, {n: INTS}),
    (gamma(n + 3), Q.integer(n) & Q.le(n + 3, 0), zoo, {n: INTS}),
    # binomial
    (binomial(n, n), Q.nonnegative(n), S.One, {n: MIXED}),
    (binomial(n, k), Q.eq(n, k) & Q.nonnegative(n), S.One, {n: INTS, k: INTS}),
    (binomial(n, n), ~Q.integer(n) & Q.complex(n), S.One, {n: MIXED}),
    (binomial(n, n), Q.imaginary(n), S.One, {n: MIXED}),
    (binomial(n + 1, n + 1), Q.integer(n) & Q.nonnegative(n), S.One, None),
    (binomial(n, n - 1), Q.nonnegative(n), n, {n: MIXED}),
    (binomial(n, n - 1), ~Q.integer(n) & Q.real(n), n, {n: MIXED}),
    (binomial(n, k), Q.integer(k) & Q.negative(k), S.Zero, {n: MIXED, k: INTS}),
    (binomial(n, n), Q.integer(n) & Q.negative(n), S.Zero, None),
    (binomial(n, k), Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.gt(k, n), S.Zero,
     {n: INTS, k: INTS}),
    (binomial(n, k), Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.positive(k - n), S.Zero,
     {n: INTS, k: INTS}),
    (binomial(n, k), Q.integer(n) & Q.negative(n) & ~Q.integer(k), zoo, {n: INTS, k: MIXED}),
    # RisingFactorial
    (rf(x, n), Q.eq(x, 1), factorial(n), {x: INTS, n: MIXED}),
    (rf(x, k), Q.integer(x) & Q.nonpositive(x) & Q.integer(k) & Q.positive(x + k), S.Zero,
     {x: INTS, k: INTS}),
    (rf(x, k), Q.integer(x) & Q.nonpositive(x) & Q.integer(k) & Q.gt(x + k, 0), S.Zero,
     {x: INTS, k: INTS}),
    (rf(x, k), Q.integer(x) & Q.negative(x) & ~Q.integer(k), S.Zero, {x: INTS, k: MIXED}),
    (rf(x, k), Q.positive(x), gamma(x + k)/gamma(x), {x: MIXED, k: MIXED}),
    (rf(x, k), ~Q.integer(x) & Q.complex(x), gamma(x + k)/gamma(x), {x: MIXED, k: MIXED}),
    (rf(x, k), Q.imaginary(x), gamma(x + k)/gamma(x), {x: MIXED, k: MIXED}),
    (rf(x, k), Q.integer(x) & Q.positive(x) & Q.integer(k) & Q.nonnegative(k),
     factorial(x + k - 1)/factorial(x - 1), {x: INTS, k: INTS}),
    # FallingFactorial
    (ff(x, k), Q.eq(x, k) & Q.integer(k), factorial(k), {x: INTS, k: INTS}),
    (ff(n, k), Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.gt(k, n), S.Zero,
     {n: INTS, k: INTS}),
    (ff(n, k), Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.le(k, n),
     factorial(n)/factorial(n - k), {n: INTS, k: INTS}),
    (ff(n, k), Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.nonnegative(n - k),
     factorial(n)/factorial(n - k), {n: INTS, k: INTS}),
    (ff(n, k), Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.negative(k),
     factorial(n)/factorial(n - k), {n: INTS, k: INTS}),
]

NEGATIVE = [  # v3's refusals
    (factorial(n), Q.positive(n)),                  # no gamma form
    (factorial(n), Q.integer(n)),
    (factorial(n), Q.negative(n) & ~Q.integer(n)),  # finite off the integers
    (gamma(n), Q.integer(n)),
    (gamma(n), Q.positive(n)),
    (gamma(n), Q.integer(n) & Q.negative(n - 1)),
    (gamma(n + HALF), Q.integer(n) & Q.nonnegative(n)),
    (binomial(n, n), Q.integer(n)),                 # binomial(-1, -1) = 0
    (binomial(n, n - 1), Q.integer(n)),             # binomial(-1, -2) = 0
    (binomial(n, k), Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.nonnegative(k)),
    (binomial(n, k), Q.integer(n) & Q.nonnegative(n) & Q.gt(k, n)),       # k not integer
    (binomial(n, k), Q.integer(n) & Q.negative(n) & Q.integer(k) & Q.positive(k)),
    (rf(x, k), Q.integer(x) & Q.negative(x) & Q.integer(k) & Q.positive(k)),  # rf(-3, 2) = 6
    (rf(x, k), Q.integer(x)),                       # rf(-2, 2) = 2, no gamma ratio
    (rf(x, k), Q.negative(x)),
    (ff(x, k), Q.eq(x, k)),                         # k not known integer
    (ff(n, k), Q.integer(n) & Q.negative(n) & Q.integer(k) & Q.positive(k)),  # ff(-2, 2) = 6
    (ff(n, k), Q.integer(n) & Q.nonnegative(n) & Q.integer(k)),               # order unknown
    (ff(n, k), Q.integer(n) & Q.nonnegative(n) & ~Q.integer(k) & Q.gt(k, n)),
    # checker: oo is not an integer, so ~Q.integer alone admits it (v3 fires on these)
    (binomial(n, n), ~Q.integer(n)),                # binomial(oo, oo) = nan
    (binomial(n, n), Q.positive_infinite(n)),
    (binomial(n, n - 1), ~Q.integer(n)),            # binomial(oo, oo - 1) = nan
    (rf(x, k), ~Q.integer(x)),                      # rf(oo, 2) = oo, gamma ratio is not
    (rf(x, k), Q.positive_infinite(x) & Q.integer(k) & Q.positive(k)),
]


def test_infinite_counterexamples():
    """The values behind the ``Q.finite`` provisos: at ``oo`` the old right sides disagree."""
    from sympy import nan, oo
    assert binomial(oo, oo) is nan and binomial(n, n).subs(n, oo) is nan
    assert rf(oo, 2) == oo
    assert (gamma(x + k)/gamma(x)).subs({x: oo, k: 2}) != oo


def _id(row):
    return f"{row[0]}|{row[1]}"


@pytest.mark.parametrize("expr, assumptions, expected, values", POSITIVE, ids=map(_id, POSITIVE))
def test_row_fires(expr, assumptions, expected, values):
    assert refine(expr, assumptions) == expected


@pytest.mark.parametrize("expr, assumptions, expected, values", POSITIVE, ids=map(_id, POSITIVE))
def test_row_is_sound(expr, assumptions, expected, values):
    assert_refinement_valid(expr, assumptions, refine(expr, assumptions), samples=40, values=values)


@pytest.mark.parametrize("expr, assumptions", NEGATIVE, ids=map(_id, NEGATIVE))
def test_refusal(expr, assumptions):
    assert refine(expr, assumptions) == expr


def test_table_size():
    from satrefine.identities.rules import combinatorial as mod
    assert len(mod.RULES) == 17
