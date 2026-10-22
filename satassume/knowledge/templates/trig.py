"""``sin``, ``cos``, ``tan``, ``cot``, ``sec`` and ``csc``.

Values follow SymPy's conventions: ``zoo`` at a pole, no claim at an
infinite argument (``sin(oo)`` is ``AccumBounds``; ``real`` and ``complex``
imply ``finite``).
"""
from __future__ import annotations

from sympy import Q, cos, cot, csc, oo, sec, sin, tan, zoo

from ._rows import Icc, Ioo, by_function, closed, f, for_all, rules, signature, x
from .functions import _pi_trig, _unary
from .registry import registry

RULES = (
    # entire: no poles, finite at every finite point
    for_all((sin, cos),
        closed(f, Q.finite) & closed(f, Q.complex)),

    # real where finite: f(conj z) == conj f(z), a number wherever it is
    # finite (zoo at a pole)
    for_all((tan, cot, sec, csc),
        Q.finite(f(x)) >> (closed(f, Q.real) & closed(f, Q.complex))),

    # imaginary axis: sin(I*t) == I*sinh(t), tan(I*t) == I*tanh(t),
    # cot(I*t) == -I*coth(t), csc(I*t) == -I*csch(t), nonzero for t != 0
    for_all((sin, tan, cot, csc),
        closed(f, Q.imaginary)),

    # nonvanishing: 1/f is entire
    for_all((sec, csc),
        Q.complex(x) >> ~Q.zero(f(x))),

    # Lindemann: f(a) == R(exp(I*a)), R rational with algebraic coefficients
    # and not constant, no pole at an algebraic a != 0; an algebraic value b
    # would make exp(I*a) a root of R - b, against Lindemann-Weierstrass
    for_all((sin, cos, tan, cot, sec, csc),
        (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(f(x))),

    # real only on the reals: Im tan(x + I*y) == sinh(2*y)/(cos(2*x) +
    # cosh(2*y)) != 0 for y != 0, and cot == 1/tan
    for_all((tan, cot),
        (Q.finite(x) & ~Q.extended_real(x)) >> ~Q.extended_real(f(x))),

    # bounded on the reals
    for_all((sin, cos),
        signature(f, (Q.real, Icc(-1, 1)))),

    # odd, finite at 0
    for_all((sin, tan),
        signature(f, (Q.zero, 0))),

    # even, f(0) == 1
    for_all((cos, sec),
        signature(f, (Q.zero, 1))),

    # pole at 0
    for_all((cot, csc),
        signature(f, (Q.zero, zoo))),

    # cos(I*t) == cosh(t)
    for_all((cos,),
        signature(f, (Q.imaginary, Ioo(1, oo)))),

    # sec(I*t) == 1/cosh(t)
    for_all((sec,),
        signature(f, (Q.imaginary, Ioo(0, 1)))),
)

#: each function and its rows
ROWS = by_function(RULES)


for _f, _all in ROWS:
    _gen = rules(_f, _all, __name__)
    if _f in (sin, cos):
        registry.register(_f)(_pi_trig(_f.__name__, _gen, _f is cos))
    else:
        registry.register(_f)(_unary(_f.__name__, _gen))
