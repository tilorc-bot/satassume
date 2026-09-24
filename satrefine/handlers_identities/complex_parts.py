"""``re``, ``im``, ``arg``, ``sign``, ``Abs``, ``conjugate`` and the conjugate
pair in ``Mul`` as tables.

Rows: 3 facts, 1 split, 38 rules, 1 shared zero row; ``handlers_v3/complex_parts.py``
is 567 lines.  The exponential forms are the ones in
:mod:`.power_exp_log`.

This family is the base layer: the branch bookkeeping of every other
family (``principal``, the wraps) reduces through ``re``/``im`` of
exponentials, logarithms, sums and products and through ``arg`` and
``Abs`` under sign facts, all of which are rules here (the ``BASE``
rows).  What the bookkeeping needs beyond rows is the simple layer of
:mod:`._simple`: ``floor`` of a bounded quantity and ``Piecewise``.

The facts: ``Abs`` and ``arg`` of an exponential, composed with the
exponential forms so that ``Abs(b**e) = Abs(b)**e``, ``Abs(p*r) =
Abs(p)*Abs(r)`` and ``arg(p*r) = arg(p) + arg(r)`` up to the principal
wrap derive (``arg`` only with the product forms: v3 leaves ``arg(w**e)``
alone); and ``arg`` of a conjugate, exact through its own bookkeeping,
which collapses whenever ``w`` is provably off the negative real axis.
Products under ``sign`` split by an exact identity whose ordering
requires a factor to resolve, which is v3's "fires only if at least one
factor resolves"; the same ordering makes ``Abs(x*y)`` split only when a
factor resolves, and it counts ``re`` nodes for ``Abs`` so that
``Abs(b**e)`` for an imaginary ``b`` is not rewritten as
``exp(re(e*log(b)))`` (v3 declines there too).  Sums and products under
``conjugate`` are distributed by SymPy itself.

Where the rows fire and v3 does not: ``arg(x*y)`` for a negative ``y`` is
``arg(-x)`` (the product form with both signs flipped; v3 pulls positive
factors only).  Other forms: ``Abs(x**-2)`` for a real ``x`` is ``x**-2``
(v3: ``1/Abs(x**2)``), ``conjugate(x + y)`` for a real ``y`` is ``y +
conjugate(x)`` (v3 conjugates every term first).

Not covered (and why): ``x**3*conjugate(x) -> x**2*Abs(x)**2`` (the
leftover power's exponent is computed, not matched: a ``conjugate(x)``
factor is not a ``Pow``); ``conjugate(exp(w))`` for a ``w`` that does not
resolve (v3 pushes the conjugate inside unconditionally; the ordering
here wants a node to disappear); ``re``/``im`` of a power with a non-real
base (no identity without ``expand(complex=True)``, as in v3).
"""
from __future__ import annotations

from sympy import Abs, I, Q, S, arg, conjugate, cos, exp, floor, im, log, pi, re, sign, sin, symbols, true, zoo
from sympy.core import Mul, Pow

from .._upstream import handlers_dict
from ._engine import Row, derive, identity_handler, part, rule_handler
from ._tables import ZERO, chain, node_measure
from .power_exp_log import EXP_FORMS

z, b, e, p, r, w, a, n = symbols('z b e p r w a n')
c = part('c', Q.imaginary)   # the imaginary factors of a product
s = part('s', Q.real)        # the real factors of a product

FACTS: list[Row] = [   # (lhs, rhs, domain)
    (Abs(exp(z), evaluate=False), exp(re(z)),                          true),   # |exp z| = exp(re z) (SymPy evaluates the lhs)
    (arg(exp(z)),       im(z) + 2*pi*floor(S.Half - im(z)/(2*pi)),     true),   # arg(exp z) = im z wrapped onto (-pi, pi]
    (arg(conjugate(w)), -arg(w) + 2*pi*floor(S.Half + arg(w)/(2*pi)),  true),   # arg is odd off the negative axis (nan at 0 on both sides)
]

SPLITS: list[Row] = [   # an exact multiplicative identity; the ordering demands progress
    (sign(p*r),        sign(p)*sign(r),                 true),   # sign is multiplicative
]
# conjugate needs no split rows: SymPy distributes conjugate over sums and products on
# construction, so conjugate(x*y) reaches the table as conjugate(x)*conjugate(y).

_IM_POSITIVE = Q.positive(im(a)) | Q.positive(-I*a)   # the two spellings of "on the positive imaginary axis"
_IM_NEGATIVE = Q.negative(im(a)) | Q.negative(-I*a)

