"""Clause-generating functions registered per (predicate, argument classes).

This is satassume's counterpart of ``Predicate.register`` in SymPy's new
assumptions system.  A registered function receives the argument(s) of the
applied predicate and returns what it knows:

* ``True`` / ``False``: the predicate holds / does not hold for these
  arguments (a unit clause);
* ``None``: nothing;
* a formula over :class:`satassume.formula.P` atoms (or an iterable of
  them), asserted as clauses.  The atom for the predicate itself is
  ``P(name, arg)`` for a unary predicate and ``P(name, (arg1, arg2, ...))``
  for a polyadic one; the formula may also mention vocabulary atoms about
  any expression (``P('integer', log(n + 1, 2))``), which the engine then
  visits.

Two kinds of registration are useful:

* a **custom predicate** (a name outside :data:`satassume.rules.PREDICATES`)
  gets its own atom variable per argument tuple, outside the per-node rule
  block, so it takes part in propagation and search like any other atom
  (``ask(Q.mersenne(n), Q.mersenne(n))`` is decided propositionally);
* a **vocabulary predicate on a new class** (``register('prime', MyType)``)
  adds facts to the node's rule block when a node of that class is visited,
  just like a structural template.

Registration matches on ``isinstance`` for every argument, so a function
registered for ``Symbol`` also applies to ``Dummy``.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from .formula import Formula, Not, P
from .rules import PRED_INDEX

Handler = Callable[..., Any]


class Args(tuple):
    """The argument tuple of a polyadic predicate, used as the ``expr`` of
    its atom: ``P('sexyprime', Args((5, 11)))``."""
    __slots__ = ()


def _name(pred) -> str:
    """Accept a string or a SymPy ``Predicate``."""
    name = getattr(pred, 'name', pred)
    name = getattr(name, 'name', name)   # Predicate.name is a Str
    if not isinstance(name, str):
        raise TypeError(f"predicate name expected, got {pred!r}")
    return name


class Extensions:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[Tuple[Tuple[type, ...], Handler]]] = {}
        self._vocab: Dict[str, List[Tuple[Tuple[type, ...], Handler]]] = {}
        self._node_cache: Dict[type, List[Tuple[str, Handler]]] = {}

    # -- registration --------------------------------------------------------
    def register(self, pred, *classes: type):
        """Decorator: register ``f(*args)`` for ``pred`` applied to arguments
        of the given classes (one class per argument)."""
        name = _name(pred)
        if not classes:
            raise TypeError("register() needs at least one argument class")

        def deco(f: Handler) -> Handler:
            self._handlers.setdefault(name, []).append((classes, f))
            if name in PRED_INDEX and len(classes) == 1:
                self._vocab.setdefault(name, []).append((classes, f))
                self._node_cache.clear()
            return f

        return deco

    def unregister(self, pred) -> None:
        """Forget every function registered for ``pred``."""
        name = _name(pred)
        self._handlers.pop(name, None)
        if self._vocab.pop(name, None) is not None:
            self._node_cache.clear()

    def is_registered(self, pred, arity: int = 1) -> bool:
        """Whether ``pred`` has a function registered for ``arity`` arguments
        (of any classes)."""
        name = _name(pred)
        return any(len(classes) == arity for classes, _ in self._handlers.get(name, ()))

    # -- lookup ---------------------------------------------------------------
    def handlers(self, name: str, args: tuple) -> List[Handler]:
        n = len(args)
        return [f for classes, f in self._handlers.get(name, ())
                if len(classes) == n and all(isinstance(a, c) for a, c in zip(args, classes))]

    def is_scalar_like(self, obj) -> bool:
        """Whether ``type(obj)`` has a vocabulary predicate registered: such
        objects are nodes of the engine like any scalar expression."""
        if not self._vocab:
            return False
        return bool(self._node_handlers(type(obj)))

    def facts_for(self, atom: P) -> List[Any]:
        """Formulas for a custom-predicate atom ``P(name, arg | Args)``."""
        args = atom.expr if isinstance(atom.expr, Args) else (atom.expr,)
        out: List[Any] = []
        for f in self.handlers(atom.pred, args):
            _collect(f(*args), atom, out)
        return out

    def node_facts(self, node) -> List[Any]:
        """Formulas from vocabulary predicates registered for ``type(node)``
        (the template-like use)."""
        if not self._vocab:
            return []
        out: List[Any] = []
        for name, f in self._node_handlers(type(node)):
            _collect(f(node), P(name, node), out)
        return out

    def _node_handlers(self, cls: type) -> List[Tuple[str, Handler]]:
        hs = self._node_cache.get(cls)
        if hs is None:
            hs = []
            for name, lst in self._vocab.items():
                for classes, f in lst:
                    if issubclass(cls, classes[0]):
                        hs.append((name, f))
            self._node_cache[cls] = hs
        return hs


def _collect(result, atom: P, out: List[Any]) -> None:
    if result is None:
        return
    if result is True:
        out.append(atom)
    elif result is False:
        out.append(Not(atom))
    elif isinstance(result, (P, Formula)):
        out.append(result)
    else:
        for r in result:
            _collect(r, atom, out)


#: The default registry, used by :func:`satassume.sympy_api.ask`.
extensions = Extensions()


def register(pred, *classes: type):
    """Register a clause-generating function on the default registry; see
    the module docstring.  ``pred`` is a name or a SymPy ``Predicate``.

    >>> @register('mersenne', Integer)          # doctest: +SKIP
    ... def _(n):
    ...     return Implies(P('integer', log(n + 1, 2)), P('mersenne', n))
    """
    return extensions.register(pred, *classes)


def unregister(pred) -> None:
    extensions.unregister(pred)
