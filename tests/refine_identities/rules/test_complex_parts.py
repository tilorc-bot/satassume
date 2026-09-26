"""``handlers_identities.complex_parts`` against the v3 cases (see ``_rows``)."""
from __future__ import annotations

import pytest
from sympy import (Abs, I, Mul, Q, S, arg, conjugate, cos, cosh, exp, im, log, pi, re, sign, sin, sqrt, symbols)

from _rows import check_relation, check_valid, ids

x, y, z, t, n = symbols("x y z t n")
u = symbols("u")   # sampled at +-oo only
AC = "same"
ARG = "same"

ROWS = [
    # Abs
    (Abs(x), Q.nonnegative(x), x, "same"), (Abs(x), Q.real(x) & ~Q.negative(x), x, "same"),
    (Abs(x), Q.negative(x), -x, "same"), (Abs(x), Q.real(x) & ~Q.positive(x), -x, "same"),
    (Abs(x), Q.zero(x), S.Zero, "same"), (Abs(x), Q.imaginary(x) & Q.positive(im(x)), -I*x, "same"),
    (Abs(x), Q.real(x), None, "neither"), (Abs(x), Q.positive(re(x)), None, "neither"),
    (Abs(x*y), Q.positive(y), y*Abs(x), "same"), (Abs(x*y), Q.negative(y), -y*Abs(x), "same"),
    (Abs(x*y*z), Q.positive(y) & Q.negative(z), -y*z*Abs(x), "same"),
    (Abs(x*y), Q.positive(re(y)), None, "neither"),
    (Abs(Mul(I, x, evaluate=False)), True, Abs(x), "same"),
    (Abs(x**2), Q.real(x), x**2, "same"), (Abs(x**n), Q.real(x) & Q.even(n) & ~Q.zero(x), x**n, "same"),
    (Abs(x**2), Q.complex(x), Abs(x)**2, "same"), (Abs(x**3), Q.real(x), Abs(x)**3, "same"),
    (Abs(x**n), Q.real(x) & Q.integer(n) & Q.positive(n), Abs(x)**n, "same"),
    (Abs(x**y), Q.real(y) & ~Q.zero(x), Abs(x)**y, "same"), (Abs(x**y), Q.positive(x) & Q.real(y), x**y, "same"),
    (Abs(x**y), Q.real(y), None, "neither"), (Abs(x**n), Q.real(x) & Q.even(n), None, "neither"),
    (Abs(exp(x)), Q.real(x), exp(x), "same"), (Abs(exp(I*t)), Q.real(t), S.One, "same"),
    (Abs(conjugate(x)), Q.negative(x), -x, "same"),
    (Abs(x + y), Q.real(x) & Q.real(y), None, "neither"), (Abs(x)**2, Q.complex(x), None, "neither"),
    # re / im
    (re(x), Q.real(x), x, "same"), (im(x), Q.real(x), S.Zero, "same"),
    (re(x), Q.imaginary(x), S.Zero, "same"), (im(x), Q.imaginary(x), -I*x, "same"),
    (re(x), Q.zero(x), S.Zero, "same"), (im(x), Q.negative(x), S.Zero, "same"),
    (re(x*y), Q.real(y), y*re(x), "same"), (im(x*y), Q.real(y), y*im(x), "same"),
    (re(x*y), Q.imaginary(y), I*y*im(x), "same"), (im(x*y), Q.imaginary(y), -I*y*re(x), "same"),
    (re(x*y), Q.real(x) & Q.real(y), x*y, "same"), (im(x*y), Q.real(x) & Q.real(y), S.Zero, "same"),
    (re(x*y*z), Q.real(y) & Q.imaginary(z), I*y*z*im(x), "same"),
    (re(x*y), Q.complex(x) & Q.complex(y), None, "neither"),
    (re(I*x), Q.real(x), S.Zero, "same"), (im(I*x), Q.real(x), x, "same"),
    (re(x + I*y), Q.real(x) & Q.real(y), x, "same"), (im(x + I*y), Q.real(x) & Q.real(y), y, "same"),
    (re(x + y), Q.real(y), y + re(x), "same"),
    (re(exp(x)), Q.real(x), exp(x), "same"), (im(exp(x)), Q.real(x), S.Zero, "same"),
    (re(exp(x)), Q.imaginary(x), cosh(x), "same"), (im(exp(I*t)), Q.real(t), sin(t), "same"),
    (re(exp(I*t)), Q.real(t), cos(t), "same"),
    (re(conjugate(x)), Q.imaginary(x), S.Zero, "same"), (im(conjugate(x)), Q.imaginary(x), I*x, "same"),
    (re(x**n), Q.real(x) & Q.integer(n) & Q.positive(n), x**n, "same"),
    (im(x**n), Q.real(x) & Q.integer(n) & Q.positive(n), S.Zero, "same"),
    (re(x**2), Q.real(x), x**2, "same"),
    (re(x**n), Q.real(x) & Q.integer(n), None, "neither"),
    (re(x**z), Q.imaginary(z) & Q.real(x), None, "neither"),
    # arg
    (arg(x), Q.positive(x), S.Zero, "same"), (arg(x), Q.negative(x), pi, "same"),
    (arg(x), Q.imaginary(x) & Q.positive(im(x)), pi/2, "same"),
    (arg(x), Q.imaginary(x) & Q.negative(im(x)), -pi/2, "same"),
    (arg(x), Q.real(x), None, "neither"), (arg(x), Q.zero(x), None, "extra: nan, as arg(0) is (the input is undefined there); v3 declines"), (arg(x), Q.nonnegative(x), None, "neither"),
    (arg(x*y), Q.positive(y), arg(x), "same"), (arg(x*y*z), Q.positive(y) & Q.positive(z), arg(x), "same"),
    (arg(x*y), Q.positive(x) & Q.positive(y), S.Zero, "same"),
    (arg(x*y), Q.real(y), None, "neither"), (arg(x*y), Q.negative(y), None, "extra: arg(-x), exact; v3 declines"),
    (arg(x*y), Q.nonnegative(y), None, "neither"),
    (arg(exp(I*t)), Q.real(t) & Q.positive(t + pi) & Q.nonpositive(t - pi), t, "same"),
    (arg(exp(x)), Q.real(x), S.Zero, "same"),
    (arg(exp(I*t)), Q.real(t), None, "neither"),
    (arg(exp(I*t)), Q.positive(t), None, "neither"),
    (arg(conjugate(x)), Q.positive(re(x)), -arg(x), ARG), (arg(conjugate(x)), ~Q.zero(im(x)), -arg(x), ARG),
    (arg(conjugate(x)), Q.positive(x), S.Zero, "same"), (arg(conjugate(x)), Q.negative(x), pi, "same"),
    (arg(conjugate(x)), True, None, "neither"), (arg(conjugate(x)), Q.negative(re(x)), None, "neither"),
    # sign
    (sign(x), Q.positive(x), S.One, "same"), (sign(x), Q.negative(x), S.NegativeOne, "same"),
    (sign(x), Q.zero(x), S.Zero, "same"), (sign(x), Q.imaginary(x) & Q.positive(im(x)), I, "same"),
    (sign(x), Q.imaginary(x) & Q.negative(im(x)), -I, "same"),
    (sign(x), Q.real(x), None, "neither"), (sign(x), Q.nonnegative(x), None, "neither"),
    (sign(Abs(x)), ~Q.zero(x), S.One, "same"), (sign(Abs(x)), Q.nonzero(x), S.One, "same"),
    (sign(Abs(x)), Q.imaginary(x), S.One, "same"), (sign(exp(x)), Q.real(x), S.One, "same"),
    (sign(Abs(x)), Q.complex(x), None, "neither"), (sign(exp(x)), Q.complex(x), None, "neither"),
    (sign(exp(x)), Q.imaginary(x), None, "neither"),
    (sign(x*y), Q.positive(y), sign(x), "same"), (sign(x*y), Q.negative(y), -sign(x), "same"),
    (sign(x*y), Q.zero(y), S.Zero, "same"), (sign(x*y), Q.imaginary(y) & Q.positive(im(y)), I*sign(x), "same"),
    (sign(x*Abs(y)), Q.positive(x) & ~Q.zero(y), S.One, "same"),
    (sign(x*y*z), Q.negative(y) & Q.positive(z), -sign(x), "same"),
    (sign(x*y), Q.real(y), None, "neither"), (sign(x*y), Q.complex(x) & Q.complex(y), None, "neither"),
    # conjugate
    (conjugate(x), Q.real(x), x, "same"), (conjugate(x), Q.imaginary(x), -x, "same"),
    (conjugate(x), Q.zero(x), S.Zero, "same"), (conjugate(Abs(x)), True, Abs(x), "same"),
    (conjugate(x), Q.complex(x), None, "neither"),
    (conjugate(x + y), Q.real(y), y + conjugate(x), "same"),
    (conjugate(x*y), Q.imaginary(y), -y*conjugate(x), "same"),
    (conjugate(x + I*y), Q.real(x) & Q.real(y), x - I*y, "same"),
    (conjugate(x*y), Q.real(x) & Q.real(y), x*y, "same"),
    (conjugate(x + y), Q.complex(x) & Q.complex(y), None, "neither"),
    (conjugate(x**n), Q.integer(n), conjugate(x)**n, "same"),
    (conjugate(x**n), Q.integer(n) & Q.real(x), x**n, "same"), (conjugate(x**3), Q.real(x), x**3, "same"),
    (conjugate(x**y), Q.positive(x), x**conjugate(y), "same"),
    (conjugate(x**y), Q.positive(x) & Q.real(y), x**y, "same"), (conjugate(sqrt(x)), Q.positive(x), sqrt(x), "same"),
    (conjugate(sqrt(x)), Q.complex(x), None, "neither"), (conjugate(x**y), Q.real(y), None, "neither"),
    (conjugate(x**y), Q.negative(x), None, "neither"),
    (conjugate(exp(x)), Q.real(x), exp(x), "same"),
    # Mul
    (x*conjugate(x), True, Abs(x)**2, "same"), (-x*conjugate(x), True, -Abs(x)**2, AC),
    (2*x*y*conjugate(x), True, 2*y*Abs(x)**2, AC), (x**2*conjugate(x)**2, True, Abs(x)**4, "same"),
    (x**n*conjugate(x)**n, Q.integer(n), Abs(x)**(2*n), "same"),
    (x**3*conjugate(x), True, x**2*Abs(x)**2, "miss: a computed exponent is not a row"),
    (Abs(x**n), Q.real(x) & Q.integer(n) & Q.positive(n), Abs(x)**n, "same"),
    (arg(conjugate(u)), Q.negative_infinite(u), pi, "extra: conjugate(-oo) = -oo, arg(-oo) = pi (rows over the extended reals)"),
    (x/conjugate(x), True, None, "neither"), (x*conjugate(y), True, None, "neither"),
    (x**n*conjugate(x)**n, True, None, "neither"), (sqrt(x)*sqrt(conjugate(x)), True, None, "neither"),
    (x*y, Q.real(x) & Q.real(y), None, "neither"),
    (x*conjugate(x), Q.real(x), x**2, "same"), (x*conjugate(x), Q.imaginary(x), -x**2, "same"),
]

COMPLEX = [S.One, S(-1), I, -I, 1 + I, -1 + I, -2 - 3*I, 2 - I, S(3), S.Half]
VALUES = {x: COMPLEX, y: COMPLEX, z: COMPLEX, t: [S.Zero, S.One, S(-1), S(3), pi, S.Half], n: [-2, -1, 0, 1, 2, 3],
          u: [S.Infinity, S.NegativeInfinity]}


@pytest.mark.parametrize("expr, assumptions, team, relation", ROWS, ids=ids(ROWS))
def test_output_is_valid(expr, assumptions, team, relation):
    if assumptions is not True and assumptions.has(Q.zero):
        pytest.skip("zero points are compared structurally")
    check_valid(expr, assumptions, relation=relation, values=VALUES)


@pytest.mark.parametrize("expr, assumptions, team, relation", ROWS, ids=ids(ROWS))
def test_relation_to_team(expr, assumptions, team, relation):
    check_relation(expr, assumptions, team, relation)
