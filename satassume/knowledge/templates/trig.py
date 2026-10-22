"""``sin``, ``cos``, ``tan``, ``cot``, ``sec`` and ``csc``.

Values follow SymPy's conventions: ``zoo`` at a pole, no claim at an
infinite argument (``sin(oo)`` is ``AccumBounds``; ``real`` and ``complex``
imply ``finite``).
"""
from __future__ import annotations

from sympy import Q, cos, cot, csc, oo, sec, sin, tan, zoo

from ._rows import Icc, Ioo, closed, f, rules, signature, x
from .functions import _pi_trig, _unary
from .registry import registry

#: no poles: finite at every finite point
ENTIRE = closed(f, Q.finite) & closed(f, Q.complex)

#: f(conj z) == conj f(z), and a number wherever it is finite
REAL_WHERE_FINITE = Q.finite(f(x)) >> (closed(f, Q.real) & closed(f, Q.complex))

#: f(I*t) is I times a real function of t, finite and nonzero for t != 0
#: (sin(I*t) == I*sinh(t), tan(I*t) == I*tanh(t), cot(I*t) == -I*coth(t),
#: csc(I*t) == -I*csch(t))
IMAGINARY_AXIS = closed(f, Q.imaginary)

#: 1/f is entire
NONVANISHING = Q.complex(x) >> ~Q.zero(f(x))

#: f(a) == R(exp(I*a)), R rational with algebraic coefficients and not
#: constant, with no pole at an algebraic a != 0: an algebraic value b
#: would make exp(I*a) a root of R - b, against Lindemann-Weierstrass
LINDEMANN = (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(f(x))

#: Im f(x + I*y) != 0 for y != 0: Im tan(x + I*y) == sinh(2*y)/(cos(2*x)
#: + cosh(2*y)), and cot == 1/tan
REAL_ONLY_ON_REALS = (Q.finite(x) & ~Q.extended_real(x)) >> ~Q.extended_real(f(x))

SIN = (ENTIRE, IMAGINARY_AXIS, LINDEMANN, signature(
    (Q.real, Icc(-1, 1)),
    (Q.zero, 0),
))

COS = (ENTIRE, LINDEMANN, signature(
    (Q.real, Icc(-1, 1)),
    (Q.zero, 1),
    (Q.imaginary, Ioo(1, oo)),          # cos(I*t) == cosh(t)
))

TAN = (REAL_WHERE_FINITE, IMAGINARY_AXIS, LINDEMANN, REAL_ONLY_ON_REALS, signature(
    (Q.zero, 0),
))

COT = (REAL_WHERE_FINITE, IMAGINARY_AXIS, LINDEMANN, REAL_ONLY_ON_REALS, signature(
    (Q.zero, zoo),
))

SEC = (REAL_WHERE_FINITE, NONVANISHING, LINDEMANN, signature(
    (Q.zero, 1),
    (Q.imaginary, Ioo(0, 1)),           # sec(I*t) == 1/cosh(t)
))

CSC = (REAL_WHERE_FINITE, NONVANISHING, IMAGINARY_AXIS, LINDEMANN, signature(
    (Q.zero, zoo),
))

#: each function and its rules
ROWS = ((sin, SIN), (cos, COS), (tan, TAN), (cot, COT), (sec, SEC), (csc, CSC))


for _f, _table in ROWS:
    _gen = rules(_f, _table, __name__)
    if _f in (sin, cos):
        registry.register(_f)(_pi_trig(_f.__name__, _gen, _f is cos))
    else:
        registry.register(_f)(_unary(_f.__name__, _gen))
