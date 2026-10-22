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

A row comparing ``x`` with an integer keeps the sign of ``x`` the legacy
rule had (``Q.positive(x) & Q.lt(x, 1)``): to the engine ``x`` and ``x -
1`` are separate terms, and a template's block must be satisfiable
whatever facts its terms are given (``tests/test_totality.py``).

``owens_t`` is new in SymPy 1.15; with an older SymPy it is ``None``, and
its statements hold for no function.
"""
from __future__ import annotations

from sympy import (
    Chi, Ci, Ei, Equivalent, Li, Q, Shi, Si, erf, erf2, erfc, erfcinv, erfi, erfinv, expint,
    fresnelc, fresnels, li,
)

from ._rows import closed, f, for_all, x, y

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
        (Q.finite(x) & Q.finite(y)) >> Q.finite(f(x, y)),
        (Q.complex(x) & Q.complex(y)) >> Q.complex(f(x, y))),

    # Complex off 0
    #     a logarithmic singularity at 0 only (principal value)
    for_all((Ei, Ci, Chi),
        (Q.complex(x) & ~Q.zero(x)) >> Q.complex(f(x))),

    # Complex off 1
    #     a logarithmic singularity at 1 only (principal value), li(0) == 0
    for_all((li, Li),
        (Q.complex(x) & Q.ne(x, 1)) >> Q.complex(f(x))),

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

    # Real on the extended reals, in both arguments
    #     erf(+-oo) == +-1
    for_all((erf2,),
        (Q.extended_real(x) & Q.extended_real(y)) >> Q.real(f(x, y))),

    # Real on the positive reals
    for_all((Ei, Ci, Chi),
        Q.positive(x) >> Q.real(f(x))),

    # Real on the positive reals but at 1
    #     li(1) == -oo, Li(x) == li(x) - li(2)
    for_all((li, Li),
        (Q.positive(x) & Q.ne(x, 1)) >> Q.real(f(x))),

    # Zero only at 0
    #     erfinv is the inverse of erf on (-1, 1), and erf(0) == 0
    for_all((erfinv,),
        Equivalent(Q.zero(f(x)), Q.zero(x))),

    # Zero only at 1
    #     erfcinv(z) == erfinv(1 - z)
    for_all((erfcinv,),
        Equivalent(Q.zero(f(x)), Q.eq(x, 1))),

    # Zero at 0
    #     li(0) == 0 (its other zero is the Ramanujan-Soldner constant
    #     1.4513...)
    for_all((li,),
        Q.zero(x) >> Q.zero(f(x))),

    # Zero at (0, 0)
    #     erf2(0, 0) == erf(0) - erf(0)
    for_all((erf2,),
        (Q.zero(x) & Q.zero(y)) >> Q.zero(f(x, y))),

    # Zero at a == 0
    #     owens_t(h, 0) == 0 for a number h (owens_t(nan, 0) is nan)
    for_all((owens_t,),
        (Q.complex(x) & Q.zero(y)) >> Q.zero(f(x, y))),

    # Zero at a real infinite h
    #     owens_t(+-oo, a) == 0: the integrand vanishes
    for_all((owens_t,),
        (Q.infinite(x) & Q.extended_real(x) & Q.extended_real(y)) >> Q.zero(f(x, y))),

    # Of the sign of a
    #     owens_t(h, a) is the integral over (0, a) of
    #     exp(-h**2*(1 + t**2)/2)/(1 + t**2)/(2*pi), positive for real h
    #     (owens_t(h, +-oo) == +-erfc(|h|/sqrt(2))/4), and for h == I*s,
    #     where it is exp(s**2*(1 + t**2)/2)/..., with a finite integral
    #     for a finite a only
    for_all((owens_t,),
        (Q.real(x) & Q.extended_positive(y)) >> Q.positive(f(x, y)),
        (Q.real(x) & Q.extended_negative(y)) >> Q.negative(f(x, y)),
        (Q.imaginary(x) & Q.positive(y)) >> Q.positive(f(x, y)),
        (Q.imaginary(x) & Q.negative(y)) >> Q.negative(f(x, y))),

    # Positive for a real order and a positive argument
    #     expint(nu, z) is the integral over (1, oo) of exp(-z*t)/t**nu
    for_all((expint,),
        (Q.real(x) & Q.positive(y)) >> Q.positive(f(x, y))),

    # Positive on (0, 1)
    #     erf is increasing and of the sign of its argument;
    #     erfcinv(z) == erfinv(1 - z)
    for_all((erfinv, erfcinv),
        (Q.positive(x) & Q.lt(x, 1)) >> Q.positive(f(x))),

    # Negative on (-1, 0)
    for_all((erfinv,),
        (Q.negative(x) & Q.gt(x, -1)) >> Q.negative(f(x))),

    # Negative on (1, 2)
    #     erfcinv(z) == erfinv(1 - z)
    for_all((erfcinv,),
        (Q.positive(x) & Q.gt(x, 1) & Q.lt(x, 2)) >> Q.negative(f(x))),

    # Negative on (0, 1)
    #     1/log(t) < 0 on (0, 1); Li(x) == li(x) - li(2), and li(2) > 0
    for_all((li, Li),
        (Q.positive(x) & Q.lt(x, 1)) >> Q.negative(f(x))),

    # Of the sign of x - 2 beyond 1
    #     Li(x) == li(x) - li(2) increases on (1, oo), Li(2) == 0
    for_all((Li,),
        (Q.real(x) & Q.gt(x, 1) & Q.lt(x, 2)) >> Q.negative(f(x)),
        (Q.real(x) & Q.gt(x, 1) & Q.eq(x, 2)) >> Q.zero(f(x)),
        (Q.real(x) & Q.gt(x, 1) & Q.gt(x, 2)) >> Q.positive(f(x))),

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

    # Infinite at 1 and -1
    #     erfinv(+-1) == +-oo
    for_all((erfinv,),
        (Q.positive(x) & Q.eq(x, 1)) >> (Q.infinite(f(x)) & Q.extended_positive(f(x))),
        (Q.negative(x) & Q.eq(x, -1)) >> (Q.infinite(f(x)) & Q.extended_negative(f(x)))),

    # Infinite at 0 and 2
    #     erfcinv(0) == oo, erfcinv(2) == -oo
    for_all((erfcinv,),
        (Q.zero(x) & Q.lt(x, 1)) >> (Q.infinite(f(x)) & Q.extended_positive(f(x))),
        (Q.positive(x) & Q.gt(x, 1) & Q.eq(x, 2)) >> (
            Q.infinite(f(x)) & Q.extended_negative(f(x)))),

    # -oo at 1
    #     li(1) == -oo, a logarithmic singularity
    for_all((li,),
        (Q.positive(x) & Q.eq(x, 1)) >> (Q.infinite(f(x)) & Q.extended_negative(f(x)))),

    # Infinite at a real infinity
    #     erfi(+-oo) == Shi(+-oo) == +-oo
    for_all((erfi, Shi),
        (Q.infinite(x) & Q.extended_real(x)) >> Q.infinite(f(x))),

    # oo at oo
    for_all((Ei, Chi, li, Li),
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
