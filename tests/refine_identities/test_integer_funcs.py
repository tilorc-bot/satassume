"""The ``integer_funcs`` rule table: every row fires where v3's rule does,
agrees numerically with the input, and the v3 refusals stay refusals.

Relational assumptions get real ``values=`` (the harness cannot order
complex samples); ``Mod``/``Rem`` divisors exclude 0.
"""
from __future__ import annotations

import pytest
from sympy import Mod, Q, Rational, S, ceiling, floor, frac, oo, pi, sqrt, symbols
from sympy.functions.elementary.miscellaneous import Rem

from satrefine import refine
from satrefine._upstream import handlers_dict
from satrefine.harness import assert_refinement_valid

x, y, n, m, k, a, b = symbols('x y n m k a b')

RATIONALS = [S(v) for v in range(-4, 5)] + [Rational(v, 2) for v in (-5, -3, -1, 1, 3, 5)] + [
    Rational(1, 3), Rational(-7, 3)]
REALS = RATIONALS + [pi, -pi, sqrt(2)]
# SymPy evaluates Mod/Rem only for Number divisors (Rem(1, pi) stays), and the
# harness compares numbers, so divisors are rational.
DIVISORS = [v for v in RATIONALS if v != 0]
INTS = [S(v) for v in range(-5, 6)]
R = {x: REALS, a: RATIONALS, b: DIVISORS}   # Rem(pi, 4) stays unevaluated too

POSITIVE = [  # (expr, assumptions, expected, values)
    # F1, F2 (one row, generic head)
    (floor(x), Q.integer(x), x, None),
    (ceiling(x), Q.integer(x), x, None),
    (floor(x), Q.infinite(x) & Q.extended_real(x), x, {x: [oo, -oo]}),
    (ceiling(x), Q.infinite(x) & Q.extended_real(x), x, {x: [oo, -oo]}),
    # F3
    (floor(x + n), Q.integer(n), n + floor(x), None),
    (ceiling(x + n), Q.integer(n), n + ceiling(x), None),
    (floor(x + 2*n + m), Q.integer(n) & Q.integer(m), 2*n + m + floor(x), None),
    (floor(x + floor(y)), Q.finite(y), floor(x) + floor(y), None),
    (floor(x + ceiling(y)), Q.finite(y), floor(x) + ceiling(y), None),
    (ceiling(x + floor(y)), Q.finite(y), ceiling(x) + floor(y), None),
    (ceiling(x + ceiling(y)), Q.finite(y), ceiling(x) + ceiling(y), None),
    # F4
    (floor(x), Q.nonnegative(x) & Q.lt(x, 1), S.Zero, R),
    (floor(x), Q.nonnegative(x) & Q.positive(1 - x), S.Zero, R),
    (ceiling(x), Q.nonpositive(x) & Q.gt(x, -1), S.Zero, R),
    # R1, R2, R3
    (frac(x), Q.integer(x), S.Zero, None),
    (frac(x + n), Q.integer(n), frac(x), None),
    (frac(x + floor(y)), Q.finite(y), frac(x), None),
    (frac(x + ceiling(y)), Q.finite(y), frac(x), None),
    (frac(x), Q.nonnegative(x) & Q.lt(x, 1), x, R),
    # M1 (with M2 even and Mod(x, 1))
    (Mod(n, 2), Q.even(n), S.Zero, None),
    (Mod(n, -2), Q.even(n), S.Zero, None),
    (Mod(x, 1), Q.integer(x), S.Zero, None),
    (Mod(k*n, n), Q.integer(k) & Q.nonzero(n), S.Zero, {n: DIVISORS}),
    (Mod(a, b), Q.integer(a/b) & Q.nonzero(b), S.Zero, {b: DIVISORS}),
    # M2 odd, generalized
    (Mod(n, 2), Q.odd(n), S.One, None),
    (Mod(n, -2), Q.odd(n), S.NegativeOne, None),
    (Mod(2*n + 1, 2), Q.integer(n), S.One, None),
    (Mod(2*n + 3, -2), Q.integer(n), S.NegativeOne, None),
    (Mod(3*n, 6), Q.odd(n), S(3), None),                      # beyond v3, exact
    # M3
    (Mod(x + 2*n, 2), Q.integer(n), Mod(x, 2), None),
    (Mod(x + k*b, b), Q.integer(k) & Q.nonzero(b), Mod(x, b), {x: REALS, b: DIVISORS, k: INTS}),
    # M4
    (Mod(a, b), Q.nonnegative(a) & Q.lt(a, b), a, R),
    (Mod(a, b), Q.nonpositive(a) & Q.gt(a, b), a, R),
    # M5
    (Mod(a, b), Q.positive(a) & Q.positive(b), Rem(a, b), R),
    (Mod(a, b), Q.negative(a) & Q.negative(b), Rem(a, b), R),
    # Q1
    (Rem(n, 2), Q.even(n), S.Zero, None),
    (Rem(x, 1), Q.integer(x), S.Zero, None),
    (Rem(a, b), Q.integer(a/b) & Q.nonzero(b), S.Zero, {b: DIVISORS}),
    # Q2 odd, by the sign of a/b
    (Rem(n, 2), Q.odd(n) & Q.positive(n), S.One, None),
    (Rem(n, 2), Q.odd(n) & Q.negative(n), S.NegativeOne, None),
    (Rem(n, -2), Q.odd(n) & Q.positive(n), S.One, None),
    (Rem(n, -2), Q.odd(n) & Q.negative(n), S.NegativeOne, None),
    # Q3
    (Rem(a, b), Q.nonnegative(a) & Q.lt(a, b), a, R),
    (Rem(a, b), Q.nonnegative(a) & Q.lt(a, -b), a, R),
    (Rem(a, b), Q.nonpositive(a) & Q.gt(a, -b), a, R),
    (Rem(a, b), Q.nonpositive(a) & Q.gt(a, b), a, R),
    (Rem(a, b), Q.positive(b) & Q.lt(a, b) & Q.gt(a, -b), a, R),
    (Rem(a, b), Q.negative(b) & Q.gt(a, b) & Q.lt(a, -b), a, R),
]

