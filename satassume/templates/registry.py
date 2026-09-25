"""Registry of structural rule templates keyed by SymPy class.

A template is a plain function ``f(expr) -> formula | iterable of formulas``
(``None`` is tolerated and means "nothing").  Templates are registered for
one or more classes; :meth:`TemplateRegistry.facts_for` walks the MRO of the
expression's type, so a template registered for a base class also applies
to every subclass.  Most-specific classes come first in the result.

This module does not import SymPy.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List

from ..formula import Formula, P
from ._common import Compiled

Template = Callable[[Any], Any]

#: bound of the :meth:`TemplateRegistry.clauses_for` memo (cleared when full)
CLAUSES_CACHE_SIZE = 50_000


class TemplateRegistry:
    def __init__(self) -> None:
        self._by_class: Dict[type, List[Template]] = {}
        self._mro_cache: Dict[type, List[Template]] = {}
        #: ``expr -> (compiled, formulas)`` of :meth:`clauses_for`; templates
        #: are pure functions of the expression, so the result only changes
        #: when templates are registered (which clears it)
        self._clauses_cache: Dict[Any, Any] = {}

    def register(self, *classes: type):
        """Decorator registering ``f`` as a template for ``classes``."""
        if not classes:
            raise TypeError("register() needs at least one class")

        def deco(f: Template) -> Template:
            for cls in classes:
                self._by_class.setdefault(cls, []).append(f)
            self._mro_cache.clear()
            self._clauses_cache.clear()
            return f

        return deco

    def templates_for(self, cls: type) -> List[Template]:
        """All templates applying to ``cls``, most specific class first."""
        out = self._mro_cache.get(cls)
        if out is None:
            out = []
            for base in cls.__mro__:
                out.extend(self._by_class.get(base, ()))
            self._mro_cache[cls] = out
        return out

    def facts_for(self, expr: Any) -> List[Any]:
        """Every formula emitted by every template matching ``type(expr)``
        (compiled patterns expanded to formulas)."""
        out: List[Any] = []
        for f in self.templates_for(type(expr)):
            _collect(f(expr), out)
        return out

    def clauses_for(self, expr: Any):
        """``(compiled, formulas)``: the compiled patterns and the plain
        formulas emitted by the templates matching ``type(expr)``.  This is
        what the engine uses; :meth:`facts_for` is the same information as
        formulas.  Memoized per expression; the result must not be mutated."""
        r = self._clauses_cache.get(expr)
        if r is not None:
            return r
        compiled: List[Compiled] = []
        formulas: List[Any] = []
        for f in self.templates_for(type(expr)):
            r = f(expr)
            if type(r) is Compiled:
                compiled.append(r)
            else:
                _split(r, compiled, formulas)
        cache = self._clauses_cache
        if len(cache) >= CLAUSES_CACHE_SIZE:
            cache.clear()
        r = cache[expr] = (compiled, formulas)
        return r

    def classes(self) -> Iterable[type]:
        return self._by_class.keys()


def _collect(result: Any, out: List[Any]) -> None:
    if result is None or result is True:
        # ``True`` is the degenerate formula (e.g. ``allargs`` of no args):
        # asserting it is a no-op.
        return
    if result is False or isinstance(result, (P, Formula)):
        out.append(result)
        return
    if type(result) is Compiled:
        out.extend(result.formulas())
        return
    for r in result:
        _collect(r, out)


def _split(result: Any, compiled: List[Compiled], formulas: List[Any]) -> None:
    if result is None or result is True:
        return
    if type(result) is Compiled:
        compiled.append(result)
        return
    if result is False or isinstance(result, (P, Formula)):
        formulas.append(result)
        return
    for r in result:
        _split(r, compiled, formulas)


registry = TemplateRegistry()
