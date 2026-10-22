"""``floor`` and ``ceiling``, and ``factorial``.

The rows of ``RoundFunction``, the base class of ``floor`` and
``ceiling``, hold for both (the registry walks the MRO).  Values follow
SymPy's conventions: ``floor(+-oo) == +-oo``, ``floor(zoo) == zoo``, and
``floor`` and ``ceiling`` of a non-real argument round each part
(``floor(1 + I/2) == 1``); ``factorial(n) == zoo`` for a negative integer
``n``, ``factorial(oo) == oo``, and ``factorial(x) == gamma(x + 1)`` off
the integers.
"""
from __future__ import annotations

from sympy import Equivalent, Q, ceiling, factorial, floor
from sympy.functions.elementary.integers import RoundFunction

from ._rows import closed, f, for_all, x

RULES = (
    # Finite only at a finite argument
    for_all((RoundFunction,),
        Equivalent(Q.finite(f(x)), Q.finite(x))),

    # Extended real and complex
    #     each part is rounded: floor(1 + I/2) == 1
    for_all((RoundFunction,),
        closed(f, Q.extended_real) & closed(f, Q.complex)),

    # Integer where real
    #     a real value is an integer (floor(1 + I/2) == 1 is real; floor(oo)
    #     == oo is not); a non-real argument may give an integer
    for_all((RoundFunction,),
        Q.real(f(x)) >> Q.integer(f(x))),

    # The argument at an integer
    #     floor(n) == ceiling(n) == n: the same parity and sign
    for_all((RoundFunction,),
        Q.integer(x) >> (
            Equivalent(Q.even(f(x)), Q.even(x))
            & Equivalent(Q.positive(f(x)), Q.positive(x))
            & Equivalent(Q.negative(f(x)), Q.negative(x)))),

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
        (Q.integer(x) & Q.nonnegative(x)) >> Q.integer(f(x))),

    # Positive on the nonnegatives
    #     factorial(x) == gamma(x + 1) > 0 for x >= 0
    for_all((factorial,),
        Q.nonnegative(x) >> Q.positive(f(x))),

    # Odd at 0
    #     0! == 1
    for_all((factorial,),
        Q.zero(x) >> Q.odd(f(x))),

    # Composite at a composite
    #     n! for a composite n >= 4 has the factor 2 and is larger than 2
    for_all((factorial,),
        closed(f, Q.composite)),

    # Even from 2 on
    #     n! has the factor 2 for an integer n >= 2, that is a prime or a
    #     composite (the rule base: an even positive number is one of them)
    for_all((factorial,),
        Q.prime(x) >> Q.even(f(x)),
        Q.composite(x) >> Q.even(f(x))),

    # Real and nonzero off the integers
    #     factorial(x) == gamma(x + 1), which has no zero and poles only at
    #     the integers x < 0
    for_all((factorial,),
        (Q.noninteger(x) & Q.finite(x)) >> (Q.real(f(x)) & ~Q.zero(f(x)))),

    # Pole at a negative integer
    #     the value is zoo
    for_all((factorial,),
        (Q.integer(x) & Q.negative(x)) >> (Q.infinite(f(x)) & ~Q.extended_real(f(x)))),
)
