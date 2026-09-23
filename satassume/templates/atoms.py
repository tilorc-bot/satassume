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

from sympy import S
from sympy.core.numbers import ComplexInfinity, ImaginaryUnit, Number, NumberSymbol
from sympy.core.symbol import Symbol

from ..formula import Not, P
from ._common import VOCAB
from .registry import registry

_ORACLE_PREDS = tuple(sorted(VOCAB))


@registry.register(Symbol)
def symbol_units(expr):
    for fact, value in expr.assumptions0.items():
        if fact in VOCAB and value is not None:
            yield P(fact, expr) if value else Not(P(fact, expr))


@registry.register(Number, NumberSymbol, ImaginaryUnit, ComplexInfinity)
def constant_units(expr):
    for pred in _ORACLE_PREDS:
        value = getattr(expr, 'is_' + pred, None)
        if value is not None:
            yield P(pred, expr) if value else Not(P(pred, expr))
    # The old system has no ``is_positive_infinite``; state the signed
    # infinities explicitly.
    if expr is S.Infinity:
        yield P('positive_infinite', expr)
        yield Not(P('negative_infinite', expr))
    elif expr is S.NegativeInfinity:
        yield P('negative_infinite', expr)
        yield Not(P('positive_infinite', expr))
    elif expr is S.ComplexInfinity or getattr(expr, 'is_finite', None):
        yield Not(P('positive_infinite', expr))
        yield Not(P('negative_infinite', expr))
