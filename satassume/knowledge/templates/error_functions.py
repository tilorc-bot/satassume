"""``erf``, ``erfc``, ``erfi``, the exponential integral ``Ei``, the sine
and cosine integrals ``Si``, ``Ci``, ``Shi``, ``Chi``, and the Fresnel
integrals ``fresnels`` and ``fresnelc``.

Values follow SymPy's conventions: principal values (``Ei``, ``Ci`` and
``Chi`` off the positive reals), the limit at a real infinity
(``erf(+-oo) == +-1``, ``erfc(oo) == 0``, ``erfc(-oo) == 2``,
``erfi(+-oo) == Shi(+-oo) == +-oo``, ``Si(+-oo) == +-pi/2``,
``fresnels(+-oo) == fresnelc(+-oo) == +-1/2``, ``Ei(oo) == oo``,
``Ei(-oo) == 0``, ``Ci(oo) == 0``, ``Ci(-oo) == I*pi``), and
``Chi(+-oo) == oo``, ``Ei(0) == -oo``, ``Ci(0) == Chi(0) == zoo``.
``erf``, ``erfc``, ``erfi`` and the Fresnel integrals are real at some
non-real points (the complex zeros of ``erf``), so a non-real argument off
the imaginary axis gives no claim.
"""
from __future__ import annotations

from sympy import Chi, Ci, Ei, Equivalent, Q, Shi, Si, erf, erfc, erfi, fresnelc, fresnels

from ._rows import closed, f, for_all, x

RULES = (
    # Entire
    #     no poles: finite at every finite point
    for_all((erf, erfc, erfi, Si, Shi, fresnels, fresnelc),
        closed(f, Q.finite) & closed(f, Q.complex)),

    # Complex off 0
    #     a logarithmic singularity at 0 only (principal value)
    for_all((Ei, Ci, Chi),
        (Q.complex(x) & ~Q.zero(x)) >> Q.complex(f(x))),

    # Sign of the argument
    #     odd, and of the sign of the argument on the extended reals:
    #     erf, erfi and Shi increase, Si(t) > 0 and the Fresnel integrals are
    #     positive for t > 0 (the lobes of the integrand shrink)
    for_all((erf, erfi, Si, Shi, fresnels, fresnelc),
        Q.extended_real(x) >> (
            Equivalent(Q.extended_positive(f(x)), Q.extended_positive(x))
            & Equivalent(Q.extended_negative(f(x)), Q.extended_negative(x))
            & Equivalent(Q.zero(f(x)), Q.zero(x)))),

    # Real on the extended reals
    #     Si(+-oo) == +-pi/2
    for_all((Si,),
        Q.extended_real(x) >> Q.real(f(x))),

    # Real on the positive reals
    for_all((Ei, Ci, Chi),
        Q.positive(x) >> Q.real(f(x))),

    # Positive on the reals
    #     erfc(t) == 1 - erf(t) is in (0, 2)
    for_all((erfc,),
        Q.real(x) >> Q.positive(f(x))),

    # Negative on the nonpositive reals
    #     Ei(t) == -E1(-t) < 0 for t < 0, Ei(0) == -oo
    for_all((Ei,),
        Q.nonpositive(x) >> Q.extended_negative(f(x))),

    # Not real on the negative reals
    #     Ci(-t) == Ci(t) + I*pi and Chi(-t) == Chi(t) + I*pi for t > 0
    for_all((Ci, Chi),
        Q.negative(x) >> ~Q.extended_real(f(x))),

    # Not an integer off 0
    #     erf(t) is in (-1, 1), erfc(t) in (0, 2), the Fresnel integrals in
    #     (-1, 1), and only erf(0) == fresnels(0) == fresnelc(0) == 0 and
    #     erfc(0) == 1
    for_all((erf, erfc, fresnels, fresnelc),
        (Q.real(x) & ~Q.zero(x)) >> ~Q.integer(f(x))),

    # One at 0
    #     1 is odd, and neither prime nor composite
    for_all((erfc,),
        Q.zero(x) >> (Q.odd(f(x)) & ~Q.prime(f(x)) & ~Q.composite(f(x)))),

    # Infinite at 0
    #     Ei(0) == -oo, Ci(0) == Chi(0) == zoo
    for_all((Ei, Ci, Chi),
        Q.zero(x) >> Q.infinite(f(x))),

    # Infinite at a real infinity
    #     erfi(+-oo) == Shi(+-oo) == +-oo
    for_all((erfi, Shi),
        (Q.infinite(x) & Q.extended_real(x)) >> Q.infinite(f(x))),

    # oo at oo
    for_all((Ei, Chi),
        (Q.infinite(x) & Q.extended_positive(x)) >> (
            Q.infinite(f(x)) & Q.extended_positive(f(x)))),

    # oo at -oo
    #     Chi(-oo) == oo, SymPy's value: Chi(-t) == Chi(t) + I*pi for t > 0
    for_all((Chi,),
        (Q.infinite(x) & Q.extended_negative(x)) >> (
            Q.infinite(f(x)) & Q.extended_positive(f(x)))),

    # Zero at oo
    for_all((erfc, Ci),
        (Q.infinite(x) & Q.extended_positive(x)) >> Q.zero(f(x))),

    # Zero at -oo
    for_all((Ei,),
        (Q.infinite(x) & Q.extended_negative(x)) >> Q.zero(f(x))),

    # One at a real infinity, up to sign
    #     erf(+-oo) == +-1
    for_all((erf,),
        (Q.infinite(x) & Q.extended_real(x)) >> Q.odd(f(x))),

    # Two at -oo
    #     erfc(-oo) == 2
    for_all((erfc,),
        (Q.infinite(x) & Q.extended_negative(x)) >> (Q.even(f(x)) & Q.positive(f(x)))),

    # One half at a real infinity, up to sign
    #     fresnels(+-oo) == fresnelc(+-oo) == +-1/2
    for_all((fresnels, fresnelc),
        (Q.infinite(x) & Q.extended_real(x)) >> (Q.rational(f(x)) & ~Q.integer(f(x)))),

    # I*pi at -oo
    #     Ci(-oo) == I*pi
    for_all((Ci,),
        (Q.infinite(x) & Q.extended_negative(x)) >> Q.imaginary(f(x))),

    # Imaginary axis
    #     erf(I*t) == I*erfi(t), erfi(I*t) == I*erf(t), Si(I*t) == I*Shi(t),
    #     Shi(I*t) == I*Si(t), fresnels(I*t) == -I*fresnels(t),
    #     fresnelc(I*t) == I*fresnelc(t), nonzero for t != 0
    for_all((erf, erfi, Si, Shi, fresnels, fresnelc),
        closed(f, Q.imaginary)),

    # erfc on the imaginary axis
    #     erfc(I*t) == 1 - I*erfi(t), and erfi(t) is real and nonzero for
    #     real t != 0
    for_all((erfc,),
        Q.imaginary(x) >> (~Q.extended_real(f(x)) & ~Q.imaginary(f(x)))),
)
