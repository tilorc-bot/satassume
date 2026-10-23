"""``erf``, ``erfc``, ``erfi``, ``erf2(x, y) == erf(y) - erf(x)``, the
inverses ``erfinv`` and ``erfcinv``, the exponential integrals ``Ei`` and
``expint``, the logarithmic integrals ``li`` and ``Li``, the sine and
cosine integrals ``Si``, ``Ci``, ``Shi``, ``Chi``, the Fresnel integrals
``fresnels`` and ``fresnelc``, and Owen's T function ``owens_t``.

Values follow SymPy's conventions: principal values (``Ei``, ``Ci`` and
``Chi`` off the positive reals), the limit at a real infinity
(``erf(+-oo) == +-1``, ``erfc(oo) == 0``, ``erfc(-oo) == 2``,
``erfi(+-oo) == Shi(+-oo) == +-oo``, ``Si(+-oo) == +-pi/2``,
``fresnels(+-oo) == fresnelc(+-oo) == +-1/2``, ``Ei(oo) == li(oo) ==
Li(oo) == oo``, ``Ei(-oo) == 0``, ``Ci(oo) == 0``, ``Ci(-oo) == I*pi``),
the limit at the ends of an interval (``erfinv(+-1) == +-oo``,
``erfcinv(0) == oo``, ``erfcinv(2) == -oo``, ``li(1) == -oo``), and
``Chi(+-oo) == oo``, ``Ei(0) == -oo``, ``Ci(0) == Chi(0) == zoo``,
``owens_t(+-oo, a) == 0``.
``erf``, ``erfc``, ``erfi`` and the Fresnel integrals are real at some
non-real points (the complex zeros of ``erf``), so a non-real argument off
the imaginary axis gives no claim.

A row comparing ``argument`` with an integer keeps the sign of
``argument`` the legacy rule had (``Q.positive(argument) & Q.lt(argument,
1)``): to the engine ``argument`` and ``argument - 1`` are separate terms,
and a template's block must be satisfiable whatever facts its terms are
given (``tests/test_totality.py``).

``owens_t`` is new in SymPy 1.15; with an older SymPy it is ``None``, and
its statements hold for no function.
"""
from __future__ import annotations

from sympy import (
    Chi, Ci, Ei, Equivalent, Li, Q, Shi, Si, erf, erf2, erfc, erfcinv, erfi, erfinv, expint,
    fresnelc, fresnels, li,
)

from ._rows import argument, closed, f, for_all, lower, order, upper

try:  # new in SymPy 1.15
    from sympy.functions.special.error_functions import owens_t
except ImportError:  # pragma: no cover - depends on the SymPy version
    owens_t = None

