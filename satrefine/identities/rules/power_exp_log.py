"""``Pow``, ``exp`` and ``log`` as tables.

Rows: 4 facts, 3 exponential forms (shared with the complex parts), 18
rules, 2 negative-base rows, 1 shared zero row; ``handlers_v3/power_exp_log.py``
is 345 lines.

``log`` is two facts: ``log`` inverts ``exp`` up to the principal branch,
and the complex logarithm is the real logarithm of the modulus plus ``I``
times the argument.  Composed with the exponential forms of a power and of
a product (:func:`._tables.derive`) they give every ``log(x**a)`` and
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
``log(1/oo)`` is ``zoo`` while ``-log(oo)`` is ``-oo``, and ``log(oo**0)``
is ``0`` while ``0*log(oo)`` is ``nan``.  The log rows therefore derive
with a power form that needs a finite or real base or a positive exponent
(``LOG_FORMS``): ``log(1/x)`` under ``Q.extended_positive(x)`` and
``log(x**n)`` under ``Q.gt(x, 1)`` stay (as in v3, which asks
``Q.finite``), while an imaginary or complex base, which ``ask`` proves
finite, keeps its rows (a domain on ``e*log(b)`` being finite would lose
them: ``ask`` cannot show that for an imaginary ``b``).

``log(x**n)`` for a real ``x`` and an even ``n`` (literal or symbolic,
negative too: ``log(x**(-2))``) is a rule, ``n*log(Abs(x))``, tried after
the identities; it needs ``n != 0`` or ``x != 0`` (``0*log(0)`` is ``nan``).

Not covered (and why): ``log(1/x)`` for an infinite ``x`` in v3's
sense (``Q.finite`` is not part of any row; see above), and ``(x**a)**b``
for an imaginary ``x`` with ``a = 0 mod 4`` and a symbolic ``b`` in v3's
form (the derived ``exp(a*b*log(Abs(x)))`` folds only when the fold sees
``a*b`` as the exponent, which it does; the ``2 mod 4`` case is the rule
above).  ``(-1)**((-1)**n/2 + r)`` for an integer ``n`` is
``(-1)**(n + r + 1/2)`` for any ``r``: ``(-1)**n/2`` is ``+-1/2`` and
``(-1)**z`` is 2-periodic.
Checked (adversarial pass, 2026-09-24): every rule and generated row by
hand; ``log``/``Pow``/``exp`` of products, quotients, powers (integer,
half-integer, symbolic) over 19 profiles per symbol on a grid of real,
imaginary, complex and infinite points (about 700 random cases), the
documented extras (``log(2*x)``, ``log(-2*x)``, ``log(pi*x)``,
``log(x**(3/2))`` for negative ``x``), ``exp(I*t)**s`` and ``log(exp(I*t))``
under open and closed bounds, and ``python -m satrefine.tools.refine_differential`` (seeds
2, 3, 7, both modes).  Found no wrong result at a finite point from these
rows.  At infinity SymPy's arithmetic breaks the facts themselves, as the
note above says for ``log(1/x)`` (now declined, ``LOG_FORMS``); the same class:
``log(exp(x)) -> re(x)`` under ``Q.extended_negative(x)`` (``log(exp(-oo))
= zoo``), ``(1/x)**y -> x**(-y)`` for integer ``y`` at ``x = oo``, and
``exp(y*log(x)) -> x**y`` at ``x = -oo`` or ``y = +-oo``, and inputs that
are ``nan`` (``exp(0*log(0))``) become numbers.  Left as documented.
"""
from __future__ import annotations

from sympy import Abs, E, I, Mod, Q, S, arg, exp, floor, im, log, pi, symbols, true, zoo
from sympy.core import Pow

