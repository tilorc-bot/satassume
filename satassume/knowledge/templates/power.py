"""``Pow``: ``f(base, exponent)`` is ``base**exponent``.

Values follow SymPy's conventions: ``0**0 == 1`` and ``b**0 == 1`` also for
``zoo`` and ``nan``, ``1/0 == zoo``, ``1**oo`` and ``1**-oo`` are ``nan``,
``zoo**(-1/2) == 0``, ``(-oo)**(-2) == 0``.  The rules mirror SymPy's
``_eval_is_*`` methods of ``sympy/core/power.py`` except where those are
unsound under value semantics (noted under the rows).

A row about ``f(E, exponent)``, ``f(-1, exponent)``, ``f(base, 1)``, ...
is about the powers of that shape only; ``f(exp(log_base), exponent)`` is
about a base ``exp(u)`` (or an unevaluated ``E**u``), ``f(base, base)``
about a power of a symbol to itself, and ``number`` stands for a constant
(an atomic number) base or exponent (see ``_rows``).  ``base - 1``,
``base + 1`` (from ``Q.ne(base, 1)`` and the like) exist only when neither
argument is a number, and ``2*exponent`` when the exponent is not a
number; a row about a term that does not exist is left out.  The rules
the template adds itself (``wiring.POWER``): ``E**(I*pi*c*s)`` is a root of
unity or on the unit circle (``core.ipi_rules``), ``b**(p/q)`` for a
positive rational ``b`` that is not a ``q``-th power is irrational,
``b**e`` for ``b`` in ``I, -1, -I`` and a numeric ``e`` has the facts of
its value (``core._unit_power_units``).  ``(c0 + c1*u)**e`` for a
negative integer ``e`` has no rule of its own since #315 step 2 (it
answered nothing on the stream, gate2 or SymPy's assumption tests).
"""
from __future__ import annotations

from sympy import Abs, E, Equivalent, I, Pow, Q, exp
from sympy.assumptions.assume import Predicate

from ._rows import base, exponent, f, for_all, log_base, number

