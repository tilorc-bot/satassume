"""``exp_polar``, ``polar_lift`` and ``principal_branch`` (#180).

The value at a finite argument is a point of the Riemann surface of the
logarithm, so it is polar (``polar_lift(-2) == 2*exp_polar(I*pi)``); at an
infinite one it is not (``polar_lift(oo*I) == oo*exp_polar(I*pi/2)``, not
polar for SymPy), and ``principal_branch(x, oo) == x`` (unevaluated with
``evaluate=False``), so a period must be finite and positive.
``exp_polar(x)`` of a real ``x`` lies on the sheet of the positive reals
(``exp_polar(0)`` is 1, SymPy: rational, issue 8008), its value there is
``exp(x)``.  Nothing else is claimed: ``exp_polar(2*I*pi)`` is not 1.
SymPy's ``Q`` has no ``polar``; ``Predicate('polar')`` is satassume's.
"""
from __future__ import annotations

from sympy import Q, exp_polar, polar_lift, principal_branch
from sympy.assumptions.assume import Predicate

from ._rows import f, for_all, x, y

RULES = (
    # Polar where finite
    #     a point of the Riemann surface of the logarithm
    for_all((exp_polar, polar_lift),
        Q.finite(x) >> Predicate('polar')(f(x))),

    # Polar where finite, for a positive period
    #     principal_branch(x, p) of the period p; principal_branch(x, oo) == x
    for_all((principal_branch,),
        (Q.finite(x) & Q.positive(y)) >> Predicate('polar')(f(x, y))),

    # Positive on the reals
    #     exp_polar(t) == exp(t) for real t
    for_all((exp_polar,),
        Q.real(x) >> Q.positive(f(x))),

    # Rational at 0
    #     exp_polar(0) == 1
    for_all((exp_polar,),
        Q.zero(x) >> Q.rational(f(x))),

    # Lindemann
    #     exp(a) is transcendental for an algebraic a != 0
    #     (Lindemann-Weierstrass), here for a real a only
    for_all((exp_polar,),
        (Q.real(x) & Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(f(x))),
)
