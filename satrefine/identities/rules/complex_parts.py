"""``re``, ``im``, ``arg``, ``sign``, ``Abs``, ``conjugate`` and the conjugate
pair in ``Mul`` as tables.

Rows: 3 facts, 1 split, 41 rules (26 of them the base layer: ``re``,
``im``, ``arg``, ``Abs`` under sign facts and of exponentials, logarithms,
sums, products and conjugates), 1 shared zero row;
``handlers_v3/complex_parts.py`` is 567 lines.  The exponential forms are
the ones in :mod:`.power_exp_log` (imported, not owned).

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
Checked (adversarial pass, 2026-09-24): every rule and generated row by
hand; ``re``/``im``/``arg``/``Abs``/``sign``/``conjugate`` of products,
powers, exponentials, logarithms and conjugates over 19 assumption
profiles per symbol (about 700 random cases on real, imaginary, complex
and infinite points), ``arg(x*y)`` for negative ``y`` and ``arg`` of a
conjugate on the negative axis, and ``tools/refine_differential.py``.
Found no wrong row.  Two wrong results traced below the tables: SymPy's
``ask`` calls ``Abs(x)`` zero for an imaginary ``x`` and the combined
backend passes that on (``arg(exp(I*Abs(x)))`` became ``0``;
``needs/test_checker_abs_of_imaginary_is_zero.py``), and one ``ask`` can
rewrite the old assumptions of every plain symbol in the process
(``needs/test_checker_ask_poisons_plain_symbols.py``).  At infinity:
``arg(exp(x)) -> 0`` under ``Q.extended_real(x)`` is ``nan`` at ``-oo``,
and products with a zero and an infinite factor (``0*oo``) become ``0`` or
``zoo``; the same class as ``power_exp_log``'s.
"""
from __future__ import annotations

from sympy import Abs, I, Interval, Q, S, arg, conjugate, exp, floor, im, log, pi, re, sign, symbols, true, zoo
from sympy.core import Mul

from ..._upstream import handlers_dict
from ._tables import Row, derive, identity_handler, part, rule_handler
from ._simple import register_ranges
from ._tables import ZERO, chain, node_measure
from .power_exp_log import EXP_FORMS as _EXP_FORMS   # not owned here (counted in power_exp_log)

z, b, e, p, r, w, a, n, y = symbols('z b e p r w a n y')
c = part('c', Q.imaginary)   # the imaginary factors of a product
s = part('s', Q.real)        # the real factors of a product

DEFINITIONS: list[Row] = [   # (lhs, rhs, domain): stage 0 definitions through sign
    (Abs(z), z/sign(z),        ~Q.zero(z) & Q.finite(z)),   # sign z = z/|z| (Abs(zoo) is oo)
    (arg(z), -I*log(sign(z)),  ~Q.zero(z)),                 # sign z = exp(I*arg z), arg in (-pi, pi]
]
# With the sign rows below they give Abs and arg of positive, negative and imaginary
# arguments.  re/im of conjugates, sums, exponentials and logarithms and |conjugate w|
# are evaluated by SymPy when the node is built and need no row; re/im of a real power
# follow from the real-argument rows (ask proves b**n real).  re, im and Abs of a real,
# imaginary or signed argument stay stated: a definition through conjugate would lose
# them for products (SymPy distributes conjugate(x*y) before Q.real(x*y) can apply).

FACTS: list[Row] = DEFINITIONS + [   # (lhs, rhs, domain)
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
    # Abs, re, im under sign facts
    (Abs(a), a,      Q.nonnegative(a)),                                  # |a| = a for a >= 0
    (Abs(a), -a,     Q.nonpositive(a)),                                  # |a| = -a for a <= 0
    (re(a), a,       Q.real(a)),                                         # re a = a, real a
    (im(a), S.Zero,  Q.real(a)),                                         # im a = 0, real a
    (re(a), S.Zero,  Q.imaginary(a)),                                    # re a = 0, imaginary a
    (im(a), -I*a,    Q.imaginary(a)),                                    # im(i*t) = t
    # re / im are linear over the reals (these hold at infinity, where the definitions need a finite argument)
    (re(s*w), s*re(w), true),                                            # a real factor comes out of re
    (im(s*w), s*im(w), true),                                            # ... and of im
    (re(c*w), -I*c*re(I*w), true),                                       # re(c*w) = (-i*c)*re(i*w), imaginary c
    (im(c*w), -I*c*im(I*w), true),                                       # im(c*w) = (-i*c)*im(i*w), imaginary c
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
    ((-1)**a*(-1)**e, (-1)**(a + e), true),                               # (-1)**a = exp(I*pi*a): the powers of -1 combine
]

_OFF_NEGATIVE_AXIS = ~Q.extended_negative(y) | Q.nonnegative(re(y)) | ~Q.zero(im(y))

RANGES: list = [   # (head(y), range, condition): read by the floor of a bounded quantity (_simple)
    (arg(y), Interval.open(-pi, pi),  _OFF_NEGATIVE_AXIS),   # arg is pi only on the negative axis (and at -oo)
    (arg(y), Interval.Lopen(-pi, pi), true),                 # the principal range
]
register_ranges(RANGES)

_PRODUCT_FORMS = [row for row in _EXP_FORMS if isinstance(row[0], Mul)]
_OTHER_FACTS = FACTS[len(DEFINITIONS):]
IDENTITIES: list[Row] = (derive([row for row in _OTHER_FACTS if isinstance(row[0], Abs)], _EXP_FORMS)
                         + derive([row for row in _OTHER_FACTS if isinstance(row[0], arg)], _PRODUCT_FORMS))

_rules = rule_handler([ZERO] + RULES)   # also arg: arg(0) is nan, which is what arg(x) is at x = 0


def _definition(head, **kw):
    return identity_handler([row for row in DEFINITIONS if row[0].func is head], **kw)


def _identity(head, **kw):
    rows = [row for row in IDENTITIES if row[0].func is head]
    return identity_handler(rows, measure=node_measure((head,)), **kw)


def _splits(head):
    rows = [row for row in SPLITS if row[0].func is head]
    return identity_handler(rows, measure=node_measure((head,)))


# the splits get a handler of their own so they can fire inside a derived row's candidate
refine_Abs = chain(_rules, identity_handler([row for row in IDENTITIES if row[0].func is Abs],
                                            measure=node_measure((Abs, re))),
                   _definition(Abs, opaque=(sign,)))
refine_re = _rules
refine_im = _rules
refine_arg = chain(_rules, _identity(arg, opaque=(floor, im)),   # arg is the result, not bookkeeping
                   _definition(arg, opaque=(sign,)))
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
