"""``Abs``, ``re``, ``im``, ``sign`` and ``conjugate``.

Values follow SymPy's conventions: ``Abs(zoo) == Abs(oo*I) == oo``,
``sign(+-oo) == +-1``, ``sign(oo*I) == I``.  ``re`` and ``im`` are not
extended real for every argument: ``re(zoo) == im(zoo) == nan``.  The
vocabulary cannot tell ``zoo`` from ``oo*I`` (``re(oo*I) == 0``) or ``oo +
oo*I``, so an infinite non-real argument gets no claim; a finite argument
gives a real part, an extended real one gives itself (``re``) or zero
(``im``).  ``sign(zoo)`` and ``conjugate(zoo)`` are left unevaluated; the
rows claim that ``sign`` is a number for every argument.  ``re`` and ``im``
of ``floor(y)`` and ``ceiling(y)`` are not rows
(``functions.parts_of_round_templates``, registered after these by
``wiring.AFTER_ROWS``).
"""
from __future__ import annotations

from sympy import Abs, Equivalent, Q, conjugate, im, re, sign

from ._rows import argument, closed, f, for_all

RULES = (
    # Real at a finite argument
    #     a finite argument is a complex number: its modulus and its parts are real
    for_all((Abs, re, im),
        Q.finite(argument) >> Q.real(f(argument))),

    # Algebraic at an algebraic argument
    #     the algebraic numbers are a field closed under conjugation:
    #     Abs(a) == sqrt(a*conjugate(a)), re(a) == (a + conjugate(a))/2,
    #     im(a) == (a - conjugate(a))/(2*I), sign(a) == a/Abs(a) or 0
    for_all((Abs, re, im, sign),
        closed(f, Q.algebraic)),

    # Zero only at 0
    for_all((Abs, sign),
        Equivalent(Q.zero(f(argument)), Q.zero(argument))),

    # Nonnegative
    #     Abs(zoo) == Abs(oo*I) == oo
    for_all((Abs,),
        Q.extended_nonnegative(f(argument))),

    # Infinite at infinity
    #     Abs(+-oo) == Abs(zoo) == oo
    for_all((Abs,),
        closed(f, Q.infinite)),

    # Plus or minus the argument on the extended reals
    #     Abs(x) is x or -x: both or neither are rational, even, odd or
    #     algebraic
    for_all((Abs,),
        Q.extended_real(argument) >> (
            Equivalent(Q.rational(f(argument)), Q.rational(argument))
            & Equivalent(Q.even(f(argument)), Q.even(argument))
            & Equivalent(Q.odd(f(argument)), Q.odd(argument))
            & Equivalent(Q.algebraic(f(argument)), Q.algebraic(argument)))),

    # The argument on the nonnegatives
    #     Abs(x) == x for x >= 0
    for_all((Abs,),
        Q.extended_nonnegative(argument) >> (
            Equivalent(Q.prime(f(argument)), Q.prime(argument))
            & Equivalent(Q.composite(f(argument)), Q.composite(argument)))),

    # The argument on the extended reals
    #     re(x) == x; zero and integer follow from the sign and the parity
    for_all((re,),
        Q.extended_real(argument) >> (
            Equivalent(Q.extended_positive(f(argument)), Q.extended_positive(argument))
            & Equivalent(Q.extended_negative(f(argument)), Q.extended_negative(argument))
            & Equivalent(Q.rational(f(argument)), Q.rational(argument))
            & Equivalent(Q.even(f(argument)), Q.even(argument))
            & Equivalent(Q.odd(f(argument)), Q.odd(argument))
            & Equivalent(Q.algebraic(f(argument)), Q.algebraic(argument))
            & Equivalent(Q.finite(f(argument)), Q.finite(argument))
            & Equivalent(Q.prime(f(argument)), Q.prime(argument))
            & Equivalent(Q.composite(f(argument)), Q.composite(argument)))),

    # Zero on the imaginary axis
    #     re(I*t) == 0
    for_all((re,),
        Q.imaginary(argument) >> Q.zero(f(argument))),

    # Zero on the extended reals
    #     im(oo) == 0
    for_all((im,),
        Q.extended_real(argument) >> Q.zero(f(argument))),

    # Nonzero off the real line
    #     a finite non-real argument has a nonzero imaginary part
    for_all((im,),
        (Q.finite(argument) & ~Q.extended_real(argument)) >> ~Q.zero(f(argument))),

    # A number
    #     0 or a point of the unit circle; sign(zoo) is left unevaluated
    for_all((sign,),
        Q.complex(f(argument))),

    # Sign of the argument
    #     sign(x) is 1 for x > 0 (oo too), -1 for x < 0, and 0 at 0;
    #     negative follows from odd and positive
    for_all((sign,),
        (Q.extended_real(argument) & ~Q.zero(argument)) >> Q.odd(f(argument)),
        Q.extended_real(argument) >> Equivalent(
            Q.positive(f(argument)), Q.extended_positive(argument))),

    # Imaginary on the imaginary axis
    #     sign(I*t) == I*sign(t)
    for_all((sign,),
        closed(f, Q.imaginary)),

    # Invariant under conjugation
    #     the rule base derives the rest (zero, extended_real, integer,
    #     real, the sign predicates, nonzero, infinite, irrational,
    #     transcendental, hermitian, antihermitian...; commutative always holds)
    for_all((conjugate,),
        Equivalent(Q.finite(f(argument)), Q.finite(argument)),
        Equivalent(Q.extended_positive(f(argument)), Q.extended_positive(argument)),
        Equivalent(Q.extended_negative(f(argument)), Q.extended_negative(argument)),
        Equivalent(Q.rational(f(argument)), Q.rational(argument)),
        Equivalent(Q.even(f(argument)), Q.even(argument)),
        Equivalent(Q.odd(f(argument)), Q.odd(argument)),
        Equivalent(Q.algebraic(f(argument)), Q.algebraic(argument)),
        Equivalent(Q.complex(f(argument)), Q.complex(argument)),
        Equivalent(Q.imaginary(f(argument)), Q.imaginary(argument)),
        Equivalent(Q.prime(f(argument)), Q.prime(argument)),
        Equivalent(Q.composite(f(argument)), Q.composite(argument))),
)
