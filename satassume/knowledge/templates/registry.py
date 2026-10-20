"""Registry of structural rule templates keyed by SymPy class.

A template is a plain function ``f(expr) -> formula | iterable of formulas``
(``None`` is tolerated and means "nothing").  Templates are registered for
one or more classes; :meth:`TemplateRegistry.facts_for` walks the MRO of the
expression's type, so a template registered for a base class also applies
to every subclass.  Most-specific classes come first in the result.

Except where a subclass redefines a fact on purpose (#180 S10): when the
expression's type, or a class between it and a base, overrides an
``_eval_is_<fact>`` handler that the base has, the base's templates do not
apply to it.  The
engine never calls the handler, so it cannot tell a refinement from a
contradiction (``sympy.printing.rust.float_floor`` is a ``floor`` whose
``_eval_is_integer`` returns False).  Dropping templates is sound: only
facts are lost.  A template that reads the object's own facts instead of
deriving them (:func:`own_facts`: the facts of a numeric constant, the
declared facts of a symbol) follows the override and still applies.  Only
handlers count: a subclass that changes a fact through a class attribute
(``is_integer = False``) still gets the base's templates (in SymPy only
``MatAdd``, ``MatMul`` and ``RandomMatrixSymbol`` do, and they are out of
scope).  Handlers are read when a class is first used (memoized): one
patched in later is not seen.

The built-in template modules other than :mod:`satassume.knowledge.templates.atoms`
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

from ...state.epoch import bump as _bump
from ...sat.formula import Formula, P
from ...state.memos import adopt as _adopt_memo
from . import _common
from ._common import Compiled

Template = Callable[[Any], Any]

_OWN_FACTS = "_satassume_own_facts"


def own_facts(f: Template) -> Template:
    """Mark ``f`` as a template that reads the facts of the object itself
    (SymPy's ``is_*`` of a constant): it still applies to a subclass that
    overrides a handler of its class (see the module docstring)."""
    setattr(f, _OWN_FACTS, True)
    return f


def _redefines(below, base: type) -> bool:
    """Does a class of ``below`` override an ``_eval_is_<fact>`` handler
    that ``base`` has?  Only facts count: ``_eval_is_polynomial`` and the
    like are no assumptions."""
    return any(n.startswith("_eval_is_") and n[9:] in _common.VOCAB
               and getattr(base, n, None) is not None
               for k in below for n in vars(k))

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
        #: ``(expr, preds) -> {pred: True | False | None}``, the answers of
        #: context-free queries, for templates that take facts of a part that
        #: is no slot (the function of a ``Sum``, whose variable is bound);
        #: set by :mod:`satassume.engine`, which this layer cannot import
        #: (None: no such facts)
        self.context_free: Callable[[Any, Iterable[str]], Dict[str, Any]] | None = None

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
        when the modules were loaded.

        A class may also be given by name, ``"module:Class"``, for a class
        of a module that SymPy does not import itself
        (``sympy.codegen.cfunctions``): declaring it imports nothing, and
        :meth:`load_all` imports ``module`` only once that module is
        imported (before, no object of the class exists)."""
        self._lazy.append((classes, module))

    @staticmethod
    def _covers(cls, classes) -> bool:
        """Is ``cls`` one of ``classes`` (classes or ``"module:Class"``
        names, see :meth:`lazy`) or a subclass of one?"""
        for c in classes:
            if isinstance(c, str):
                if any(f"{k.__module__}:{k.__qualname__}" == c for k in cls.__mro__):
                    return True
            elif issubclass(cls, c):
                return True
        return False

    @staticmethod
    def _imported(classes) -> bool:
        """Can an object of one of ``classes`` exist yet?"""
        return any(not isinstance(c, str) or c.partition(':')[0] in sys.modules
                   for c in classes)

    def _load(self, cls) -> None:
        """Import the declared modules covering ``cls`` (all of them whose
        classes can have objects yet for None)."""
        todo = [m for c, m in self._lazy
                if (self._imported(c) if cls is None else self._covers(cls, c))]
        for m in todo:
            importlib.import_module(m)
            # the module (and any declared module it imports) registered
            # itself: drop what is loaded now
            self._lazy = [(c, n) for c, n in self._lazy if n != m and n not in sys.modules]

    def load_all(self) -> None:
        """Import every declared module (:meth:`lazy`) whose classes can
        have objects yet."""
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
                if not all(self._covers(cls, covers[0]) for cls in classes):
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
            mro = cls.__mro__
            for i, base in enumerate(mro):
                ts = self._by_class.get(base, ())
                if ts and i and _redefines(mro[:i], base):
                    # a subclass redefines a fact of the base (#180 S10)
                    ts = [t for t in ts if getattr(t, _OWN_FACTS, False)]
                out.extend(ts)
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
            _split(f(expr), compiled, formulas)
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
        if result.pattern.wide:
            formulas.extend(result.wide_formulas())
        return
    if result is False or isinstance(result, (P, Formula)):
        formulas.append(result)
        return
    for r in result:
        _split(r, compiled, formulas)


registry = TemplateRegistry()
_adopt_memo(__name__, "registry._clauses_cache", "epoch")
_adopt_memo(__name__, "registry._mro_cache", "epoch")
