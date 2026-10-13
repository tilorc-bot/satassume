"""``re``, ``im``, ``arg``, ``sign``, ``Abs`` and ``conjugate``, and products of a factor and its conjugate."""
from __future__ import annotations

from sympy import Abs, I, Interval, Q, S, arg, conjugate, exp, floor, im, log, pi, re, sign, symbols, true, zoo
from sympy.core import Mul

from ._tables import Row, add_rules, derive, exponent, part
from .power_exp_log import EXP_FORMS as _EXP_FORMS

z, b, e, y, r, w, a = symbols('z b e y r w a')
d, f, g, n, u, v = symbols('d f g n u v')
imaginary_factors = part('vs', Q.imaginary)
real_factors = part('s', Q.real)
h, m = exponent('h'), exponent('m')

DEFINITIONS: list[Row] = add_rules({~Q.zero(f) & Q.finite(f), ~Q.zero(d)}, [
    (Abs(f), f/sign(f)),
    (arg(d), -I*log(sign(d))),
])

ABS_OF_EXP: list[Row] = add_rules(set(), [
    (Abs(exp(z), evaluate=False), exp(re(z))),
])

ARG_FACTS: list[Row] = add_rules(set(), [
    (arg(exp(z)),       im(z) + 2*pi*floor(S.Half - im(z)/(2*pi))),
    (arg(conjugate(w)), -arg(w) + 2*pi*floor(S.Half + arg(w)/(2*pi))),
])

FACTS: list[Row] = DEFINITIONS + ABS_OF_EXP + ARG_FACTS

SPLITS: list[Row] = add_rules(set(), [
    (sign(y*r), sign(y)*sign(r)),
])

RULES: list[Row] = (
    add_rules({Q.nonnegative(a) | Q.extended_nonnegative(a)}, [
        (Abs(a), a),
    ])
    + add_rules({Q.nonpositive(a) | Q.extended_nonpositive(a)}, [
        (Abs(a), -a),
    ])
    + add_rules({Q.real(u) | Q.extended_real(u), Q.imaginary(v)}, [
        (re(u), u),
        (im(u), S.Zero),
        (re(v), S.Zero),
        (im(v), -I*v),
        (re(real_factors*w), real_factors*re(w)),
        (im(real_factors*w), real_factors*im(w)),
        (re(imaginary_factors*w), -I*imaginary_factors*re(I*w)),
        (im(imaginary_factors*w), -I*imaginary_factors*im(I*w)),
    ])
    + add_rules({Q.positive(a) | Q.extended_positive(a)}, [
        (sign(a), S.One),
    ])
    + add_rules({Q.negative(a) | Q.extended_negative(a)}, [
        (sign(a), S.NegativeOne),
    ])
    + add_rules({Q.imaginary(v), Q.positive(im(v)) | Q.positive(-I*v)}, [
        (sign(v), I),
    ])
    + add_rules({Q.imaginary(v), Q.negative(im(v)) | Q.negative(-I*v)}, [
        (sign(v), -I),
    ])
    + add_rules({~Q.zero(d)}, [
        (sign(Abs(d)), S.One),
    ])
    + add_rules({Q.real(z)}, [
        (sign(exp(z)), S.One),
    ])
    + add_rules({Q.real(u) | Q.extended_real(u), Q.imaginary(v), Q.integer(n)}, [
        (conjugate(u), u),
        (conjugate(v), -v),
        (conjugate(exp(z), evaluate=False), exp(conjugate(z))),
        (conjugate(b**n), conjugate(b)**n),
    ])
    + add_rules({Q.positive(b)}, [
        (conjugate(b**e), b**conjugate(e)),
    ])
    + add_rules({Q.commutative(g), Q.integer(n)}, [
        (g*conjugate(g), Abs(g)**2),
        (g**n*conjugate(g)**n, Abs(g)**(2*n)),
    ])
    + add_rules({Q.commutative(g), Q.integer(h), Q.integer(m), Q.positive(m), Q.positive(h - m)}, [
        (g**h*conjugate(g)**m, Abs(g)**(2*m)*g**(h - m)),
    ])
    + add_rules({Q.commutative(g), Q.integer(h), Q.integer(m), Q.positive(h), Q.positive(m - h)}, [
        (g**h*conjugate(g)**m, Abs(g)**(2*h)*conjugate(g)**(m - h)),
    ])
    + add_rules({~Q.zero(f) & Q.finite(f)}, [
        (f*zoo, zoo),
        ((-1)**a*(-1)**e, (-1)**(a + e)),
    ])
)

RANGES: list = [
    (arg(y), Interval.open(-pi, pi),  ~Q.extended_negative(y) | Q.nonnegative(re(y)) | ~Q.zero(im(y))),
    (arg(y), Interval.Lopen(-pi, pi), true),
]

IDENTITIES: list[Row] = (derive(ABS_OF_EXP, _EXP_FORMS)
                         + derive(ARG_FACTS, [row for row in _EXP_FORMS if isinstance(row[0], Mul)]))