RULES: list[Row] = [   # (lhs, rhs, hypothesis)
    # Abs
    (Abs(a), a,      Q.nonnegative(a)),                                  # |a| = a for a >= 0
    (Abs(a), -a,     Q.nonpositive(a)),                                  # |a| = -a for a <= 0
    (Abs(a), -I*a,   Q.imaginary(a) & _IM_POSITIVE),                     # |i*t| = t for t > 0
    (Abs(a), I*a,    Q.imaginary(a) & _IM_NEGATIVE),                     # |i*t| = -t for t < 0
    (Abs(conjugate(w)), Abs(w), true),                                   # |conjugate w| = |w|
    # re / im
    (re(a), a,       Q.real(a)),                                         # re a = a, real a
    (im(a), S.Zero,  Q.real(a)),                                         # im a = 0, real a
    (re(a), S.Zero,  Q.imaginary(a)),                                    # re a = 0, imaginary a
    (im(a), -I*a,    Q.imaginary(a)),                                    # im(i*t) = t
    (re(conjugate(w)), re(w),   true),                                   # re conjugate = re
    (im(conjugate(w)), -im(w),  true),                                   # im conjugate = -im
    (re(exp(z)), exp(re(z))*cos(im(z)), true),                           # re(exp z) = exp(re z) cos(im z)
    (im(exp(z)), exp(re(z))*sin(im(z)), true),                           # im(exp z) = exp(re z) sin(im z)
    (re(log(w)), log(Abs(w)), true),                                     # re(log w) = log|w|
    (im(log(w)), arg(w),      true),                                     # im(log w) = arg w
    (re(a + b), re(a) + re(b), true),                                    # re is additive
    (im(a + b), im(a) + im(b), true),                                    # im is additive
    (re(s*w), s*re(w), true),                                            # a real factor comes out of re
    (im(s*w), s*im(w), true),                                            # ... and of im
    (re(c*w), -I*c*re(I*w), true),                                       # re(c*w) = (-i*c)*re(i*w), imaginary c
    (im(c*w), -I*c*im(I*w), true),                                       # im(c*w) = (-i*c)*im(i*w), imaginary c
    (re(b**n), b**n,   Q.real(b) & Q.integer(n) & (Q.nonnegative(n) | ~Q.zero(b))),   # b**n is real (0**n is zoo for n < 0)
    (im(b**n), S.Zero, Q.real(b) & Q.integer(n) & (Q.nonnegative(n) | ~Q.zero(b))),
    # arg
    (arg(a), S.Zero, Q.positive(a)),                                     # arg a = 0 for a > 0
    (arg(a), pi,     Q.negative(a)),                                     # arg a = pi for a < 0
    (arg(a), pi/2,   Q.imaginary(a) & _IM_POSITIVE),                     # arg(i*t) = pi/2 for t > 0
    (arg(a), -pi/2,  Q.imaginary(a) & _IM_NEGATIVE),                     # arg(i*t) = -pi/2 for t < 0
    # sign
    (sign(a), S.One,         Q.positive(a)),                             # sign a = 1 for a > 0
    (sign(a), S.NegativeOne, Q.negative(a)),                             # sign a = -1 for a < 0
    (sign(a), I,             Q.imaginary(a) & _IM_POSITIVE),             # sign(i*t) = i for t > 0
    (sign(a), -I,            Q.imaginary(a) & _IM_NEGATIVE),             # sign(i*t) = -i for t < 0
    (sign(Abs(w)), S.One,    ~Q.zero(w)),                                # sign|w| = 1 for w != 0
    (sign(exp(z)), S.One,    Q.real(z)),                                 # sign(exp z) = 1 for real z
    # conjugate
    (conjugate(a), a,  Q.real(a)),                                       # conjugate a = a, real a
    (conjugate(a), -a, Q.imaginary(a)),                                  # conjugate a = -a, imaginary a
    (conjugate(exp(z), evaluate=False), exp(conjugate(z)), true),        # conjugate(exp z) = exp(conjugate z) (SymPy evaluates the lhs)
    (conjugate(b**e), conjugate(b)**e, Q.integer(e)),                    # conjugate(b**e) = conjugate(b)**e, integer e
    (conjugate(b**e), b**conjugate(e), Q.positive(b)),                   # conjugate(b**e) = b**conjugate(e), b > 0
    # Mul
    (w*conjugate(w), Abs(w)**2, Q.commutative(w)),                       # w*conjugate(w) = |w|**2
    (w**e*conjugate(w)**e, Abs(w)**(2*e), Q.integer(e) & Q.commutative(w)),   # ... and for integer powers
    (a*zoo, zoo, Q.finite(a) & ~Q.zero(a)),                              # zoo absorbs a nonzero finite factor
]

_PRODUCT_FORMS = [row for row in EXP_FORMS if isinstance(row[0], Mul)]
IDENTITIES: list[Row] = (derive([row for row in FACTS if isinstance(row[0], Abs)], EXP_FORMS)
                         + derive([row for row in FACTS if isinstance(row[0], arg)], _PRODUCT_FORMS))

_rules = rule_handler([ZERO] + RULES)
_rules_no_zero = rule_handler(RULES)          # arg(0) is nan: no zero row for arg


def _identity(head, **kw):
    rows = [row for row in IDENTITIES if row[0].func is head]
    return identity_handler(rows, measure=node_measure((head,)), **kw)


def _splits(head):
    rows = [row for row in SPLITS if row[0].func is head]
    return identity_handler(rows, measure=node_measure((head,)))


BASE: list[Row] = [row for row in RULES if row[0].func in (re, im, arg, Abs)]
"""The rows the other families' bookkeeping reduces through."""

# the splits get a handler of their own so they can fire inside a derived row's candidate
refine_Abs = chain(_rules, identity_handler([row for row in IDENTITIES if row[0].func is Abs],
                                            measure=node_measure((Abs, re))))
refine_re = _rules
refine_im = _rules
refine_arg = chain(_rules_no_zero, _identity(arg, opaque=(floor, im)))   # arg is the result, not bookkeeping
refine_sign = chain(_rules, _splits(sign))
refine_conjugate = _rules
refine_Mul = rule_handler([row for row in RULES if isinstance(row[0], Mul)])

handlers_dict['Abs'] = refine_Abs
handlers_dict['re'] = refine_re
handlers_dict['im'] = refine_im
handlers_dict['arg'] = refine_arg
handlers_dict['sign'] = refine_sign
handlers_dict['conjugate'] = refine_conjugate
handlers_dict['Mul'] = refine_Mul
