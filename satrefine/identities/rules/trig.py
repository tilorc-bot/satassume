"""``sin``, ``cos``, ``tan``, ``cot``, ``sec``, ``csc`` and ``sinc``: shifts by multiples of ``pi/2``."""
from __future__ import annotations

from sympy import Q, cos, cot, csc, pi, sec, sin, sinc, symbols, tan
from sympy.calculus.accumulationbounds import AccumBounds

from ._tables import ZERO, Row, add_rules

n, r, k, zero, u = symbols('n r k zero u')

ASSUMED = {Q.integer(k), ~Q.zero(k),
           Q.zero(zero),
           Q.infinite(u), Q.extended_real(u)}

RULES: list[Row] = (
    [ZERO]
    + add_rules({Q.even(n)}, [
        (sin(n*pi/2 + r), (-1)**(n/2)*sin(r)),
        (cos(n*pi/2 + r), (-1)**(n/2)*cos(r)),
        (sec(n*pi/2 + r), (-1)**(n/2)*sec(r)),
        (csc(n*pi/2 + r), (-1)**(n/2)*csc(r)),
        (tan(n*pi/2 + r), tan(r)),
        (cot(n*pi/2 + r), cot(r)),
    ])
    + add_rules({Q.odd(n)}, [
        (sin(n*pi/2 + r), (-1)**((n - 1)/2)*cos(r)),
        (cos(n*pi/2 + r), (-1)**((n + 1)/2)*sin(r)),
        (sec(n*pi/2 + r), (-1)**((n + 1)/2)*csc(r)),
        (csc(n*pi/2 + r), (-1)**((n - 1)/2)*sec(r)),
        (tan(n*pi/2 + r), -cot(r)),
        (cot(n*pi/2 + r), -tan(r)),
    ])
    + add_rules(set(), [
        (sinc(k*pi/2 + zero), sin(k*pi/2)/(k*pi/2)),
    ])
    + add_rules(set(), [
        (sin(u), AccumBounds(-1, 1)),
        (cos(u), AccumBounds(-1, 1)),
    ])
)
