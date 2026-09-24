"""``handlers_identities.inverse`` against the v3 cases (see ``_rows``).

The trigonometric inverse rows wait on ``floor`` of a symbol bounded by
relations (``needs/test_branchcut_floor_bounds.py``); those cases are
expected failures naming it.
"""
from __future__ import annotations

import pytest
from sympy import (Abs, I, Q, S, acos, acosh, acot, acoth, acsch, asech, asin, asinh, atan, atan2, atanh, cos,
                   cosh, cot, coth, csch, nan, pi, sech, sign, sin, sinh, symbols, tan, tanh)

from _rows import check_relation, check_valid, ids

x, y, t = symbols("x y t")
NEEDS = "miss: floor of a symbol bounded by relations (needs/test_branchcut_floor_bounds.py)"

ROWS = [
    (asin(sin(x)), Q.ge(x, -pi/2) & Q.le(x, pi/2), x, NEEDS),
    (asin(sin(x)), Q.ge(x, pi/2) & Q.le(x, 3*pi/2), pi - x, NEEDS),
    (asin(cos(x)), Q.ge(x, 0) & Q.le(x, pi), pi/2 - x, NEEDS),
    (acos(cos(x)), Q.ge(x, 0) & Q.le(x, pi), x, NEEDS),
    (acos(cos(x)), Q.ge(x, -pi) & Q.le(x, 0), -x, NEEDS),
    (atan(tan(x)), Q.gt(x, -pi/2) & Q.lt(x, pi/2), x, NEEDS),
    (atan(tan(x)), Q.gt(x, pi/2) & Q.lt(x, 3*pi/2), x - pi, NEEDS),
    (atan(cot(x)), Q.gt(x, 0) & Q.lt(x, pi), pi/2 - x, NEEDS),
    (asin(sin(x)), Q.real(x), None, "neither"), (asin(sin(x)), Q.positive(x), None, "neither"),
    (acos(cos(x)), Q.nonnegative(x), None, "neither"), (atan(tan(x)), Q.real(x), None, "neither"),
    (asin(x), Q.positive(x), None, "neither"),
    (atan2(y, x), Q.real(y) & Q.positive(x), atan(y/x), "same"),
    (atan2(y, x), Q.zero(y) & Q.positive(x), S.Zero, "same"),
    (atan2(y, x), Q.negative(y) & Q.negative(x), atan(y/x) - pi, "same"),
    (atan2(y, x), Q.positive(y) & Q.negative(x), atan(y/x) + pi, "same"),
    (atan2(y, x), Q.nonnegative(y) & Q.negative(x), atan(y/x) + pi, "same"),
    (atan2(y, x), Q.zero(y) & Q.negative(x), pi, "same"),
    (atan2(y, x), Q.positive(y) & Q.zero(x), pi/2, "same"),
    (atan2(y, x), Q.negative(y) & Q.zero(x), -pi/2, "same"),
    (atan2(y, x), Q.nonzero(y) & Q.zero(x), sign(y)*pi/2, "same"),
    (atan2(y, x), Q.zero(y) & Q.zero(x), nan, "same"),
    (atan2(y, x), Q.positive(x), None, "neither"), (atan2(y, x), Q.real(y) & Q.real(x), None, "neither"),
    (atan2(y, x), Q.real(y) & Q.zero(x), None, "neither"), (atan2(y, x), Q.positive(x) & Q.imaginary(y), None, "neither"),
    (atan2(y, x), Q.nonpositive(y) & Q.negative(x), None, "neither"),
    (atan2(y, -1), Q.nonnegative(y), pi - atan(y), "same"), (atan2(1, x), Q.zero(x), pi/2, "same"),
    (asinh(sinh(x)), Q.real(x), x, "same"), (asinh(sinh(x)), Q.positive(x), x, "same"),
    (asinh(sinh(x + 1)), Q.real(x), x + 1, "same"),
    (asinh(sinh(x)), True, None, "neither"), (asinh(sinh(x)), Q.imaginary(x), None, "neither"),
    (atanh(tanh(x)), Q.real(x), x, "same"), (atanh(tanh(x)), Q.negative(x), x, "same"),
    (atanh(tanh(x)), Q.complex(x), None, "neither"),
    (acosh(cosh(x)), Q.nonnegative(x), x, "same"), (acosh(cosh(x)), Q.nonpositive(x), -x, "same"),
    (acosh(cosh(x)), Q.real(x), Abs(x), "same"), (acosh(cosh(x)), Q.imaginary(x), None, "neither"),
    (asech(sech(x)), Q.negative(x), -x, "same"), (asech(sech(x)), Q.rational(x), Abs(x), "same"),
    (acoth(coth(x)), Q.nonzero(x), x, "same"), (acsch(csch(x)), Q.positive(x), x, "same"),
    (acoth(coth(x)), Q.real(x), None, "neither"), (acsch(csch(x)), Q.nonnegative(x), None, "neither"),
    (acosh(cosh(x)) + asinh(sinh(x)), Q.positive(x), 2*x, "same"),
    (acosh(cosh(acosh(cosh(x)))), Q.real(x), Abs(x), "same"),
]

VALUES = {x: [S(-3), S(-1), -S.Half, S.Zero, S.Half, S.One, S(2), pi, 2*I, -I, 1 + I],
          y: [S(-2), S(-1), S.Zero, S.One, S(3), I]}


@pytest.mark.parametrize("expr, assumptions, team, relation", ROWS, ids=ids(ROWS))
def test_output_is_valid(expr, assumptions, team, relation):
    if assumptions is not True and assumptions.has(Q.zero):
        pytest.skip("nan cases and zero points are compared structurally")
    check_valid(expr, assumptions, relation=relation, values=VALUES)


@pytest.mark.parametrize("expr, assumptions, team, relation", ROWS, ids=ids(ROWS))
def test_relation_to_team(expr, assumptions, team, relation):
    check_relation(expr, assumptions, team, relation)
