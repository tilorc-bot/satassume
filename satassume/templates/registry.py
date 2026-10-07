"""Registry of structural rule templates keyed by SymPy class.

A template is a plain function ``f(expr) -> formula | iterable of formulas``
(``None`` is tolerated and means "nothing").  Templates are registered for
one or more classes; :meth:`TemplateRegistry.facts_for` walks the MRO of the
expression's type, so a template registered for a base class also applies
to every subclass.  Most-specific classes come first in the result.

The built-in template modules other than :mod:`satassume.templates.atoms`
are imported on first use (:meth:`TemplateRegistry.lazy`): a module is
loaded when the templates of a class it registers for, or of a subclass,
are first asked for, so a query whose nodes are all symbols and numbers
never loads the templates of sums, products, powers and functions.  This
is not a change of the templates in force: the lazily loaded templates
count as registered from the start (no epoch bump, no memo is emptied),
which is exact because no memo can hold a result for a class they cover
before they are loaded (see :meth:`TemplateRegistry.templates_for`).

This module does not import SymPy.
"""
from __future__ import annotations

import importlib
import sys
from typing import Any, Callable, Dict, Iterable, List, Tuple

from ..epoch import bump as _bump
from ..formula import Formula, P
from . import _common
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
        #: built-in template modules not imported yet, as ``(classes,
        #: module name)``: the module registers templates for ``classes``
        #: only (:meth:`lazy`)
        self._lazy: List[Tuple[tuple, str]] = []

    def lazy(self, module: str, *classes: type) -> None:
        """Declare the built-in template module ``module`` (a module name),
        which registers templates for ``classes`` and their subclasses only;
        it is imported by the first :meth:`templates_for` of such a class
        (or by :meth:`load_all`).  Its registrations are part of the
        templates in force from the start: they bump no epoch and empty no
        memo, which is exact because every memo entry about a class it
        covers is made after it is loaded (:meth:`templates_for` loads it
        first), and its pattern keys are its own (``_common._CACHE``).  A
        template registered by anyone else loads every declared module
        first, so the order of the templates of a class never depends on
        when the modules were loaded."""
        self._lazy.append((classes, module))

    def _load(self, cls) -> None:
        """Import the declared modules covering ``cls`` (all of them for
        None)."""
        todo = [m for c, m in self._lazy if cls is None or issubclass(cls, c)]
        for m in todo:
            importlib.import_module(m)
            # the module (and any declared module it imports) registered
            # itself: drop what is loaded now
            self._lazy = [(c, n) for c, n in self._lazy if n != m and n not in sys.modules]

    def load_all(self) -> None:
        """Import every declared module (:meth:`lazy`)."""
        if self._lazy:
            self._load(None)

    def register(self, *classes: type):
        """Decorator registering ``f`` as a template for ``classes``."""
        if not classes:
            raise TypeError("register() needs at least one class")

        def deco(f: Template) -> Template:
            mod = getattr(f, "__module__", None)
            covers = [c for c, m in self._lazy if m == mod]
            if covers:
                # a declared built-in module registering itself (on first
                # use, or imported directly): part of the templates in force
                # from the start, see lazy()
                if not all(issubclass(cls, covers[0]) for cls in classes):
                    raise TypeError(f"{mod} registers a template for a class "
                                    f"outside its declared classes {covers[0]}")
                for cls in classes:
                    self._by_class.setdefault(cls, []).append(f)
                return f
            # anyone else's template comes after every built-in one
            self.load_all()
            for cls in classes:
                self._by_class.setdefault(cls, []).append(f)
            self._mro_cache.clear()
            self._clauses_cache.clear()
            # compiled patterns are keyed on the template's own key, which
            # a later template may reuse with other rules (#97 P4 review)
            _common._CACHE.clear()
            # the engines' caches hold facts the old templates derived
            _bump()
            return f

        return deco

    def templates_for(self, cls: type) -> List[Template]:
        """All templates applying to ``cls``, most specific class first.
        The declared modules covering ``cls`` are imported first
        (:meth:`lazy`), so neither this memo nor the ones built from it
        (:meth:`clauses_for`, the compiled patterns, the engines' caches)
        ever hold a result for a class whose templates were not all
        loaded."""
        out = self._mro_cache.get(cls)
        if out is None:
            if self._lazy:
                self._load(cls)
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
        self.load_all()
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
