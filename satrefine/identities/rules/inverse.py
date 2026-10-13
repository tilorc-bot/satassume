"""The inverse trigonometric and hyperbolic functions of their forward functions, and ``atan2``."""
from __future__ import annotations

from sympy import (Abs, Interval, Piecewise, Q, S, acos, acosh, acot, acoth, acsch, asech, asin, asinh, atan, atan2,
                   atanh, cos, cosh, cot, coth, csch, im, nan, pi, sech, sign, sin, sinh, symbols, tan, tanh, true)

from ._tables import Row, add_rules
from ._wraps import off_cut_lines, reflect_full, reflect_half, reflect_half_imag, sawtooth, sawtooth_imag

d, t, u, x, y, z = symbols('d t u x y z')

FACTS: list[Row] = (
    add_rules({Q.real(t)}, [
        (asin(sin(t)), reflect_half(t)),
        (asin(cos(t)), reflect_half(pi/2 - t)),
        (acos(cos(t)), reflect_full(t)),
        (acos(sin(t)), reflect_full(pi/2 - t)),
    ])
    + add_rules({Q.real(t), ~Q.integer(t/pi + S.Half)}, [
        (atan(tan(t)), sawtooth(t, pi)),
    ])
    + add_rules({Q.real(t), ~Q.integer(t/pi)}, [
        (atan(cot(t)), sawtooth(pi/2 - t, pi)),
    ])
    + add_rules({off_cut_lines(z)}, [
        (asinh(sinh(z)), reflect_half_imag(z)),
        (atanh(tanh(z)), sawtooth_imag(z)),
    ])
    + add_rules({~Q.zero(d), off_cut_lines(d)}, [
        (acoth(coth(d)), sawtooth_imag(d)),
    ])
    + add_rules({~Q.zero(d), Q.real(d) | Q.finite(d) & ~Q.integer(im(d)/pi + S.Half)}, [
        (acsch(csch(d)), reflect_half_imag(d)),
    ])
    + add_rules(set(), [
        (atan2(y, x), Piecewise((atan(y/x), Q.positive(x) & Q.real(y)),
                                (atan(y/x) + pi, Q.negative(x) & Q.nonnegative(y)),
                                (atan(y/x) - pi, Q.negative(x) & Q.negative(y)),
                                (sign(y)*pi/2, Q.zero(x) & Q.nonzero(y)),
                                (nan, Q.zero(x) & Q.zero(y)),
                                (atan2(y, x), true))),
    ])
)

RULES: list[Row] = add_rules({Q.real(u) | Q.extended_real(u)}, [
    (acosh(cosh(u)), Abs(u)),
    (asech(sech(u)), Abs(u)),
])

RANGES: list = [
    (atan(y), Interval.open(-pi/2, pi/2),  Q.real(y)),
    (acot(y), Interval.Lopen(-pi/2, pi/2), Q.real(y)),
    (asin(y), Interval(-pi/2, pi/2),       Q.real(asin(y))),
    (acos(y), Interval(0, pi),             Q.real(acos(y))),
]
