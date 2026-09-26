"""``Pow``, ``exp`` and ``log`` as tables.

Rows: 4 facts, 3 exponential forms (shared with the complex parts), 18
rules, 2 negative-base rows, 1 shared zero row; ``handlers_v3/power_exp_log.py``
is 345 lines.

``log`` is two facts: ``log`` inverts ``exp`` up to the principal branch,
and the complex logarithm is the real logarithm of the modulus plus ``I``
times the argument.  Composed with the exponential forms of a power and of
a product (:func:`._engine.derive`) they give every ``log(x**a)`` and
``log(x*y)`` rule of v3: the bookkeeping ``floor`` collapses under the
rule's precondition, through the ``arg`` bounds of the simple layer or
the engine's sign case split.  The product has two exponential forms,
``log(p) + log(r)`` and ``log(-p) + log(-r)``, which is how a negative
factor's sign is absorbed into the other factor (``log(x*y) = log(-x) +
log(-y)`` for negative ``x``).

``Pow`` has one fact, ``b**e == exp(e*log(b))``: it fires when the
logarithm collapses and the exponential folds back to a power (``log`` is
opaque for that table), which derives ``(x**a)**b -> x**(a*b)`` for a
positive base, ``(x**a)**b -> Abs(x)**(a*b)`` (``(-x)**(a*b)``,
``Abs(x)**(a*b)`` for an imaginary ``x`` with ``a = 0 mod 4``) for an
even ``a`` and ``exp(a)**b -> exp(a*b)`` for a real ``a``.  SymPy folds
``exp(e*log(b))`` back to ``b**e`` on construction when ``e`` is a number,
so the fact reaches symbolic outer exponents only; literal ones
(``sqrt(x**2)``) are the rules' business.  Rules cover what the bookkeeping cannot
reach: an integer outer exponent (no branch at all), a nonnegative base
and a real base with a positive even inner exponent (the fact needs
``b != 0``; these rules are exact at ``0`` because ``0**a = 0`` for
``a > 0``), ``Abs(x)**n``, ``(-1)**z`` by parity, a negative number base by
parity, and the imaginary base with an even ``a`` (``a = 2 mod 4`` has
the derived form ``exp(b*(2*log(Abs(x)) + I*pi))``, which does not fold
to v3's ``(-1)**b*Abs(x)**(2*b)``; ``a = 0 mod 4`` derives for a symbolic
``b`` only).

``exp`` has one fact, ``exp(a + b) == exp(a)*exp(b)``, ordered by the
number of ``exp`` nodes so it fires only when a factor evaluates away
(``exp(log(Abs(p)) + log(Abs(r)))``), and three rules: ``I*pi`` times an
integer or half-integer leaves as ``(-1)**n`` or ``I*(-1)**n``, and
``exp(e*log(b))`` folds back to ``b**e`` on the power form's domain
(``b != 0`` or ``e > 0``: whatever the form unfolded, the fold refolds, so
no result is left as ``exp(e*log(b))``, which is ``nan`` at ``b = 0``
where ``b**e`` is ``0``).

Where the rows fire and v3 does not: ``log(2*x)`` is ``log(2) + log(x)``
(v3 wants a symbolic factor of known sign; the product form needs no
condition), and ``log(x**n)`` for a negative ``x`` and an odd ``n`` comes
out as ``log(-x**n) + I*pi`` (the negative-argument row; ``ask`` cannot
show ``(1 - n)/2`` an integer for an odd ``n``, so the power form's
``floor`` does not collapse to v3's ``n*log(-x) + I*pi``).

At infinity SymPy's arithmetic breaks the identities themselves:
``log(1/oo)`` is ``zoo`` while ``-log(oo)`` is ``-oo``, so ``log(1/x)``
under ``Q.extended_positive(x)`` gives ``-log(x)`` here where v3 (which
asks ``Q.finite``) declines; a finiteness domain would lose every
``~Q.zero(x)`` and complex case (``ask`` cannot show ``e*log(b)`` finite
for an imaginary or complex ``b``).

Not covered (and why): ``log(x**n)`` for a merely real ``x`` and a
symbolic even ``n``, ``log(x**(-2))`` for a real ``x`` and ``log(1/x)``
for a zero ``x`` (the power form needs ``b != 0`` or ``e > 0``: at a zero
base ``0*log(0)`` is ``nan`` and ``Abs(0**e)`` is ``oo``, not ``zoo``, for
``e < 0``; v3 checks the zero base per rule), ``(-1)**((-1)**n/2 + m/2)`` (a vendored
special case), ``log(1/x)`` for an infinite ``x`` (``Q.finite`` is not
part of any row), and ``(x**a)**b`` for an imaginary ``x`` with ``a = 0
mod 4`` and a symbolic ``b`` in v3's form (the derived
``exp(a*b*log(Abs(x)))`` folds only when the fold sees ``a*b`` as the
exponent, which it does; the ``2 mod 4`` case is the rule above).
Checked (adversarial pass, 2026-09-24): every rule and generated row by
hand; ``log``/``Pow``/``exp`` of products, quotients, powers (integer,
half-integer, symbolic) over 19 profiles per symbol on a grid of real,
imaginary, complex and infinite points (about 700 random cases), the
documented extras (``log(2*x)``, ``log(-2*x)``, ``log(pi*x)``,
``log(x**(3/2))`` for negative ``x``), ``exp(I*t)**s`` and ``log(exp(I*t))``
under open and closed bounds, and ``tools/refine_differential.py`` (seeds
2, 3, 7, both modes).  Found no wrong result at a finite point from these
rows.  At infinity SymPy's arithmetic breaks the facts themselves, as the
note above says for ``log(1/x)`` (confirmed: ``-log(x)`` under
``Q.extended_positive(x)``, ``log(1/oo) = zoo``); the same class:
``log(exp(x)) -> re(x)`` under ``Q.extended_negative(x)`` (``log(exp(-oo))
= zoo``), ``(1/x)**y -> x**(-y)`` for integer ``y`` at ``x = oo``, and
``exp(y*log(x)) -> x**y`` at ``x = -oo`` or ``y = +-oo``, and inputs that
are ``nan`` (``exp(0*log(0))``) become numbers.  Left as documented.
"""
from __future__ import annotations

