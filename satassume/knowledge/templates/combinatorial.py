"""``factorial2``, ``subfactorial``, ``catalan``, ``andre``, ``partition``,
``genocchi``, ``RisingFactorial``, ``FallingFactorial`` and ``binomial``
(#180; ``factorial`` is in :mod:`.integer_funcs`).

These functions are defined on (nonnegative) integers, and SymPy leaves
them unevaluated or raises elsewhere (``factorial2(-4)``,
``partition(1/2)``); the rows state facts for the integer points and for
the real points where SymPy's extension is a theorem (``catalan(x) =
4**x*gamma(x + 1/2)/(sqrt(pi)*gamma(x + 2)) > 0`` for ``x >= 0``).
SymPy's values kept as they are: ``rf(x, 0) == ff(x, 0) == 1`` for every
``x`` but ``nan`` (``zoo`` gets no claim), ``binomial(x, 0) == 1``, and
``binomial(x, k) == 0`` for an integer ``k < 0``.  A node with a constant
integer argument (``genocchi(8, evaluate=False)``) also gets the facts of
its value, and ``genocchi(n)`` for an even ``n > 0`` those of the sign of
``G_n`` from the parity of ``n/2`` (``wiring.VALUE_AT_INTEGER`` and
``wiring.HALF_ARGUMENT``).  The polynomials ``genocchi(n, x)`` get no
facts.
"""
from __future__ import annotations

from sympy import (
    FallingFactorial, Q, RisingFactorial, andre, binomial, catalan, factorial2, genocchi,
    partition, subfactorial,
)

from ._rows import argument, f, for_all, size, start, total

