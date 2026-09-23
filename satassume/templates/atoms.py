"""Unit facts for atomic SymPy objects (symbols and numeric constants).

* ``Symbol`` (and its subclasses ``Dummy`` and ``Wild``): the user-declared
  assumptions and their closure, as stored in ``assumptions0``.
* Numbers, number symbols (``pi``, ``E``, ...), ``I``, ``oo``, ``-oo``,
  ``zoo`` and ``nan``: these objects have fixed values, so every old-system
  ``is_<pred>`` property that is not ``None`` is a trustworthy static fact
  (the "atom oracle").

Any other leaf emits nothing.
"""
from __future__ import annotations

from sympy.core.numbers import ComplexInfinity, ImaginaryUnit, Number, NumberSymbol
from sympy.core.symbol import Symbol

from ._common import VOCAB, const_key, const_value, units
from .registry import registry

_ORACLE_PREDS = tuple(sorted(VOCAB))


@registry.register(Symbol)
def symbol_units(expr):
    a0 = expr.assumptions0
    key = ('symbol', frozenset(a0.items()))
    return units(key, lambda: [(fact, value) for fact, value in a0.items()
                               if fact in VOCAB and value is not None], expr)


@registry.register(Number, NumberSymbol, ImaginaryUnit, ComplexInfinity)
def constant_units(expr):
    def gen():
        out = []
        for pred in _ORACLE_PREDS:
            value = const_value(expr, pred)
            if value is not None:
                out.append((pred, value))
        return out
    return units(('const', const_key(expr)), gen, expr)
