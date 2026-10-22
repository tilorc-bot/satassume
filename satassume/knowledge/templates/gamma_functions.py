"""``gamma``, ``loggamma``, ``digamma``, ``trigamma``, ``polygamma``,
``lowergamma`` and ``uppergamma``.

Values follow SymPy's conventions: ``gamma(-n) == digamma(-n) ==
trigamma(-n) == polygamma(m, -n) == zoo`` at the nonpositive integers
(``m >= 0``), ``loggamma(-n) == oo``, ``loggamma(-oo) == loggamma(oo*I)
== zoo``, ``gamma(oo) == loggamma(oo) == polygamma(0, oo) == oo`` and
``polygamma(m, oo) == 0`` for ``m >= 1``.  ``polygamma(m, x)`` is
claimed for an integer order ``m >= 0`` only (``polygamma(-1, x)`` is
``loggamma(x)``).  SymPy's own handlers are not followed where they are not
theorems: ``gamma(oo)`` is not real, ``polygamma(1, 0) == zoo`` is not
positive and ``polygamma(m, 0)`` is not complex.  ``multigamma`` is in
:mod:`.special`: its rules are about ``2*x`` and depend on a constant
``p``, which rows do not state.
"""
from __future__ import annotations

from sympy import Q, S, digamma, gamma, loggamma, lowergamma, polygamma, trigamma, uppergamma
from sympy.abc import a, n

from ._rows import f, for_all, x

