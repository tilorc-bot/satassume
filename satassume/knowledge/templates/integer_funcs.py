"""``floor`` and ``ceiling``, ``factorial``, and ``Mod``.

The rows of ``RoundFunction``, the base class of ``floor`` and
``ceiling``, hold for both (the registry walks the MRO).  Values follow
SymPy's conventions: ``floor(+-oo) == +-oo``, ``floor(zoo) == zoo``, and
``floor`` and ``ceiling`` of a non-real argument round each part
(``floor(1 + I/2) == 1``); ``factorial(n) == zoo`` for a negative integer
``n``, ``factorial(oo) == oo``, and ``factorial(x) == gamma(x + 1)`` off
the integers.  ``Mod(p, q) == p - q*floor(p/q)`` for real ``p`` and real
``q != 0``; ``Mod(p, 0)`` raises, an infinite argument gives nan, and
non-real arguments get no claim.
"""
from __future__ import annotations

from sympy import Equivalent, Mod, Q, ceiling, factorial, floor
from sympy.functions.elementary.integers import RoundFunction

from ._rows import argument, closed, dividend, divisor, f, for_all

RULES = (
    # Finite only at a finite argument
    for_all((RoundFunction,),
        Equivalent(Q.finite(f(argument)), Q.finite(argument))),

    # Extended real and complex
    #     each part is rounded: floor(1 + I/2) == 1
    for_all((RoundFunction,),
        closed(f, Q.extended_real) & closed(f, Q.complex)),

    # Integer where real
    #     a real value is an integer (floor(1 + I/2) == 1 is real; floor(oo)
    #     == oo is not); a non-real argument may give an integer
    for_all((RoundFunction,),
        Q.real(f(argument)) >> Q.integer(f(argument))),

    # The argument at an integer
    #     floor(n) == ceiling(n) == n: the same parity and sign
    for_all((RoundFunction,),
        Q.integer(argument) >> (
            Equivalent(Q.even(f(argument)), Q.even(argument))
            & Equivalent(Q.positive(f(argument)), Q.positive(argument))
            & Equivalent(Q.negative(f(argument)), Q.negative(argument)))),

    # Rounds down
    #     floor(x) <= x, and floor(x) >= 0 for x >= 0
    for_all((floor,),
        closed(f, Q.negative) & closed(f, Q.extended_negative)
        & closed(f, Q.nonnegative) & closed(f, Q.extended_nonnegative)),

    # Rounds up
    #     ceiling(x) >= x, and ceiling(x) <= 0 for x <= 0
    for_all((ceiling,),
        closed(f, Q.positive) & closed(f, Q.extended_positive)
        & closed(f, Q.nonpositive) & closed(f, Q.extended_nonpositive)),

    # Integer at a natural number
    #     n! == 1*2*...*n, and 0! == 1
    for_all((factorial,),
        (Q.integer(argument) & Q.nonnegative(argument)) >> Q.integer(f(argument))),

    # Positive on the nonnegatives
    #     factorial(x) == gamma(x + 1) > 0 for x >= 0
    for_all((factorial,),
        Q.nonnegative(argument) >> Q.positive(f(argument))),

    # Odd at 0
    #     0! == 1
    for_all((factorial,),
        Q.zero(argument) >> Q.odd(f(argument))),

    # Composite at a composite
    #     n! for a composite n >= 4 has the factor 2 and is larger than 2
    for_all((factorial,),
        closed(f, Q.composite)),

    # Even from 2 on
    #     n! has the factor 2 for an integer n >= 2, that is a prime or a
    #     composite (the rule base: an even positive number is one of them)
    for_all((factorial,),
        Q.prime(argument) >> Q.even(f(argument)),
        Q.composite(argument) >> Q.even(f(argument))),

    # Real and nonzero off the integers
    #     factorial(x) == gamma(x + 1), which has no zero and poles only at
    #     the integers x < 0
    for_all((factorial,),
        (Q.noninteger(argument) & Q.finite(argument)) >> (
            Q.real(f(argument)) & ~Q.zero(f(argument)))),

    # Pole at a negative integer
    #     the value is zoo
    for_all((factorial,),
        (Q.integer(argument) & Q.negative(argument)) >> (
            Q.infinite(f(argument)) & ~Q.extended_real(f(argument)))),

    # Integer and rational at a nonzero divisor
    #     Mod(p, q) == p - q*floor(p/q), and floor(p/q) is an integer
    for_all((Mod,),
        (Q.integer(dividend) & Q.integer(divisor) & ~Q.zero(divisor))
        >> Q.integer(f(dividend, divisor)),
        (Q.rational(dividend) & Q.rational(divisor) & ~Q.zero(divisor))
        >> Q.rational(f(dividend, divisor))),

    # The sign of the divisor
    #     Mod(p, q) is in [0, q) for q > 0 and in (q, 0] for q < 0
    for_all((Mod,),
        (Q.real(dividend) & Q.positive(divisor)) >> Q.nonnegative(f(dividend, divisor)),
        (Q.real(dividend) & Q.negative(divisor)) >> Q.nonpositive(f(dividend, divisor))),
)
