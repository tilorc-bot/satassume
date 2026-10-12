"""``Pow``, ``exp`` and ``log`` as tables.

``log`` is two facts: ``log`` inverts ``exp`` up to the principal branch,
and the complex logarithm is the real logarithm of the modulus plus ``I``
times the argument.  Composed with the exponential forms of a power and of
a product (:func:`._tables.derive`) they give every ``log(x**a)`` and
``log(x*y)`` rule of v3: the bookkeeping ``floor`` collapses under the
rule's precondition, through the ``arg`` bounds of the simple layer or
the engine's sign case split.  The product has two exponential forms,
``log(y) + log(r)`` and ``log(-y) + log(-r)``, which is how a negative
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
(``exp(log(Abs(y)) + log(Abs(r)))``), and three rules: ``I*pi`` times an
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

``log(x**n)`` for a real ``x`` and an even ``n`` is a rule (``LOG_RULES``),
tried after the identities.

The exponential forms are shared with :mod:`.complex_parts`.

Not covered: ``log(1/x)`` for an infinite ``x`` in v3's sense (``Q.finite``
is not part of any row; see above).

Still wrong at infinity (the same class as ``log(1/x)``, left as is):
``log(exp(x)) -> re(x)`` under ``Q.extended_negative(x)`` (``log(exp(-oo))
= zoo``), ``(1/x)**y -> x**(-y)`` for integer ``y`` at ``x = oo``,
``exp(y*log(x)) -> x**y`` at ``x = -oo`` or ``y = +-oo``, and inputs that are
``nan`` (``exp(0*log(0))``) become numbers.
"""
from __future__ import annotations

from sympy import Abs, E, I, Mod, Q, S, arg, exp, log, pi, symbols, true, zoo
from sympy.core import Pow

from ._tables import Row, add_rules, by_cases, derive, part, principal

# b is a base; a and e are exponents; y and r are factors of a product; z and x are arguments:
# all arbitrary (b, e, y and r also appear in the exponential forms, which assume nothing).
z, b, e, y, r, x, a = symbols('z b e y r x a')
d, k, m, n, p, q, t, v = symbols('d k m n p q t v')
h = part('h', lambda t: S(bool(t.is_Rational)))   # the rational constant of a sum (never a symbol: Mod must evaluate)

# Assumed throughout: a row takes each fact whose variables are all in its left side.
ASSUMED = {~Q.zero(d),
           Q.integer(m),
           Q.even(n),
           Q.odd(k),          # (so nonzero)
           Q.positive(p),
           Q.negative(q),
           Q.real(t),
           Q.imaginary(v)}

FACTS: list[Row] = add_rules(set(), [   # lhs == rhs wherever the family's facts hold
    (log(exp(z)), principal(z)),               # log inverts exp up to the principal branch
    (log(d),      log(Abs(d)) + I*arg(d)),     # definition of the complex logarithm
    (d**e,        exp(e*log(d))),              # definition of the principal power
    (exp(a + b),  exp(a)*exp(b)),              # exp is a homomorphism (fires when a factor evaluates)
])
# The power and product forms are identities only off zero (at b = 0 the right side of a
# derived log row is nan in SymPy's arithmetic).  Their domains are relaxed so the engine's
# sign case split may try them; the split checks its result at the excluded point before
# accepting, and a collapse without a split needs arg(b) bounded, which excludes b = 0 too.
# The power form still needs e > 0 when b may be 0: log(0**0) is 0 but 0*log(0) is nan, and
# Abs(0**e) is oo for e < 0 while Abs(0)**e is zoo.
# The domains below that are marked by_cases hold under a profile stating them only as a whole
# (the generator refines a row under profile & domain): Abs(b**e) = Abs(b)**e for a real e
# with e > 0 or b != 0, by the cases of that Or (#50).

EXP_FORMS: list[Row] = [   # (L, W, domain): L == exp(W) wherever the domain holds
    (b**e, e*log(b),           by_cases(~Q.zero(b), Q.positive(e))),  # a power is an exponential (see the note above)
    (y*r,  log(y) + log(r),    true),                      # a product is an exponential (see the note above)
    (y*r,  log(-y) + log(-r),  true),                      # ... with both signs flipped: y*r == (-y)*(-r)
]

