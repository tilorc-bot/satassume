"""Rules X1-X2 of :mod:`satrefine.handlers_v2.minmax`."""
from __future__ import annotations

import pytest
from sympy import Abs, Max, Min, Q, S
from sympy.abc import x, y, z

from .conftest import REAL_SAMPLES

REALS = {x: REAL_SAMPLES, y: REAL_SAMPLES, z: REAL_SAMPLES}


def test_X1_sign_information_alone(check):
    check(Max(x, y), Q.nonnegative(x) & Q.nonpositive(y), x)
    check(Min(x, y), Q.nonnegative(x) & Q.nonpositive(y), y)
    check(Max(x, 0), Q.positive(x), x)
    check(Max(x, 0), Q.negative(x), S.Zero)
    check(Min(x, y, 0), Q.positive(x) & Q.positive(y), S.Zero)
    check(Max(x, y, z), Q.positive(x) & Q.negative(y) & Q.negative(z), x)
    check(Max(x, y), Q.positive(x - y), x)


def test_X1_relations(check):
    check(Max(x, y), Q.ge(x, y), x, values=REALS)
    check(Min(x, y), Q.ge(x, y), y, values=REALS)
    check(Max(x, y, z), Q.ge(x, y) & Q.ge(x, z), x, values=REALS)
    check(Max(x, y, z), Q.ge(x, y), Max(x, z), values=REALS)


def test_X2_absolute_value(check, unchanged):
    check(Max(x, -x), Q.real(x), Abs(x))
    check(Min(x, -x), Q.real(x), -Abs(x))
    unchanged(Max(x, -x), Q.complex(x))


@pytest.mark.parametrize("expr, assumptions", [
    (Max(x, y), Q.real(x) & Q.real(y)),
    (Max(x, y), Q.positive(x) & Q.positive(y)),
    (Min(x, y), Q.ge(x, z)),
    (Max(x, 0), Q.real(x)),
])
def test_does_not_fire_without_the_precondition(unchanged, expr, assumptions):
    unchanged(expr, assumptions)
