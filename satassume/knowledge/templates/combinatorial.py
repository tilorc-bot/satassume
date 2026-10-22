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

from ._rows import f, for_all, x, y

RULES = (
    # Integer at a natural number
    #     C_n == binomial(2*n, n)/(n + 1), the number of alternating
    #     permutations, G_n == 2*(1 - 2**n)*B_n
    for_all((catalan, andre, genocchi),
        (Q.integer(x) & Q.nonnegative(x)) >> Q.integer(f(x))),

    # Positive at a natural number
    #     a number of permutations or of partitions: A_0 == p(0) == 1
    for_all((andre, partition),
        (Q.integer(x) & Q.nonnegative(x)) >> Q.positive(f(x))),

    # A positive integer from -1 on
    #     n!! == n*(n - 2)*...*1 or ...*2, and (-1)!! == 0!! == 1
    for_all((factorial2,),
        (Q.integer(x) & Q.ge(x, -1)) >> (Q.integer(f(x)) & Q.positive(f(x)))),

    # Odd at an odd number from -3 on
    #     a product of odd numbers, and (-3)!! == -1
    for_all((factorial2,),
        (Q.odd(x) & Q.ge(x, -3)) >> Q.odd(f(x))),

    # Rational and not even at an odd number
    #     n!! == (n + 2)!!/(n + 2) for odd n < -1: (-5)!! == 1/3
    for_all((factorial2,),
        Q.odd(x) >> (Q.rational(f(x)) & ~Q.even(f(x)))),

    # One at 0
    #     0!! == 1
    for_all((factorial2,),
        Q.zero(x) >> (Q.odd(f(x)) & Q.positive(f(x)))),

    # Even and positive at an even positive number
    #     (2*k)!! == 2**k*k!
    for_all((factorial2,),
        (Q.even(x) & Q.positive(x)) >> (Q.even(f(x)) & Q.positive(f(x)))),

    # Nonnegative at a natural number
    #     a number of permutations: !1 == 0
    for_all((subfactorial,),
        (Q.integer(x) & Q.nonnegative(x)) >> Q.nonnegative(f(x))),

    # The other parity than the argument
    #     !n == n*!(n - 1) + (-1)**n, !0 == 1
    for_all((subfactorial,),
        (Q.odd(x) & Q.nonnegative(x)) >> Q.even(f(x)),
        (Q.even(x) & Q.nonnegative(x)) >> Q.odd(f(x))),

    # Positive on the nonnegatives
    #     4**x*gamma(x + 1/2)/(sqrt(pi)*gamma(x + 2)) > 0
    for_all((catalan,),
        Q.nonnegative(x) >> Q.positive(f(x))),

    # Composite from 4 on
    #     C_n is prime only for n == 2, 3 (1, 1, 2, 5, 14, 42, ...)
    for_all((catalan,),
        (Q.integer(x) & Q.gt(x, 3)) >> Q.composite(f(x))),

    # Integer at an integer
    #     a number of partitions
    for_all((partition,),
        Q.integer(x) >> Q.integer(f(x))),

    # Zero at a negative integer
    for_all((partition,),
        (Q.integer(x) & Q.negative(x)) >> Q.zero(f(x))),

    # Zero at 0
    #     G_0 == 0
    for_all((genocchi,),
        Q.zero(x) >> Q.zero(f(x))),

    # Odd at an even positive number
    #     G_2, G_4, ... == -1, 1, -3, 17, -155, ...
    for_all((genocchi,),
        (Q.even(x) & Q.positive(x)) >> Q.odd(f(x))),

    # Minus one at 1
    #     G_1 == -1
    for_all((genocchi,),
        (Q.odd(x) & Q.eq(x, 1)) >> (Q.odd(f(x)) & Q.negative(f(x)))),

    # Zero at an odd number from 3 on
    #     B_n == 0 for odd n > 1
    for_all((genocchi,),
        (Q.odd(x) & Q.gt(x, 1)) >> Q.zero(f(x))),

    # Integer, rational and real at a natural number k
    #     rf(x, k) == x*(x + 1)*...*(x + k - 1),
    #     ff(x, k) == x*(x - 1)*...*(x - k + 1)
    for_all((RisingFactorial, FallingFactorial),
        (Q.integer(x) & Q.integer(y) & Q.nonnegative(y)) >> Q.integer(f(x, y)),
        (Q.rational(x) & Q.integer(y) & Q.nonnegative(y)) >> Q.rational(f(x, y)),
        (Q.real(x) & Q.integer(y) & Q.nonnegative(y)) >> Q.real(f(x, y))),

    # Positive at a positive x
    #     a product of positive factors
    for_all((RisingFactorial,),
        (Q.positive(x) & Q.integer(y) & Q.nonnegative(y)) >> Q.positive(f(x, y))),

    # Nonnegative at natural numbers
    #     ff(n, k) == n!/(n - k)! for k <= n, 0 for k > n
    for_all((FallingFactorial,),
        (Q.integer(x) & Q.nonnegative(x) & Q.integer(y) & Q.nonnegative(y))
        >> Q.nonnegative(f(x, y))),

    # One at k = 0
    #     the empty product, for every x but nan, which SymPy propagates
    #     first (rf(x + y, 0) is nan at x = oo, y = -oo); zoo is left out
    for_all((RisingFactorial, FallingFactorial),
        (Q.complex(x) & Q.zero(y)) >> (Q.odd(f(x, y)) & Q.positive(f(x, y))),
        (Q.extended_real(x) & Q.zero(y)) >> (Q.odd(f(x, y)) & Q.positive(f(x, y)))),

    # Integer at integers
    #     ff(n, k)/k! for an integer k > 0, a product of k consecutive
    #     integers over k!; 1 for k == 0 and 0 for k < 0
    for_all((binomial,),
        (Q.integer(x) & Q.integer(y)) >> Q.integer(f(x, y))),

    # Zero at a negative k
    for_all((binomial,),
        (Q.integer(y) & Q.negative(y)) >> Q.zero(f(x, y))),

    # One at k = 0
    for_all((binomial,),
        Q.zero(y) >> (Q.odd(f(x, y)) & Q.positive(f(x, y)))),

    # Nonnegative at a natural number n or an even k
    #     binomial(n, k) == (-1)**k*binomial(k - n - 1, k) for n < 0
    for_all((binomial,),
        (Q.integer(x) & Q.nonnegative(x) & Q.integer(y)) >> Q.nonnegative(f(x, y)),
        (Q.integer(x) & Q.even(y)) >> Q.nonnegative(f(x, y))),
)
