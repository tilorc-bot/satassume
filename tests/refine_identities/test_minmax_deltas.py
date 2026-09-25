"""The ``minmax_deltas`` rule table: every row fires where v3's rule does,
agrees numerically with the input (infinite endpoints included through
``values=``), and the v3 refusals stay refusals.

``DiracDelta`` is compared off the origin only: the scaling rule is an
identity of distributions, and ``DiracDelta(0)`` has no value to compare.
"""
from __future__ import annotations

import pytest
from sympy import (Abs, DiracDelta, Eq, Heaviside, KroneckerDelta, Max, Min, Q, Rational, S,
                   nan, oo, symbols)

from satrefine import refine
from satrefine.harness import assert_refinement_valid

x, y, z, k, i, j, z_, w_ = symbols('x y z k i j z_ w_')
REALS = [S(v) for v in range(-3, 4)] + [Rational(1, 2), Rational(-7, 2)]
EXT = REALS + [oo, -oo]
NONZERO = [v for v in REALS if v != 0]
ON = {x: EXT, y: EXT, z: EXT}

POSITIVE = [  # (expr, assumptions, expected, values)
    # Max/Min, sign row
    (Max(x, y), Q.negative(x) & Q.nonnegative(y), y, None),
    (Min(x, y), Q.negative(x) & Q.nonnegative(y), x, None),
    (Max(x, y), Q.nonpositive(x) & Q.positive(y), y, None),
    (Max(x, y), Q.positive(x) & Q.negative(y), x, None),       # a relation ask raises here
    (Min(x, y), Q.positive(x) & Q.negative(y), y, None),
    (Max(x, y), Q.positive_infinite(x) & Q.real(y), x, ON),
    (Min(x, y), Q.positive_infinite(x) & Q.real(y), y, ON),
    (Max(x, y), Q.negative_infinite(x) & Q.real(y), y, ON),
    (Min(x, y), Q.negative_infinite(x) & Q.real(y), x, ON),
    (Max(x, y), Q.negative_infinite(x) & Q.positive_infinite(y), y, ON),
    # an infinite argument decides without y known real: Max is defined only at extended
    # real arguments (Max(oo, I) raises), so the rows are exact wherever the input has a value
    (Max(x, y), Q.positive_infinite(x), x, ON), (Max(x, y), Q.negative_infinite(y), x, ON),
    (Min(x, y), Q.negative_infinite(x), x, ON), (Min(x, y), Q.positive_infinite(y), x, ON),
    (Max(x, y, z), Q.negative_infinite(x), Max(y, z), ON),
    (Min(x, y), Q.positive_infinite(x) & Q.nonpositive(y), y, ON),
    (Max(x, 0), Q.negative(x), S.Zero, ON),
    (Max(x, 0), Q.nonnegative(x), x, ON),
    (Min(x, 0), Q.positive(x), S.Zero, ON),
    (Max(x, y, z), Q.negative(x) & Q.positive(y), Max(y, z), ON),
    (Min(x, y, z), Q.positive_infinite(z) & Q.real(x), Min(x, y), ON),
    # Max/Min, relation row
    (Max(x, y), Q.le(x, y), y, ON),
    (Min(x, y), Q.le(x, y), x, ON),
    (Max(x, y), Q.lt(y, x), x, ON),
    (Min(x, y), Q.gt(x, y), y, ON),
    (Min(x, y), Q.eq(x, y), x, ON),
    (Max(x, y), Q.eq(x, y), x, ON),
    (Max(x, y, z), Q.lt(x, y) & Q.le(z, y), y, ON),
    # DiracDelta
    (DiracDelta(x), Q.nonzero(x), S.Zero, None),
    (DiracDelta(x), Q.negative(x), S.Zero, None),
    (DiracDelta(x, 2), Q.positive(x), S.Zero, None),
    (DiracDelta(x - y), Q.nonzero(x - y), S.Zero, {x: REALS, y: REALS}),
    (DiracDelta(k*x), Q.nonzero(k) & Q.real(x), DiracDelta(x)/Abs(k), {k: NONZERO, x: NONZERO}),
    (DiracDelta(k*x), Q.positive(k) & Q.real(x), DiracDelta(x)/k, {k: NONZERO, x: NONZERO}),
    (DiracDelta(k*x), Q.negative(k) & Q.real(x), -DiracDelta(x)/k, {k: NONZERO, x: NONZERO}),
    (DiracDelta(3*x), Q.real(x), DiracDelta(x)/3, {x: NONZERO}),
    # KroneckerDelta
    (KroneckerDelta(i, j), Q.nonzero(i - j), S.Zero, None),
    (KroneckerDelta(i, j), Q.positive(i) & Q.negative(j), S.Zero, None),
    (KroneckerDelta(i, j), Q.ne(i, j), S.Zero, {i: REALS, j: REALS}),
    (KroneckerDelta(i, j), Q.lt(i, j), S.Zero, {i: REALS, j: REALS}),
    (KroneckerDelta(i, j, (1, 3)), Q.ne(i, j), S.Zero, {i: REALS, j: REALS}),
    (KroneckerDelta(i, j), Q.zero(i - j), S.One, None),
    (KroneckerDelta(i, j), Q.eq(i, j), S.One, {i: REALS, j: REALS}),
    (KroneckerDelta(i, j), Q.eq(j, i), S.One, {i: REALS, j: REALS}),
    (KroneckerDelta(i, j), Eq(i, j), S.One, {i: REALS, j: REALS}),
    # Heaviside
    (Heaviside(x), Q.positive(x), S.One, None),
    (Heaviside(x), Q.positive_infinite(x), S.One, ON),
    (Heaviside(x), Q.negative(x), S.Zero, None),
    (Heaviside(x), Q.negative_infinite(x), S.Zero, ON),
    (Heaviside(x), Q.zero(x), S.Half, None),
    (Heaviside(x, 1), Q.zero(x), S.One, None),
    (Heaviside(x, 0), Q.zero(x), S.Zero, None),
    (Heaviside(x, nan), Q.zero(x), nan, None),
]

