"""``Pow``, ``exp`` and ``log`` as tables.

Rows: 2 log facts, 2 exponential forms (shared with the complex parts),
1 Pow fact, 18 rules, 2 negative-base rows, 1 shared zero row; ``handlers_v3/power_exp_log.py``
is 345 lines.

``log`` is two facts, ``log`` inverts ``exp`` up to the principal branch and
the complex logarithm is the real logarithm of the modulus plus ``I`` times
the argument, composed with the exponential forms of a power and a product
(:func:`._engine.derive`).  ``Pow`` has one fact, ``b**e == exp(e*log(b))``,
which fires only when the logarithm collapses and the exponential folds
back to a power (``log`` is opaque for that table), plus rules for the
cases whose hypotheses cannot be derived from the bookkeeping: an integer
outer exponent, an even inner exponent over a real or imaginary base, a
power of ``Abs``, ``(-1)**z`` by parity, and a negative base by parity;
and, until the exponential fold can see a ``log`` factor inside a longer
product (filed under ``needs``), the positive-base and nonnegative-base
``(b**a)**e`` cases and ``exp(a)**e`` for integer ``e``, which the fact
would otherwise derive.
``exp`` has two rules: ``exp`` splits off ``I*pi`` times an integer as
``(-1)**n``, and ``exp(e*log(b))`` folds back to ``b**e``.

Not covered (and why): ``log`` of a square of a real or imaginary base
(needs a two-branch case split), ``log`` of a product with a positive
factor and an unknown one and ``log(1/x)`` for imaginary ``x`` (need
``arg`` bounded inside ``floor``), the odd-exponent negative-base
logarithm in v3's exact form (``ask`` cannot show ``(n-1)/2`` integer for
odd ``n``; row D gives another correct form), ``(-1)**((-1)**n/2 + m/2)``
(a vendored special case), and ``(x**2)**b`` for imaginary ``x`` in the
``(-1)**b*Abs(x)**(2*b)`` form (only the ``x**4``-type cases with ``b``
real derive).
"""
from __future__ import annotations

from sympy import Abs, E, I, Q, S, arg, exp, floor, im, log, pi, symbols, true
from sympy.core import Pow

from .._upstream import handlers_dict
from ._engine import Row, derive, identity_handler, principal, rule_handler
from ._tables import ZERO, chain, negative_number_base_measure, node_measure

z, b, e, p, r, x, a, n = symbols('z b e p r x a n')

FACTS: list[Row] = [   # (lhs, rhs, domain): lhs == rhs wherever the domain holds
    (log(exp(z)), principal(z),            true),          # log inverts exp up to the principal branch
    (log(x),      log(Abs(x)) + I*arg(x),  ~Q.zero(x)),    # definition of the complex logarithm
    (b**e,        exp(e*log(b)),           ~Q.zero(b)),    # definition of the principal power
]
# The first two exponential forms are identities only off zero (at b = 0 the right side of the
# derived log row is nan in SymPy's arithmetic).  Their domains are relaxed so the engine's sign
# case split may try them; the split checks its result at the excluded point before accepting.

EXP_FORMS: list[Row] = [   # (L, W, domain): L == exp(W) wherever the domain holds
    (b**e, e*log(b),         ~Q.zero(b) | ~Q.zero(e)),    # a power is an exponential (see the note above)
    (p*r,  log(p) + log(r),  true),                        # a product is an exponential (see the note above)
]

RULES: list[Row] = [   # (lhs, rhs, hypothesis): a conditional rewrite
    # Pow
    (Pow(E, x, evaluate=False), exp(x), true),                                  # E**x is exp(x)
    ((b**a)**e, b**(a*e), Q.integer(e)),                                        # (b**a)**e = b**(a*e), integer e
    ((b**a)**e, b**(a*e), Q.positive(b) & Q.real(a)),                           # ... or a*log(b) real (no wrap)
    ((b**a)**e, b**(a*e), Q.nonnegative(b) & Q.positive(a)),                    # ... including b = 0 for a > 0
    (exp(a)**e, exp(a*e), Q.integer(e)),                                        # exp(a)**e = exp(a*e), integer e
    ((b**a)**e, Abs(b)**(a*e), Q.real(b) & Q.even(a) & ~Q.zero(b)),             # even inner exponent, real base
    ((b**a)**e, Abs(b)**(a*e), Q.real(b) & Q.even(a) & Q.positive(a)),          # ... or a positive one (0**a = 0)
    ((b**a)**e, Abs(b)**(a*e), Q.imaginary(b) & Q.even(a/2)),                   # (I*t)**a = t**a for a = 0 mod 4
    ((b**a)**e, (-1)**e*Abs(b)**(a*e), Q.imaginary(b) & Q.odd(a/2)),            # (I*t)**a = -t**a for a = 2 mod 4
    (Abs(b)**n, b**n, Q.real(b) & Q.even(n)),                                   # |b|**n = b**n, real b, even n
    (Abs(b)**n, (-1)**(n/2)*b**n, Q.imaginary(b) & Q.even(n)),                  # |I*t|**n = (-1)**(n/2)*(I*t)**n
    ((-1)**x, S.One, Q.even(x)),                                                # (-1)**even = 1
    ((-1)**x, S.NegativeOne, Q.odd(x)),                                         # (-1)**odd = -1
    ((-1)**(n + r), (-1)**r, Q.even(n)),                                        # (-1)**z is 2-periodic: drop even terms
    ((-1)**(n + r), (-1)**(r + 1), Q.odd(n)),                                   # ... an odd term becomes 1
    # exp
    (exp(n*pi*I + r), (-1)**n*exp(r), Q.integer(n)),                            # exp splits over sums; exp(I*pi*n) = (-1)**n
    (exp(n*pi*I + r), I*(-1)**(n - S.Half)*exp(r), Q.integer(n - S.Half)),       # exp(I*pi*(k + 1/2)) = I*(-1)**k
    (exp(e*log(b)), b**e, ~Q.zero(b)),                                          # the definition of Pow, folded back
]

NEGATIVE_BASE: list[Row] = [   # exact for integer n; ordered so they fire for a negative number only
    (b**n, (-b)**n,  Q.negative(b) & Q.even(n)),                                # c**n = (-c)**n, even n
    (b**n, -(-b)**n, Q.negative(b) & Q.odd(n)),                                 # c**n = -(-c)**n, odd n
]

IDENTITIES: list[Row] = derive([row for row in FACTS if isinstance(row[0], log)], EXP_FORMS)
POW_IDENTITIES: list[Row] = [row for row in FACTS if isinstance(row[0], Pow)]

_rules = rule_handler(RULES)
_zero = rule_handler([ZERO])

refine_log = chain(_zero, identity_handler(IDENTITIES))
refine_Pow = chain(_rules,
                   identity_handler(POW_IDENTITIES, measure=node_measure((Pow, exp)), opaque=(floor, im, arg, log)),
                   identity_handler(NEGATIVE_BASE, measure=negative_number_base_measure))
refine_exp = chain(_zero, _rules)

handlers_dict['log'] = refine_log
handlers_dict['Pow'] = refine_Pow
handlers_dict['exp'] = refine_exp
