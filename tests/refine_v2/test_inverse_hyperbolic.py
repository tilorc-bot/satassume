"""Rules J1-J4 of :mod:`satrefine.handlers_v2.inverse_hyperbolic`."""
from __future__ import annotations

import pytest
from sympy import Abs, I, Q, S, acosh, acoth, acsch, asech, asinh, atanh, cosh, coth, csch, oo, pi, sech, sinh, tanh, zoo
from sympy.abc import x


def test_J1_zero(check):
    check(asinh(x), Q.zero(x), S.Zero)
    check(acosh(x), Q.zero(x), I * pi / 2)
    check(atanh(x), Q.zero(x), S.Zero)
    check(acoth(x), Q.zero(x), I * pi / 2)
    check(asech(x), Q.zero(x), oo)
    check(acsch(x), Q.zero(x), zoo)


def test_J2_bijections_on_the_reals(check):
    check(asinh(sinh(x)), Q.real(x), x)
    check(atanh(tanh(x)), Q.real(x), x)


def test_J3_even_functions_give_abs(check):
    check(acosh(cosh(x)), Q.real(x), Abs(x))
    check(acosh(cosh(x)), Q.nonnegative(x), x)
    check(acosh(cosh(x)), Q.negative(x), -x)
    check(asech(sech(x)), Q.real(x), Abs(x))
    check(asech(sech(x)), Q.positive(x), x)


def test_J4_bijections_on_the_nonzero_reals(check):
    check(acoth(coth(x)), Q.real(x) & Q.nonzero(x), x)
    check(acsch(csch(x)), Q.real(x) & Q.nonzero(x), x)
    check(acoth(coth(x)), Q.negative(x), x)


@pytest.mark.parametrize("expr, assumptions", [
    (asinh(sinh(x)), Q.complex(x)),
    (asinh(sinh(x)), Q.imaginary(x)),
    (acosh(cosh(x)), Q.complex(x)),
    (atanh(tanh(x)), True),
    (acoth(coth(x)), Q.real(x)),
    (acsch(csch(x)), Q.real(x)),
    (asech(sech(x)), Q.imaginary(x)),
    (asinh(x), Q.real(x)),
])
def test_does_not_fire_without_the_precondition(unchanged, expr, assumptions):
    unchanged(expr, assumptions)


def test_complex_counterexample():
    assert asinh(sinh(4 * I)) != 4 * I
    assert abs(complex(asinh(sinh(4 * I)).evalf()) - complex(4 * I)) > 1
