"""Templates for ``AccumulationBounds`` and ``Idx`` (#180, C-NOTMPL).

* ``AccumBounds(a, b)`` stands for a value in the real interval
  ``[a, b]`` (``a < b``, both extended real: SymPy raises otherwise), so
  it is extended real, and real when both ends are (SymPy's
  ``_eval_is_real``).  No sign rule: nothing relates the ends, and a block
  with ``a`` positive and ``b`` negative must stay total.
* ``Idx`` (``sympy.tensor``) is an integer index (the class has
  ``is_integer``, ``is_finite`` and ``is_real``), whatever its range.
"""
from __future__ import annotations

from sympy.calculus.accumulationbounds import AccumulationBounds
from sympy.tensor.indexed import Idx

from ._common import Rules, consts_of, facts, pattern_key, units
from .registry import registry

A, B, N = 0, 1, 2


def _accum():
    R = Rules()
    R.rule([], (N, 'extended_real', True))
    R.rule([(A, 'real', True), (B, 'real', True)], (N, 'real', True))
    return R.rules


@registry.register(AccumulationBounds)
def accumbounds_templates(expr):
    args = expr.args
    consts = consts_of(args)
    return facts(pattern_key('AccumBounds', 2, consts), _accum, consts, (*args, expr), N)


@registry.register(Idx)
def idx_units(expr):
    return units(('idx',), lambda: [('integer', True)], expr)
