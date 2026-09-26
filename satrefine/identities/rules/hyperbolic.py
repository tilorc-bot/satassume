"""``sinh``, ``cosh``, ``tanh``, ``coth``, ``sech`` and ``csch`` as tables.

Rows: 12 rules, 1 shared zero row; ``handlers_v3/hyperbolic.py`` is 225
lines.

The family is the trigonometric periodicity table rotated: an argument
``m*pi*I/2 + x`` shifts by a quarter of the period ``2*pi*I`` ``m`` times.
For ``m`` even the shift is ``(-1)**(m/2)``; for ``m`` odd it exchanges the
function with its cofunction times ``I*(-1)**((m-1)/2)`` (``-I`` for
``sech`` and ``csch``).  ``tanh`` and ``coth`` have period ``pi*I``.  Real
multiples of ``pi`` are not shifts of the period and never bind (the
pattern form collects only terms whose ratio to ``pi*I/2`` is free of
``pi`` and ``I``).

The sign power collapses through the ``Pow`` rules once the residue of
``m`` mod 4 is known, and stays symbolic otherwise, as in the trigonometric
table: ``sinh(x + k*pi*I) = (-1)**k*sinh(x)`` under ``Q.integer(k)`` (SymPy's
and the old ``handlers``' form).  v3 fires ``sinh``, ``cosh``, ``sech`` and
``csch`` only when the residue is known (phase 3 made the rows exact with a
symbolic sign instead: rows "default: hyperbolic i*pi shift" of ``tests/refine_identities/regressions.py``).
Like the trigonometric table, the whole coefficient of ``pi*I/2`` is tried
under both parities before a single term of it (``by_binding``).

Not covered: nothing v3 states.  ``f(k*pi*I)`` auto-evaluates to a
trigonometric function in SymPy, so the exact-point rules of v3 are the
trigonometric family's rows here (``sinh(I*pi*k)`` is ``I*sin(pi*k)``,
which gives ``0`` rather than v3's unrefined form).
Checked (adversarial pass, 2026-09-24): every row with ``m`` even, odd and
of known residue mod 4, at the poles (``coth``, ``csch`` at ``m*pi*I``,
``tanh``, ``sech`` at odd multiples of ``pi*I/2``), real multiples of
``pi`` (must not bind), sums of shifts, and ``python -m satrefine.tools.refine_differential``.
Found nothing.
"""
from __future__ import annotations

from sympy import I, Q, cosh, coth, csch, pi, sech, sinh, symbols, tanh

from ._tables import ZERO, Family, Row, Rules

m, x = symbols('m x')

_EVEN = Q.even(m)
_ODD = Q.odd(m)

RULES: list[Row] = [   # (lhs, rhs, hypothesis); the argument is m*pi*I/2 + x
    (sinh(m*pi*I/2 + x), (-1)**(m/2)*sinh(x),          _EVEN),       # sinh(x + n*pi*I) = (-1)**n sinh x
    (sinh(m*pi*I/2 + x), I*(-1)**((m - 1)/2)*cosh(x),  _ODD),        # sinh(x + pi*I/2) = I cosh x
    (cosh(m*pi*I/2 + x), (-1)**(m/2)*cosh(x),          _EVEN),       # cosh(x + n*pi*I) = (-1)**n cosh x
    (cosh(m*pi*I/2 + x), I*(-1)**((m - 1)/2)*sinh(x),  _ODD),        # cosh(x + pi*I/2) = I sinh x
    (sech(m*pi*I/2 + x), (-1)**(m/2)*sech(x),          _EVEN),       # sech = 1/cosh
    (sech(m*pi*I/2 + x), -I*(-1)**((m - 1)/2)*csch(x), _ODD),
    (csch(m*pi*I/2 + x), (-1)**(m/2)*csch(x),          _EVEN),       # csch = 1/sinh
    (csch(m*pi*I/2 + x), -I*(-1)**((m - 1)/2)*sech(x), _ODD),
    (tanh(m*pi*I/2 + x), tanh(x),                      Q.even(m)),   # tanh has period pi*I
    (tanh(m*pi*I/2 + x), coth(x),                      Q.odd(m)),    # tanh(x + pi*I/2) = coth x
    (coth(m*pi*I/2 + x), coth(x),                      Q.even(m)),   # coth has period pi*I
    (coth(m*pi*I/2 + x), tanh(x),                      Q.odd(m)),    # coth(x + pi*I/2) = tanh x
]

_shift = Rules([ZERO] + RULES, by_binding=True)

SPEC = Family({'sinh': _shift, 'cosh': _shift, 'tanh': _shift, 'coth': _shift, 'sech': _shift, 'csch': _shift},
              rules=[ZERO] + RULES)
