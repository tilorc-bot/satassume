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


def _basic_subclasses():
    """Every subclass of ``Basic`` defined so far (SymPy's own and any other
    loaded module's), by class name."""
    from sympy import Basic
    by_name: dict = {}
    seen = set()
    todo = [Basic]
    while todo:
        cls = todo.pop()
        for sub in cls.__subclasses__():
            if sub not in seen:
                seen.add(sub)
                by_name.setdefault(sub.__name__, []).append(sub)
                todo.append(sub)
    return by_name


def _resolve(name: str):
    """The object ``srepr`` means by ``name``.  ``srepr`` prints
    ``type(expr).__name__`` for any class, including ones SymPy does not
    export at the top level (``AccumulationBounds``, ``ExprCondPair``,
    ``TupleArg``, ...).  Tried in order: the ``sympy`` namespace and
    ``_EXTRA_MODULES``; the subclasses of ``Basic`` with that name (if
    several classes share it, those SymPy defines first, then by module
    name, for a deterministic choice); any class of that name in a loaded
    ``sympy`` module."""
    import sys
    for mod in ("sympy",) + _EXTRA_MODULES:
        try:
            return getattr(importlib.import_module(mod), name)
        except (AttributeError, ImportError):
            continue
    cands = _basic_subclasses().get(name)
    if cands:
        cands.sort(key=lambda c: (not c.__module__.startswith("sympy."), c.__module__, c.__qualname__))
        return cands[0]
    for modname in sorted(m for m in list(sys.modules) if m == "sympy" or m.startswith("sympy.")):
        obj = getattr(sys.modules[modname], name, None)
        if isinstance(obj, type) and obj.__name__ == name:
            return obj
    raise NameError(name)


class _Namespace(dict):
    """srepr output names classes from all over SymPy; resolve them lazily."""

    def __missing__(self, name):
        obj = _resolve(name)
        self[name] = obj
        return obj


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


def _exact(cls):
    """``srepr`` prints the spelling of a Boolean node; rebuilding it with
    SymPy's constructor would rewrite it (``Not(x >= a)`` becomes ``x < a``,
    which means something else when ``x`` can be non-real; a nested or
    reordered ``And`` is flattened and sorted).  ``evaluate=False`` keeps
    what was printed, and equals the evaluated node whenever that node was
    canonical to begin with."""
    def build(*args, **kw):
        kw.setdefault("evaluate", False)
        return cls(*args, **kw)
    return build


_NS = _Namespace()
_NS["True"], _NS["False"], _NS["None"] = True, False, None
_NS["Q"] = _QProxy()
from sympy.logic.boolalg import And as _And, Or as _Or, Not as _Not  # noqa: E402
_NS["And"], _NS["Or"], _NS["Not"] = _exact(_And), _exact(_Or), _exact(_Not)


def to_srepr(obj) -> str:
    if obj is True or obj is False or obj is None:
        return repr(obj)
    return srepr(obj)


def from_srepr(s: str):
    return eval(s, _NS)  # noqa: S307 - our own srepr output