RULES: list[Row] = (   # conditional rewrites: a block's assume set is the hypothesis of its rows
    # Pow
    add_rules(set(), [
        (Pow(E, x, evaluate=False), exp(x)),
        ((b**a)**m, b**(a*m)),
    ])
    + add_rules({Q.nonnegative(b) | Q.extended_nonnegative(b)}, [
        ((b**p)**e, b**(p*e)),                   # ... p*log(b) real, 0**p = 0, oo**p = oo
    ])
    + add_rules(set(), [
        ((p**t)**e, p**(t*e)),                   # ... t*log(p) real (sqrt(1/x) = 1/sqrt(x))
    ])
    + add_rules({Q.positive(n) | ~Q.zero(t) | Q.real(e)}, [
        # t**n = |t|**n; 0**n = 0 for n > 0.  At t = 0 with n < 0 it needs a real e: SymPy's
        # zoo**oo is 0 while 0**(-oo) is zoo, and zoo**(1 + I) stays while 0**(-2 - 2*I) is nan
        ((t**n)**e, Abs(t)**(n*e)),
    ])
    + add_rules({Q.extended_real(b), Q.positive(n)}, [
        ((b**n)**e, Abs(b)**(n*e)),              # ... also at b = +-oo for n > 0 ((+-oo)**n = oo)
    ])
    + add_rules(set(), [
        (exp(a)**m, exp(a*m)),
    ])
    + add_rules({Q.even(a/2)}, [
        ((v**a)**e, Abs(v)**(a*e)),              # (I*t)**a = t**a for a = 0 mod 4
    ])
    + add_rules({Q.odd(a/2)}, [
        ((v**a)**e, (-1)**e*Abs(v)**(a*e)),      # (I*t)**a = -t**a for a = 2 mod 4
    ])
    + add_rules(set(), [
        (Pow(S.Zero, p, evaluate=False), S.Zero),
    ])
    + add_rules({Q.zero(b)}, [
        (b**q, zoo),                             # 0**q = zoo (1/x at x = 0)
    ])
    + add_rules(set(), [
        (Abs(t)**n, t**n),
        (Abs(v)**n, (-1)**(n/2)*v**n),           # |I*t|**n = (-1)**(n/2)*(I*t)**n
        ((-1)**n, S.One),
        ((-1)**k, S.NegativeOne),
    ])
    # ... the parity stated one lower: (-1)**((n + 1)/2) under a parity of (n - 1)/2
    # (ask does not shift it)
    + add_rules({Q.even(x - 1)}, [
        ((-1)**x, S.NegativeOne),
    ])
    + add_rules({Q.odd(x - 1)}, [
        ((-1)**x, S.One),
    ])
    + add_rules(set(), [
        ((-1)**((-1)**m/2 + r), (-1)**(m + r + S.Half)),   # (-1)**m/2 = +-1/2 and (-1)**z is 2-periodic
        ((-1)**(n + r), (-1)**r),                          # (-1)**z is 2-periodic: drop even terms
        ((-1)**(k + r), (-1)**(r + 1)),                    # ... an odd term becomes 1
        ((-1)**(h + r), (-1)**(r + Mod(h, 2))),            # ... a rational constant is reduced mod 2
        # exp
        (exp(m*pi*I + r), (-1)**m*exp(r)),                 # exp splits over sums; exp(I*pi*m) = (-1)**m
    ])
    + add_rules({Q.integer(x - S.Half)}, [
        (exp(x*pi*I + r), I*(-1)**(x - S.Half)*exp(r)),    # exp(I*pi*(m + 1/2)) = I*(-1)**m
    ])
    + add_rules({by_cases(~Q.zero(b), Q.positive(e))}, [
        (exp(e*log(b)), b**e),                   # the definition of Pow, folded back (the form's domain)
    ])
)

LOG_RULES: list[Row] = add_rules({by_cases(~Q.zero(n), ~Q.zero(t))}, [   # tried after the log identities
    # t**n = |t|**n, and log(r**e) = e*log(r) for r > 0 and a real e.  At t = 0 both sides are
    # zoo (log(0) = log(zoo) = zoo) unless n = 0, where 0*log(0) is nan: hence n != 0 or t != 0.
    (log(t**n), n*log(Abs(t))),
])

NEGATIVE_BASE: list[Row] = add_rules(set(), [   # exact for integer n; ordered so they fire for a negative number only
    (q**n, (-q)**n),
    (q**k, -(-q)**k),
])

# At an infinite base the power form is not an identity for e <= 0: (+-oo)**0 is 1 but 0*log(+-oo)
# is nan, and oo**e is 0 for e < 0, whose log is zoo, not -oo.  Where the form's exponential
# folds back (Abs(b**e) = Abs(b)**e in complex_parts) the result is right there, but the derived
# log row's right side is not: log(x**n) -> n*log(x) at x = oo, n = 0 (issue #10, B5), and
# log(1/x) -> -log(x) at x = oo.  So the log rows derive with an infinite base excluded unless
# e > 0: a finite or real base (Q.real is decided from stated bounds only for a finite quantity;
# an imaginary or complex base is finite) or a positive exponent will do, a one-sided bound or
# Q.extended_positive alone does not.
LOG_FORMS: list[Row] = [(EXP_FORMS[0][0], EXP_FORMS[0][1], EXP_FORMS[0][2] & by_cases(Q.finite(b), Q.real(b), Q.positive(e)))
                        ] + EXP_FORMS[1:]

IDENTITIES: list[Row] = derive([row for row in FACTS if isinstance(row[0], log)], LOG_FORMS)
