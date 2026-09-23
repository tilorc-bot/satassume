"""Rules I1-I4 of :mod:`satrefine.handlers_v2.inverse_trig`."""
from __future__ import annotations

from sympy import Q, Rational, S, acos, asin, atan, atan2, cos, cot, nan, pi, sin, tan
from sympy.abc import x, y

IN_RANGE = {x: (S.Zero, S.One, S.NegativeOne, Rational(3, 2), Rational(-3, 2), pi / 2, -pi / 2, pi / 4)}
IN_0_PI = {x: (S.Zero, S.One, S(2), S(3), pi / 2, pi, pi / 6)}


def test_I1_zero(check):
    check(asin(x), Q.zero(x), S.Zero)
    check(acos(x), Q.zero(x), pi / 2)
    check(atan(x), Q.zero(x), S.Zero)


def test_I2_inversion_on_the_principal_range(check):
    half = Q.ge(x, -pi / 2) & Q.le(x, pi / 2)
    check(asin(sin(x)), half, x, values=IN_RANGE)
    check(acos(sin(x)), half, pi / 2 - x, values=IN_RANGE)
    check(acos(cos(x)), Q.ge(x, 0) & Q.le(x, pi), x, values=IN_0_PI)
    check(asin(cos(x)), Q.ge(x, 0) & Q.le(x, pi), pi / 2 - x, values=IN_0_PI)
    check(atan(tan(x)), Q.gt(x, -pi / 2) & Q.lt(x, pi / 2), x,
          values={x: (S.Zero, S.One, S.NegativeOne, pi / 4, -pi / 3, Rational(3, 2))})
    check(atan(cot(x)), Q.gt(x, 0) & Q.lt(x, pi), pi / 2 - x,
          values={x: (S.One, S(2), S(3), pi / 2, pi / 6, 5 * pi / 6)})


def test_I2_needs_both_bounds(unchanged):
    unchanged(asin(sin(x)), Q.le(x, pi / 2))
    unchanged(asin(sin(x)), Q.real(x))
    unchanged(acos(cos(x)), Q.ge(x, 0))
    unchanged(atan(tan(x)), Q.ge(x, -pi / 2) & Q.le(x, pi / 2))
    assert asin(sin(S(2))) != 2


def test_I3_reciprocal(check, unchanged):
    check(atan(1 / x), Q.positive(x), pi / 2 - atan(x))
    check(atan(1 / x), Q.negative(x), -pi / 2 - atan(x))
    unchanged(atan(1 / x), Q.real(x))
    unchanged(atan(1 / x), Q.imaginary(x))


def test_I4_atan2(check):
    check(atan2(y, x), Q.real(y) & Q.positive(x), atan(y / x))
    check(atan2(y, x), Q.negative(y) & Q.negative(x), atan(y / x) - pi)
    check(atan2(y, x), Q.positive(y) & Q.negative(x), atan(y / x) + pi)
    check(atan2(y, x), Q.zero(y) & Q.negative(x), pi)
    check(atan2(y, x), Q.positive(y) & Q.zero(x), pi / 2)
    check(atan2(y, x), Q.negative(y) & Q.zero(x), -pi / 2)
    assert __import__("satrefine").refine(atan2(y, x), Q.zero(y) & Q.zero(x)) is nan


def test_atan2_does_not_fire_for_complex(unchanged):
    unchanged(atan2(y, x), Q.positive(x))
    unchanged(atan2(y, x), Q.real(y) & Q.real(x))
