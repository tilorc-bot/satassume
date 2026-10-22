"""``sin``, ``cos``, ``tan``, ``cot``, ``sec`` and ``csc``.

Values follow SymPy's conventions: ``zoo`` at a pole, no claim at an
infinite argument (``sin(oo)`` is ``AccumBounds``; ``real`` and ``complex``
imply ``finite``).
"""
from __future__ import annotations

from sympy import Q, cos, cot, csc, sec, sin, tan

from ._rows import closed, f, for_all, x

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
        Q.finite(f(x)) >> (closed(f, Q.real) & closed(f, Q.complex))),

    # Imaginary axis
    #     sin(I*t) == I*sinh(t), tan(I*t) == I*tanh(t), cot(I*t) == -I*coth(t),
    #     csc(I*t) == -I*csch(t), nonzero for t != 0
    for_all((sin, tan, cot, csc),
        closed(f, Q.imaginary)),

    # Nonvanishing
    #     1/f is entire
    for_all((sec, csc),
        Q.complex(x) >> ~Q.zero(f(x))),

    # Lindemann
    #     f(a) == R(exp(I*a)), R rational with algebraic coefficients and not
    #     constant, no pole at an algebraic a != 0: an algebraic value b would
    #     make exp(I*a) a root of R - b, against Lindemann-Weierstrass
    for_all((sin, cos, tan, cot, sec, csc),
        (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(f(x))),

    # Real only on the reals
    #     Im tan(x + I*y) == sinh(2*y)/(cos(2*x) + cosh(2*y)) != 0 for y != 0,
    #     and cot == 1/tan
    for_all((tan, cot),
        (Q.finite(x) & ~Q.extended_real(x)) >> ~Q.extended_real(f(x))),

    # Zero at 0
    for_all((sin, tan),
        Q.zero(x) >> Q.zero(f(x))),

    # One at 0
    #     1 is odd and positive, and neither prime nor composite
    for_all((cos, sec),
        Q.zero(x) >> (
            Q.odd(f(x)) & Q.positive(f(x)) & ~Q.prime(f(x)) & ~Q.composite(f(x)))),

    # Pole at 0
    #     the value is zoo
    for_all((cot, csc),
        Q.zero(x) >> (Q.infinite(f(x)) & ~Q.extended_real(f(x)))),

    # cos on the imaginary axis
    #     cos(I*t) == cosh(t) > 1
    for_all((cos,),
        Q.imaginary(x) >> Q.positive(f(x))),

    # sec on the imaginary axis
    #     sec(I*t) == 1/cosh(t) is in (0, 1) for real t != 0
    for_all((sec,),
        Q.imaginary(x) >> (Q.positive(f(x)) & Q.noninteger(f(x)))),
)
