"""``sin``, ``cos``, ``tan``, ``cot``, ``sec`` and ``csc``.

Values follow SymPy's conventions: ``zoo`` at a pole, no claim at an
infinite argument (``sin(oo)`` is ``AccumBounds``; ``real`` and ``complex``
imply ``finite``).
"""
from __future__ import annotations

from sympy import Q, cos, cot, csc, sec, sin, tan

from ._rows import argument, closed, f, for_all

RULES = (
    # Entire
    #     no poles: finite at every finite point
    for_all((sin, cos),
        closed(f, Q.finite) & closed(f, Q.complex)),

    # Real on the reals
    for_all((sin, cos),
        closed(f, Q.real)),

    # Real where finite
    #     f(conj z) == conj f(z), and a number wherever it is finite (zoo at a pole)
    for_all((tan, cot, sec, csc),
        Q.finite(f(argument)) >> (closed(f, Q.real) & closed(f, Q.complex))),

    # Imaginary axis
    #     sin(I*t) == I*sinh(t), tan(I*t) == I*tanh(t), cot(I*t) == -I*coth(t),
    #     csc(I*t) == -I*csch(t), nonzero for t != 0
    for_all((sin, tan, cot, csc),
        closed(f, Q.imaginary)),

    # Nonvanishing
    #     1/f is entire
    for_all((sec, csc),
        Q.complex(argument) >> ~Q.zero(f(argument))),

    # Lindemann
    #     f(a) == R(exp(I*a)), R rational with algebraic coefficients and not
    #     constant, no pole at an algebraic a != 0: an algebraic value b would
    #     make exp(I*a) a root of R - b, against Lindemann-Weierstrass
    for_all((sin, cos, tan, cot, sec, csc),
        (Q.algebraic(argument) & ~Q.zero(argument)) >> Q.transcendental(f(argument))),

    # Real only on the reals
    #     Im tan(x + I*y) == sinh(2*y)/(cos(2*x) + cosh(2*y)) != 0 for y != 0,
    #     and cot == 1/tan
    for_all((tan, cot),
        (Q.finite(argument) & ~Q.extended_real(argument)) >> ~Q.extended_real(f(argument))),

    # Zero at 0
    for_all((sin, tan),
        Q.zero(argument) >> Q.zero(f(argument))),

    # One at 0
    #     1 is odd and positive, and neither prime nor composite
    for_all((cos, sec),
        Q.zero(argument) >> (
            Q.odd(f(argument)) & Q.positive(f(argument))
            & ~Q.prime(f(argument)) & ~Q.composite(f(argument)))),

    # Pole at 0
    #     the value is zoo
    for_all((cot, csc),
        Q.zero(argument) >> (Q.infinite(f(argument)) & ~Q.extended_real(f(argument)))),

    # cos on the imaginary axis
    #     cos(I*t) == cosh(t) > 1
    for_all((cos,),
        Q.imaginary(argument) >> Q.positive(f(argument))),

    # sec on the imaginary axis
    #     sec(I*t) == 1/cosh(t) is in (0, 1) for real t != 0
    for_all((sec,),
        Q.imaginary(argument) >> (Q.positive(f(argument)) & Q.noninteger(f(argument)))),
)
