"""Rules T1-T3 and N1-N2 of :mod:`satrefine.handlers_v2.trig`."""
from __future__ import annotations

import pytest
from sympy import AccumBounds, Q, S, cos, cot, csc, oo, pi, sec, sin, sinc, tan
from sympy.abc import m, n, x, y


def test_T1_zero(check):
    check(sin(x), Q.zero(x), S.Zero)
    check(cos(x), Q.zero(x), S.One)
    check(tan(x), Q.zero(x), S.Zero)
    check(sec(x), Q.zero(x), S.One)
    check(cot(x), Q.zero(x), S.ComplexInfinity)
    check(csc(x), Q.zero(x), S.ComplexInfinity)


def test_T2_sin_cos_full_and_half_periods(check):
    check(sin(x + n * pi), Q.integer(n), (-1)**n * sin(x))
    check(cos(x + n * pi), Q.integer(n), (-1)**n * cos(x))
    check(sin(x + n * pi), Q.even(n), sin(x))
    check(cos(x + n * pi), Q.odd(n), -cos(x))
    check(sin(x - n * pi), Q.odd(n), -sin(x))
    check(sin(x + y + 2 * n * pi), Q.integer(n), sin(x + y))
    check(sin(n * pi), Q.integer(n), S.Zero)
    check(cos(n * pi / 2), Q.odd(n), S.Zero)
    check(sin(n * pi / 2), Q.odd(n) & Q.odd((n - 1) / 2), S.NegativeOne)


def test_T2_sin_cos_quarter_periods(check):
    check(sin(x + n * pi / 2), Q.even(n), (-1)**(n / 2) * sin(x))
    check(cos(x + n * pi / 2), Q.even(n), (-1)**(n / 2) * cos(x))
    check(sin(x + n * pi / 2), Q.odd(n), (-1)**((n + 3) / 2) * cos(x))
    check(cos(x + n * pi / 2), Q.odd(n), (-1)**((n + 1) / 2) * sin(x))
    check(sin(x - n * pi / 2), Q.odd(n), (-1)**((n + 3) / 2) * -cos(x))
    check(cos(x + n * pi + m * pi / 2), Q.integer(n) & Q.odd(m), (-1)**(n + (m + 1) / 2) * sin(x))
    check(cos(x + n * pi + m * pi / 2), Q.integer(n) & Q.integer(m), (-1)**n * cos(x + m * pi / 2))


def test_T2_sec_csc(check):
    check(sec(x + n * pi), Q.integer(n), (-1)**n * sec(x))
    check(csc(x + n * pi), Q.odd(n), -csc(x))
    check(sec(x + n * pi / 2), Q.odd(n), (-1)**((n + 1) / 2) * csc(x))
    check(csc(x + n * pi / 2), Q.odd(n), (-1)**((n + 3) / 2) * sec(x))
    check(csc(x + n * pi / 2), Q.even(n), (-1)**(n / 2) * csc(x))


def test_T2_tan_cot(check):
    check(tan(x + n * pi), Q.integer(n), tan(x))
    check(cot(x + n * pi), Q.integer(n), cot(x))
    check(tan(x + n * pi / 2), Q.odd(n), -cot(x))
    check(cot(x + n * pi / 2), Q.odd(n), -tan(x))
    check(tan(x + n * pi / 2), Q.even(n), tan(x))
    check(tan(x - 3 * n * pi), Q.integer(n), tan(x))


def test_T3_bounded_at_infinity():
    from satrefine import refine
    infinite = Q.infinite(x) & Q.extended_real(x)
    assert refine(sin(x), infinite) == AccumBounds(-1, 1) == sin(oo) == sin(-oo)
    assert refine(cos(x), infinite) == AccumBounds(-1, 1) == cos(oo) == cos(-oo)


def test_N1_N2_sinc(check):
    check(sinc(x), Q.zero(x), S.One)
    check(sinc(x), Q.nonzero(x), sin(x) / x)
    check(sinc(x), Q.imaginary(x), sin(x) / x)
    check(sinc(n * pi), Q.integer(n) & Q.nonzero(n), S.Zero)


@pytest.mark.parametrize("expr, assumptions", [
    (sin(x + n * pi / 2), Q.integer(n)),
    (cos(x + y + n * pi / 2), Q.integer(n)),
    (sin(x + n * pi), Q.rational(n)),
    (tan(x + n * pi / 2), Q.integer(n)),
    (sec(x + n * pi), Q.real(n)),
    (sin(x), Q.infinite(x)),
    (sin(x), Q.real(x)),
    (sinc(x), Q.real(x)),
    (sinc(n * pi), Q.integer(n)),
])
def test_does_not_fire_without_the_precondition(unchanged, expr, assumptions):
    unchanged(expr, assumptions)
