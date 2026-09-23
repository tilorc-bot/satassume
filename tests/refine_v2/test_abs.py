"""Rules A1-A6 of :mod:`satrefine.handlers_v2.abs`."""
from __future__ import annotations

import pytest
from sympy import Abs, Determinant, I, MatrixSymbol, Q, S, sign
from sympy.abc import n, x, y, z

from .conftest import NONZERO_SAMPLES


def test_A1_nonnegative(check):
    check(Abs(x), Q.nonnegative(x), x)
    check(Abs(x), Q.positive(x), x)
    check(Abs(x), Q.zero(x), S.Zero)
    check(1 + Abs(x), Q.positive(x), 1 + x)


def test_A2_negative(check):
    check(Abs(x), Q.negative(x), -x)
    check(Abs(x + 1), Q.negative(x + 1), -x - 1)


def test_A3_product_splits_only_the_decided_factors(check):
    check(Abs(x * y), Q.positive(x), x * Abs(y))
    check(Abs(x * y * z), Q.positive(x), x * Abs(y * z))
    check(Abs(x * y), Q.negative(x) & Q.positive(y), -x * y)
    check(Abs(2 * x * y), Q.negative(x), -2 * x * Abs(y))


def test_A4_powers(check):
    check(Abs(x**2), Q.real(x), x**2)
    check(Abs(x**n), Q.integer(n), Abs(x)**n, values={x: NONZERO_SAMPLES})
    check(Abs(x**y), Q.positive(x) & Q.real(y), x**y)
    check(Abs(x**y), Q.real(x) & Q.real(y), Abs(x)**y, values={x: NONZERO_SAMPLES})
    check(Abs(x**4), Q.real(x), x**4)


def test_A4_integer_exponent_needs_no_assumption(check, unchanged):
    check(Abs(x**2), Q.complex(x), Abs(x)**2)
    unchanged(Abs(x)**2, Q.complex(x))


def test_A5_sign(check):
    check(Abs(sign(x)), Q.nonzero(x), S.One)
    check(Abs(sign(x)), Q.imaginary(x), S.One)
    check(Abs(sign(x)), Q.positive(x), S.One)


def test_A6_determinant_of_unitary():
    from satrefine import refine
    X = MatrixSymbol("X", 2, 2)
    assert refine(Abs(Determinant(X)), Q.orthogonal(X)) == 1
    assert refine(Abs(Determinant(X)), Q.unitary(X)) == 1
    assert refine(Abs(Determinant(X)), Q.invertible(X)) == Abs(Determinant(X))


@pytest.mark.parametrize("expr, assumptions", [
    (Abs(x), Q.real(x)),
    (Abs(x), Q.complex(x)),
    (Abs(x**y), Q.real(x)),
    (Abs(sign(x)), True),
    (Abs(x * y), Q.real(x)),
])
def test_does_not_fire_without_the_precondition(unchanged, expr, assumptions):
    unchanged(expr, assumptions)


def test_complex_counterexample_shows_why_real_is_needed():
    assert Abs(I**2) != I**2
    assert abs(complex(Abs((1 + I)**2).evalf()) - abs(complex(((1 + I)**2).evalf()))) < 1e-12
    assert Abs((1 + I)**2) != (1 + I)**2
