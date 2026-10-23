"""``zeta`` (Riemann's ``zeta(s)`` and Hurwitz's ``zeta(s, a)``),
``dirichlet_eta`` and ``polylog``.

Values follow SymPy's conventions: ``zeta(1) == zeta(1, a) == zoo`` (a
pole), ``zeta(oo) == 1``, ``polylog(s, 0) == 0``.  ``zeta(s)`` is not
finite at ``s = -oo``, and ``zeta(1, nan)`` is nan, so the pole of
``zeta(s, a)`` asks for a complex or extended real ``a``.  ``zeta`` of
another number of arguments, ``dirichlet_eta(s, a)`` and ``polylog`` of
other than two get no facts.
"""
from __future__ import annotations

from sympy import Q, dirichlet_eta, polylog, zeta

from ._rows import argument, closed, f, for_all, order, parameter

RULES = (
    # Pole at 1
    #     zeta(1) == zeta(1, a) == zoo; the sign and parity premises keep
    #     the row apart from the even argument, which the engine does not
    #     relate to argument - 1
    for_all((zeta,),
        (Q.positive(argument) & ~Q.even(argument) & Q.eq(argument, 1)) >> (
            Q.infinite(f(argument)) & ~Q.extended_real(f(argument))),
        (Q.eq(argument, 1) & Q.complex(parameter)) >> (
            Q.infinite(f(argument, parameter)) & ~Q.extended_real(f(argument, parameter))),
        (Q.eq(argument, 1) & Q.extended_real(parameter)) >> (
            Q.infinite(f(argument, parameter)) & ~Q.extended_real(f(argument, parameter)))),

    # Finite but at 1
    #     the analytic continuation has its only pole at 1
    for_all((zeta,),
        (Q.complex(argument) & Q.ne(argument, 1)) >> Q.complex(f(argument))),

    # Positive beyond 1
    #     zeta(s) == sum(1/n**s) and zeta(s, a) == sum(1/(n + a)**s) for
    #     a > 0, converging for s > 1
    for_all((zeta,),
        (Q.positive(argument) & Q.gt(argument, 1)) >> Q.positive(f(argument)),
        (Q.positive(argument) & Q.gt(argument, 1) & Q.positive(parameter))
        >> Q.positive(f(argument, parameter))),

    # Real below 1
    #     real on the real line but at the pole
    for_all((zeta,),
        (Q.real(argument) & Q.lt(argument, 1)) >> Q.real(f(argument))),

    # Negative on [0, 1)
    #     zeta(0) == -1/2; the premises keep the row apart from the even
    #     argument > 0, which the engine does not relate to argument - 1
    for_all((zeta,),
        Q.zero(argument) >> Q.negative(f(argument)),
        (Q.positive(argument) & ~Q.integer(argument) & Q.lt(argument, 1))
        >> Q.negative(f(argument))),

    # One at oo
    #     zeta(oo) == 1
    for_all((zeta,),
        (Q.infinite(argument) & Q.extended_positive(argument)) >> (
            Q.odd(f(argument)) & Q.positive(f(argument)))),

    # Zero at the negative even integers
    #     the trivial zeros of zeta; dirichlet_eta(s) == (1 - 2**(1 - s))*zeta(s)
    for_all((zeta, dirichlet_eta),
        (Q.even(argument) & Q.negative(argument)) >> Q.zero(f(argument))),

    # Rational at the nonpositive integers
    #     zeta(-n) == (-1)**n*bernoulli(n + 1)/(n + 1), zeta(0) == -1/2
    for_all((zeta,),
        (Q.integer(argument) & Q.nonpositive(argument)) >> Q.rational(f(argument))),

    # Transcendental at the positive even integers
    #     zeta(2*n) is a positive rational times pi**(2*n) (Euler)
    for_all((zeta,),
        (Q.even(argument) & Q.positive(argument)) >> (
            Q.positive(f(argument)) & Q.transcendental(f(argument)))),

    # Entire
    #     dirichlet_eta(s) == (1 - 2**(1 - s))*zeta(s): the zero of the
    #     factor at s = 1 cancels the pole (dirichlet_eta(1) == log(2))
    for_all((dirichlet_eta,),
        closed(f, Q.finite) & closed(f, Q.complex)),

    # Real on the reals
    for_all((dirichlet_eta,),
        closed(f, Q.real)),

    # Positive on the positive reals
    #     an alternating series of decreasing terms, of positive sum
    for_all((dirichlet_eta,),
        closed(f, Q.positive)),

    # Real on the reals below 1
    #     polylog(s, z) == sum(z**k/k**s), and its continuation to z < -1
    #     is real
    for_all((polylog,),
        (Q.real(order) & Q.real(argument) & Q.lt(argument, 1)) >> Q.real(f(order, argument))),

    # Positive on (0, 1)
    #     a series of positive terms
    for_all((polylog,),
        (Q.real(order) & Q.positive(argument) & Q.lt(argument, 1))
        >> Q.positive(f(order, argument))),

    # Negative on the negative reals, for an order >= 0
    #     z/gamma(s) times a positive integral, z/(1 - z) for s == 0
    for_all((polylog,),
        (Q.nonnegative(order) & Q.negative(argument)) >> Q.negative(f(order, argument))),

    # Zero at 0
    for_all((polylog,),
        Q.zero(argument) >> Q.zero(f(order, argument))),

    # Finite but at 1
    #     polylog(s, 1) == zeta(s); the branch cut is on (1, oo)
    for_all((polylog,),
        (Q.complex(order) & Q.complex(argument) & Q.ne(argument, 1))
        >> Q.complex(f(order, argument))),
)
