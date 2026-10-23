"""``sinh``, ``cosh``, ``tanh``, ``coth``, ``sech`` and ``csch``.

Values follow SymPy's conventions: ``zoo`` at a pole (``coth(0)``,
``csch(0)``), the limit at a real infinity (``sinh(+-oo) == +-oo``,
``cosh(+-oo) == oo``, ``tanh(+-oo) == coth(+-oo) == +-1``, ``sech(+-oo) ==
csch(+-oo) == 0``), no claim at a non-real infinite argument.
"""
from __future__ import annotations

from sympy import Equivalent, Q, cosh, coth, csch, sech, sinh, tanh

from ._rows import argument, closed, f, for_all, x

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
        Q.extended_real(x) >> (
            Equivalent(Q.extended_positive(f(x)), Q.extended_positive(x))
            & Equivalent(Q.extended_negative(f(x)), Q.extended_negative(x))
            & Equivalent(Q.zero(f(x)), Q.zero(x)))),

    # Sign of the argument, at infinity too
    #     coth(t) > 1 for t > 0, coth(+-oo) == +-1
    for_all((coth,),
        Q.extended_positive(x) >> Q.positive(f(x)),
        Q.extended_negative(x) >> Q.negative(f(x))),

    # Sign of a finite argument
    #     csch(t) == 1/sinh(t)
    for_all((csch,),
        Q.positive(x) >> Q.positive(f(x)),
        Q.negative(x) >> Q.negative(f(x))),

    # Real on the extended reals
    #     no pole on the reals, and tanh(+-oo) == +-1
    for_all((tanh,),
        Q.extended_real(x) >> Q.real(f(x))),

    # Positive on the extended reals
    #     cosh(t) >= 1, cosh(+-oo) == oo
    for_all((cosh,),
        Q.extended_real(x) >> Q.extended_positive(f(x))),

    # Positive on the reals
    #     sech(t) == 1/cosh(t) is in (0, 1]
    for_all((sech,),
        Q.real(x) >> Q.positive(f(x))),

    # Infinite at a real infinity
    #     sinh(+-oo) == +-oo; cosh(+-oo) == oo too, but cosh's block for an
    #     argument r + I*pi*c*s does not relate the argument to r, and would
    #     not be total with it (tests/test_totality.py)
    for_all((sinh,),
        (Q.infinite(x) & Q.extended_real(x)) >> Q.infinite(f(x))),

    # Zero at a real infinity
    for_all((sech, csch),
        (Q.infinite(x) & Q.extended_real(x)) >> Q.zero(f(x))),

    # Nonvanishing
    #     1/f is entire
    for_all((sech, csch),
        Q.complex(x) >> ~Q.zero(f(x))),

    # Lindemann
    #     f(a) == R(exp(a)), R rational with algebraic coefficients and not
    #     constant, no pole at an algebraic a != 0: an algebraic value b would
    #     make exp(a) a root of R - b, against Lindemann-Weierstrass
    for_all((sinh, cosh, tanh, coth, sech, csch),
        (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(f(x))),

    # One at 0
    #     1 is odd, and neither prime nor composite
    for_all((cosh, sech),
        Q.zero(x) >> (Q.odd(f(x)) & ~Q.prime(f(x)) & ~Q.composite(f(x)))),

    # Pole at 0
    #     the value is zoo
    for_all((coth, csch),
        Q.zero(x) >> (Q.infinite(f(x)) & ~Q.extended_real(f(x)))),

    # Imaginary axis
    #     sinh(I*t) == I*sin(t), tanh(I*t) == I*tan(t), coth(I*t) == -I*cot(t),
    #     csch(I*t) == -I*csc(t): imaginary, 0 or zoo
    for_all((sinh, tanh, coth, csch),
        (Q.imaginary(x) & Q.finite(f(x))) >> (Q.imaginary(f(x)) | Q.zero(f(x))),
        Q.imaginary(x) >> (~Q.extended_real(f(x)) | Q.zero(f(x)))),

    # Real on the imaginary axis
    #     cosh(I*t) == cos(t), sech(I*t) == sec(t) (zoo at a pole)
    for_all((cosh, sech),
        (Q.imaginary(x) & Q.finite(f(x))) >> Q.real(f(x))),
)
