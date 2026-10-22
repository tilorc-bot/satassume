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

from ._rows import closed, f, for_all, x

RULES = (
    # Entire
    #     no poles: finite at every finite point
    for_all((exp,),
        closed(f, Q.finite) & closed(f, Q.complex)),

    # Nonvanishing
    #     exp(a)*exp(-a) == 1
    for_all((exp,),
        Q.finite(x) >> ~Q.zero(f(x))),

    # Positive on the reals
    for_all((exp,),
        Q.real(x) >> Q.positive(f(x))),

    # Limits at the real infinities
    #     exp(-oo) == 0, exp(oo) == oo
    for_all((exp,),
        (Q.infinite(x) & Q.extended_negative(x)) >> Q.zero(f(x)),
        (Q.infinite(x) & Q.extended_positive(x)) >> (
            Q.infinite(f(x)) & Q.extended_positive(f(x)))),

    # One at 0
    #     1 is odd, and neither prime nor composite
    for_all((exp,),
        Q.zero(x) >> (Q.odd(f(x)) & ~Q.prime(f(x)) & ~Q.composite(f(x)))),

    # Lindemann
    #     exp(a) is transcendental at an algebraic a != 0 (Lindemann-Weierstrass;
    #     exp(a) != 0); exp(log(a)) == a: a value b != 0 of log at an
    #     algebraic a != 0, if algebraic, would make exp(b) == a transcendental
    for_all((exp, log),
        (Q.algebraic(x) & ~Q.zero(x) & ~Q.zero(f(x))) >> Q.transcendental(f(x))),

    # Finite but at 0
    #     a branch cut on the negative reals, and no pole but 0
    for_all((log,),
        (Q.complex(x) & ~Q.zero(x)) >> Q.complex(f(x)),
        (Q.finite(x) & ~Q.zero(x)) >> Q.finite(f(x))),

    # Pole at 0
    #     the value is zoo
    for_all((log,),
        Q.zero(x) >> (Q.infinite(f(x)) & ~Q.extended_real(f(x)))),

    # Infinite at infinity
    #     log(+-oo) == oo, log(zoo) == zoo
    for_all((log,),
        closed(f, Q.infinite),
        (Q.infinite(x) & Q.extended_real(x)) >> Q.extended_positive(f(x))),

    # Real on the positive reals
    for_all((log,),
        Q.positive(x) >> Q.real(f(x))),

    # Not real off the positive reals
    #     the imaginary part of log(z) is arg(z), which is 0 only on the
    #     positive reals: pi on the negative reals
    for_all((log,),
        Q.negative(x) >> ~Q.extended_real(f(x)),
        (Q.complex(x) & ~Q.extended_real(x)) >> ~Q.extended_real(f(x))),

    # Zero at 1, positive beyond, negative below
    #     log(1) == 0, log is increasing on the positive reals, log(oo) == oo
    for_all((log,),
        Equivalent(Q.zero(f(x)), Q.eq(x, 1)),
        Q.gt(x, 1) >> Q.extended_positive(f(x)),
        Q.positive(x) >> (
            Equivalent(Q.positive(f(x)), Q.gt(x, 1))
            & Equivalent(Q.negative(f(x)), Q.lt(x, 1)))),
)