from sympy import Abs, E, I, Mod, Q, S, arg, exp, floor, im, log, pi, symbols, true, zoo
from sympy.core import Pow

from ..._upstream import handlers_dict
from ...build import specialize as _specialize
from ._tables import Row, derive, identity_handler, part, principal, rule_handler
from ._tables import ZERO, chain, exp_node_measure, negative_number_base_measure, node_measure

z, b, e, p, r, x, a, n = symbols('z b e p r x a n')
c = part('c', lambda t: S(bool(t.is_Rational)))   # the rational constant of a sum (never a symbol: Mod must evaluate)

FACTS: list[Row] = [   # (lhs, rhs, domain): lhs == rhs wherever the domain holds
    (log(exp(z)), principal(z),            true),          # log inverts exp up to the principal branch
    (log(x),      log(Abs(x)) + I*arg(x),  ~Q.zero(x)),    # definition of the complex logarithm
    (b**e,        exp(e*log(b)),           ~Q.zero(b)),    # definition of the principal power
    (exp(a + b),  exp(a)*exp(b),           true),          # exp is a homomorphism (fires when a factor evaluates)
]
# The power and product forms are identities only off zero (at b = 0 the right side of a
# derived log row is nan in SymPy's arithmetic).  Their domains are relaxed so the engine's
# sign case split may try them; the split checks its result at the excluded point before
# accepting, and a collapse without a split needs arg(b) bounded, which excludes b = 0 too.
# The power form still needs e > 0 when b may be 0: log(0**0) is 0 but 0*log(0) is nan, and
# Abs(0**e) is oo for e < 0 while Abs(0)**e is zoo.

EXP_FORMS: list[Row] = [   # (L, W, domain): L == exp(W) wherever the domain holds
    (b**e, e*log(b),           ~Q.zero(b) | Q.positive(e)),  # a power is an exponential (see the note above)
    (p*r,  log(p) + log(r),    true),                      # a product is an exponential (see the note above)
    (p*r,  log(-p) + log(-r),  true),                      # ... with both signs flipped: p*r == (-p)*(-r)
]