RULES = (
    # Entire
    #     no poles: finite at every finite point
    for_all((erf, erfc, erfi, Si, Shi, fresnels, fresnelc),
        closed(f, Q.finite) & closed(f, Q.complex)),

    # Entire in both arguments
    #     erf2(x, y) == erf(y) - erf(x)
    for_all((erf2,),
        (Q.finite(lower) & Q.finite(upper)) >> Q.finite(f(lower, upper)),
        (Q.complex(lower) & Q.complex(upper)) >> Q.complex(f(lower, upper))),

    # Complex off 0
    #     a logarithmic singularity at 0 only (principal value)
    for_all((Ei, Ci, Chi),
        (Q.complex(argument) & ~Q.zero(argument)) >> Q.complex(f(argument))),

    # Complex off 1
    #     a logarithmic singularity at 1 only (principal value), li(0) == 0
    for_all((li, Li),
        (Q.complex(argument) & Q.ne(argument, 1)) >> Q.complex(f(argument))),

    # Sign of the argument
    #     odd, and of the sign of the argument on the extended reals:
    #     erf, erfi and Shi increase, Si(t) > 0 and the Fresnel integrals are
    #     positive for t > 0 (the lobes of the integrand shrink)
    for_all((erf, erfi, Si, Shi, fresnels, fresnelc),
        Q.extended_real(argument) >> (
            Equivalent(Q.extended_positive(f(argument)), Q.extended_positive(argument))
            & Equivalent(Q.extended_negative(f(argument)), Q.extended_negative(argument))
            & Equivalent(Q.zero(f(argument)), Q.zero(argument)))),

    # Real on the extended reals
    #     Si(+-oo) == +-pi/2
    for_all((Si,),
        Q.extended_real(argument) >> Q.real(f(argument))),

    # Real on the extended reals, in both arguments
    #     erf(+-oo) == +-1
    for_all((erf2,),
        (Q.extended_real(lower) & Q.extended_real(upper)) >> Q.real(f(lower, upper))),

    # Real on the positive reals
    for_all((Ei, Ci, Chi),
        Q.positive(argument) >> Q.real(f(argument))),

    # Real on the positive reals but at 1
    #     li(1) == -oo, Li(x) == li(x) - li(2)
    for_all((li, Li),
        (Q.positive(argument) & Q.ne(argument, 1)) >> Q.real(f(argument))),

    # Zero only at 0
    #     erfinv is the inverse of erf on (-1, 1), and erf(0) == 0
    for_all((erfinv,),
        Equivalent(Q.zero(f(argument)), Q.zero(argument))),

    # Zero only at 1
    #     erfcinv(z) == erfinv(1 - z)
    for_all((erfcinv,),
        Equivalent(Q.zero(f(argument)), Q.eq(argument, 1))),

    # Zero at 0
    #     li(0) == 0 (its other zero is the Ramanujan-Soldner constant
    #     1.4513...)
    for_all((li,),
        Q.zero(argument) >> Q.zero(f(argument))),

    # Zero at (0, 0)
    #     erf2(0, 0) == erf(0) - erf(0)
    for_all((erf2,),
        (Q.zero(lower) & Q.zero(upper)) >> Q.zero(f(lower, upper))),

    # Zero at upper == 0
    #     owens_t(h, 0) == 0 for a number h (owens_t(nan, 0) is nan)
    for_all((owens_t,),
        (Q.complex(argument) & Q.zero(upper)) >> Q.zero(f(argument, upper))),

    # Zero at a real infinite argument
    #     owens_t(+-oo, a) == 0: the integrand vanishes
    for_all((owens_t,),
        (Q.infinite(argument) & Q.extended_real(argument) & Q.extended_real(upper))
        >> Q.zero(f(argument, upper))),

    # Of the sign of the upper limit
    #     owens_t(h, a) is the integral over (0, a) of
    #     exp(-h**2*(1 + t**2)/2)/(1 + t**2)/(2*pi), positive for real h
    #     (owens_t(h, +-oo) == +-erfc(|h|/sqrt(2))/4), and for h == I*s,
    #     where it is exp(s**2*(1 + t**2)/2)/..., with a finite integral
    #     for a finite a only
    for_all((owens_t,),
        (Q.real(argument) & Q.extended_positive(upper)) >> Q.positive(f(argument, upper)),
        (Q.real(argument) & Q.extended_negative(upper)) >> Q.negative(f(argument, upper)),
        (Q.imaginary(argument) & Q.positive(upper)) >> Q.positive(f(argument, upper)),
        (Q.imaginary(argument) & Q.negative(upper)) >> Q.negative(f(argument, upper))),

    # Positive for a real order and a positive argument
    #     expint(nu, z) is the integral over (1, oo) of exp(-z*t)/t**nu
    for_all((expint,),
        (Q.real(order) & Q.positive(argument)) >> Q.positive(f(order, argument))),

    # Positive on (0, 1)
    #     erf is increasing and of the sign of its argument;
    #     erfcinv(z) == erfinv(1 - z)
    for_all((erfinv, erfcinv),
        (Q.positive(argument) & Q.lt(argument, 1)) >> Q.positive(f(argument))),

    # Negative on (-1, 0)
    for_all((erfinv,),
        (Q.negative(argument) & Q.gt(argument, -1)) >> Q.negative(f(argument))),

    # Negative on (1, 2)
    #     erfcinv(z) == erfinv(1 - z)
    for_all((erfcinv,),
        (Q.positive(argument) & Q.gt(argument, 1) & Q.lt(argument, 2)) >> Q.negative(f(argument))),

    # Negative on (0, 1)
    #     1/log(t) < 0 on (0, 1); Li(x) == li(x) - li(2), and li(2) > 0
    for_all((li, Li),
        (Q.positive(argument) & Q.lt(argument, 1)) >> Q.negative(f(argument))),

    # Of the sign of argument - 2 beyond 1
    #     Li(x) == li(x) - li(2) increases on (1, oo), Li(2) == 0
    for_all((Li,),
        (Q.real(argument) & Q.gt(argument, 1) & Q.lt(argument, 2)) >> Q.negative(f(argument)),
        (Q.real(argument) & Q.gt(argument, 1) & Q.eq(argument, 2)) >> Q.zero(f(argument)),
        (Q.real(argument) & Q.gt(argument, 1) & Q.gt(argument, 2)) >> Q.positive(f(argument))),

    # Positive on the reals
    #     erfc(t) == 1 - erf(t) is in (0, 2)
    for_all((erfc,),
        Q.real(argument) >> Q.positive(f(argument))),

    # Negative on the nonpositive reals
    #     Ei(t) == -E1(-t) < 0 for t < 0, Ei(0) == -oo
    for_all((Ei,),
        Q.nonpositive(argument) >> Q.extended_negative(f(argument))),

    # Not real on the negative reals
    #     Ci(-t) == Ci(t) + I*pi and Chi(-t) == Chi(t) + I*pi for t > 0
    for_all((Ci, Chi),
        Q.negative(argument) >> ~Q.extended_real(f(argument))),

    # Not an integer off 0
    #     erf(t) is in (-1, 1), erfc(t) in (0, 2), the Fresnel integrals in
    #     (-1, 1), and only erf(0) == fresnels(0) == fresnelc(0) == 0 and
    #     erfc(0) == 1
    for_all((erf, erfc, fresnels, fresnelc),
        (Q.real(argument) & ~Q.zero(argument)) >> ~Q.integer(f(argument))),

    # One at 0
    #     1 is odd, and neither prime nor composite
    for_all((erfc,),
        Q.zero(argument) >> (
            Q.odd(f(argument)) & ~Q.prime(f(argument)) & ~Q.composite(f(argument)))),

    # Infinite at 0
    #     Ei(0) == -oo, Ci(0) == Chi(0) == zoo
    for_all((Ei, Ci, Chi),
        Q.zero(argument) >> Q.infinite(f(argument))),

    # Infinite at 1 and -1
    #     erfinv(+-1) == +-oo
    for_all((erfinv,),
        (Q.positive(argument) & Q.eq(argument, 1)) >> (
            Q.infinite(f(argument)) & Q.extended_positive(f(argument))),
        (Q.negative(argument) & Q.eq(argument, -1)) >> (
            Q.infinite(f(argument)) & Q.extended_negative(f(argument)))),

    # Infinite at 0 and 2
    #     erfcinv(0) == oo, erfcinv(2) == -oo
    for_all((erfcinv,),
        (Q.zero(argument) & Q.lt(argument, 1)) >> (
            Q.infinite(f(argument)) & Q.extended_positive(f(argument))),
        (Q.positive(argument) & Q.gt(argument, 1) & Q.eq(argument, 2)) >> (
            Q.infinite(f(argument)) & Q.extended_negative(f(argument)))),

    # -oo at 1
    #     li(1) == -oo, a logarithmic singularity
    for_all((li,),
        (Q.positive(argument) & Q.eq(argument, 1)) >> (
            Q.infinite(f(argument)) & Q.extended_negative(f(argument)))),

    # Infinite at a real infinity
    #     erfi(+-oo) == Shi(+-oo) == +-oo
    for_all((erfi, Shi),
        (Q.infinite(argument) & Q.extended_real(argument)) >> Q.infinite(f(argument))),

    # oo at oo
    for_all((Ei, Chi, li, Li),
        (Q.infinite(argument) & Q.extended_positive(argument)) >> (
            Q.infinite(f(argument)) & Q.extended_positive(f(argument)))),

    # oo at -oo
    #     Chi(-oo) == oo, SymPy's value: Chi(-t) == Chi(t) + I*pi for t > 0
    for_all((Chi,),
        (Q.infinite(argument) & Q.extended_negative(argument)) >> (
            Q.infinite(f(argument)) & Q.extended_positive(f(argument)))),

    # Zero at oo
    for_all((erfc, Ci),
        (Q.infinite(argument) & Q.extended_positive(argument)) >> Q.zero(f(argument))),

    # Zero at -oo
    for_all((Ei,),
        (Q.infinite(argument) & Q.extended_negative(argument)) >> Q.zero(f(argument))),

    # One at a real infinity, up to sign
    #     erf(+-oo) == +-1
    for_all((erf,),
        (Q.infinite(argument) & Q.extended_real(argument)) >> Q.odd(f(argument))),

    # Two at -oo
    #     erfc(-oo) == 2
    for_all((erfc,),
        (Q.infinite(argument) & Q.extended_negative(argument)) >> (
            Q.even(f(argument)) & Q.positive(f(argument)))),

    # One half at a real infinity, up to sign
    #     fresnels(+-oo) == fresnelc(+-oo) == +-1/2
    for_all((fresnels, fresnelc),
        (Q.infinite(argument) & Q.extended_real(argument)) >> (
            Q.rational(f(argument)) & ~Q.integer(f(argument)))),

    # I*pi at -oo
    #     Ci(-oo) == I*pi
    for_all((Ci,),
        (Q.infinite(argument) & Q.extended_negative(argument)) >> Q.imaginary(f(argument))),

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
        Q.imaginary(argument) >> (~Q.extended_real(f(argument)) & ~Q.imaginary(f(argument)))),
)
