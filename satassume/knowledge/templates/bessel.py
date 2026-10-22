"""The Airy functions ``airyai``, ``airybi``, ``airyaiprime`` and
``airybiprime``, and the Bessel functions ``besselj``, ``bessely``,
``besseli`` and ``besselk`` of order ``nu`` at ``z`` (``f(x, y)`` is
``f(nu, z)``).

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

from ._rows import closed, f, for_all, x, y

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
        Q.nonnegative(x) >> Q.positive(f(x))),

    # Negative on the nonnegative reals
    #     Ai decreases on the nonnegative reals
    for_all((airyaiprime,),
        Q.nonnegative(x) >> Q.negative(f(x))),

    # oo at oo
    for_all((airybi, airybiprime),
        (Q.infinite(x) & Q.extended_positive(x)) >> (
            Q.infinite(f(x)) & Q.extended_positive(f(x)))),

    # Zero at oo
    for_all((airyai, airyaiprime),
        (Q.infinite(x) & Q.extended_positive(x)) >> Q.zero(f(x))),

    # Zero at -oo
    for_all((airyai, airybi),
        (Q.infinite(x) & Q.extended_negative(x)) >> Q.zero(f(x))),

    # Real on the positive reals, for a real order
    for_all((besselj, bessely, besseli),
        (Q.real(x) & Q.positive(y)) >> Q.real(f(x, y))),

    # Real on the reals, for an integer order
    #     J_n and I_n are entire, with real Taylor coefficients
    for_all((besselj, besseli),
        (Q.integer(x) & Q.real(y)) >> Q.real(f(x, y))),

    # Positive on the positive reals, for a real order
    #     K_nu is an integral of exp(-z*cosh(t))*cosh(nu*t) over t > 0
    for_all((besselk,),
        (Q.real(x) & Q.positive(y)) >> Q.positive(f(x, y))),

    # Positive on the positive reals, for an integer order
    #     I_n == I_-n is a series of positive terms there
    for_all((besseli,),
        (Q.integer(x) & Q.positive(y)) >> Q.positive(f(x, y))),

    # oo at oo, for an order
    for_all((besseli,),
        (Q.real(x) & Q.infinite(y) & Q.extended_positive(y)) >> (
            Q.infinite(f(x, y)) & Q.extended_positive(f(x, y)))),

    # Zero at oo, for an order
    for_all((bessely, besselk),
        (Q.real(x) & Q.infinite(y) & Q.extended_positive(y)) >> Q.zero(f(x, y))),

    # Zero at a real infinity, for an order
    for_all((besselj,),
        (Q.real(x) & Q.infinite(y) & Q.extended_real(y)) >> Q.zero(f(x, y))),

    # Infinite at 0, for a real order
    #     SymPy's value: bessely(nu, 0) == besselk(nu, 0) == zoo, though the
    #     limit of bessely(nu, z) at 0 is 0 for a negative half-integer nu
    for_all((bessely, besselk),
        (Q.real(x) & Q.zero(y)) >> Q.infinite(f(x, y))),
)