RULES: list[Row] = [   # (lhs, rhs, hypothesis): a conditional rewrite
    # Pow
    (Pow(E, x, evaluate=False), exp(x), true),                                  # E**x is exp(x)
    ((b**a)**e, b**(a*e), Q.integer(e)),                                        # (b**a)**e = b**(a*e), integer e
    ((b**a)**e, b**(a*e), Q.nonnegative(b) & Q.positive(a)),                    # ... a*log(b) real, 0**a = 0 for a > 0
    ((b**a)**e, b**(a*e), Q.positive(b) & Q.real(a)),                           # ... a*log(b) real for b > 0 (sqrt(1/x) = 1/sqrt(x))
    ((b**a)**e, Abs(b)**(a*e), Q.real(b) & Q.even(a) & (Q.positive(a) | ~Q.zero(b))),   # b**a = |b|**a, even a; 0**a = 0 for a > 0
    (exp(a)**e, exp(a*e), Q.integer(e)),                                        # exp(a)**e = exp(a*e), integer e
    ((b**a)**e, Abs(b)**(a*e), Q.imaginary(b) & Q.even(a/2)),                   # (I*t)**a = t**a for a = 0 mod 4
    ((b**a)**e, (-1)**e*Abs(b)**(a*e), Q.imaginary(b) & Q.odd(a/2)),            # (I*t)**a = -t**a for a = 2 mod 4
    (Pow(S.Zero, n, evaluate=False), S.Zero, Q.positive(n)),                    # 0**n = 0 for n > 0
    (b**e, zoo, Q.zero(b) & Q.negative(e)),                                     # 0**e = zoo for e < 0 (1/x at x = 0)
    (Abs(b)**n, b**n, Q.real(b) & Q.even(n)),                                   # |b|**n = b**n, real b, even n
    (Abs(b)**n, (-1)**(n/2)*b**n, Q.imaginary(b) & Q.even(n)),                  # |I*t|**n = (-1)**(n/2)*(I*t)**n
    ((-1)**x, S.One, Q.even(x)),                                                # (-1)**even = 1
    ((-1)**x, S.NegativeOne, Q.odd(x)),                                         # (-1)**odd = -1
    ((-1)**x, S.NegativeOne, Q.even(x - 1)),                                    # ... the parity stated one lower: (-1)**((n + 1)/2)
    ((-1)**x, S.One, Q.odd(x - 1)),                                             #     under a parity of (n - 1)/2 (ask does not shift it)
    ((-1)**((-1)**x/2 + r), (-1)**(x + r + S.Half), Q.integer(x) & Q.integer(r + S.Half)),   # (-1)**x/2 = +-1/2 (SymPy's continuation)
    ((-1)**(n + r), (-1)**r, Q.even(n)),                                        # (-1)**z is 2-periodic: drop even terms
    ((-1)**(n + r), (-1)**(r + 1), Q.odd(n)),                                   # ... an odd term becomes 1
    ((-1)**(c + r), (-1)**(r + Mod(c, 2)), true),                               # ... a rational constant is reduced mod 2
    # exp
    (exp(n*pi*I + r), (-1)**n*exp(r), Q.integer(n)),                            # exp splits over sums; exp(I*pi*n) = (-1)**n
    (exp(n*pi*I + r), I*(-1)**(n - S.Half)*exp(r), Q.integer(n - S.Half)),       # exp(I*pi*(k + 1/2)) = I*(-1)**k
    (exp(e*log(b)), b**e, ~Q.zero(b) | Q.positive(e)),                          # the definition of Pow, folded back (the form's domain)
]

NEGATIVE_BASE: list[Row] = [   # exact for integer n; ordered so they fire for a negative number only
    (b**n, (-b)**n,  Q.negative(b) & Q.even(n)),                                # c**n = (-c)**n, even n
    (b**n, -(-b)**n, Q.negative(b) & Q.odd(n)),                                 # c**n = -(-c)**n, odd n
]

CATALOG = {None: _specialize.CATALOG + [lambda v: ~Q.zero(v)],       # the log rows' domains speak of b != 0
           "e": _specialize.CATALOG + [_specialize.Literal(-1), _specialize.Literal(2)]}   # log(1/b), log(b**2)

IDENTITIES: list[Row] = derive([row for row in FACTS if isinstance(row[0], log)], EXP_FORMS)
POW_IDENTITIES: list[Row] = [row for row in FACTS if isinstance(row[0], Pow)]
EXP_IDENTITIES: list[Row] = [row for row in FACTS if isinstance(row[0], exp)]

_rules = rule_handler(RULES)
_zero = rule_handler([ZERO])

refine_log = chain(_zero, identity_handler(IDENTITIES))
refine_Pow = chain(_rules,
                   identity_handler(POW_IDENTITIES, measure=node_measure((Pow, exp)), opaque=(floor, im, arg, log)),
                   identity_handler(NEGATIVE_BASE, measure=negative_number_base_measure))
refine_exp = chain(_zero, _rules, identity_handler(EXP_IDENTITIES, measure=exp_node_measure))

handlers_dict['log'] = refine_log
handlers_dict['Pow'] = refine_Pow
handlers_dict['exp'] = refine_exp
