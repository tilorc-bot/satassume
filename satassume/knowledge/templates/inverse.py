"""``asin``, ``acos``, ``atan``, ``acot``, ``asec``, ``acsc``, ``asinh``,
``acosh``, ``atanh``, ``acoth``, ``asech`` and ``acsch``.

Values at the special points follow SymPy's conventions: ``acsch(0) ==
asec(0) == acsc(0) == zoo``, ``acosh(+-oo) == oo``, ``atanh(+-1) == +-oo``,
``atanh(+-oo) == -+I*pi/2``, ``acoth(+-1) == +-oo``, ``acoth(0) ==
I*pi/2``, ``asech(0) == oo``, ``asech(+-oo) == I*pi/2``, ``acot(0) ==
pi/2``, ``atan(+-oo) == +-pi/2``, and ``acoth``, ``acsch``, ``acsc`` are 0
and ``asec`` is ``pi/2`` at every infinity (``acoth(1 + oo*I)`` is left
unevaluated: no claim there).  Branch cuts follow the principal branches
(``acosh(x) == log(x + sqrt(x + 1)*sqrt(x - 1))``, ``atanh(x) == (log(1 +
x) - log(1 - x))/2``, ``acoth(x) == atanh(1/x)``, ``asech(x) ==
acosh(1/x)``, ``acsch(x) == asinh(1/x)``, ``asec(x) == acos(1/x)``,
``acsc(x) == asin(1/x)``); the rows only use on which side of a cut a
value lies, never the sign of its imaginary part on the cut.

A row comparing ``argument`` with 1 or -1 also states its sign
(``Q.positive(argument) & Q.lt(argument, 1)``): to the engine
``argument`` and ``argument - 1`` are separate terms, and a template's
block must be satisfiable whatever facts its terms are given
(``tests/test_totality.py``).
"""
from __future__ import annotations

from sympy import (
    Equivalent, Q, acos, acosh, acot, acoth, acsc, acsch, asec, asech, asin, asinh, atan, atanh,
)

from ._rows import argument, closed, f, for_all

