"""Rules M1-M3 of :mod:`satrefine.handlers_v2.mul`."""
from __future__ import annotations

from sympy import Abs, I, Q, conjugate, exp, sign
from sympy.abc import x, y


def test_M1_conjugate_pairs_need_no_assumption(check):
    check(x * conjugate(x), True, Abs(x)**2)
    check(x**2 * conjugate(x)**2 * y, True, y * Abs(x)**4)
    check(x**2 * conjugate(x), True, x * Abs(x)**2)
    check(x * conjugate(x), Q.real(x), x**2)


def test_M2_sign_times_abs_needs_no_assumption(check):
    check(sign(x) * Abs(x), True, x)
    check(2 * sign(x) * Abs(x) * y, True, 2 * x * y)


def test_M3_x_times_sign_needs_real(check, unchanged):
    check(x * sign(x), Q.real(x), Abs(x))
    check(2 * x * sign(x), Q.real(x), 2 * Abs(x))
    unchanged(x * sign(x), True)
    unchanged(x * sign(x), Q.complex(x))
    assert I * sign(I) != Abs(I)


def test_general_products_are_left_alone(unchanged):
    unchanged(x * y, Q.positive(x) & Q.positive(y))
    unchanged(x * exp(x), Q.real(x))
    unchanged(x**2 * conjugate(y), Q.real(x))
    unchanged(x * conjugate(x)**y, True)