RULES = (
    # --- sign ---

    # Positive base, real exponent: positive
    for_all((Pow,),
        (Q.positive(base) & Q.real(exponent)) >> Q.positive(f(base, exponent))),

    # Extended positive base, positive exponent: extended positive
    for_all((Pow,),
        (Q.extended_positive(base) & Q.positive(exponent))
        >> Q.extended_positive(f(base, exponent))),

    # Extended positive base, real exponent: extended nonnegative
    #     a finite exponent: 1**oo and 1**-oo are nan
    for_all((Pow,),
        (Q.extended_positive(base) & Q.real(exponent))
        >> Q.extended_nonnegative(f(base, exponent))),

    # Extended nonnegative base, nonnegative exponent: extended nonnegative
    for_all((Pow,),
        (Q.extended_nonnegative(base) & Q.nonnegative(exponent))
        >> Q.extended_nonnegative(f(base, exponent))),

    # Extended nonnegative base, extended real exponent: not extended negative
    for_all((Pow,),
        (Q.extended_nonnegative(base) & Q.extended_real(exponent))
        >> ~Q.extended_negative(f(base, exponent))),

    # Even power of an extended real: not extended negative
    for_all((Pow,),
        (Q.extended_real(base) & Q.even(exponent)) >> ~Q.extended_negative(f(base, exponent))),

    # Even power of a nonzero number: positive
    for_all((Pow,),
        (Q.nonzero(base) & Q.even(exponent)) >> Q.positive(f(base, exponent))),

    # Nonnegative even power of an extended negative: extended positive
    #     (-oo)**(-2) == 0, so the extended version needs a nonnegative exponent
    for_all((Pow,),
        (Q.extended_negative(base) & Q.even(exponent) & Q.nonnegative(exponent))
        >> Q.extended_positive(f(base, exponent))),

    # Odd power of a negative number: negative
    for_all((Pow,),
        (Q.negative(base) & Q.odd(exponent)) >> Q.negative(f(base, exponent))),

    # Odd power of an extended negative: extended nonpositive
    for_all((Pow,),
        (Q.extended_negative(base) & Q.odd(exponent))
        >> Q.extended_nonpositive(f(base, exponent))),

    # Odd power of an extended nonpositive: not extended positive
    for_all((Pow,),
        (Q.extended_nonpositive(base) & Q.odd(exponent))
        >> ~Q.extended_positive(f(base, exponent))),

    # Positive odd power of a real base: the base is positive
    for_all((Pow,),
        (Q.positive(f(base, exponent)) & Q.real(base) & Q.odd(exponent)) >> Q.positive(base)),

    # Negative odd power of a real base: the base is negative
    for_all((Pow,),
        (Q.negative(f(base, exponent)) & Q.real(base) & Q.odd(exponent)) >> Q.negative(base)),

    # --- zero base, zero exponent (b**0 == 1, also for zoo and nan) ---

    # Zero to an extended positive power: zero
    for_all((Pow,),
        (Q.zero(base) & Q.extended_positive(exponent)) >> Q.zero(f(base, exponent))),

    # Zero to an extended nonpositive power: not zero
    for_all((Pow,),
        (Q.zero(base) & Q.extended_nonpositive(exponent)) >> ~Q.zero(f(base, exponent))),

    # Zero to an extended negative power: infinite
    for_all((Pow,),
        (Q.zero(base) & Q.extended_negative(exponent)) >> Q.infinite(f(base, exponent))),

    # Zero exponent: positive
    for_all((Pow,),
        Q.zero(exponent) >> Q.positive(f(base, exponent))),

    # Zero exponent, finite base: odd
    #     SymPy leaves oo**0.0 unevaluated and calls it non-integer
    for_all((Pow,),
        (Q.zero(exponent) & Q.finite(base)) >> Q.odd(f(base, exponent))),

    # --- zero / nonzero / finite / infinite ---

    # Finite power of a finite nonzero commutative base: nonzero
    #     (a commutative base: A**2 == 0 for a nilpotent A)
    for_all((Pow,),
        (~Q.zero(base) & Q.commutative(base) & Q.finite(base) & Q.finite(exponent))
        >> ~Q.zero(f(base, exponent))),

    # Infinite base, negative exponent: zero
    for_all((Pow,),
        (Q.infinite(base) & Q.negative(exponent)) >> Q.zero(f(base, exponent))),

    # Nonnegative power of a nonzero commutative base: nonzero
    for_all((Pow,),
        (~Q.zero(base) & Q.commutative(base) & Q.nonnegative(exponent))
        >> ~Q.zero(f(base, exponent))),

    # Finite base, negative exponent: nonzero
    for_all((Pow,),
        (Q.finite(base) & Q.negative(exponent)) >> ~Q.zero(f(base, exponent))),

    # Finite base, finite nonnegative exponent: finite
    for_all((Pow,),
        (Q.finite(base) & Q.finite(exponent) & Q.nonnegative(exponent))
        >> Q.finite(f(base, exponent))),

    # Finite nonzero base, finite exponent: finite
    for_all((Pow,),
        (Q.finite(base) & Q.finite(exponent) & ~Q.zero(base)) >> Q.finite(f(base, exponent))),

    # Infinite base, positive exponent: infinite
    for_all((Pow,),
        (Q.infinite(base) & Q.positive(exponent)) >> Q.infinite(f(base, exponent))),

    # --- integer / rational ---

    # Nonnegative integer power of an integer: integer
    for_all((Pow,),
        (Q.integer(base) & Q.integer(exponent) & Q.nonnegative(exponent))
        >> Q.integer(f(base, exponent))),

    # Positive integer power of an even number: even
    for_all((Pow,),
        (Q.even(base) & Q.integer(exponent) & Q.positive(exponent)) >> Q.even(f(base, exponent))),

    # Nonnegative integer power of an odd number: odd
    for_all((Pow,),
        (Q.odd(base) & Q.integer(exponent) & Q.nonnegative(exponent))
        >> Q.odd(f(base, exponent))),

    # Positive rational power of a rational non-integer: not an integer
    for_all((Pow,),
        (Q.rational(base) & ~Q.integer(base) & Q.rational(exponent) & Q.positive(exponent))
        >> ~Q.integer(f(base, exponent))),

    # Nonnegative integer power of a rational: rational
    for_all((Pow,),
        (Q.rational(base) & Q.integer(exponent) & Q.nonnegative(exponent))
        >> Q.rational(f(base, exponent))),

    # Integer power of a nonzero rational: rational
    for_all((Pow,),
        (Q.rational(base) & Q.integer(exponent) & ~Q.zero(base)) >> Q.rational(f(base, exponent))),

    # --- extended real / imaginary ---

    # Integer power of an extended nonzero base: extended real
    for_all((Pow,),
        (Q.extended_nonzero(base) & Q.integer(exponent)) >> Q.extended_real(f(base, exponent))),

    # Nonnegative integer power of an extended real: extended real
    for_all((Pow,),
        (Q.extended_real(base) & Q.integer(exponent) & Q.nonnegative(exponent))
        >> Q.extended_real(f(base, exponent))),

    # Real non-integer power of a negative number: not extended real
    for_all((Pow,),
        (Q.negative(base) & Q.real(exponent) & ~Q.integer(exponent))
        >> ~Q.extended_real(f(base, exponent))),

    # Integer power of an extended real: not imaginary
    for_all((Pow,),
        (Q.extended_real(base) & Q.integer(exponent)) >> ~Q.imaginary(f(base, exponent))),

    # Extended real irrational power of an extended real: not imaginary
    for_all((Pow,),
        (Q.extended_real(base) & Q.extended_real(exponent) & ~Q.rational(exponent))
        >> ~Q.imaginary(f(base, exponent))),

    # Extended real power of a positive number: not imaginary
    for_all((Pow,),
        (Q.positive(base) & Q.extended_real(exponent)) >> ~Q.imaginary(f(base, exponent))),

    # Even power of an imaginary number: nonzero
    for_all((Pow,),
        (Q.imaginary(base) & Q.even(exponent)) >> Q.nonzero(f(base, exponent))),

    # Odd power of an imaginary number: imaginary
    for_all((Pow,),
        (Q.imaginary(base) & Q.odd(exponent)) >> Q.imaginary(f(base, exponent))),

    # --- complex ---

    # Complex power of a nonzero complex number: complex
    for_all((Pow,),
        (Q.complex(base) & Q.complex(exponent) & ~Q.zero(base)) >> Q.complex(f(base, exponent))),

    # Nonnegative power of a complex number: complex
    for_all((Pow,),
        (Q.complex(base) & Q.complex(exponent) & Q.nonnegative(exponent))
        >> Q.complex(f(base, exponent))),

    # --- prime ---

    # Prime power of an integer: not prime
    for_all((Pow,),
        (Q.integer(base) & Q.prime(exponent)) >> ~Q.prime(f(base, exponent))),

    # Positive even power of an integer: not prime
    for_all((Pow,),
        (Q.integer(base) & Q.even(exponent) & Q.positive(exponent))
        >> ~Q.prime(f(base, exponent))),

    # --- algebraic ---

    # Rational power of a nonzero algebraic number: algebraic
    for_all((Pow,),
        (Q.algebraic(base) & Q.rational(exponent) & ~Q.zero(base))
        >> Q.algebraic(f(base, exponent))),

    # Positive rational power of an algebraic number: algebraic
    for_all((Pow,),
        (Q.algebraic(base) & Q.rational(exponent) & Q.positive(exponent))
        >> Q.algebraic(f(base, exponent))),

    # Nonzero rational power of a transcendental number: not algebraic
    for_all((Pow,),
        (Q.transcendental(base) & Q.rational(exponent) & ~Q.zero(exponent))
        >> ~Q.algebraic(f(base, exponent))),

    # --- polar / commutative ---

    # Power of a polar number: polar
    for_all((Pow,),
        Predicate('polar')(base) >> Predicate('polar')(f(base, exponent))),

    # Commutative base and exponent: commutative
    #     not commutative(b**e) -> commutative(b) (A**2 is 1 for a
    #     reflection A, A**0 == 1) or -> commutative(e) (1**A == 1); see #47
    #     and the row for 1/b below
    for_all((Pow,),
        (Q.commutative(base) & Q.commutative(exponent)) >> Q.commutative(f(base, exponent))),

    # --- powers of E ---

    # E to an extended real power: extended real
    for_all((Pow,),
        Q.extended_real(exponent) >> Q.extended_real(f(E, exponent))),

    # E to an extended real power: extended nonnegative
    for_all((Pow,),
        Q.extended_real(exponent) >> Q.extended_nonnegative(f(E, exponent))),

    # E to a real power: positive
    for_all((Pow,),
        Q.real(exponent) >> Q.positive(f(E, exponent))),

    # E to a complex power: complex
    for_all((Pow,),
        Q.complex(exponent) >> Q.complex(f(E, exponent))),

    # E to an extended negative power: complex
    for_all((Pow,),
        Q.extended_negative(exponent) >> Q.complex(f(E, exponent))),

    # E to a finite power: finite
    for_all((Pow,),
        Q.finite(exponent) >> Q.finite(f(E, exponent))),

    # E to a finite power: nonzero
    for_all((Pow,),
        Q.finite(exponent) >> ~Q.zero(f(E, exponent))),

    # E to a nonzero algebraic power: transcendental
    for_all((Pow,),
        (Q.algebraic(exponent) & ~Q.zero(exponent)) >> Q.transcendental(f(E, exponent))),

    # E to the power -oo: zero
    for_all((Pow,),
        (Q.infinite(exponent) & Q.extended_negative(exponent)) >> Q.zero(f(E, exponent))),

    # --- special bases and exponents ---

    # A power of a symbol to itself
    for_all((Pow,),
        Q.extended_nonnegative(base) >> Q.extended_positive(f(base, base))),

    # The first power is the base
    for_all((Pow,),
        Q.eq(f(base, 1), base)),

    # Integer power of a composite: not prime
    #     a power of a composite is 1, a fraction or composite
    for_all((Pow,),
        (Q.composite(base) & Q.integer(exponent)) >> ~Q.prime(f(base, exponent))),

    # Imaginary algebraic power of a nonzero algebraic number: not imaginary
    #     for algebraic b = r*exp(I*phi) != 0 and algebraic e = I*t, b**e is
    #     exp(-t*phi)*exp(I*t*log(r)) with r algebraic; t*log(r) in pi*Q with
    #     t algebraic nonzero forces log(r)/(I*pi) algebraic, hence rational
    #     (Gelfond-Schneider), hence r == 1.  So b**e is never imaginary, and
    #     it is real iff |b| == 1 (then it is positive).
    for_all((Pow,),
        (Q.algebraic(base) & ~Q.zero(base) & Q.imaginary(exponent) & Q.algebraic(exponent))
        >> ~Q.imaginary(f(base, exponent))),

    # Imaginary algebraic power of an algebraic real number of absolute value not 1: not real
    #     (the row above, for a real b with |b| not in {0, 1})
    for_all((Pow,),
        (Q.irrational(base) & Q.algebraic(base) & Q.imaginary(exponent)
         & Q.algebraic(exponent)) >> ~Q.extended_real(f(base, exponent)),
        (Q.noninteger(base) & Q.algebraic(base) & Q.imaginary(exponent)
         & Q.algebraic(exponent)) >> ~Q.extended_real(f(base, exponent)),
        (Q.prime(base) & Q.algebraic(base) & Q.imaginary(exponent)
         & Q.algebraic(exponent)) >> ~Q.extended_real(f(base, exponent)),
        (Q.composite(base) & Q.algebraic(base) & Q.imaginary(exponent)
         & Q.algebraic(exponent)) >> ~Q.extended_real(f(base, exponent))),

    # Imaginary power of I, -1 and -I: positive
    #     exp(I*pi*theta)**(I*t) == exp(-pi*theta*t)
    for_all((Pow,),
        Q.imaginary(exponent) >> Q.positive(f(I, exponent)),
        Q.imaginary(exponent) >> Q.positive(f(-1, exponent)),
        Q.imaginary(exponent) >> Q.positive(f(-I, exponent))),

    # Imaginary power of exp of an imaginary number: positive
    #     (exp(u))**e == exp(e*(u - 2*pi*I*k)) is positive for imaginary u, e
    for_all((Pow,),
        (Q.imaginary(log_base) & Q.imaginary(exponent))
        >> Q.positive(f(exp(log_base), exponent))),

    # Negative integer power of an integer other than 0, 1 and -1: not an integer
    #     a fraction (0 gives zoo)
    for_all((Pow,),
        (Q.integer(base) & Q.integer(exponent) & Q.negative(exponent) & Q.ne(base, 1)
         & Q.ne(base, -1)) >> ~Q.integer(f(base, exponent))),

    # An integer negative integer power of an integer is 1 or -1
    #     so its base is +-1 (0**-k is zoo)
    for_all((Pow,),
        (Q.integer(base) & Q.integer(exponent) & Q.negative(exponent)
         & Q.integer(f(base, exponent))) >> Q.odd(f(base, exponent)),
        (Q.integer(base) & Q.integer(exponent) & Q.negative(exponent)
         & Q.integer(f(base, exponent))) >> ~Q.prime(f(base, exponent)),
        (Q.integer(base) & Q.integer(exponent) & Q.negative(exponent)
         & Q.integer(f(base, exponent))) >> ~Q.composite(f(base, exponent)),
        (Q.integer(base) & Q.integer(exponent) & Q.negative(exponent)
         & Q.integer(f(base, exponent))) >> Q.odd(base)),

    # Negative integer power of a prime or composite: not an integer
    for_all((Pow,),
        (Q.prime(base) & Q.integer(exponent) & Q.negative(exponent))
        >> ~Q.integer(f(base, exponent)),
        (Q.composite(base) & Q.integer(exponent) & Q.negative(exponent))
        >> ~Q.integer(f(base, exponent))),

    # Rational power of a real base: imaginary iff a negative base to half an odd integer
    for_all((Pow,),
        (Q.extended_real(base) & Q.rational(exponent) & ~Q.integer(2*exponent))
        >> ~Q.imaginary(f(base, exponent)),
        (Q.negative(base) & Q.rational(exponent) & Q.integer(2*exponent)
         & ~Q.integer(exponent)) >> Q.imaginary(f(base, exponent))),

    # A power to half an odd integer of a real base is imaginary iff the base is negative
    #     b**(k/2) for real b
    for_all((Pow,),
        (Q.extended_real(base) & Q.rational(number) & Q.integer(2*number)
         & ~Q.integer(number))
        >> Equivalent(Q.imaginary(f(base, number)), Q.negative(base))),

    # A power to half an odd integer of a real base is not extended negative
    for_all((Pow,),
        (Q.extended_real(base) & Q.rational(number) & Q.integer(2*number)
         & ~Q.integer(number)) >> ~Q.extended_negative(f(base, number))),

    # A power to another non-integer rational of a real base is not imaginary
    for_all((Pow,),
        (Q.extended_real(base) & Q.rational(number) & ~Q.integer(2*number)
         & ~Q.integer(number)) >> ~Q.imaginary(f(base, number))),

    # A root 1/q of a non-real base is not real
    #     (b**(1/q))**q == b: a non-real base gives a non-real root
    for_all((Pow,),
        (~Q.extended_real(base) & Q.integer(1/number) & Q.positive(number)
         & ~Q.integer(number)) >> ~Q.extended_real(f(base, number))),

    # A power -1/q of a finite non-real base is not real
    #     likewise for 1/b**(1/q), but zoo**(-1/2) == 0 is real
    for_all((Pow,),
        (~Q.extended_real(base) & Q.finite(base) & Q.integer(1/number) & Q.negative(number)
         & ~Q.integer(number)) >> ~Q.extended_real(f(base, number))),

    # The inverse of an irrational number is irrational
    #     1/b is rational iff b is (nonzero) rational
    for_all((Pow,),
        Q.irrational(base) >> Q.irrational(f(base, -1))),

    # The inverse of a nonzero complex number has a commutative base
    #     b is the inverse of a nonzero number 1/b
    for_all((Pow,),
        (Q.complex(f(base, -1)) & ~Q.zero(f(base, -1))) >> Q.commutative(base)),

    # An integer power of -1 is odd
    for_all((Pow,),
        Q.integer(exponent) >> Q.odd(f(-1, exponent))),

    # A complex power of 1 is 1
    #     1**e == exp(e*log(1)) == 1 for complex e (1**oo is nan)
    for_all((Pow,),
        Q.complex(exponent) >> (
            Q.positive(f(1, exponent)) & Q.odd(f(1, exponent)) & ~Q.prime(f(1, exponent))
            & ~Q.composite(f(1, exponent)))),

    # The inverse of a number is imaginary only if the number is
    #     1/b is imaginary iff b is (1/0 == zoo, 1/oo == 0)
    for_all((Pow,),
        Q.imaginary(f(base, -1)) >> Q.imaginary(base)),

    # A power 2 mod 4 of an imaginary number is negative
    #     (I*t)**e == I**e * t**e for real t != 0: I**e is -1 or 1
    for_all((Pow,),
        (Q.imaginary(base) & Q.odd(number/2)) >> Q.negative(f(base, number))),

    # A power 0 mod 4 of an imaginary number is positive
    for_all((Pow,),
        (Q.imaginary(base) & Q.even(number/2)) >> Q.positive(f(base, number))),

    # A negative power of an integer other than 0, 1 and -1 is not an integer
    #     |b|**e < 1 for negative e
    for_all((Pow,),
        (Q.integer(number) & Q.ge(Abs(number), 2) & Q.negative(exponent))
        >> ~Q.integer(f(number, exponent))),

    # Gelfond-Schneider for a constant base: algebraic iff the exponent is rational
    #     an algebraic power of an algebraic number b other than 0 and 1 is
    #     algebraic iff the exponent is rational; an algebraic b != 0 is not 1 when it is no
    #     integer, negative, prime or composite
    for_all((Pow,),
        (Q.algebraic(number) & ~Q.zero(number) & ~Q.integer(number) & Q.algebraic(exponent))
        >> Equivalent(Q.algebraic(f(number, exponent)), Q.rational(exponent)),
        (Q.algebraic(number) & ~Q.zero(number) & Q.negative(number) & Q.algebraic(exponent))
        >> Equivalent(Q.algebraic(f(number, exponent)), Q.rational(exponent)),
        (Q.algebraic(number) & ~Q.zero(number) & Q.prime(number) & Q.algebraic(exponent))
        >> Equivalent(Q.algebraic(f(number, exponent)), Q.rational(exponent)),
        (Q.algebraic(number) & ~Q.zero(number) & Q.composite(number) & Q.algebraic(exponent))
        >> Equivalent(Q.algebraic(f(number, exponent)), Q.rational(exponent))),

    # A power of a number of absolute value above 1 to an extended negative exponent is finite
    #     exact comparisons of a number with 1 (no assumptions involved)
    for_all((Pow,),
        (Q.finite(number) & Q.gt(Abs(number), 1) & Q.extended_negative(exponent))
        >> Q.finite(f(number, exponent))),

    # A power of a number of absolute value above 1 to the power -oo is zero
    for_all((Pow,),
        (Q.finite(number) & Q.gt(Abs(number), 1) & Q.negative_infinite(exponent))
        >> Q.zero(f(number, exponent))),

    # A power of a number of absolute value above 1 to the power oo is infinite
    for_all((Pow,),
        (Q.finite(number) & Q.gt(Abs(number), 1) & Q.positive_infinite(exponent))
        >> Q.infinite(f(number, exponent))),

    # A power of a number of absolute value below 1 to an extended positive exponent is finite
    for_all((Pow,),
        (~Q.zero(number) & Q.lt(Abs(number), 1) & Q.extended_positive(exponent))
        >> Q.finite(f(number, exponent))),

    # A power of a number of absolute value below 1 to the power oo is zero
    for_all((Pow,),
        (~Q.zero(number) & Q.lt(Abs(number), 1) & Q.positive_infinite(exponent))
        >> Q.zero(f(number, exponent))),

    # A power of a number of absolute value below 1 to the power -oo is infinite
    #     disagrees with SymPy for negative b ((-1/2)**(-oo) == nan); kept as is
    #     pending an owner decision, see tests/test_p6_review.py (issue #97 P6 review)
    for_all((Pow,),
        (~Q.zero(number) & Q.lt(Abs(number), 1) & Q.negative_infinite(exponent))
        >> Q.infinite(f(number, exponent))),

    # A power 2 or more of an integer 2 or more is composite
    for_all((Pow,),
        (Q.prime(base) & Q.integer(number) & Q.ge(number, 2)) >> Q.composite(f(base, number)),
        (Q.composite(base) & Q.integer(number) & Q.ge(number, 2))
        >> Q.composite(f(base, number)),
        (Q.even(base) & Q.positive(base) & Q.integer(number) & Q.ge(number, 2))
        >> Q.composite(f(base, number))),

    # A positive integer power of an integer 2 or more is prime or composite
    #     b**e >= 2 for an integer b >= 2 and a positive integer e (composite
    #     with the row below: 3 formulas, not 3**2 for both premises >= 2)
    for_all((Pow,),
        (Q.prime(base) & Q.integer(exponent) & Q.positive(exponent))
        >> (Q.prime(f(base, exponent)) | Q.composite(f(base, exponent))),
        (Q.composite(base) & Q.integer(exponent) & Q.positive(exponent))
        >> (Q.prime(f(base, exponent)) | Q.composite(f(base, exponent))),
        (Q.even(base) & Q.positive(base) & Q.integer(exponent) & Q.positive(exponent))
        >> (Q.prime(f(base, exponent)) | Q.composite(f(base, exponent)))),

    # A power 2 or more of an integer is not prime
    #     0, +-1, a negative number or composite
    for_all((Pow,),
        (Q.integer(base) & Q.prime(exponent)) >> ~Q.prime(f(base, exponent)),
        (Q.integer(base) & Q.composite(exponent)) >> ~Q.prime(f(base, exponent)),
        (Q.integer(base) & Q.even(exponent) & Q.positive(exponent))
        >> ~Q.prime(f(base, exponent))),

    # A positive even power of an integer -2 or less is composite
    for_all((Pow,),
        (Q.integer(base) & Q.negative(base) & Q.lt(base, -1) & Q.even(exponent)
         & Q.positive(exponent)) >> Q.composite(f(base, exponent))),

    # An algebraic irrational power of an algebraic number other than 0 and 1 is not algebraic
    #     Gelfond-Schneider; an algebraic b is not 0 or 1 when it is irrational,
    #     no integer, negative, prime or composite
    for_all((Pow,),
        (Q.irrational(base) & Q.algebraic(base) & Q.algebraic(number) & ~Q.rational(number))
        >> ~Q.algebraic(f(base, number)),
        (Q.noninteger(base) & Q.algebraic(base) & Q.algebraic(number) & ~Q.rational(number))
        >> ~Q.algebraic(f(base, number)),
        (Q.negative(base) & Q.algebraic(base) & Q.algebraic(number) & ~Q.rational(number))
        >> ~Q.algebraic(f(base, number)),
        (Q.prime(base) & Q.algebraic(base) & Q.algebraic(number) & ~Q.rational(number))
        >> ~Q.algebraic(f(base, number)),
        (Q.composite(base) & Q.algebraic(base) & Q.algebraic(number) & ~Q.rational(number))
        >> ~Q.algebraic(f(base, number))),

    # Gelfond-Schneider, for a symbolic base and exponent
    #     b not in {0, 1} says b != 0, b - 1 != 0
    for_all((Pow,),
        (Q.algebraic(base) & ~Q.zero(base) & Q.ne(base, 1) & Q.algebraic(exponent)
         & ~Q.rational(exponent)) >> ~Q.algebraic(f(base, exponent))),
)
