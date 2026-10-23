"""The Airy functions ``airyai``, ``airybi``, ``airyaiprime`` and
``airybiprime``, and the Bessel functions ``besselj``, ``bessely``,
``besseli`` and ``besselk`` of order ``nu`` at ``z`` (``f(order,
argument)`` is ``f(nu, z)``).

Values follow SymPy's conventions: the limits at the real infinities
(``airyai(+-oo) == 0``, ``airybi(oo) == oo``, ``airybi(-oo) == 0``,
``airyaiprime(oo) == 0``, ``airybiprime(oo) == oo``; ``besselj(nu, +-oo)
== bessely(nu, oo) == besselk(nu, oo) == 0``, ``besseli(nu, oo) == oo``),
and ``bessely(nu, 0) == besselk(nu, 0) == zoo`` for real ``nu``, though
the limit of ``bessely(nu, z)`` at 0 is 0 for a negative half-integer
``nu``.  SymPy leaves ``airyaiprime(-oo)`` alone.  The Airy functions have
non-real zeros, where the value is real, so a non-real argument gives no
claim.  A Bessel function of other than two arguments gets no facts.
"""
from __future__ import annotations

from sympy import (
    Q, airyai, airyaiprime, airybi, airybiprime, besseli, besselj, besselk, bessely,
)

from ._rows import argument, closed, f, for_all, order

RULES = (
    # Entire
    #     no poles: finite at every finite point
    for_all((airyai, airybi, airyaiprime, airybiprime),
        closed(f, Q.finite) & closed(f, Q.complex)),

    # Real on the reals
    #     real coefficients
    for_all((airyai, airybi, airyaiprime, airybiprime),
        closed(f, Q.real)),

    # Positive on the nonnegative reals
    #     Ai and its zeros are on the negative reals; Bi and Bi' increase
    #     from positive values at 0
    for_all((airyai, airybi, airybiprime),
        Q.nonnegative(argument) >> Q.positive(f(argument))),

    # Negative on the nonnegative reals
    #     Ai decreases on the nonnegative reals
    for_all((airyaiprime,),
        Q.nonnegative(argument) >> Q.negative(f(argument))),

    # oo at oo
    for_all((airybi, airybiprime),
        (Q.infinite(argument) & Q.extended_positive(argument)) >> (
            Q.infinite(f(argument)) & Q.extended_positive(f(argument)))),

    # Zero at oo
    for_all((airyai, airyaiprime),
        (Q.infinite(argument) & Q.extended_positive(argument)) >> Q.zero(f(argument))),

    # Zero at -oo
    for_all((airyai, airybi),
        (Q.infinite(argument) & Q.extended_negative(argument)) >> Q.zero(f(argument))),

    # Real on the positive reals, for a real order
    for_all((besselj, bessely, besseli),
        (Q.real(order) & Q.positive(argument)) >> Q.real(f(order, argument))),

    # Real on the reals, for an integer order
    #     J_n and I_n are entire, with real Taylor coefficients
    for_all((besselj, besseli),
        (Q.integer(order) & Q.real(argument)) >> Q.real(f(order, argument))),

    # Positive on the positive reals, for a real order
    #     K_nu is an integral of exp(-z*cosh(t))*cosh(nu*t) over t > 0
    for_all((besselk,),
        (Q.real(order) & Q.positive(argument)) >> Q.positive(f(order, argument))),

    # Positive on the positive reals, for an integer order
    #     I_n == I_-n is a series of positive terms there
    for_all((besseli,),
        (Q.integer(order) & Q.positive(argument)) >> Q.positive(f(order, argument))),

    # oo at oo, for an order
    for_all((besseli,),
        (Q.real(order) & Q.infinite(argument) & Q.extended_positive(argument)) >> (
            Q.infinite(f(order, argument)) & Q.extended_positive(f(order, argument)))),

    # Zero at oo, for an order
    for_all((bessely, besselk),
        (Q.real(order) & Q.infinite(argument) & Q.extended_positive(argument))
        >> Q.zero(f(order, argument))),

    # Zero at a real infinity, for an order
    for_all((besselj,),
        (Q.real(order) & Q.infinite(argument) & Q.extended_real(argument))
        >> Q.zero(f(order, argument))),

    # Infinite at 0, for a real order
    #     SymPy's value: bessely(nu, 0) == besselk(nu, 0) == zoo, though the
    #     limit of bessely(nu, z) at 0 is 0 for a negative half-integer nu
    for_all((bessely, besselk),
        (Q.real(order) & Q.zero(argument)) >> Q.infinite(f(order, argument))),
)
