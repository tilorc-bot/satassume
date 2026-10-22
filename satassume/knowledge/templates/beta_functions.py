"""``beta``, ``betainc`` and ``betainc_regularized``.

SymPy's own handlers are not followed where they are not theorems:
``beta(x, y)`` and ``betainc`` of real arguments are not always real
(``beta(5, -3) == oo``, ``betainc(1/2, 1, 0, -1)`` is not real).
``beta(x)`` is ``beta(x, x)``.
"""
from __future__ import annotations

from sympy import Q, beta, betainc, betainc_regularized
from sympy.abc import a, b

from ._rows import f, for_all, x, y

RULES = (
    # Positive on the positive reals
    #     beta(x, y) == gamma(x)*gamma(y)/gamma(x + y)
    for_all((beta,),
        Q.positive(x) >> Q.positive(f(x)),
        (Q.positive(x) & Q.positive(y)) >> Q.positive(f(x, y))),

    # Real and rational for positive integers a and b
    #     betainc(a, b, x, y) == integral of t**(a - 1)*(1 - t)**(b - 1) over
    #     (x, y): a polynomial in x and y with rational coefficients;
    #     betainc_regularized divides it by beta(a, b), a positive rational
    for_all((betainc, betainc_regularized),
        (Q.integer(a) & Q.positive(a) & Q.integer(b) & Q.positive(b) & Q.real(x) & Q.real(y))
            >> Q.real(f(a, b, x, y)),
        (Q.integer(a) & Q.positive(a) & Q.integer(b) & Q.positive(b)
            & Q.rational(x) & Q.rational(y)) >> Q.rational(f(a, b, x, y))),
)
