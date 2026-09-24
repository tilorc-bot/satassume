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

v3 leaves ``sinh(x + k*pi*I)`` alone when only ``Q.integer(k)`` is known and
``sinh(x + k*pi*I/2)`` alone when only ``Q.odd(k)`` is known; these rows
fire with a symbolic sign, ``(-1)**k*sinh(x)`` and ``I*(-1)**((k-1)/2)*
cosh(x)``, which is exact (and is what the trig family does).  Flagged
for the checker.
"""
from __future__ import annotations

from sympy import I, Q, cosh, coth, csch, pi, sech, sinh, symbols, tanh

from .._upstream import handlers_dict
from ._engine import Row, rule_handler
from ._tables import ZERO

m, x = symbols('m x')

RULES: list[Row] = [   # (lhs, rhs, hypothesis); the argument is m*pi*I/2 + x
    (sinh(m*pi*I/2 + x), (-1)**(m/2)*sinh(x),         Q.even(m)),   # sinh(x + n*pi*I) = (-1)**n sinh x
    (sinh(m*pi*I/2 + x), I*(-1)**((m - 1)/2)*cosh(x), Q.odd(m)),    # sinh(x + pi*I/2) = I cosh x
    (cosh(m*pi*I/2 + x), (-1)**(m/2)*cosh(x),         Q.even(m)),   # cosh(x + n*pi*I) = (-1)**n cosh x
    (cosh(m*pi*I/2 + x), I*(-1)**((m - 1)/2)*sinh(x), Q.odd(m)),    # cosh(x + pi*I/2) = I sinh x
    (sech(m*pi*I/2 + x), (-1)**(m/2)*sech(x),         Q.even(m)),   # sech = 1/cosh
    (sech(m*pi*I/2 + x), -I*(-1)**((m - 1)/2)*csch(x), Q.odd(m)),
    (csch(m*pi*I/2 + x), (-1)**(m/2)*csch(x),         Q.even(m)),   # csch = 1/sinh
    (csch(m*pi*I/2 + x), -I*(-1)**((m - 1)/2)*sech(x), Q.odd(m)),
    (tanh(m*pi*I/2 + x), tanh(x),                     Q.even(m)),   # tanh has period pi*I
    (tanh(m*pi*I/2 + x), coth(x),                     Q.odd(m)),    # tanh(x + pi*I/2) = coth x
    (coth(m*pi*I/2 + x), coth(x),                     Q.even(m)),   # coth has period pi*I
    (coth(m*pi*I/2 + x), tanh(x),                     Q.odd(m)),    # coth(x + pi*I/2) = tanh x
]

_shift = rule_handler([ZERO] + RULES)

handlers_dict['sinh'] = _shift
handlers_dict['cosh'] = _shift
handlers_dict['tanh'] = _shift
handlers_dict['coth'] = _shift
handlers_dict['sech'] = _shift
handlers_dict['csch'] = _shift
