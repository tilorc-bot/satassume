"""``re``, ``im``, ``arg``, ``sign``, ``Abs``, ``conjugate`` and the conjugate
pair in ``Mul`` as tables.

Rows: 4 facts, 3 splits, 32 rules, 1 shared zero row; ``handlers_v3/complex_parts.py``
is 567 lines.  The exponential forms are the ones in
:mod:`.power_exp_log`; the simple rules of :mod:`._simple` (``re``/``im``
of exponentials, logarithms, sums and products; ``arg`` of an exponential
and on the imaginary axis) are chained after the rows and not repeated.

The facts: ``Abs``, ``sign`` and ``conjugate`` of an exponential, composed
with the exponential forms so that ``Abs(b**e)``, ``Abs(p*r)``,
``sign(b**e)``, ``conjugate(b**e)`` and the product forms derive; and
``arg`` of a conjugate, exact through its own bookkeeping.  Products under
``sign`` and ``conjugate`` and sums under ``conjugate`` split by an exact
identity whose ordering requires a factor or term to resolve, which is
v3's "fires only if at least one factor resolves".

Not covered (and why): the ``Mul`` conjugate-pair rules with a leftover
power (``x**3*conjugate(x) -> x**2*Abs(x)**2``; a computed exponent is not
a row) and the pair inside a longer product (needs a sub-product pattern
with a rest; filed under ``needs``); ``arg(conjugate(w))`` from a sign of
``re(w)`` alone (needs ``arg`` bounded by a relation on ``re``); ``Abs`` of
a product is split only when a factor resolves, as in v3, so the
unconditional split of the simple layer is not chained for ``Abs``.
"""
from __future__ import annotations

from sympy import Abs, I, Q, S, arg, conjugate, exp, floor, im, log, pi, re, sign, symbols, true
from sympy.core import Mul, Pow

from .. import _upstream
from .._upstream import handlers_dict
from . import _simple
from ._engine import Row, derive, identity_handler, part, rule_handler
from ._tables import ZERO, chain, node_measure
from .power_exp_log import EXP_FORMS

z, b, e, p, r, w, a, n = symbols('z b e p r w a n')
c = part('c', Q.imaginary)   # the imaginary factors of a product

FACTS: list[Row] = [   # (lhs, rhs, domain)
    (Abs(exp(z)),       exp(re(z)),                                    true),   # |exp z| = exp(re z)
    (sign(exp(z)),      exp(I*im(z)),                                  true),   # sign(exp z) = exp(i im z)
    (conjugate(exp(z)), exp(conjugate(z)),                             true),   # conjugate(exp z) = exp(conjugate z)
    (arg(conjugate(w)), -arg(w) + 2*pi*floor(S.Half + arg(w)/(2*pi)),  ~Q.zero(w)),  # arg is odd off the negative axis
]

SPLITS: list[Row] = [   # exact multiplicative or additive identities; the ordering demands progress
    (sign(p*r),      sign(p)*sign(r),           true),    # sign is multiplicative
    (conjugate(p*r), conjugate(p)*conjugate(r), true),    # conjugation is multiplicative
    (conjugate(a + b), conjugate(a) + conjugate(b), true),  # ... and additive
]

