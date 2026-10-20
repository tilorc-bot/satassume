"""Unit facts for ``RandomSymbol`` of ``sympy.stats`` (#180, C-NOTMPL).

A random symbol is an atom whose value is a sample of its probability
space: SymPy's class has ``is_finite``, takes ``positive`` and ``integer``
from its symbol, and ``real`` from its symbol or its space
(``RandomSymbol._eval_is_real``: ``Normal('x', 0, 1)`` is real).  These
are its facts here; the closure gives the rest (``units``).

SymPy does not import ``sympy.stats`` itself, so this module is declared
with the class name (:meth:`TemplateRegistry.lazy`) and imported when the
first random symbol is met.
"""
from __future__ import annotations

from sympy.stats.rv import RandomSymbol

from ._common import units
from .registry import registry


@registry.register(RandomSymbol)
def randomsymbol_units(expr):
    sym = expr.symbol
    out = [('finite', True)]
    for pred in ('positive', 'integer'):
        v = getattr(sym, 'is_' + pred)  # sympy-boundary: declared symbol facts, as RandomSymbol reads them
        if v is not None:
            out.append((pred, v))
    if sym.is_real or expr.pspace.is_real:  # sympy-boundary: RandomSymbol._eval_is_real
        out.append(('real', True))
    out = tuple(out)
    return units(('random', out), lambda: list(out), expr)
