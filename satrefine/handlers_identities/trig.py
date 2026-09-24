"""``sin``, ``cos``, ``tan``, ``cot``, ``sec``, ``csc`` and ``sinc`` as tables.

Rows: 14 rules, 1 shared zero row; ``handlers_v3/trig.py`` is 221 lines.
A value at a pole comes out as ``(-1)**k*zoo``, which the ``Mul`` row of
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
"""
from __future__ import annotations

from sympy import Function, Q, S, cos, cot, csc, pi, sec, sin, sinc, symbols, tan, true
from sympy.calculus.accumulationbounds import AccumBounds

from .._upstream import handlers_dict
from ._engine import Row, rule_handler
from ._tables import ZERO, chain

n, r, x = symbols('n r x')
F = Function('F')

RULES: list[Row] = [   # (lhs, rhs, hypothesis); the argument is n*pi/2 + r
    (sin(n*pi/2 + r), (-1)**(n/2)*sin(r),       Q.even(n)),   # sin(r + k*pi) = (-1)**k sin r
    (sin(n*pi/2 + r), (-1)**((n - 1)/2)*cos(r), Q.odd(n)),    # sin(r + pi/2 + k*pi) = (-1)**k cos r
    (cos(n*pi/2 + r), (-1)**(n/2)*cos(r),       Q.even(n)),   # cos(r + k*pi) = (-1)**k cos r
    (cos(n*pi/2 + r), -(-1)**((n - 1)/2)*sin(r), Q.odd(n)),   # cos(r + pi/2 + k*pi) = -(-1)**k sin r
    (sec(n*pi/2 + r), (-1)**(n/2)*sec(r),       Q.even(n)),   # sec = 1/cos
    (sec(n*pi/2 + r), -(-1)**((n - 1)/2)*csc(r), Q.odd(n)),
    (csc(n*pi/2 + r), (-1)**(n/2)*csc(r),       Q.even(n)),   # csc = 1/sin
    (csc(n*pi/2 + r), (-1)**((n - 1)/2)*sec(r), Q.odd(n)),
    (tan(n*pi/2 + r), tan(r),                   Q.even(n)),   # tan has period pi
    (tan(n*pi/2 + r), -cot(r),                  Q.odd(n)),    # tan(r + pi/2) = -cot r
    (cot(n*pi/2 + r), cot(r),                   Q.even(n)),   # cot has period pi
    (cot(n*pi/2 + r), -tan(r),                  Q.odd(n)),    # cot(r + pi/2) = -tan r
    (sinc(n*pi/2 + r), sin(n*pi/2)/(n*pi/2),    Q.zero(r) & Q.integer(n) & ~Q.zero(n)),  # sinc x = sin x / x, x != 0
]

BOUNDED: list[Row] = [
    (F(x), AccumBounds(-1, 1), Q.infinite(x) & Q.extended_real(x)),   # sin, cos of a real infinity (SymPy's value)
]

_shift = rule_handler([ZERO] + RULES)
_bounded = rule_handler(BOUNDED)

handlers_dict['sin'] = chain(_shift, _bounded)
handlers_dict['cos'] = chain(_shift, _bounded)
handlers_dict['tan'] = _shift
handlers_dict['cot'] = _shift
handlers_dict['sec'] = _shift
handlers_dict['csc'] = _shift
handlers_dict['sinc'] = _shift
