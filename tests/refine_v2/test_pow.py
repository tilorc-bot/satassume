"""Rules P1-P9 of :mod:`satrefine.handlers_v2.pow`."""
from __future__ import annotations

import pytest
from sympy import Abs, Determinant, I, MatrixSymbol, Q, Rational, S, sign, sqrt
from sympy.abc import n, x, y, z

from .conftest import NONZERO_SAMPLES


def test_P1_P2_zero_exponent_and_zero_base(check):
    check(x**y, Q.zero(y), S.One)
    check(x**y, Q.zero(x) & Q.positive(y), S.Zero)


def test_P3_even_power_of_abs(check, unchanged):
    check(Abs(x)**2, Q.real(x), x**2)
    check(Abs(x)**n, Q.real(x) & Q.even(n), x**n, values={x: NONZERO_SAMPLES})
    unchanged(Abs(x)**3, Q.real(x))
    unchanged(Abs(x)**2, True)
    unchanged(Abs(x)**2, Q.complex(x))


def test_P4_negative_number_base(check):
    check((-1)**x, Q.even(x), S.One)
    check((-1)**x, Q.odd(x), S.NegativeOne)
    check((-2)**x, Q.even(x), 2**x)
    check((-2)**x, Q.odd(x), -(2**x))


def test_P5_nested_powers(check, unchanged):
    check(sqrt(x**2), Q.real(x), Abs(x))
    check(sqrt(x**2), Q.positive(x), x)
    check((x**4)**Rational(1, 4), Q.real(x), Abs(x))
    check((x**3)**Rational(1, 3), Q.positive(x), x)
    check(sqrt(1 / x), Q.positive(x), 1 / sqrt(x))
    check((x**y)**z, Q.positive(x) & Q.real(y), x**(y * z))
    check((x**y)**Rational(1, 3), Q.nonnegative(x) & Q.positive(y), x**(y / 3))
    # the vendored rewrite fires on all of these; every one is false for some sample
    unchanged(sqrt(x**2), True)
    unchanged(sqrt(x**2), Q.complex(x))
    unchanged((x**3)**Rational(1, 3), Q.real(x))
    unchanged(sqrt(1 / x), Q.real(x))
    unchanged((x**y)**z, Q.positive(x))


def test_P5_vendored_rewrite_is_unsound():
    """``(x**2)**(1/2) -> Abs(x)`` with only ``x**2`` real fails at ``x = I``."""
    assert sqrt(I**2) == I
    assert Abs(I) == 1


def test_P6_positive_factor_leaves_the_power(check, unchanged):
    check(sqrt(x * y), Q.positive(x), sqrt(x) * sqrt(y))
    check((x * y)**z, Q.positive(y), x**z * y**z)
    unchanged(sqrt(x * y), Q.real(x))
    unchanged(sqrt(2 * x), True)


def test_P7_powers_of_sign(check, unchanged):
    check(sign(x)**2, Q.real(x) & Q.nonzero(x), S.One)
    check(sign(x)**n, Q.real(x) & Q.nonzero(x) & Q.odd(n), sign(x))
    unchanged(sign(x)**2, ~Q.zero(x) & Q.complex(x))
    assert sign(I)**2 == -1
    unchanged(sign(x)**2, Q.real(x))


def test_P8_even_power_of_orthogonal_determinant():
    from sympy import Matrix
    from satrefine import refine
    X = MatrixSymbol("X", 2, 2)
    assert refine(Determinant(X)**2, Q.orthogonal(X)) == 1
    assert refine(Determinant(X)**2, Q.unitary(X)) == Determinant(X)**2
    assert refine(Determinant(X)**3, Q.orthogonal(X)) == Determinant(X)**3
    reflection = Matrix([[0, 1], [1, 0]])
    assert reflection.det() == -1 and reflection.det()**2 == 1


def test_P9_powers_of_minus_one(check):
    check((-1)**(x + y), Q.even(x), (-1)**y)
    check((-1)**(x + y + z), Q.odd(x) & Q.odd(z), (-1)**y)
    check((-1)**(x + y + 1), Q.odd(x), (-1)**y)
    check((-1)**(x + y + 2), Q.odd(x), (-1)**(y + 1))
    check((-1)**(x + 3), True, (-1)**(x + 1))
    check((-1)**((-1)**x / 2 - S.Half), Q.integer(x), (-1)**x)
    check((-1)**((-1)**x / 2 + S.Half), Q.integer(x), (-1)**(x + 1))
    check((-1)**((-1)**x / 2 + 5 * S.Half), Q.integer(x), (-1)**(x + 1))
    check((-1)**((-1)**x / 2 - 7 * S.Half), Q.integer(x), (-1)**(x + 1))


@pytest.mark.parametrize("expr, assumptions", [
    ((-1)**x, Q.integer(x)),
    ((-1)**x, Q.real(x)),
    (x**y, Q.real(x) & Q.real(y)),
    (x**y, Q.zero(x)),
])
def test_does_not_fire_without_the_precondition(unchanged, expr, assumptions):
    unchanged(expr, assumptions)
