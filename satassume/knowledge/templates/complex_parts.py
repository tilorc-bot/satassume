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

from ._rows import closed, f, for_all, x

RULES = (
    # Real at a finite argument
    #     a finite argument is a complex number: its modulus and its parts are real
    for_all((Abs, re, im),
        Q.finite(x) >> Q.real(f(x))),

    # Algebraic at an algebraic argument
    #     the algebraic numbers are a field closed under conjugation:
    #     Abs(a) == sqrt(a*conjugate(a)), re(a) == (a + conjugate(a))/2,
    #     im(a) == (a - conjugate(a))/(2*I), sign(a) == a/Abs(a) or 0
    for_all((Abs, re, im, sign),
        closed(f, Q.algebraic)),

    # Zero only at 0
    for_all((Abs, sign),
        Equivalent(Q.zero(f(x)), Q.zero(x))),

    # Nonnegative
    #     Abs(zoo) == Abs(oo*I) == oo
    for_all((Abs,),
        Q.extended_nonnegative(f(x))),

    # Infinite at infinity
    #     Abs(+-oo) == Abs(zoo) == oo
    for_all((Abs,),
        closed(f, Q.infinite)),

    # Plus or minus the argument on the extended reals
    #     Abs(x) is x or -x: both or neither are rational, even, odd or
    #     algebraic
    for_all((Abs,),
        Q.extended_real(x) >> (
            Equivalent(Q.rational(f(x)), Q.rational(x))
            & Equivalent(Q.even(f(x)), Q.even(x))
            & Equivalent(Q.odd(f(x)), Q.odd(x))
            & Equivalent(Q.algebraic(f(x)), Q.algebraic(x)))),

    # The argument on the nonnegatives
    #     Abs(x) == x for x >= 0
    for_all((Abs,),
        Q.extended_nonnegative(x) >> (
            Equivalent(Q.prime(f(x)), Q.prime(x))
            & Equivalent(Q.composite(f(x)), Q.composite(x)))),

    # The argument on the extended reals
    #     re(x) == x; zero and integer follow from the sign and the parity
    for_all((re,),
        Q.extended_real(x) >> (
            Equivalent(Q.extended_positive(f(x)), Q.extended_positive(x))
            & Equivalent(Q.extended_negative(f(x)), Q.extended_negative(x))
            & Equivalent(Q.rational(f(x)), Q.rational(x))
            & Equivalent(Q.even(f(x)), Q.even(x))
            & Equivalent(Q.odd(f(x)), Q.odd(x))
            & Equivalent(Q.algebraic(f(x)), Q.algebraic(x))
            & Equivalent(Q.finite(f(x)), Q.finite(x))
            & Equivalent(Q.prime(f(x)), Q.prime(x))
            & Equivalent(Q.composite(f(x)), Q.composite(x)))),

    # Zero on the imaginary axis
    #     re(I*t) == 0
    for_all((re,),
        Q.imaginary(x) >> Q.zero(f(x))),

    # Zero on the extended reals
    #     im(oo) == 0
    for_all((im,),
        Q.extended_real(x) >> Q.zero(f(x))),

    # Nonzero off the real line
    #     a finite non-real argument has a nonzero imaginary part
    for_all((im,),
        (Q.finite(x) & ~Q.extended_real(x)) >> ~Q.zero(f(x))),

    # A number
    #     0 or a point of the unit circle; sign(zoo) is left unevaluated
    for_all((sign,),
        Q.complex(f(x))),

    # Sign of the argument
    #     sign(x) is 1 for x > 0 (oo too), -1 for x < 0, and 0 at 0;
    #     negative follows from odd and positive
    for_all((sign,),
        (Q.extended_real(x) & ~Q.zero(x)) >> Q.odd(f(x)),
        Q.extended_real(x) >> Equivalent(Q.positive(f(x)), Q.extended_positive(x))),

    # Imaginary on the imaginary axis
    #     sign(I*t) == I*sign(t)
    for_all((sign,),
        closed(f, Q.imaginary)),

    # Invariant under conjugation
    #     the rule base derives the rest (zero, extended_real, integer,
    #     real, the sign predicates, nonzero, infinite, irrational,
    #     transcendental, hermitian, antihermitian...; commutative always holds)
    for_all((conjugate,),
        Equivalent(Q.finite(f(x)), Q.finite(x)),
        Equivalent(Q.extended_positive(f(x)), Q.extended_positive(x)),
        Equivalent(Q.extended_negative(f(x)), Q.extended_negative(x)),
        Equivalent(Q.rational(f(x)), Q.rational(x)),
        Equivalent(Q.even(f(x)), Q.even(x)),
        Equivalent(Q.odd(f(x)), Q.odd(x)),
        Equivalent(Q.algebraic(f(x)), Q.algebraic(x)),
        Equivalent(Q.complex(f(x)), Q.complex(x)),
        Equivalent(Q.imaginary(f(x)), Q.imaginary(x)),
        Equivalent(Q.prime(f(x)), Q.prime(x)),
        Equivalent(Q.composite(f(x)), Q.composite(x))),
)
