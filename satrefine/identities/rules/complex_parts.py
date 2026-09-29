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
exponential forms so that ``Abs(b**e) = Abs(b)**e``, ``Abs(y*r) =
Abs(y)*Abs(r)`` and ``arg(y*r) = arg(y) + arg(r)`` up to the principal
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

Not covered (and why): ``conjugate(exp(w))`` for a ``w`` that does not
resolve (v3 pushes the conjugate inside unconditionally; the ordering
here wants a node to disappear); ``re``/``im`` of a power with a non-real
base (no identity without ``expand(complex=True)``, as in v3).
Checked (adversarial pass, 2026-09-24): every rule and generated row by
hand; ``re``/``im``/``arg``/``Abs``/``sign``/``conjugate`` of products,
powers, exponentials, logarithms and conjugates over 19 assumption
profiles per symbol (about 700 random cases on real, imaginary, complex
and infinite points), ``arg(x*y)`` for negative ``y`` and ``arg`` of a
conjugate on the negative axis, and ``python -m satrefine.tools.refine_differential``.
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

from ._tables import ZERO, Family, Identities, Row, Rules, derive, exponent, node_measure, part
from .power_exp_log import EXP_FORMS as _EXP_FORMS   # not owned here (counted in power_exp_log)

# z, b, e, y, r, w and a are arbitrary (b, e, y and r also appear in power_exp_log's
# exponential forms, which assume nothing).
z, b, e, y, r, w, a = symbols('z b e y r w a')
d, f, g, n, u, v = symbols('d f g n u v')
vs = part('vs', Q.imaginary)   # the imaginary factors of a product
s = part('s', Q.real)          # the real factors of a product
h, m = exponent('h'), exponent('m')   # exponents that also bind 1 (conjugate(x) is conjugate(x)**1)

# Assumed throughout: a row takes each fact whose variables are all in its left side.
ASSUMED = {~Q.zero(d),                     # d is nonzero
           ~Q.zero(f) & Q.finite(f),       # f is nonzero and finite
           Q.integer(n),                   # n is an integer
           Q.integer(h), Q.integer(m),     # h and m are integers (h may be 0, so not k)
           Q.real(u) | Q.extended_real(u),   # u is an extended real (+-oo included)
           Q.imaginary(v),                 # v is imaginary
           Q.commutative(g)}               # g commutes (a factor of a product)

DEFINITIONS: list[Row] = [   # (lhs, rhs[, domain]): stage 0 definitions through sign
    (Abs(f), f/sign(f)),                   # sign f = f/|f| (Abs(zoo) is oo)
    (arg(d), -I*log(sign(d))),             # sign d = exp(I*arg d), arg in (-pi, pi]
]
# With the sign rows below they give Abs and arg of positive, negative and imaginary
# arguments.  re/im of conjugates, sums, exponentials and logarithms and |conjugate w|
# are evaluated by SymPy when the node is built and need no row; re/im of a real power
# follow from the real-argument rows (ask proves b**n real).  re, im and Abs of a real,
# imaginary or signed argument stay stated: a definition through conjugate would lose
# them for products (SymPy distributes conjugate(x*y) before Q.real(x*y) can apply).

FACTS: list[Row] = DEFINITIONS + [   # (lhs, rhs[, domain])
    (Abs(exp(z), evaluate=False), exp(re(z))),                         # |exp z| = exp(re z) (SymPy evaluates the lhs)
    (arg(exp(z)),       im(z) + 2*pi*floor(S.Half - im(z)/(2*pi))),    # arg(exp z) = im z wrapped onto (-pi, pi]
    (arg(conjugate(w)), -arg(w) + 2*pi*floor(S.Half + arg(w)/(2*pi))), # arg is odd off the negative axis (nan at 0 on both sides)
]

SPLITS: list[Row] = [   # an exact multiplicative identity; the ordering demands progress
    (sign(y*r),        sign(y)*sign(r)),                 # sign is multiplicative
]
# conjugate needs no split rows: SymPy distributes conjugate over sums and products on
# construction, so conjugate(x*y) reaches the table as conjugate(x)*conjugate(y).

_IM_POSITIVE = Q.positive(im(v)) | Q.positive(-I*v)   # the two spellings of "on the positive imaginary axis"
_IM_NEGATIVE = Q.negative(im(v)) | Q.negative(-I*v)