NEGATIVE = [  # v3's refusals
    (Max(x, y), Q.real(x) & Q.real(y)),
    (Min(x, y), Q.real(x) & Q.real(y)),
    (Max(x, y), Q.positive(x) & Q.positive(y)),
    (Max(x, y), Q.negative(x) & Q.negative(y)),
    (Max(x, y, z), True),
    (DiracDelta(x), Q.real(x)),
    (DiracDelta(x), Q.nonnegative(x)),
    (DiracDelta(k*x), Q.real(k) & Q.real(x)),
    (DiracDelta(k*x), Q.nonzero(k)),                # x may not be real
    (DiracDelta(k*x, 1), Q.positive(k) & Q.real(x)),  # derivatives pick up sign(k)**n
    (KroneckerDelta(i, j), True),
    (KroneckerDelta(i, j), Q.integer(i) & Q.integer(j)),
    (KroneckerDelta(i, j, (1, 3)), Q.eq(i, j)),     # equal indices may lie outside the range
    # SymPy's ask calls Q.eq(i, j) True for i = -oo and j <= 0: refused by `unless`
    (KroneckerDelta(i, j), Q.negative_infinite(i) & Q.extended_nonpositive(j) & Q.eq(z_, w_)),
    (KroneckerDelta(i, j), Q.negative_infinite(i) & Q.negative_infinite(j) & Q.eq(z_, w_)),
    (Heaviside(x), Q.real(x)),
    (Heaviside(x), Q.nonnegative(x)),
    (Heaviside(x), Q.nonzero(x)),
]


def _id(row):
    return f"{row[0]}|{row[1]}"


@pytest.mark.parametrize("expr, assumptions, expected, values", POSITIVE, ids=map(_id, POSITIVE))
def test_row_fires(expr, assumptions, expected, values):
    assert refine(expr, assumptions) == expected or (expected is nan and refine(expr, assumptions) is nan)


@pytest.mark.parametrize("expr, assumptions, expected, values", POSITIVE, ids=map(_id, POSITIVE))
def test_row_is_sound(expr, assumptions, expected, values):
    assert_refinement_valid(expr, assumptions, refine(expr, assumptions), samples=40, values=values)


@pytest.mark.parametrize("expr, assumptions", NEGATIVE, ids=map(_id, NEGATIVE))
def test_refusal(expr, assumptions):
    assert refine(expr, assumptions) == expr


def test_max_under_the_wrong_eq_answer_stays_correct():
    """Under the assumptions where ``ask`` wrongly proves ``Q.eq(y, x)``, the
    sign row fires first and keeps the right argument."""
    assumptions = Q.negative_infinite(x) & Q.extended_nonpositive(y)
    got = refine(Max(x, y), assumptions)
    assert got in (Max(x, y), y)
    for point in ({x: -oo, y: -1}, {x: -oo, y: 0}, {x: -oo, y: -oo}):
        assert Max(x, y).subs(point) == got.subs(point)


def test_table_size():
    """Five Piecewise definitions (Max, Min, KroneckerDelta with and without a
    range, Heaviside), three DiracDelta rule rows and four rows for an infinite
    argument of Max/Min."""
    from satrefine.handlers_identities import minmax_deltas as mod
    assert (len(mod.FACTS), len(mod.RULES)) == (5, 7)


BEYOND_V3 = [  # derived by the definitions, not by v3's rules
    (KroneckerDelta(i, j, (1, 3)), Q.eq(i, j) & Q.ge(i, 1) & Q.le(i, 3), S.One, {i: REALS, j: REALS}),
    (KroneckerDelta(i, j, (1, 3)), Q.eq(i, j) & Q.gt(i, 3), S.Zero, {i: [S(4), Rational(9, 2)], j: [S(4), Rational(9, 2)]}),
]


@pytest.mark.parametrize("expr, assumptions, expected, values", BEYOND_V3, ids=map(_id, BEYOND_V3))
def test_definition_beyond_v3(expr, assumptions, expected, values):
    got = refine(expr, assumptions)
    assert got == expected
    assert_refinement_valid(expr, assumptions, got, samples=40, values=values)


@pytest.mark.parametrize("expr, assumptions", [
    (Max(x, y), Q.imaginary(x) & Q.real(y)),       # incomparable: never the nan default branch
    (Heaviside(x), Q.imaginary(x)),
    (KroneckerDelta(i, j), Q.negative_infinite(i) & Q.negative_infinite(j)),
], ids=str)
def test_undefined_stays(expr, assumptions):
    assert refine(expr, assumptions) == expr
