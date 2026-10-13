"""``re``, ``im``, ``arg``, ``sign``, ``Abs``, ``conjugate`` and the conjugate
pair in ``Mul`` as tables.

This family is the base layer: the branch bookkeeping of every other family
(``principal``, the wraps) reduces through ``re``/``im`` of exponentials,
logarithms, sums and products and through ``arg`` and ``Abs`` under sign
facts, all rules here.  What the bookkeeping needs beyond rows is the simple
layer of :mod:`._simple`: ``floor`` of a bounded quantity and ``Piecewise``.
The exponential forms are :mod:`.power_exp_log`'s (imported, not owned).

The facts: ``Abs`` and ``arg`` of an exponential, composed with the
exponential forms so that ``Abs(b**e) = Abs(b)**e``, ``Abs(y*r) =
Abs(y)*Abs(r)`` and ``arg(y*r) = arg(y) + arg(r)`` up to the principal wrap
derive (``arg`` only with the product forms: v3 leaves ``arg(w**e)``
alone); and ``arg`` of a conjugate, exact through its own bookkeeping, which
collapses whenever ``w`` is provably off the negative real axis.

Ordering (``node_measure``): ``sign`` of a product splits only when a factor
resolves, and so does ``Abs(x*y)``; ``Abs`` also counts ``re`` nodes, so
``Abs(b**e)`` for an imaginary ``b`` is not rewritten as
``exp(re(e*log(b)))``.  Sums and products under ``conjugate`` are
distributed by SymPy itself.

Forms that differ from v3: ``arg(x*y)`` for a negative ``y`` is ``arg(-x)``
(v3 pulls out positive factors only); ``Abs(x**-2)`` for a real ``x`` is
``x**-2``; ``conjugate(x + y)`` for a real ``y`` is ``y + conjugate(x)``.

Not covered: ``conjugate(exp(w))`` for a ``w`` that does not resolve (the
ordering wants a node to disappear); ``re``/``im`` of a power with a
non-real base (no identity without ``expand(complex=True)``).

Wrong at infinity: ``arg(exp(x)) -> 0`` under ``Q.extended_real(x)`` is
``nan`` at ``-oo``, and products with a zero and an infinite factor
(``0*oo``) become ``0`` or ``zoo``; the same class as ``power_exp_log``'s.
"""
from __future__ import annotations

from sympy import Abs, I, Interval, Q, S, arg, conjugate, exp, floor, im, log, pi, re, sign, symbols, true, zoo
from sympy.core import Mul

from ._tables import Row, add_rules, derive, exponent, part
from .power_exp_log import EXP_FORMS as _EXP_FORMS   # not owned here (counted in power_exp_log)

# z, b, e, y, r, w and a are arbitrary (b, e, y and r also appear in power_exp_log's
# exponential forms, which assume nothing).
z, b, e, y, r, w, a = symbols('z b e y r w a')
d, f, g, n, u, v = symbols('d f g n u v')
vs = part('vs', Q.imaginary)   # the imaginary factors of a product
s = part('s', Q.real)          # the real factors of a product
h, m = exponent('h'), exponent('m')   # exponents that also bind 1 (conjugate(x) is conjugate(x)**1)

DEFINITIONS: list[Row] = add_rules({~Q.zero(f) & Q.finite(f), ~Q.zero(d)}, [   # stage 0 definitions through sign
    (Abs(f), f/sign(f)),                   # sign f = f/|f| (Abs(zoo) is oo)
    (arg(d), -I*log(sign(d))),             # sign d = exp(I*arg d), arg in (-pi, pi]
])
# With the sign rows below they give Abs and arg of positive, negative and imaginary
# arguments.  re/im of conjugates, sums, exponentials and logarithms and |conjugate w|
# are evaluated by SymPy when the node is built and need no row; re/im of a real power
# follow from the real-argument rows (ask proves b**n real).  re, im and Abs of a real,
# imaginary or signed argument stay stated: a definition through conjugate would lose
# them for products (SymPy distributes conjugate(x*y) before Q.real(x*y) can apply).

FACTS: list[Row] = DEFINITIONS + add_rules(set(), [
    (Abs(exp(z), evaluate=False), exp(re(z))),                         # |exp z| = exp(re z) (SymPy evaluates the lhs)
    (arg(exp(z)),       im(z) + 2*pi*floor(S.Half - im(z)/(2*pi))),    # arg(exp z) = im z wrapped onto (-pi, pi]
    (arg(conjugate(w)), -arg(w) + 2*pi*floor(S.Half + arg(w)/(2*pi))), # arg is odd off the negative axis (nan at 0 on both sides)
])

SPLITS: list[Row] = add_rules(set(), [   # an exact multiplicative identity; the ordering demands progress
    (sign(y*r),        sign(y)*sign(r)),                 # sign is multiplicative
])
# conjugate needs no split rows: SymPy distributes conjugate over sums and products on
# construction, so conjugate(x*y) reaches the table as conjugate(x)*conjugate(y).