RULES = (
    # No poles
    #     finite at every finite point: branch cuts, but no poles
    for_all((asin, acos, asinh, acosh),
        closed(f, Q.finite) & closed(f, Q.complex)),

    # Infinite at infinity
    #     asinh(+-oo) == +-oo, asinh(zoo) == zoo, acosh(+-oo) == oo
    for_all((asinh, acosh),
        closed(f, Q.infinite)),

    # Complex but at 1 and -1
    #     atanh(+-1) == acoth(+-1) == +-oo
    for_all((atanh, acoth),
        (Q.complex(argument) & Q.ne(argument, 1) & Q.ne(argument, -1)) >> Q.complex(f(argument))),

    # Complex but at 0
    #     asech(0) == oo, acsch(0) == asec(0) == acsc(0) == zoo
    for_all((asech, acsch, asec, acsc),
        (Q.complex(argument) & ~Q.zero(argument)) >> Q.complex(f(argument))),

    # Zero only at 0
    for_all((asin, atan, asinh, atanh),
        Equivalent(Q.zero(f(argument)), Q.zero(argument))),

    # Zero only at 1
    #     acos(1) == acosh(1) == 0, asech(x) == acosh(1/x), asec(x) == acos(1/x)
    for_all((acos, acosh, asech, asec),
        Equivalent(Q.zero(f(argument)), Q.eq(argument, 1))),

    # Zero only at infinity
    #     acsch(x) == asinh(1/x), acsc(x) == asin(1/x), 0 at every infinity
    for_all((acsch, acsc),
        Equivalent(Q.zero(f(argument)), Q.infinite(argument))),

    # Zero at a real infinity
    #     acot(+-oo) == acoth(+-oo) == 0
    for_all((acot, acoth),
        (Q.infinite(argument) & Q.extended_real(argument)) >> Q.zero(f(argument))),

    # Pole at 0
    #     the value is zoo
    for_all((acsch, asec, acsc),
        Q.zero(argument) >> (Q.infinite(f(argument)) & ~Q.extended_real(f(argument)))),

    # Lindemann
    #     g(g^-1(a)) == a for the trigonometric or hyperbolic g: a value
    #     b != 0 at an algebraic a, if algebraic, would make g(b) transcendental
    for_all((asin, acos, atan, asec, acsc, asinh, acosh, atanh, acoth, asech, acsch),
        (Q.algebraic(argument) & Q.complex(f(argument)) & ~Q.zero(f(argument)))
        >> Q.transcendental(f(argument))),

    # Imaginary axis
    #     asin(I*t) == I*asinh(t), atanh(I*t) == I*atan(t),
    #     acoth(I*t) == -I*atan(1/t), acsc(I*t) == -I*asinh(1/t)
    for_all((asin, atanh, acoth, acsc),
        closed(f, Q.imaginary)),

    # Not real on the imaginary axis
    #     atan(I*t) == I*atanh(t), asinh(I*t) == I*asin(t): imaginary, or
    #     infinite, or with a real part +-pi/2
    for_all((atan, acot, asinh, acsch, acosh, asech, asec),
        Q.imaginary(argument) >> ~Q.extended_real(f(argument))),

    # Not imaginary on the imaginary axis
    #     acosh(I*t) == asinh(|t|) +- I*pi/2, asec(I*t) == pi/2 + I*asinh(1/t)
    for_all((acosh, asech, asec),
        Q.imaginary(argument) >> ~Q.imaginary(f(argument))),

    # Imaginary at a real infinity
    #     atanh(+-oo) == -+I*pi/2, asech(+-oo) == I*pi/2
    for_all((atanh, asech),
        (Q.infinite(argument) & Q.extended_real(argument)) >> Q.imaginary(f(argument))),

    # Infinite at 1 and -1
    #     atanh(+-1) == acoth(+-1) == +-oo
    for_all((atanh, acoth),
        (Q.positive(argument) & Q.eq(argument, 1)) >> (
            Q.infinite(f(argument)) & Q.extended_positive(f(argument))),
        (Q.negative(argument) & Q.eq(argument, -1)) >> (
            Q.infinite(f(argument)) & Q.extended_negative(f(argument)))),

    # Not real on (-1, 1)
    #     acoth(x) == atanh(1/x), asec(x) == acos(1/x), acsc(x) == asin(1/x)
    #     with |1/x| > 1 (acoth(0) == I*pi/2, asec(0) == acsc(0) == zoo)
    for_all((acoth, asec, acsc),
        (Q.real(argument) & Q.gt(argument, -1) & Q.lt(argument, 1))
        >> ~Q.extended_real(f(argument))),

    # asin: sign where real
    #     odd and increasing on [-1, 1]
    for_all((asin,),
        Q.real(f(argument)) >> (
            Equivalent(Q.positive(f(argument)), Q.positive(argument))
            & Equivalent(Q.negative(f(argument)), Q.negative(argument)))),

    # asin: real on [0, 1]
    for_all((asin,),
        (Q.nonnegative(argument) & Q.le(argument, 1)) >> Q.real(f(argument))),

    # acos: in [0, pi] where real
    #     real only on the reals, x == cos(acos(x)); acos(0) == pi/2
    for_all((acos,),
        Q.real(f(argument)) >> (Q.real(argument) & Q.nonnegative(f(argument))),
        Q.zero(argument) >> Q.positive(f(argument))),

    # atan: sign of the argument
    #     odd and increasing: atan(+-oo) == +-pi/2
    for_all((atan,),
        Q.extended_real(argument) >> (
            Equivalent(Q.positive(f(argument)), Q.extended_positive(argument))
            & Equivalent(Q.negative(f(argument)), Q.extended_negative(argument)))),

    # asinh: sign of the argument
    #     odd and increasing: asinh(+-oo) == +-oo
    for_all((asinh,),
        Q.extended_real(argument) >> (
            Equivalent(Q.extended_positive(f(argument)), Q.extended_positive(argument))
            & Equivalent(Q.extended_negative(f(argument)), Q.extended_negative(argument)))),

    # acot: sign on the reals
    #     acot(t) == atan(1/t) for t != 0, acot(0) == pi/2
    for_all((acot,),
        Q.nonnegative(argument) >> Q.positive(f(argument)),
        Q.negative(argument) >> Q.negative(f(argument))),

    # acot: Lindemann
    #     not algebraic at an algebraic point: acot(+-I) is infinite, else
    #     as above
    for_all((acot,),
        Q.algebraic(argument) >> ~Q.algebraic(f(argument))),

    # acosh on the reals
    #     positive on (1, oo]; I*acos(x) on [-1, 1), log(-x + sqrt(x**2 - 1))
    #     + I*pi below
    for_all((acosh,),
        (Q.real(argument) & Q.gt(argument, 1)) >> Q.positive(f(argument)),
        (Q.real(argument) & Q.lt(argument, 1)) >> ~Q.extended_real(f(argument)),
        (Q.infinite(argument) & Q.extended_real(argument)) >> Q.extended_positive(f(argument))),

    # atanh on the reals
    #     real on (-1, 1) with the sign of the argument, not real beyond
    for_all((atanh,),
        (Q.gt(argument, -1) & Q.lt(argument, 1)) >> Q.real(f(argument)),
        (Q.positive(argument) & Q.lt(argument, 1)) >> Q.positive(f(argument)),
        (Q.negative(argument) & Q.gt(argument, -1)) >> Q.negative(f(argument)),
        (Q.positive(argument) & Q.gt(argument, 1)) >> ~Q.extended_real(f(argument)),
        (Q.negative(argument) & Q.lt(argument, -1)) >> ~Q.extended_real(f(argument))),

    # acoth on the reals
    #     acoth(x) == atanh(1/x): the sign of the argument beyond 1 and -1;
    #     0 only at an infinity
    for_all((acoth,),
        (Q.positive(argument) & Q.gt(argument, 1)) >> Q.positive(f(argument)),
        (Q.negative(argument) & Q.lt(argument, -1)) >> Q.negative(f(argument)),
        Q.zero(f(argument)) >> Q.infinite(argument)),

    # asech on the reals
    #     asech(x) == acosh(1/x): positive on (0, 1), I*acos(1/x) for x > 1,
    #     acosh of a number below 0 for x < 0, asech(0) == oo
    for_all((asech,),
        (Q.positive(argument) & Q.lt(argument, 1)) >> Q.positive(f(argument)),
        (Q.positive(argument) & Q.gt(argument, 1)) >> Q.imaginary(f(argument)),
        Q.negative(argument) >> ~Q.extended_real(f(argument)),
        Q.zero(argument) >> (Q.infinite(f(argument)) & Q.extended_positive(f(argument)))),

    # acsch: sign of the argument
    #     acsch(x) == asinh(1/x)
    for_all((acsch,),
        Q.positive(argument) >> Q.positive(f(argument)),
        Q.negative(argument) >> Q.negative(f(argument))),

    # asec on the reals
    #     asec(x) == acos(1/x) is in [0, pi] for |x| >= 1, pi/2 at every infinity
    for_all((asec,),
        Q.infinite(argument) >> Q.positive(f(argument)),
        (Q.positive(argument) & Q.ge(argument, 1)) >> Q.nonnegative(f(argument)),
        (Q.negative(argument) & Q.le(argument, -1)) >> Q.positive(f(argument))),

    # acsc on the reals
    #     acsc(x) == asin(1/x) has the sign of x for |x| >= 1
    for_all((acsc,),
        (Q.positive(argument) & Q.ge(argument, 1)) >> Q.positive(f(argument)),
        (Q.negative(argument) & Q.le(argument, -1)) >> Q.negative(f(argument))),
)
