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

from ._rows import argument, f, for_all, order, parameter

RULES = (
    # Poles at the nonpositive integers
    #     gamma(-n) == digamma(-n) == trigamma(-n) == zoo
    for_all((gamma, digamma, trigamma),
        (Q.integer(argument) & Q.nonpositive(argument)) >> (
            Q.infinite(f(argument)) & ~Q.extended_real(f(argument)))),

    # Poles at the nonpositive integers, of order >= 0
    #     polygamma(n, -k) == zoo
    for_all((polygamma,),
        (Q.integer(order) & Q.nonnegative(order) & Q.integer(argument)
         & Q.nonpositive(argument)) >> (
            Q.infinite(f(order, argument)) & ~Q.extended_real(f(order, argument)))),

    # oo at the nonpositive integers
    #     loggamma(-n) == oo, SymPy's value
    for_all((loggamma,),
        (Q.integer(argument) & Q.nonpositive(argument)) >> Q.infinite(f(argument))),

    # Real on the positive reals
    for_all((loggamma, digamma),
        Q.positive(argument) >> Q.real(f(argument))),

    # Real at the real non-integers
    for_all((gamma, digamma),
        (Q.real(argument) & ~Q.integer(argument)) >> Q.real(f(argument))),

    # Real at the real non-poles, of order >= 0
    for_all((polygamma,),
        (Q.integer(order) & Q.nonnegative(order) & Q.positive(argument))
        >> Q.real(f(order, argument)),
        (Q.integer(order) & Q.nonnegative(order) & Q.real(argument) & ~Q.integer(argument))
        >> Q.real(f(order, argument))),

    # Complex at the real non-integers
    #     loggamma(-t) for a non-integer t > 0: log|gamma(-t)| plus a nonzero
    #     multiple of I*pi
    for_all((loggamma,),
        (Q.real(argument) & ~Q.integer(argument)) >> Q.complex(f(argument))),

    # Not real at the negative non-integers
    for_all((loggamma,),
        (Q.negative(argument) & ~Q.integer(argument)) >> ~Q.extended_real(f(argument))),

    # Complex off the real line
    #     no pole off the real line; not "a non-real value": gamma is real
    #     on a curve through its minimum x0 ~ 1.4616, so loggamma is real at
    #     7/5 + 0.6388873...*I (#194 review)
    for_all((gamma, loggamma, digamma, trigamma),
        (Q.complex(argument) & ~Q.extended_real(argument)) >> Q.complex(f(argument))),

    # Complex off the real line, of order >= 0
    for_all((polygamma,),
        (Q.integer(order) & Q.nonnegative(order) & Q.complex(argument)
         & ~Q.extended_real(argument)) >> Q.complex(f(order, argument))),

    # Never zero
    #     1/gamma is entire, so gamma has no zeros
    for_all((gamma,),
        (Q.real(argument) & ~Q.integer(argument)) >> ~Q.zero(f(argument)),
        (Q.complex(argument) & ~Q.extended_real(argument)) >> ~Q.zero(f(argument))),

    # Positive on the positive reals
    #     gamma(t) == integral of s**(t - 1)*exp(-s) over (0, oo)
    for_all((gamma,),
        Q.positive(argument) >> Q.positive(f(argument))),

    # Integer at the positive integers
    #     gamma(k) == (k - 1)!
    for_all((gamma,),
        (Q.integer(argument) & Q.positive(argument)) >> Q.integer(f(argument))),

    # Sign at the negative half-integers
    #     gamma has the sign (-1)**k on (-k, -k + 1); argument == s + 1/2 < 0
    #     lies in (s, s + 1), so gamma(argument) has the sign (-1)**s
    for_all((gamma,),
        (Q.even(argument - S.Half) & Q.negative(argument) & ~Q.integer(argument))
        >> Q.positive(f(argument)),
        (Q.odd(argument - S.Half) & Q.negative(argument) & ~Q.integer(argument))
        >> Q.negative(f(argument))),

    # Positive at the real non-poles
    #     trigamma(t) == sum(1/(t + k)**2)
    for_all((trigamma,),
        Q.positive(argument) >> Q.positive(f(argument)),
        (Q.real(argument) & ~Q.integer(argument)) >> Q.positive(f(argument))),

    # Positive at the real non-poles, of odd order
    #     polygamma(n, t) == (-1)**(n + 1)*n!*sum(1/(t + k)**(n + 1)), each
    #     term positive for odd n
    for_all((polygamma,),
        (Q.odd(order) & Q.positive(order) & Q.positive(argument))
        >> Q.positive(f(order, argument)),
        (Q.odd(order) & Q.positive(order) & Q.real(argument) & ~Q.integer(argument))
        >> Q.positive(f(order, argument))),

    # Negative on the positive reals, of even order >= 2
    #     the same sum, of negative terms for even n
    for_all((polygamma,),
        (Q.even(order) & Q.positive(order) & Q.positive(argument))
        >> Q.negative(f(order, argument))),

    # oo at oo
    for_all((gamma, loggamma, digamma),
        (Q.infinite(argument) & Q.extended_positive(argument)) >> (
            Q.infinite(f(argument)) & Q.extended_positive(f(argument)))),

    # oo at oo, of order 0
    #     digamma(t) ~ log(t)
    for_all((polygamma,),
        (Q.zero(order) & Q.infinite(argument) & Q.extended_positive(argument)) >> (
            Q.infinite(f(order, argument)) & Q.extended_positive(f(order, argument)))),

    # Infinite at an infinity
    #     loggamma(-oo) == loggamma(oo*I) == zoo, SymPy's value
    for_all((loggamma,),
        Q.infinite(argument) >> Q.infinite(f(argument))),

    # Zero at oo
    for_all((trigamma,),
        (Q.infinite(argument) & Q.extended_positive(argument)) >> Q.zero(f(argument))),

    # Zero at oo, of order >= 1
    for_all((polygamma,),
        (Q.integer(order) & Q.positive(order) & Q.infinite(argument)
         & Q.extended_positive(argument)) >> Q.zero(f(order, argument))),

    # Positive for a positive parameter and argument
    #     lowergamma(a, x) == integral of t**(a - 1)*exp(-t) over (0, x)
    for_all((lowergamma,),
        (Q.positive(parameter) & Q.positive(argument)) >> Q.positive(f(parameter, argument))),

    # Positive for a real parameter and a positive argument
    #     uppergamma(a, x) == integral of t**(a - 1)*exp(-t) over (x, oo)
    for_all((uppergamma,),
        (Q.real(parameter) & Q.positive(argument)) >> Q.positive(f(parameter, argument))),
)