NEGATIVE = [  # v3's refusals
    (Rem(n, 2), Q.odd(n)),                          # Rem(-3, 2) = -1
    (Rem(n, 2), Q.integer(n)),
    (Mod(n, 2), Q.integer(n)),
    (Mod(n, 3), Q.odd(n)),
    (Mod(x, 2), Q.real(x)),
    (frac(x), Q.real(x)),
    (frac(x), Q.positive(x)),
    (floor(x), Q.real(x)),
    (floor(x), Q.positive(x)),
    (ceiling(x), Q.negative(x)),
    (floor(x + y), Q.real(x) & Q.real(y)),
    (Mod(a, b), Q.negative(a) & Q.positive(b)),     # signs differ: not Rem
    (Mod(a, b), Q.positive(a) & Q.negative(b)),
    (Mod(a, b), Q.nonnegative(a)),
    (Mod(a, b), Q.integer(a) & Q.integer(b)),
    (Mod(a, b), Q.lt(a, b)),                        # a may be negative
    (Rem(a, b), Q.positive(a) & Q.positive(b)),
    (Rem(a, b), Q.lt(a, b) & Q.positive(b)),        # a may be <= -b
    (Rem(x + 2*n, 2), Q.integer(n) & Q.real(x)),    # a shift can flip the sign
    (Rem(a, b), Q.integer(a/b)),                    # b may be zero
    (Mod(x + n*b, b), Q.integer(n)),                # b may be zero
    (frac(x + floor(y)), True),                     # y may be oo
    (frac(x + ceiling(y)), Q.extended_real(y)),
    (floor(x + floor(y)), True),
    (floor(x), Q.positive(x) & Q.negative(y)),      # a relation ask raises here
]


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


def test_table_size_and_registration():
    from satrefine import _upstream
    from satrefine.handlers_identities import integer_funcs as mod
    assert len(mod.RULES) == 23
    assert handlers_dict['floor'] is not _upstream.refine_floor_ceiling
    assert all(callable(handlers_dict[key]) for key in ('floor', 'ceiling', 'frac', 'Mod', 'Rem'))