RULES: list[Row] = [   # (lhs, rhs, hypothesis)
    # Abs
    (Abs(a), a,      Q.nonnegative(a)),                                  # |a| = a for a >= 0
    (Abs(a), -a,     Q.nonpositive(a)),                                  # |a| = -a for a <= 0
    (Abs(a), -I*a,   Q.imaginary(a) & Q.positive(im(a))),                # |i*t| = t for t > 0
    (Abs(a), I*a,    Q.imaginary(a) & Q.negative(im(a))),                # |i*t| = -t for t < 0
    (Abs(conjugate(w)), Abs(w), true),                                   # |conjugate w| = |w|
    (Abs(b**e), Abs(b)**e, Q.real(e) & ~Q.zero(b)),                      # |b**e| = |b|**e on the principal branch
    (Abs(b**e), Abs(b)**e, Q.real(e) & Q.nonnegative(e)),                # ... (|0**e| is oo, |0|**e is zoo for e < 0)
    # re / im
    (re(a), a,       Q.real(a)),                                         # re a = a, real a
    (im(a), S.Zero,  Q.real(a)),                                         # im a = 0, real a
    (re(a), S.Zero,  Q.imaginary(a)),                                    # re a = 0, imaginary a
    (im(a), -I*a,    Q.imaginary(a)),                                    # im(i*t) = t
    (re(conjugate(w)), re(w),   true),                                   # re conjugate = re
    (im(conjugate(w)), -im(w),  true),                                   # im conjugate = -im
    (re(c*w), -I*c*re(I*w), true),                                       # re(c*w) = (-i*c)*re(i*w), imaginary c
    (im(c*w), -I*c*im(I*w), true),                                       # im(c*w) = (-i*c)*im(i*w), imaginary c
    (re(b**n), b**n,   Q.real(b) & Q.integer(n) & Q.nonnegative(n)),     # b**n real for real b, n >= 0 integer
    (im(b**n), S.Zero, Q.real(b) & Q.integer(n) & Q.nonnegative(n)),
    (re(b**n), b**n,   Q.real(b) & Q.integer(n) & ~Q.zero(b)),           # ... or b != 0 (0**n is zoo for n < 0)
    (im(b**n), S.Zero, Q.real(b) & Q.integer(n) & ~Q.zero(b)),
    # arg
    (arg(a), S.Zero, Q.positive(a)),                                     # arg a = 0 for a > 0
    (arg(a), pi,     Q.negative(a)),                                     # arg a = pi for a < 0
    (arg(a), pi/2,   Q.imaginary(a) & Q.positive(im(a))),                # arg(i*t) = pi/2 for t > 0
    (arg(a), -pi/2,  Q.imaginary(a) & Q.negative(im(a))),                # arg(i*t) = -pi/2 for t < 0
    (arg(part('q', Q.positive)*w), arg(w), true),                        # a positive factor leaves arg unchanged
    # sign
    (sign(a), S.One,         Q.positive(a)),                             # sign a = 1 for a > 0
    (sign(a), S.NegativeOne, Q.negative(a)),                             # sign a = -1 for a < 0
    (sign(a), I,             Q.imaginary(a) & Q.positive(im(a))),        # sign(i*t) = i for t > 0
    (sign(a), -I,            Q.imaginary(a) & Q.negative(im(a))),        # sign(i*t) = -i for t < 0
    (sign(Abs(w)), S.One,    ~Q.zero(w)),                                # sign|w| = 1 for w != 0
    # conjugate
    (conjugate(a), a,  Q.real(a)),                                       # conjugate a = a, real a
    (conjugate(a), -a, Q.imaginary(a)),                                  # conjugate a = -a, imaginary a
    (conjugate(b**e), conjugate(b)**e, Q.integer(e)),                    # conjugate(b**e) = conjugate(b)**e, integer e
    (conjugate(b**e), b**conjugate(e), Q.positive(b)),                   # conjugate(b**e) = b**conjugate(e), b > 0 (derivable
                                                                         # once the exponential fold matches commutatively)
    # Mul
    (w*conjugate(w), Abs(w)**2, true),                                   # w*conjugate(w) = |w|**2
    (w**e*conjugate(w)**e, Abs(w)**(2*e), Q.integer(e)),                 # ... and for integer powers
]

IDENTITIES: list[Row] = derive([row for row in FACTS if isinstance(row[0].args[0], exp)], EXP_FORMS) + \
    [row for row in FACTS if not isinstance(row[0].args[0], exp)]

_rules = rule_handler([ZERO] + RULES)
_rules_no_zero = rule_handler(RULES)          # arg(0) is nan: no zero row for arg


def _identity(head, **kw):
    rows = [row for row in IDENTITIES if row[0].func is head]
    return identity_handler(rows, measure=node_measure((head,)), **kw)


def _splits(head):
    rows = [row for row in SPLITS if row[0].func is head]
    return identity_handler(rows, measure=node_measure((head,)))


# the splits get a handler of their own so they can fire inside a derived row's candidate
refine_Abs = chain(_rules, _identity(Abs), _upstream.refine_abs)
refine_re = chain(_rules, _simple.refine_re)
refine_im = chain(_rules, _simple.refine_im)
refine_arg = chain(_rules_no_zero, _identity(arg), _simple.refine_arg)
refine_sign = chain(_rules, _identity(sign, opaque=(floor, im, arg, log)), _splits(sign))
refine_conjugate = chain(_rules, _identity(conjugate, opaque=(floor, im, arg, log)), _splits(conjugate))
refine_Mul = rule_handler([row for row in RULES if isinstance(row[0], Mul) and row[0].has(conjugate)])

handlers_dict['Abs'] = refine_Abs
handlers_dict['re'] = refine_re
handlers_dict['im'] = refine_im
handlers_dict['arg'] = refine_arg
handlers_dict['sign'] = refine_sign
handlers_dict['conjugate'] = refine_conjugate
handlers_dict['Mul'] = refine_Mul
