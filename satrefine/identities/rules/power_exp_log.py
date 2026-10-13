"""``Pow``, ``exp`` and ``log``."""
from __future__ import annotations

from sympy import Abs, E, I, Mod, Q, S, arg, exp, log, pi, symbols, true, zoo
from sympy.core import Pow

from ._tables import Row, add_rules, by_cases, derive, principal, rational_part

z, b, e, y, r, x, a = symbols('z b e y r x a')
d, k, m, n, p, q, t, v = symbols('d k m n p q t v')
h = rational_part('h')

ASSUMED = {Q.even(n), Q.odd(k), Q.real(t)}

FACTS: list[Row] = add_rules({~Q.zero(d)}, [
    (log(exp(z)), principal(z)),
    (log(d),      log(Abs(d)) + I*arg(d)),
    (d**e,        exp(e*log(d))),
    (exp(a + b),  exp(a)*exp(b)),
])

EXP_FORMS: list[Row] = [
    (b**e, e*log(b),           by_cases(~Q.zero(b), Q.positive(e))),
    (y*r,  log(y) + log(r),    true),
    (y*r,  log(-y) + log(-r),  true),
]

RULES: list[Row] = (
    add_rules({Q.integer(m)}, [
        (Pow(E, x, evaluate=False), exp(x)),
        ((b**a)**m, b**(a*m)),
    ])
    + add_rules({Q.positive(p), Q.nonnegative(b) | Q.extended_nonnegative(b)}, [
        ((b**p)**e, b**(p*e)),
    ])
    + add_rules({Q.positive(p)}, [
        ((p**t)**e, p**(t*e)),
    ])
    + add_rules({Q.positive(n) | ~Q.zero(t) | Q.real(e)}, [
        ((t**n)**e, Abs(t)**(n*e)),
    ])
    + add_rules({Q.extended_real(b), Q.positive(n)}, [
        ((b**n)**e, Abs(b)**(n*e)),
    ])
    + add_rules({Q.integer(m)}, [
        (exp(a)**m, exp(a*m)),
    ])
    + add_rules({Q.imaginary(v), Q.even(a/2)}, [
        ((v**a)**e, Abs(v)**(a*e)),
    ])
    + add_rules({Q.imaginary(v), Q.odd(a/2)}, [
        ((v**a)**e, (-1)**e*Abs(v)**(a*e)),
    ])
    + add_rules({Q.positive(p)}, [
        (Pow(S.Zero, p, evaluate=False), S.Zero),
    ])
    + add_rules({Q.negative(q), Q.zero(b)}, [
        (b**q, zoo),
    ])
    + add_rules({Q.imaginary(v)}, [
        (Abs(t)**n, t**n),
        (Abs(v)**n, (-1)**(n/2)*v**n),
        ((-1)**n, S.One),
        ((-1)**k, S.NegativeOne),
    ])
    + add_rules({Q.even(x - 1)}, [
        ((-1)**x, S.NegativeOne),
    ])
    + add_rules({Q.odd(x - 1)}, [
        ((-1)**x, S.One),
    ])
    + add_rules({Q.integer(m)}, [
        ((-1)**((-1)**m/2 + r), (-1)**(m + r + S.Half)),
        ((-1)**(n + r), (-1)**r),
        ((-1)**(k + r), (-1)**(r + 1)),
        ((-1)**(h + r), (-1)**(r + Mod(h, 2))),
        (exp(m*pi*I + r), (-1)**m*exp(r)),
    ])
    + add_rules({Q.integer(x - S.Half)}, [
        (exp(x*pi*I + r), I*(-1)**(x - S.Half)*exp(r)),
    ])
    + add_rules({by_cases(~Q.zero(b), Q.positive(e))}, [
        (exp(e*log(b)), b**e),
    ])
)

LOG_RULES: list[Row] = add_rules({by_cases(~Q.zero(n), ~Q.zero(t))}, [
    (log(t**n), n*log(Abs(t))),
])

NEGATIVE_BASE: list[Row] = add_rules({Q.negative(q)}, [
    (q**n, (-q)**n),
    (q**k, -(-q)**k),
])

LOG_FORMS: list[Row] = [(EXP_FORMS[0][0], EXP_FORMS[0][1], EXP_FORMS[0][2] & by_cases(Q.finite(b), Q.real(b), Q.positive(e)))
                        ] + EXP_FORMS[1:]

IDENTITIES: list[Row] = derive([row for row in FACTS if isinstance(row[0], log)], LOG_FORMS)
