"""``beta``, ``betainc`` and ``betainc_regularized``.

SymPy's own handlers are not followed where they are not theorems:
``beta(x, y)`` and ``betainc`` of real arguments are not always real
(``beta(5, -3) == oo``, ``betainc(1/2, 1, 0, -1)`` is not real).
``beta(x)`` is ``beta(x, x)``.
"""
from __future__ import annotations

from sympy import Q, beta, betainc, betainc_regularized

from ._rows import argument, f, first, for_all, lower, second, upper

RULES = (
    # Positive on the positive reals
    #     beta(x, y) == gamma(x)*gamma(y)/gamma(x + y)
    for_all((beta,),
        Q.positive(argument) >> Q.positive(f(argument)),
        (Q.positive(first) & Q.positive(second)) >> Q.positive(f(first, second))),

    # Real and rational for positive integers first and second
    #     betainc(a, b, x, y) == integral of t**(a - 1)*(1 - t)**(b - 1) over
    #     (x, y): a polynomial in x and y with rational coefficients;
    #     betainc_regularized divides it by beta(a, b), a positive rational
    for_all((betainc, betainc_regularized),
        (Q.integer(first) & Q.positive(first) & Q.integer(second) & Q.positive(second)
            & Q.real(lower) & Q.real(upper)) >> Q.real(f(first, second, lower, upper)),
        (Q.integer(first) & Q.positive(first) & Q.integer(second) & Q.positive(second)
            & Q.rational(lower) & Q.rational(upper))
            >> Q.rational(f(first, second, lower, upper))),
)
