"""``sinh``, ``cosh``, ``tanh``, ``coth``, ``sech`` and ``csch``.

Values follow SymPy's conventions: ``zoo`` at a pole (``coth(0)``,
``csch(0)``), the limit at a real infinity (``sinh(+-oo) == +-oo``,
``cosh(+-oo) == oo``, ``tanh(+-oo) == coth(+-oo) == +-1``, ``sech(+-oo) ==
csch(+-oo) == 0``), no claim at a non-real infinite argument.
"""
from __future__ import annotations

from sympy import Equivalent, Q, cosh, coth, csch, sech, sinh, tanh

from ._rows import argument, closed, f, for_all

RULES = (
    # Entire
    #     no poles: finite at every finite point
    for_all((sinh, cosh),
        closed(f, Q.finite) & closed(f, Q.complex)),

    # Complex where finite
    #     meromorphic: a number wherever it is finite (zoo at a pole)
    for_all((tanh, coth, sech, csch),
        Q.finite(f(argument)) >> closed(f, Q.complex)),

    # Sign of the argument
    #     odd and increasing on the extended reals: sinh(+-oo) == +-oo,
    #     tanh(+-oo) == +-1
    for_all((sinh, tanh),
        Q.extended_real(argument) >> (
            Equivalent(Q.extended_positive(f(argument)), Q.extended_positive(argument))
            & Equivalent(Q.extended_negative(f(argument)), Q.extended_negative(argument))
            & Equivalent(Q.zero(f(argument)), Q.zero(argument)))),

    # Sign of the argument, at infinity too
    #     coth(t) > 1 for t > 0, coth(+-oo) == +-1
    for_all((coth,),
        Q.extended_positive(argument) >> Q.positive(f(argument)),
        Q.extended_negative(argument) >> Q.negative(f(argument))),

    # Sign of a finite argument
    #     csch(t) == 1/sinh(t)
    for_all((csch,),
        Q.positive(argument) >> Q.positive(f(argument)),
        Q.negative(argument) >> Q.negative(f(argument))),

    # Real on the extended reals
    #     no pole on the reals, and tanh(+-oo) == +-1
    for_all((tanh,),
        Q.extended_real(argument) >> Q.real(f(argument))),

    # Positive on the extended reals
    #     cosh(t) >= 1, cosh(+-oo) == oo
    for_all((cosh,),
        Q.extended_real(argument) >> Q.extended_positive(f(argument))),

    # Positive on the reals
    #     sech(t) == 1/cosh(t) is in (0, 1]
    for_all((sech,),
        Q.real(argument) >> Q.positive(f(argument))),

    # Infinite at a real infinity
    #     sinh(+-oo) == +-oo; cosh(+-oo) == oo too, but cosh's block for an
    #     argument r + I*pi*c*s does not relate the argument to r, and would
    #     not be total with it (tests/test_totality.py)
    for_all((sinh,),
        (Q.infinite(argument) & Q.extended_real(argument)) >> Q.infinite(f(argument))),

    # Zero at a real infinity
    for_all((sech, csch),
        (Q.infinite(argument) & Q.extended_real(argument)) >> Q.zero(f(argument))),

    # Nonvanishing
    #     1/f is entire
    for_all((sech, csch),
        Q.complex(argument) >> ~Q.zero(f(argument))),

    # Lindemann
    #     f(a) == R(exp(a)), R rational with algebraic coefficients and not
    #     constant, no pole at an algebraic a != 0: an algebraic value b would
    #     make exp(a) a root of R - b, against Lindemann-Weierstrass
    for_all((sinh, cosh, tanh, coth, sech, csch),
        (Q.algebraic(argument) & ~Q.zero(argument)) >> Q.transcendental(f(argument))),

    # One at 0
    #     1 is odd, and neither prime nor composite
    for_all((cosh, sech),
        Q.zero(argument) >> (
            Q.odd(f(argument)) & ~Q.prime(f(argument)) & ~Q.composite(f(argument)))),

    # Pole at 0
    #     the value is zoo
    for_all((coth, csch),
        Q.zero(argument) >> (Q.infinite(f(argument)) & ~Q.extended_real(f(argument)))),

    # Imaginary axis
    #     sinh(I*t) == I*sin(t), tanh(I*t) == I*tan(t), coth(I*t) == -I*cot(t),
    #     csch(I*t) == -I*csc(t): imaginary, 0 or zoo
    for_all((sinh, tanh, coth, csch),
        (Q.imaginary(argument) & Q.finite(f(argument))) >> (
            Q.imaginary(f(argument)) | Q.zero(f(argument))),
        Q.imaginary(argument) >> (~Q.extended_real(f(argument)) | Q.zero(f(argument)))),

    # Real on the imaginary axis
    #     cosh(I*t) == cos(t), sech(I*t) == sec(t) (zoo at a pole)
    for_all((cosh, sech),
        (Q.imaginary(argument) & Q.finite(f(argument))) >> Q.real(f(argument))),
)