_IM_POSITIVE = Q.positive(im(v)) | Q.positive(-I*v)   # the two spellings of "on the positive imaginary axis"
_IM_NEGATIVE = Q.negative(im(v)) | Q.negative(-I*v)

RULES: list[Row] = (   # conditional rewrites: a block's assume set is the hypothesis of its rows
    # Abs, re, im under sign facts
    # (the sign rows are stated over the extended reals: they hold at +-oo, where
    # Abs(+-oo) = oo, re(+-oo) = +-oo, im(+-oo) = 0, sign(+-oo) = +-1, conjugate(+-oo) = +-oo,
    # and a one-sided bound such as Q.gt(a, 1) proves only the extended signs: issue #10, B1-B7.
    # The finite predicate is kept first: SymPy's ask proves Q.real(sin(x)) for a real x but
    # not Q.extended_real(sin(x)), whose handler goes by signs)
    add_rules({Q.nonnegative(a) | Q.extended_nonnegative(a)}, [
        (Abs(a), a),                             # also a = oo
    ])
    + add_rules({Q.nonpositive(a) | Q.extended_nonpositive(a)}, [
        (Abs(a), -a),                            # also a = -oo
    ])
    + add_rules({Q.real(u) | Q.extended_real(u), Q.imaginary(v)}, [
        (re(u), u),
        (im(u), S.Zero),
        (re(v), S.Zero),
        (im(v), -I*v),                           # im(i*t) = t
        # re / im are linear over the reals (these hold at infinity, where the definitions need a finite argument)
        (re(s*w), s*re(w)),
        (im(s*w), s*im(w)),
        (re(vs*w), -I*vs*re(I*w)),
        (im(vs*w), -I*vs*im(I*w)),
    ])
    # sign
    + add_rules({Q.positive(a) | Q.extended_positive(a)}, [
        (sign(a), S.One),                        # also a = oo
    ])
    + add_rules({Q.negative(a) | Q.extended_negative(a)}, [
        (sign(a), S.NegativeOne),                # also a = -oo
    ])
    + add_rules({Q.imaginary(v), _IM_POSITIVE}, [
        (sign(v), I),
    ])
    + add_rules({Q.imaginary(v), _IM_NEGATIVE}, [
        (sign(v), -I),
    ])
    + add_rules({~Q.zero(d)}, [
        (sign(Abs(d)), S.One),
    ])
    + add_rules({Q.real(z)}, [
        (sign(exp(z)), S.One),
    ])
    # conjugate
    + add_rules({Q.real(u) | Q.extended_real(u), Q.imaginary(v), Q.integer(n)}, [
        (conjugate(u), u),
        (conjugate(v), -v),
        (conjugate(exp(z), evaluate=False), exp(conjugate(z))),   # evaluate=False: SymPy would evaluate the lhs
        (conjugate(b**n), conjugate(b)**n),
    ])
    + add_rules({Q.positive(b)}, [
        (conjugate(b**e), b**conjugate(e)),
    ])
    # Mul (g a factor of a product)
    + add_rules({Q.commutative(g), Q.integer(n)}, [
        (g*conjugate(g), Abs(g)**2),
        (g**n*conjugate(g)**n, Abs(g)**(2*n)),
    ])
    # unequal positive integer powers, the higher one g's ...
    + add_rules({Q.commutative(g), Q.integer(h), Q.integer(m), Q.positive(m), Q.positive(h - m)}, [
        (g**h*conjugate(g)**m, Abs(g)**(2*m)*g**(h - m)),
    ])
    # ... or conjugate(g)'s
    + add_rules({Q.commutative(g), Q.integer(h), Q.integer(m), Q.positive(h), Q.positive(m - h)}, [
        (g**h*conjugate(g)**m, Abs(g)**(2*h)*conjugate(g)**(m - h)),
    ])
    + add_rules({~Q.zero(f) & Q.finite(f)}, [
        (f*zoo, zoo),                                 # zoo absorbs a nonzero finite factor (trig's poles rely on it)
        ((-1)**a*(-1)**e, (-1)**(a + e)),             # (-1)**a = exp(I*pi*a): the powers of -1 combine
    ])
)

_OFF_NEGATIVE_AXIS = ~Q.extended_negative(y) | Q.nonnegative(re(y)) | ~Q.zero(im(y))

RANGES: list = [   # (head(y), range, condition): read by the floor of a bounded quantity (_simple)
    (arg(y), Interval.open(-pi, pi),  _OFF_NEGATIVE_AXIS),   # arg is pi only on the negative axis (and at -oo)
    (arg(y), Interval.Lopen(-pi, pi), true),                 # the principal range
]

_PRODUCT_FORMS = [row for row in _EXP_FORMS if isinstance(row[0], Mul)]
_OTHER_FACTS = FACTS[len(DEFINITIONS):]
IDENTITIES: list[Row] = (derive([row for row in _OTHER_FACTS if isinstance(row[0], Abs)], _EXP_FORMS)
                         + derive([row for row in _OTHER_FACTS if isinstance(row[0], arg)], _PRODUCT_FORMS))
