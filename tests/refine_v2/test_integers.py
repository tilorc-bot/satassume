"""Rules F1-F2 and Q1-Q3 of :mod:`satrefine.handlers_v2.integers`."""
from __future__ import annotations

import pytest
from sympy import Q, S, ceiling, floor, frac, oo
from sympy.abc import x, y, z


def test_F1_integer_or_infinite(check):
    check(floor(x), Q.integer(x), x)
    check(ceiling(x), Q.integer(x), x)
    check(floor(x), Q.infinite(x), x, values={x: (oo, -oo)})
    check(ceiling(x), Q.infinite(x), x, values={x: (oo, -oo)})


def test_F2_integer_terms_leave_floor(check):
    check(floor(x + y), Q.integer(x), x + floor(y))
    check(ceiling(x + y), Q.integer(x), x + ceiling(y))
    check(floor(x + y + z), Q.integer(x) & Q.integer(y), x + y + floor(z))
    check(ceiling(ceiling(x) + y + floor(z)), True, ceiling(x) + ceiling(y) + floor(z))


def test_Q1_Q3_frac(check):
    check(frac(x), Q.integer(x), S.Zero)
    check(frac(x + y), Q.integer(x), frac(y))
    check(frac(x + y + 3), Q.integer(x), frac(y))
    check(frac(x), Q.ge(x, 0) & Q.lt(x, 1), x, values={x: (S.Zero, S.Half, S(1) / 3, S(9) / 10)})


@pytest.mark.parametrize("expr, assumptions", [
    (floor(x), Q.real(x)),
    (ceiling(x), Q.rational(x)),
    (floor(x + y), Q.real(x)),
    (frac(x), Q.real(x)),
    (frac(x), Q.ge(x, 0)),
    (frac(x + y), Q.rational(x)),
])
def test_does_not_fire_without_the_precondition(unchanged, expr, assumptions):
    unchanged(expr, assumptions)