from ._tables import (ZERO, Family, Identities, Row, Rules, count_measure, derive, node_measure, part, principal,
                      size)

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
    ((b**a)**e, b**(a*e), (Q.nonnegative(b) | Q.extended_nonnegative(b)) & Q.positive(a)),   # ... a*log(b) real, 0**a = 0 for a > 0, oo**a = oo
    ((b**a)**e, b**(a*e), Q.positive(b) & Q.real(a)),                           # ... a*log(b) real for b > 0 (sqrt(1/x) = 1/sqrt(x))
    ((b**a)**e, Abs(b)**(a*e), Q.real(b) & Q.even(a) & (Q.positive(a) | ~Q.zero(b))),   # b**a = |b|**a, even a; 0**a = 0 for a > 0
    ((b**a)**e, Abs(b)**(a*e), Q.extended_real(b) & Q.even(a) & Q.positive(a)),        # ... also at b = +-oo for a > 0 ((+-oo)**a = oo)
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
    ((-1)**((-1)**x/2 + r), (-1)**(x + r + S.Half), Q.integer(x)),              # (-1)**x/2 = +-1/2 and (-1)**z is 2-periodic
    ((-1)**(n + r), (-1)**r, Q.even(n)),                                        # (-1)**z is 2-periodic: drop even terms
    ((-1)**(n + r), (-1)**(r + 1), Q.odd(n)),                                   # ... an odd term becomes 1
    ((-1)**(c + r), (-1)**(r + Mod(c, 2)), true),                               # ... a rational constant is reduced mod 2
    # exp
    (exp(n*pi*I + r), (-1)**n*exp(r), Q.integer(n)),                            # exp splits over sums; exp(I*pi*n) = (-1)**n
    (exp(n*pi*I + r), I*(-1)**(n - S.Half)*exp(r), Q.integer(n - S.Half)),       # exp(I*pi*(k + 1/2)) = I*(-1)**k
    (exp(e*log(b)), b**e, ~Q.zero(b) | Q.positive(e)),                          # the definition of Pow, folded back (the form's domain)
]

LOG_RULES: list[Row] = [   # tried after the log identities
    # b**e = |b|**e for a real b and an even e, and log(r**e) = e*log(r) for r > 0 and a real e.  At b = 0
    # both sides are zoo (log(0) = log(zoo) = zoo) unless e = 0, where 0*log(0) is nan: hence e != 0 or b != 0.
    (log(b**e), e*log(Abs(b)), Q.real(b) & Q.even(e) & (~Q.zero(e) | ~Q.zero(b))),
]

NEGATIVE_BASE: list[Row] = [   # exact for integer n; ordered so they fire for a negative number only
    (b**n, (-b)**n,  Q.negative(b) & Q.even(n)),                                # c**n = (-c)**n, even n
    (b**n, -(-b)**n, Q.negative(b) & Q.odd(n)),                                 # c**n = -(-c)**n, odd n
]

# At an infinite base the power form is not an identity for e <= 0: (+-oo)**0 is 1 but 0*log(+-oo)
# is nan, and oo**e is 0 for e < 0, whose log is zoo, not -oo.  Where the form's exponential
# folds back (Abs(b**e) = Abs(b)**e in complex_parts) the result is right there, but the derived
# log row's right side is not: log(x**n) -> n*log(x) at x = oo, n = 0 (issue #10, B5), and
# log(1/x) -> -log(x) at x = oo.  So the log rows derive with an infinite base excluded unless
# e > 0: a finite or real base (Q.real is decided from stated bounds only for a finite quantity;
# an imaginary or complex base is finite) or a positive exponent will do, a one-sided bound or
# Q.extended_positive alone does not.
LOG_FORMS: list[Row] = [(EXP_FORMS[0][0], EXP_FORMS[0][1], EXP_FORMS[0][2] & (Q.finite(b) | Q.real(b) | Q.positive(e)))
                        ] + EXP_FORMS[1:]

IDENTITIES: list[Row] = derive([row for row in FACTS if isinstance(row[0], log)], LOG_FORMS)
POW_IDENTITIES: list[Row] = [row for row in FACTS if isinstance(row[0], Pow)]
EXP_IDENTITIES: list[Row] = [row for row in FACTS if isinstance(row[0], exp)]


def negative_number_base_measure(e, assumptions):
    """``(powers of a negative number, size)``: the ordering for ``c**n -> (-c)**n``
    rows, which must not fire for a symbolic base (SymPy's ``Pow._eval_refine``
    rewrites ``(-x)**n`` back to ``-x**n`` for odd ``n``, a cycle)."""
    negative = sum(1 for node in e.atoms(Pow) if node.base.is_number and node.base.is_negative)
    return (negative, size(e))


_rules = Rules(RULES)
_zero = Rules([ZERO])

SPEC = Family({'log': (_zero, Identities(IDENTITIES), Rules(LOG_RULES)),
               'Pow': (_rules,
                       Identities(POW_IDENTITIES, measure=node_measure((Pow, exp)), opaque=(floor, im, arg, log)),
                       Identities(NEGATIVE_BASE, measure=negative_number_base_measure)),
               'exp': (_zero, _rules, Identities(EXP_IDENTITIES, measure=count_measure((exp,))))},
              facts=FACTS + NEGATIVE_BASE, exp_forms=LOG_FORMS, rules=[ZERO] + RULES + LOG_RULES)
