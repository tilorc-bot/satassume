"""``sin``, ``cos``, ``tan``, ``cot``, ``sec`` and ``csc``: their signatures
and the rows their properties (``properties.py``) do not give."""
from __future__ import annotations

from sympy import Q, cos, cot, csc, oo, sec, sin, tan, zoo

from ._rows import Icc, Ioo, rows, rules, signature, x
from .functions import _pi_trig, _unary
from .properties import rows_of
from .registry import registry

SIN = signature(sin,
    (Q.real, Icc(-1, 1)),
    (Q.zero, 0),
)

COS = signature(cos,
    (Q.real, Icc(-1, 1)),
    (Q.zero, 1),
    (Q.imaginary, Ioo(1, oo)),          # cos(I*t) == cosh(t)
)

TAN = signature(tan, (Q.zero, 0)) + rows(
    # Im tan(x + I*y) == sinh(2*y)/(cos(2*x) + cosh(2*y)) != 0 for y != 0
    (Q.finite(x) & ~Q.extended_real(x)) >> ~Q.extended_real(tan(x)),
    label='trig')

COT = signature(cot, (Q.zero, zoo)) + rows(
    (Q.finite(x) & ~Q.extended_real(x)) >> ~Q.extended_real(cot(x)),    # cot == 1/tan
    label='trig')

SEC = signature(sec,
    (Q.zero, 1),
    (Q.imaginary, Ioo(0, 1)),           # sec(I*t) == 1/cosh(t)
)

CSC = signature(csc, (Q.zero, zoo))

#: each function and all its rows: its properties', then its own
ROWS = tuple((f, rows_of(f) + own) for f, own in (
    (sin, SIN), (cos, COS), (tan, TAN), (cot, COT), (sec, SEC), (csc, CSC)))


for _f, _all in ROWS:
    _gen = rules(_f, _all, __name__)
    if _f in (sin, cos):
        registry.register(_f)(_pi_trig(_f.__name__, _gen, _f is cos))
    else:
        registry.register(_f)(_unary(_f.__name__, _gen))
