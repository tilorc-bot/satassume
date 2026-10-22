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

from ._rows import closed, f, for_all, x, y

RULES = (
    # Pole at 1
    #     zeta(1) == zeta(1, a) == zoo; the sign and parity premises keep
    #     the row apart from the even s, which the engine does not relate
    #     to s - 1
    for_all((zeta,),
        (Q.positive(x) & ~Q.even(x) & Q.eq(x, 1)) >> (
            Q.infinite(f(x)) & ~Q.extended_real(f(x))),
        (Q.eq(x, 1) & Q.complex(y)) >> (Q.infinite(f(x, y)) & ~Q.extended_real(f(x, y))),
        (Q.eq(x, 1) & Q.extended_real(y)) >> (
            Q.infinite(f(x, y)) & ~Q.extended_real(f(x, y)))),

    # Finite but at 1
    #     the analytic continuation has its only pole at 1
    for_all((zeta,),
        (Q.complex(x) & Q.ne(x, 1)) >> Q.complex(f(x))),

    # Positive beyond 1
    #     zeta(s) == sum(1/n**s) and zeta(s, a) == sum(1/(n + a)**s) for
    #     a > 0, converging for s > 1
    for_all((zeta,),
        (Q.positive(x) & Q.gt(x, 1)) >> Q.positive(f(x)),
        (Q.positive(x) & Q.gt(x, 1) & Q.positive(y)) >> Q.positive(f(x, y))),

    # Real below 1
    #     real on the real line but at the pole
    for_all((zeta,),
        (Q.real(x) & Q.lt(x, 1)) >> Q.real(f(x))),

    # Negative on [0, 1)
    #     zeta(0) == -1/2; the premises keep the row apart from the even
    #     s > 0, which the engine does not relate to s - 1
    for_all((zeta,),
        Q.zero(x) >> Q.negative(f(x)),
        (Q.positive(x) & ~Q.integer(x) & Q.lt(x, 1)) >> Q.negative(f(x))),

    # One at oo
    #     zeta(oo) == 1
    for_all((zeta,),
        (Q.infinite(x) & Q.extended_positive(x)) >> (Q.odd(f(x)) & Q.positive(f(x)))),

    # Zero at the negative even integers
    #     the trivial zeros of zeta; dirichlet_eta(s) == (1 - 2**(1 - s))*zeta(s)
    for_all((zeta, dirichlet_eta),
        (Q.even(x) & Q.negative(x)) >> Q.zero(f(x))),

    # Rational at the nonpositive integers
    #     zeta(-n) == (-1)**n*bernoulli(n + 1)/(n + 1), zeta(0) == -1/2
    for_all((zeta,),
        (Q.integer(x) & Q.nonpositive(x)) >> Q.rational(f(x))),

    # Transcendental at the positive even integers
    #     zeta(2*n) is a positive rational times pi**(2*n) (Euler)
    for_all((zeta,),
        (Q.even(x) & Q.positive(x)) >> (Q.positive(f(x)) & Q.transcendental(f(x)))),

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
        (Q.real(x) & Q.real(y) & Q.lt(y, 1)) >> Q.real(f(x, y))),

    # Positive on (0, 1)
    #     a series of positive terms
    for_all((polylog,),
        (Q.real(x) & Q.positive(y) & Q.lt(y, 1)) >> Q.positive(f(x, y))),

    # Negative on the negative reals, for s >= 0
    #     z/gamma(s) times a positive integral, z/(1 - z) for s == 0
    for_all((polylog,),
        (Q.nonnegative(x) & Q.negative(y)) >> Q.negative(f(x, y))),

    # Zero at 0
    for_all((polylog,),
        Q.zero(y) >> Q.zero(f(x, y))),

    # Finite but at 1
    #     polylog(s, 1) == zeta(s); the branch cut is on (1, oo)
    for_all((polylog,),
        (Q.complex(x) & Q.complex(y) & Q.ne(y, 1)) >> Q.complex(f(x, y))),
)