RULES = (
    # Integer at a natural number
    #     C_n == binomial(2*n, n)/(n + 1), the number of alternating
    #     permutations, G_n == 2*(1 - 2**n)*B_n
    for_all((catalan, andre, genocchi),
        (Q.integer(argument) & Q.nonnegative(argument)) >> Q.integer(f(argument))),

    # Positive at a natural number
    #     a number of permutations or of partitions: A_0 == p(0) == 1
    for_all((andre, partition),
        (Q.integer(argument) & Q.nonnegative(argument)) >> Q.positive(f(argument))),

    # A positive integer from -1 on
    #     n!! == n*(n - 2)*...*1 or ...*2, and (-1)!! == 0!! == 1
    for_all((factorial2,),
        (Q.integer(argument) & Q.ge(argument, -1)) >> (
            Q.integer(f(argument)) & Q.positive(f(argument)))),

    # Odd at an odd number from -3 on
    #     a product of odd numbers, and (-3)!! == -1
    for_all((factorial2,),
        (Q.odd(argument) & Q.ge(argument, -3)) >> Q.odd(f(argument))),

    # Rational and not even at an odd number
    #     n!! == (n + 2)!!/(n + 2) for odd n < -1: (-5)!! == 1/3
    for_all((factorial2,),
        Q.odd(argument) >> (Q.rational(f(argument)) & ~Q.even(f(argument)))),

    # One at 0
    #     0!! == 1
    for_all((factorial2,),
        Q.zero(argument) >> (Q.odd(f(argument)) & Q.positive(f(argument)))),

    # Even and positive at an even positive number
    #     (2*k)!! == 2**k*k!
    for_all((factorial2,),
        (Q.even(argument) & Q.positive(argument)) >> (
            Q.even(f(argument)) & Q.positive(f(argument)))),

    # Nonnegative at a natural number
    #     a number of permutations: !1 == 0
    for_all((subfactorial,),
        (Q.integer(argument) & Q.nonnegative(argument)) >> Q.nonnegative(f(argument))),

    # The other parity than the argument
    #     !n == n*!(n - 1) + (-1)**n, !0 == 1
    for_all((subfactorial,),
        (Q.odd(argument) & Q.nonnegative(argument)) >> Q.even(f(argument)),
        (Q.even(argument) & Q.nonnegative(argument)) >> Q.odd(f(argument))),

    # Positive on the nonnegatives
    #     4**x*gamma(x + 1/2)/(sqrt(pi)*gamma(x + 2)) > 0
    for_all((catalan,),
        Q.nonnegative(argument) >> Q.positive(f(argument))),

    # Composite from 4 on
    #     C_n is prime only for n == 2, 3 (1, 1, 2, 5, 14, 42, ...)
    for_all((catalan,),
        (Q.integer(argument) & Q.gt(argument, 3)) >> Q.composite(f(argument))),

    # Integer at an integer
    #     a number of partitions
    for_all((partition,),
        Q.integer(argument) >> Q.integer(f(argument))),

    # Zero at a negative integer
    for_all((partition,),
        (Q.integer(argument) & Q.negative(argument)) >> Q.zero(f(argument))),

    # Zero at 0
    #     G_0 == 0
    for_all((genocchi,),
        Q.zero(argument) >> Q.zero(f(argument))),

    # Odd at an even positive number
    #     G_2, G_4, ... == -1, 1, -3, 17, -155, ...
    for_all((genocchi,),
        (Q.even(argument) & Q.positive(argument)) >> Q.odd(f(argument))),

    # Minus one at 1
    #     G_1 == -1
    for_all((genocchi,),
        (Q.odd(argument) & Q.eq(argument, 1)) >> (Q.odd(f(argument)) & Q.negative(f(argument)))),

    # Zero at an odd number from 3 on
    #     B_n == 0 for odd n > 1
    for_all((genocchi,),
        (Q.odd(argument) & Q.gt(argument, 1)) >> Q.zero(f(argument))),

    # Integer, rational and real at a natural size
    #     rf(x, k) == x*(x + 1)*...*(x + k - 1),
    #     ff(x, k) == x*(x - 1)*...*(x - k + 1)
    for_all((RisingFactorial, FallingFactorial),
        (Q.integer(start) & Q.integer(size) & Q.nonnegative(size)) >> Q.integer(f(start, size)),
        (Q.rational(start) & Q.integer(size) & Q.nonnegative(size))
        >> Q.rational(f(start, size)),
        (Q.real(start) & Q.integer(size) & Q.nonnegative(size)) >> Q.real(f(start, size))),

    # Positive at a positive start
    #     a product of positive factors
    for_all((RisingFactorial,),
        (Q.positive(start) & Q.integer(size) & Q.nonnegative(size))
        >> Q.positive(f(start, size))),

    # Nonnegative at natural numbers
    #     ff(n, k) == n!/(n - k)! for k <= n, 0 for k > n
    for_all((FallingFactorial,),
        (Q.integer(start) & Q.nonnegative(start) & Q.integer(size) & Q.nonnegative(size))
        >> Q.nonnegative(f(start, size))),

    # One at size = 0
    #     the empty product, for every start but nan, which SymPy propagates
    #     first (rf(x + y, 0) is nan at x = oo, y = -oo); zoo is left out
    for_all((RisingFactorial, FallingFactorial),
        (Q.complex(start) & Q.zero(size)) >> (
            Q.odd(f(start, size)) & Q.positive(f(start, size))),
        (Q.extended_real(start) & Q.zero(size)) >> (
            Q.odd(f(start, size)) & Q.positive(f(start, size)))),

    # Integer at integers
    #     ff(n, k)/k! for an integer k > 0, a product of k consecutive
    #     integers over k!; 1 for k == 0 and 0 for k < 0
    for_all((binomial,),
        (Q.integer(total) & Q.integer(size)) >> Q.integer(f(total, size))),

    # Zero at a negative size
    for_all((binomial,),
        (Q.integer(size) & Q.negative(size)) >> Q.zero(f(total, size))),

    # One at size = 0
    for_all((binomial,),
        Q.zero(size) >> (Q.odd(f(total, size)) & Q.positive(f(total, size)))),

    # Nonnegative at a natural total or an even size
    #     binomial(n, k) == (-1)**k*binomial(k - n - 1, k) for n < 0
    for_all((binomial,),
        (Q.integer(total) & Q.nonnegative(total) & Q.integer(size))
        >> Q.nonnegative(f(total, size)),
        (Q.integer(total) & Q.even(size)) >> Q.nonnegative(f(total, size))),
)
