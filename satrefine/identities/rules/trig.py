"""``sin``, ``cos``, ``tan``, ``cot``, ``sec``, ``csc`` and ``sinc`` as tables.

The family is its periodicity table.  An argument ``n*pi/2 + r`` (``n`` the
whole coefficient of ``pi/2``) is ``n`` quarter turns from ``r``.  For ``n``
even the function keeps its form with sign ``(-1)**(n/2)``; for ``n`` odd it
becomes its cofunction.  The signs collapse through the ``Pow`` rules once
``n`` mod 4 is known.  ``r = 0`` needs no row of its own: ``sin(0)``,
``cos(0)``, ... evaluate.

At a pole the result is ``(-1)**m*zoo``, which the complex-parts ``Mul`` row
(``zoo`` absorbs a nonzero finite factor) turns into ``zoo``.

Not covered: ``sinc`` shifted by a nonzero remainder (no simpler form),
``AccumBounds`` for tan/cot/sec/csc at infinity, and imaginary shifts
(hyperbolic family).
"""
from __future__ import annotations

from sympy import Function, Q, cos, cot, csc, pi, sec, sin, sinc, symbols, tan
from sympy.calculus.accumulationbounds import AccumBounds

from ._tables import ZERO, Family, Row, Rules, add_rules

# n has no standing facts: each block's hypothesis gives its parity (and so integrality).
n, r, k, zero, u = symbols('n r k zero u')
F = Function('F')   # generic head standing for sin and cos in BOUNDED

ASSUMED = {Q.integer(k), ~Q.zero(k),              # k: a nonzero integer (sinc at a multiple)
           Q.zero(zero),
           Q.infinite(u), Q.extended_real(u)}     # u: +-oo

# Signs are a single power of -1 (not -(-1)**...), so the output stays one power.
RULES: list[Row] = (
    add_rules({Q.even(n)}, [  # m = n/2:  sin(r + m*pi) = (-1)**m sin r
        (sin(n*pi/2 + r), (-1)**(n/2)*sin(r)),
        (cos(n*pi/2 + r), (-1)**(n/2)*cos(r)),
        (sec(n*pi/2 + r), (-1)**(n/2)*sec(r)),
        (csc(n*pi/2 + r), (-1)**(n/2)*csc(r)),
        (tan(n*pi/2 + r), tan(r)),                    # tan, cot have period pi
        (cot(n*pi/2 + r), cot(r)),
    ])
    + add_rules({Q.odd(n)}, [  # m = (n - 1)/2:  sin(r + pi/2 + m*pi) = (-1)**m cos r
        (sin(n*pi/2 + r), (-1)**((n - 1)/2)*cos(r)),
        (cos(n*pi/2 + r), (-1)**((n + 1)/2)*sin(r)),  # cos(r + pi/2 + m*pi) = -(-1)**m sin r
        (sec(n*pi/2 + r), (-1)**((n + 1)/2)*csc(r)),
        (csc(n*pi/2 + r), (-1)**((n - 1)/2)*sec(r)),
        (tan(n*pi/2 + r), -cot(r)),                   # tan(r + pi/2) = -cot r
        (cot(n*pi/2 + r), -tan(r)),                   # cot(r + pi/2) = -tan r
    ])
    + add_rules(set(), [
        # `+ zero` gives the engine's n*pi/2 + r pattern form (so sinc(k*pi) and
        # sinc(x + 3*pi/2) with x = 0 bind) with the remainder forced to 0 by ASSUMED: the row
        # fires only at exact multiples of pi/2.  Bare sinc(k*pi/2) matches only that literal.
        (sinc(k*pi/2 + zero), sin(k*pi/2)/(k*pi/2)),
    ])
)

BOUNDED: list[Row] = add_rules(set(), [
    (F(u), AccumBounds(-1, 1)),   # sin, cos of a real infinity (SymPy's value)
])

# by_binding: try n as the whole pi/2 coefficient, under both parities, before splitting it,
# so sec(x + (2*j + 1)*pi/2) is one odd shift rather than an even shift plus a quarter turn.
_shift = Rules([ZERO] + RULES, by_binding=True)
_bounded = Rules(BOUNDED)

SPEC = Family({'sin': (_shift, _bounded), 'cos': (_shift, _bounded),
               'tan': _shift, 'cot': _shift, 'sec': _shift, 'csc': _shift, 'sinc': _shift},
              rules=[ZERO] + RULES + BOUNDED, assumed=ASSUMED)
