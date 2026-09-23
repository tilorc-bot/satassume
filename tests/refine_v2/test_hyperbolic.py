"""Rules H1-H2 of :mod:`satrefine.handlers_v2.hyperbolic`."""
from __future__ import annotations

import pytest
from sympy import I, Q, S, cosh, coth, csch, pi, sech, sinh, tanh
from sympy.abc import n, x, y


def test_H1_zero(check):
    check(sinh(x), Q.zero(x), S.Zero)
    check(cosh(x), Q.zero(x), S.One)
    check(tanh(x), Q.zero(x), S.Zero)
    check(coth(x), Q.zero(x), S.ComplexInfinity)
    check(sech(x), Q.zero(x), S.One)
    check(csch(x), Q.zero(x), S.ComplexInfinity)


def test_H2_full_periods(check):
    check(sinh(x + n * pi * I), Q.integer(n), (-1)**n * sinh(x))
    check(cosh(x + n * pi * I), Q.odd(n), -cosh(x))
    check(cosh(x + 2 * n * pi * I), Q.integer(n), cosh(x))
    check(tanh(x + n * pi * I), Q.integer(n), tanh(x))
    check(coth(x - n * pi * I), Q.integer(n), coth(x))
    check(sech(x + n * pi * I), Q.odd(n), -sech(x))
    check(csch(x - n * pi * I), Q.integer(n), (-1)**n * csch(x))
    check(sinh(x + y + n * pi * I), Q.even(n), sinh(x + y))


def test_H2_quarter_periods(check):
    check(sinh(x + n * pi * I / 2), Q.odd(n), I * (-1)**((n + 3) / 2) * cosh(x))
    check(cosh(x + n * pi * I / 2), Q.odd(n), I * (-1)**((n + 3) / 2) * sinh(x))
    check(tanh(x + n * pi * I / 2), Q.odd(n), coth(x))
    check(coth(x + n * pi * I / 2), Q.odd(n), tanh(x))
    check(sech(x + n * pi * I / 2), Q.odd(n), -I * (-1)**((n + 3) / 2) * csch(x))
    check(csch(x + n * pi * I / 2), Q.odd(n), -I * (-1)**((n + 3) / 2) * sech(x))
    check(sinh(x + n * pi * I / 2), Q.even(n), (-1)**(n / 2) * sinh(x))


@pytest.mark.parametrize("expr, assumptions", [
    (sinh(x + n * pi * I / 2), Q.integer(n)),
    (sinh(x + n * pi), Q.integer(n)),
    (cosh(x + n * pi * I), Q.real(n)),
    (tanh(x + n * I), Q.integer(n)),
    (sinh(x), Q.real(x)),
])
def test_does_not_fire_without_the_precondition(unchanged, expr, assumptions):
    unchanged(expr, assumptions)