RULES = (
    # Poles at the nonpositive integers
    #     gamma(-n) == digamma(-n) == trigamma(-n) == zoo
    for_all((gamma, digamma, trigamma),
        (Q.integer(x) & Q.nonpositive(x)) >> (Q.infinite(f(x)) & ~Q.extended_real(f(x)))),

    # Poles at the nonpositive integers, of order n >= 0
    #     polygamma(n, -k) == zoo
    for_all((polygamma,),
        (Q.integer(n) & Q.nonnegative(n) & Q.integer(x) & Q.nonpositive(x)) >> (
            Q.infinite(f(n, x)) & ~Q.extended_real(f(n, x)))),

    # oo at the nonpositive integers
    #     loggamma(-n) == oo, SymPy's value
    for_all((loggamma,),
        (Q.integer(x) & Q.nonpositive(x)) >> Q.infinite(f(x))),

    # Real on the positive reals
    for_all((loggamma, digamma),
        Q.positive(x) >> Q.real(f(x))),

    # Real at the real non-integers
    for_all((gamma, digamma),
        (Q.real(x) & ~Q.integer(x)) >> Q.real(f(x))),

    # Real at the real non-poles, of order n >= 0
    for_all((polygamma,),
        (Q.integer(n) & Q.nonnegative(n) & Q.positive(x)) >> Q.real(f(n, x)),
        (Q.integer(n) & Q.nonnegative(n) & Q.real(x) & ~Q.integer(x)) >> Q.real(f(n, x))),

    # Complex at the real non-integers
    #     loggamma(-t) for a non-integer t > 0: log|gamma(-t)| plus a nonzero
    #     multiple of I*pi
    for_all((loggamma,),
        (Q.real(x) & ~Q.integer(x)) >> Q.complex(f(x))),

    # Not real at the negative non-integers
    for_all((loggamma,),
        (Q.negative(x) & ~Q.integer(x)) >> ~Q.extended_real(f(x))),

    # Complex off the real line
    #     no pole off the real line; not "a non-real value": gamma is real
    #     on a curve through its minimum x0 ~ 1.4616, so loggamma is real at
    #     7/5 + 0.6388873...*I (#194 review)
    for_all((gamma, loggamma, digamma, trigamma),
        (Q.complex(x) & ~Q.extended_real(x)) >> Q.complex(f(x))),

    # Complex off the real line, of order n >= 0
    for_all((polygamma,),
        (Q.integer(n) & Q.nonnegative(n) & Q.complex(x) & ~Q.extended_real(x)) >> (
            Q.complex(f(n, x)))),

    # Never zero
    #     1/gamma is entire, so gamma has no zeros
    for_all((gamma,),
        (Q.real(x) & ~Q.integer(x)) >> ~Q.zero(f(x)),
        (Q.complex(x) & ~Q.extended_real(x)) >> ~Q.zero(f(x))),

    # Positive on the positive reals
    #     gamma(t) == integral of s**(t - 1)*exp(-s) over (0, oo)
    for_all((gamma,),
        Q.positive(x) >> Q.positive(f(x))),

    # Integer at the positive integers
    #     gamma(k) == (k - 1)!
    for_all((gamma,),
        (Q.integer(x) & Q.positive(x)) >> Q.integer(f(x))),

    # Sign at the negative half-integers
    #     gamma has the sign (-1)**k on (-k, -k + 1); x == s + 1/2 < 0 lies in
    #     (s, s + 1), so gamma(x) has the sign (-1)**s
    for_all((gamma,),
        (Q.even(x - S.Half) & Q.negative(x) & ~Q.integer(x)) >> Q.positive(f(x)),
        (Q.odd(x - S.Half) & Q.negative(x) & ~Q.integer(x)) >> Q.negative(f(x))),

    # Positive at the real non-poles
    #     trigamma(t) == sum(1/(t + k)**2)
    for_all((trigamma,),
        Q.positive(x) >> Q.positive(f(x)),
        (Q.real(x) & ~Q.integer(x)) >> Q.positive(f(x))),

    # Positive at the real non-poles, of odd order
    #     polygamma(n, t) == (-1)**(n + 1)*n!*sum(1/(t + k)**(n + 1)), each
    #     term positive for odd n
    for_all((polygamma,),
        (Q.odd(n) & Q.positive(n) & Q.positive(x)) >> Q.positive(f(n, x)),
        (Q.odd(n) & Q.positive(n) & Q.real(x) & ~Q.integer(x)) >> Q.positive(f(n, x))),

    # Negative on the positive reals, of even order n >= 2
    #     the same sum, of negative terms for even n
    for_all((polygamma,),
        (Q.even(n) & Q.positive(n) & Q.positive(x)) >> Q.negative(f(n, x))),

    # oo at oo
    for_all((gamma, loggamma, digamma),
        (Q.infinite(x) & Q.extended_positive(x)) >> (
            Q.infinite(f(x)) & Q.extended_positive(f(x)))),

    # oo at oo, of order 0
    #     digamma(t) ~ log(t)
    for_all((polygamma,),
        (Q.zero(n) & Q.infinite(x) & Q.extended_positive(x)) >> (
            Q.infinite(f(n, x)) & Q.extended_positive(f(n, x)))),

    # Infinite at an infinity
    #     loggamma(-oo) == loggamma(oo*I) == zoo, SymPy's value
    for_all((loggamma,),
        Q.infinite(x) >> Q.infinite(f(x))),

    # Zero at oo
    for_all((trigamma,),
        (Q.infinite(x) & Q.extended_positive(x)) >> Q.zero(f(x))),

    # Zero at oo, of order n >= 1
    for_all((polygamma,),
        (Q.integer(n) & Q.positive(n) & Q.infinite(x) & Q.extended_positive(x)) >> (
            Q.zero(f(n, x)))),

    # Positive for positive a and x
    #     lowergamma(a, x) == integral of t**(a - 1)*exp(-t) over (0, x)
    for_all((lowergamma,),
        (Q.positive(a) & Q.positive(x)) >> Q.positive(f(a, x))),

    # Positive for real a and positive x
    #     uppergamma(a, x) == integral of t**(a - 1)*exp(-t) over (x, oo)
    for_all((uppergamma,),
        (Q.real(a) & Q.positive(x)) >> Q.positive(f(a, x))),
)
