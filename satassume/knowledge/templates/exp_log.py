"""``exp`` and ``log``.

Values follow SymPy's conventions: ``exp(oo) == oo``, ``exp(-oo) == 0``,
no claim at a non-real infinite argument (``exp(zoo)`` is nan); ``log(0)
== zoo``, ``log(oo) == log(-oo) == oo``, ``log(zoo) == zoo``, and the
principal branch, ``log(z) == log(|z|) + I*arg(z)`` with ``-pi < arg(z) <=
pi`` (``log(-t) == log(t) + I*pi`` for ``t > 0``).  ``log(x, b)`` is
``log(x)/log(b)``: a node with two arguments gets no facts (#191).
``exp(I*pi*c*s)`` for a rational ``c`` gets the rules of a root of unity
too (``wiring.I_PI_ROOT``).
"""
from __future__ import annotations

from sympy import Equivalent, Q, exp, log

from ._rows import argument, closed, f, for_all

RULES = (
    # Entire
    #     no poles: finite at every finite point
    for_all((exp,),
        closed(f, Q.finite) & closed(f, Q.complex)),

    # Nonvanishing
    #     exp(a)*exp(-a) == 1
    for_all((exp,),
        Q.finite(argument) >> ~Q.zero(f(argument))),

    # Positive on the reals
    for_all((exp,),
        Q.real(argument) >> Q.positive(f(argument))),

    # Limits at the real infinities
    #     exp(-oo) == 0, exp(oo) == oo
    for_all((exp,),
        (Q.infinite(argument) & Q.extended_negative(argument)) >> Q.zero(f(argument)),
        (Q.infinite(argument) & Q.extended_positive(argument)) >> (
            Q.infinite(f(argument)) & Q.extended_positive(f(argument)))),

    # One at 0
    #     1 is odd, and neither prime nor composite
    for_all((exp,),
        Q.zero(argument) >> (
            Q.odd(f(argument)) & ~Q.prime(f(argument)) & ~Q.composite(f(argument)))),

    # Lindemann
    #     exp(a) is transcendental at an algebraic a != 0 (Lindemann-Weierstrass;
    #     exp(a) != 0); exp(log(a)) == a: a value b != 0 of log at an
    #     algebraic a != 0, if algebraic, would make exp(b) == a transcendental
    for_all((exp, log),
        (Q.algebraic(argument) & ~Q.zero(argument) & ~Q.zero(f(argument)))
        >> Q.transcendental(f(argument))),

    # Finite but at 0
    #     a branch cut on the negative reals, and no pole but 0
    for_all((log,),
        (Q.complex(argument) & ~Q.zero(argument)) >> Q.complex(f(argument)),
        (Q.finite(argument) & ~Q.zero(argument)) >> Q.finite(f(argument))),

    # Pole at 0
    #     the value is zoo
    for_all((log,),
        Q.zero(argument) >> (Q.infinite(f(argument)) & ~Q.extended_real(f(argument)))),

    # Infinite at infinity
    #     log(+-oo) == oo, log(zoo) == zoo
    for_all((log,),
        closed(f, Q.infinite),
        (Q.infinite(argument) & Q.extended_real(argument)) >> Q.extended_positive(f(argument))),

    # Real on the positive reals
    for_all((log,),
        Q.positive(argument) >> Q.real(f(argument))),

    # Not real off the positive reals
    #     the imaginary part of log(z) is arg(z), which is 0 only on the
    #     positive reals: pi on the negative reals
    for_all((log,),
        Q.negative(argument) >> ~Q.extended_real(f(argument)),
        (Q.complex(argument) & ~Q.extended_real(argument)) >> ~Q.extended_real(f(argument))),

    # Zero at 1, positive beyond, negative below
    #     log(1) == 0, log is increasing on the positive reals, log(oo) == oo
    for_all((log,),
        Equivalent(Q.zero(f(argument)), Q.eq(argument, 1)),
        Q.gt(argument, 1) >> Q.extended_positive(f(argument)),
        Q.positive(argument) >> (
            Equivalent(Q.positive(f(argument)), Q.gt(argument, 1))
            & Equivalent(Q.negative(f(argument)), Q.lt(argument, 1)))),
)
