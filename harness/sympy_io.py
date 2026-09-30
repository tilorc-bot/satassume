"""SymPy objects to and from ``srepr`` strings, so that streams and repros
can be written to files and rebuilt in another process."""
from __future__ import annotations

import importlib

from sympy import srepr

_EXTRA_MODULES = (
    "sympy.core.symbol", "sympy.assumptions", "sympy.assumptions.assume",
    "sympy.assumptions.relation.binrel", "sympy.core.function",
    "sympy.matrices.expressions", "sympy.matrices.expressions.matexpr",
    "sympy.matrices.expressions.slice", "sympy.matrices.expressions.blockmatrix",
    "sympy.matrices.expressions.diagonal", "sympy.matrices.expressions.fourier",
    "sympy.matrices.expressions.factorizations", "sympy.matrices.expressions.special",
    "sympy.functions", "sympy.core.numbers", "sympy.core.relational", "sympy.logic.boolalg",
    "sympy.functions.elementary.integers", "sympy.functions.elementary.complexes",
)


class _Namespace(dict):
    """srepr output names classes from all over SymPy; resolve them lazily."""

    def __missing__(self, name):
        for mod in ("sympy",) + _EXTRA_MODULES:
            try:
                obj = getattr(importlib.import_module(mod), name)
            except (AttributeError, ImportError):
                continue
            self[name] = obj
            return obj
        raise NameError(name)


#: custom predicate objects by name (filled by ``custom_predicate``), so that
#: srepr output (``Q.<name>``) rebuilds the same object
CUSTOM_PREDICATES: dict = {}


def custom_predicate(name: str, arity: int = 1):
    """A ``Predicate`` for a custom name: SymPy's ``UndefinedPredicate`` for
    a unary one, a ``Predicate`` subclass (which accepts any arity) for a
    polyadic one.  One object per name."""
    p = CUSTOM_PREDICATES.get(name)
    if p is None:
        from sympy.assumptions import Predicate
        if arity == 1:
            p = Predicate(name)
        else:
            p = type(f"Custom_{name}", (Predicate,), {"name": name})()
        CUSTOM_PREDICATES[name] = p
    return p


class _QProxy:
    """``Q`` for srepr output: SymPy's predicates by name, the harness's
    custom predicates, and an ``UndefinedPredicate`` otherwise (srepr
    prints every applied predicate as ``Q.<name>``)."""

    def __getattr__(self, name):
        from sympy import Q
        p = CUSTOM_PREDICATES.get(name)
        if p is not None:
            return p
        try:
            return getattr(Q, name)
        except AttributeError:
            return custom_predicate(name)


_NS = _Namespace()
_NS["True"], _NS["False"], _NS["None"] = True, False, None
_NS["Q"] = _QProxy()


def to_srepr(obj) -> str:
    if obj is True or obj is False or obj is None:
        return repr(obj)
    return srepr(obj)


def from_srepr(s: str):
    return eval(s, _NS)  # noqa: S307 - our own srepr output