RULES: list[Row] = [   # (lhs, rhs[, hypothesis])
    # Abs, re, im under sign facts
    # (the sign rows are stated over the extended reals: they hold at +-oo, where
    # Abs(+-oo) = oo, re(+-oo) = +-oo, im(+-oo) = 0, sign(+-oo) = +-1, conjugate(+-oo) = +-oo,
    # and a one-sided bound such as Q.gt(a, 1) proves only the extended signs: issue #10, B1-B7.
    # The finite predicate is kept first: SymPy's ask proves Q.real(sin(x)) for a real x but
    # not Q.extended_real(sin(x)), whose handler goes by signs)
    (Abs(a), a,      Q.nonnegative(a) | Q.extended_nonnegative(a)),      # |a| = a for a >= 0 (also a = oo)
    (Abs(a), -a,     Q.nonpositive(a) | Q.extended_nonpositive(a)),      # |a| = -a for a <= 0 (also a = -oo)
    (re(u), u),                                                          # re u = u
    (im(u), S.Zero),                                                     # im u = 0
    (re(v), S.Zero),                                                     # re v = 0
    (im(v), -I*v),                                                       # im(i*t) = t
    # re / im are linear over the reals (these hold at infinity, where the definitions need a finite argument)
    (re(s*w), s*re(w)),                                                  # a real factor comes out of re
    (im(s*w), s*im(w)),                                                  # ... and of im
    (re(vs*w), -I*vs*re(I*w)),                                           # re(vs*w) = (-i*vs)*re(i*w), imaginary vs
    (im(vs*w), -I*vs*im(I*w)),                                           # im(vs*w) = (-i*vs)*im(i*w), imaginary vs
    # sign
    (sign(a), S.One,         Q.positive(a) | Q.extended_positive(a)),    # sign a = 1 for a > 0 (also a = oo)
    (sign(a), S.NegativeOne, Q.negative(a) | Q.extended_negative(a)),    # sign a = -1 for a < 0 (also a = -oo)
    (sign(v), I,             _IM_POSITIVE),                              # sign(i*t) = i for t > 0
    (sign(v), -I,            _IM_NEGATIVE),                              # sign(i*t) = -i for t < 0
    (sign(Abs(d)), S.One),                                               # sign|d| = 1
    (sign(exp(z)), S.One,    Q.real(z)),                                 # sign(exp z) = 1 for real z
    # conjugate
    (conjugate(u), u),                                                   # conjugate u = u
    (conjugate(v), -v),                                                  # conjugate v = -v
    (conjugate(exp(z), evaluate=False), exp(conjugate(z))),              # conjugate(exp z) = exp(conjugate z) (SymPy evaluates the lhs)
    (conjugate(b**n), conjugate(b)**n),                                  # conjugate(b**n) = conjugate(b)**n
    (conjugate(b**e), b**conjugate(e), Q.positive(b)),                   # conjugate(b**e) = b**conjugate(e), b > 0
    # Mul
    (g*conjugate(g), Abs(g)**2),                                         # g*conjugate(g) = |g|**2
    (g**n*conjugate(g)**n, Abs(g)**(2*n)),                               # ... and for integer powers
    (g**h*conjugate(g)**m, Abs(g)**(2*m)*g**(h - m), Q.positive(m) & Q.positive(h - m)),            # ... unequal positive powers, the higher one g's
    (g**h*conjugate(g)**m, Abs(g)**(2*h)*conjugate(g)**(m - h), Q.positive(h) & Q.positive(m - h)),   # ... or conjugate(g)'s
    (f*zoo, zoo),                                                        # zoo absorbs a nonzero finite factor
    ((-1)**a*(-1)**e, (-1)**(a + e)),                                    # (-1)**a = exp(I*pi*a): the powers of -1 combine
]

_OFF_NEGATIVE_AXIS = ~Q.extended_negative(y) | Q.nonnegative(re(y)) | ~Q.zero(im(y))

RANGES: list = [   # (head(y), range, condition): read by the floor of a bounded quantity (_simple)
    (arg(y), Interval.open(-pi, pi),  _OFF_NEGATIVE_AXIS),   # arg is pi only on the negative axis (and at -oo)
    (arg(y), Interval.Lopen(-pi, pi), true),                 # the principal range
]

_PRODUCT_FORMS = [row for row in _EXP_FORMS if isinstance(row[0], Mul)]
_OTHER_FACTS = FACTS[len(DEFINITIONS):]
IDENTITIES: list[Row] = (derive([row for row in _OTHER_FACTS if isinstance(row[0], Abs)], _EXP_FORMS)
                         + derive([row for row in _OTHER_FACTS if isinstance(row[0], arg)], _PRODUCT_FORMS))

_rules = Rules([ZERO] + RULES)   # also arg: arg(0) is nan, which is what arg(x) is at x = 0


def _definition(head, **kw):
    return Identities([row for row in DEFINITIONS if row[0].func is head], **kw)


def _identity(head, **kw):
    rows = [row for row in IDENTITIES if row[0].func is head]
    return Identities(rows, measure=node_measure((head,)), **kw)


def _splits(head):
    rows = [row for row in SPLITS if row[0].func is head]
    return Identities(rows, measure=node_measure((head,)))


# the splits get a handler of their own so they can fire inside a derived row's candidate
SPEC = Family({'Abs': (_rules, Identities([row for row in IDENTITIES if row[0].func is Abs],
                                          measure=node_measure((Abs, re))),
                       _definition(Abs, opaque=(sign,))),
               're': _rules,
               'im': _rules,
               'arg': (_rules, _identity(arg, opaque=(floor, im)),   # arg is the result, not bookkeeping
                       _definition(arg, opaque=(sign,))),
               'sign': (_rules, _splits(sign)),
               'conjugate': _rules,
               'Mul': Rules([row for row in RULES if isinstance(row[0], Mul)])},
              facts=FACTS + SPLITS, exp_forms=_EXP_FORMS, rules=[ZERO] + RULES, ranges=RANGES,
              assumed=ASSUMED)
