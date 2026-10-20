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
# Properties read on a constant.  The rest (the extended sign predicates,
# hermitian/antihermitian, the signed infinities, nonzero, noninteger,
# irrational, ...) follows from these by the rule-base closure applied in
# ``units``; ``polar`` is undecidable for numbers.
_CONST_BASIS = (
    'algebraic', 'complex', 'composite', 'even', 'finite',
    'imaginary', 'infinite', 'integer', 'negative', 'odd', 'positive', 'prime',
    'rational', 'real', 'transcendental', 'zero', 'extended_real',
    'extended_positive', 'extended_negative',
)


@registry.register(Symbol)
def symbol_units(expr):
    a0 = expr.assumptions0  # sympy-boundary: declared symbol facts; strict ask rejects them
    key = ('symbol', frozenset(a0.items()))
    # not ``commutative``: true of every term in scope (rules.DEFINITIONS);
    # a non-commutative symbol is out of scope (sympy_api)
    return units(key, lambda: [(fact, value) for fact, value in a0.items()
                               if fact in VOCAB and value is not None
                               and fact != 'commutative'], expr)


@registry.register(Number, NumberSymbol, ImaginaryUnit, ComplexInfinity)
def constant_units(expr):
    return value_units(expr, expr)


def value_units(value, obj):
    """The unit facts of the constant ``value`` (an atom with a fixed
    value) as facts of ``obj``: for a node whose value is known to be
    ``value`` (``genocchi(8, evaluate=False)`` is 17)."""
    def gen():
        out = []
        for pred in _CONST_BASIS:
            v = const_value(value, pred)
            if v is not None:
                out.append((pred, v))
        return out
    return units(('const', const_key(value)), gen, obj)
