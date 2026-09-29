"""``sin``, ``cos``, ``tan``, ``cot``, ``sec``, ``csc`` and ``sinc`` as tables.

Rows: 13 rules, 1 bounded row (``AccumBounds`` at a real infinity), 1
shared zero row; ``handlers_v3/trig.py`` is 221 lines.
A value at a pole comes out as ``(-1)**m*zoo``, which the ``Mul`` row of
the complex parts (``zoo`` absorbs a nonzero finite factor) turns into
``zoo``.

The family is its periodicity table.  An argument ``n*pi/2 + r`` (``n`` the
collected coefficient of ``pi/2``, see the engine's pattern forms) shifts
by a quarter turn ``n`` times; for ``n`` even the shift is ``(-1)**(n/2)``
and for ``n`` odd it exchanges the function with its cofunction times
``(-1)**((n -+ 1)/2)``.  One row per function and parity states that; the
sign power collapses through the ``Pow`` rules when the residue of ``n``
mod 4 is known, and the value at an exact multiple (``r == 0``) follows
from the same rows with ``sin(0)``, ``cos(0)``, ... evaluating.  ``tan``
and ``cot`` have period ``pi``, so parity suffices.

Every row is exact over the complex plane and at the poles (both sides are
``zoo``).  An exponential-form derivation exists (``sin z = (exp(iz) -
exp(-iz))/(2i)``) but produces quotient forms that are not v3's; the
periodicity rows are the shorter statement.

Not covered: ``sinc`` shifted by a nonzero remainder (no simpler form),
``AccumBounds`` for tan/cot/sec/csc at infinity, and imaginary shifts
(hyperbolic family).
Checked (adversarial pass, 2026-09-24): every periodicity row with even,
odd, zero and symbolic coefficients of ``pi/2``, at odd multiples of
``pi/2`` (the poles of tan, sec; ``(-1)**m*zoo`` becomes ``zoo``), sums of
several ``pi`` terms, ``sinc`` at multiples, ``sin``/``cos`` at real
infinities (``AccumBounds``), about 700 random cases, and
``python -m satrefine.tools.refine_differential``.  Found nothing.
"""
from __future__ import annotations

from sympy import Function, Q, cos, cot, csc, pi, sec, sin, sinc, symbols, tan
from sympy.calculus.accumulationbounds import AccumBounds

from ._tables import ZERO, Family, Row, Rules, add_rules

# The argument is n*pi/2 + r.  Nothing is assumed about n throughout: each shift row's block
# states its parity (which also makes it an integer), and that is what tells the rows apart.
# The table is tried by binding (``by_binding``), so both rows of a function keep the same left
# side, one block each: the even row, then the odd one.
n, r, k, zero, u = symbols('n r k zero u')
F = Function('F')

ASSUMED = {Q.integer(k), ~Q.zero(k),              # k is a nonzero integer (sinc at a multiple)
           Q.zero(zero),                          # zero is 0
           Q.infinite(u), Q.extended_real(u)}     # u is extended real, here infinite: +-oo


def _parities(even: Row, odd: Row) -> list[Row]:
    """A function's two shift rows: ``even`` for an even ``n``, ``odd`` for an odd one."""
    return add_rules([even], assuming={Q.even(n)}) + add_rules([odd], assuming={Q.odd(n)})


RULES: list[Row] = (   # the argument is n*pi/2 + r
    _parities((sin(n*pi/2 + r), (-1)**(n/2)*sin(r)),          # sin(r + m*pi) = (-1)**m sin r
              (sin(n*pi/2 + r), (-1)**((n - 1)/2)*cos(r)))    # sin(r + pi/2 + m*pi) = (-1)**m cos r
    + _parities((cos(n*pi/2 + r), (-1)**(n/2)*cos(r)),        # cos(r + m*pi) = (-1)**m cos r
                (cos(n*pi/2 + r), (-1)**((n + 1)/2)*sin(r)))  # cos(r + pi/2 + m*pi) = -(-1)**m sin r
    + _parities((sec(n*pi/2 + r), (-1)**(n/2)*sec(r)),        # sec = 1/cos
                (sec(n*pi/2 + r), (-1)**((n + 1)/2)*csc(r)))  # (one power of -1: SymPy's form)
    + _parities((csc(n*pi/2 + r), (-1)**(n/2)*csc(r)),        # csc = 1/sin
                (csc(n*pi/2 + r), (-1)**((n - 1)/2)*sec(r)))
    + _parities((tan(n*pi/2 + r), tan(r)),                    # tan has period pi
                (tan(n*pi/2 + r), -cot(r)))                   # tan(r + pi/2) = -cot r
    + _parities((cot(n*pi/2 + r), cot(r)),                    # cot has period pi
                (cot(n*pi/2 + r), -tan(r)))                   # cot(r + pi/2) = -tan r
    + add_rules([
        (sinc(k*pi/2 + zero), sin(k*pi/2)/(k*pi/2)),          # sinc x = sin x / x, x != 0
    ])
)

BOUNDED: list[Row] = add_rules([
    (F(u), AccumBounds(-1, 1)),   # sin, cos of a real infinity (SymPy's value)
])

_shift = Rules([ZERO] + RULES, by_binding=True)   # the whole coefficient first, both parities
_bounded = Rules(BOUNDED)

SPEC = Family({'sin': (_shift, _bounded), 'cos': (_shift, _bounded),
               'tan': _shift, 'cot': _shift, 'sec': _shift, 'csc': _shift, 'sinc': _shift},
              rules=[ZERO] + RULES + BOUNDED, assumed=ASSUMED)
