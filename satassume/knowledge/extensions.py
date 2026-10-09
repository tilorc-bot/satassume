"""Clause-generating functions registered per (predicate, argument classes).

This is satassume's counterpart of ``Predicate.register`` in SymPy's new
assumptions system.  A registered function receives the argument(s) of the
applied predicate and returns what it knows:

* ``True`` / ``False``: the predicate holds / does not hold for these
  arguments (a unit clause);
* ``None``: nothing;
* a formula over :class:`satassume.sat.formula.P` atoms (or an iterable of
  them), asserted as clauses.  The atom for the predicate itself is
  ``P(name, arg)`` for a unary predicate and ``P(name, (arg1, arg2, ...))``
  for a polyadic one; the formula may also mention vocabulary atoms about
  any expression (``P('integer', log(n + 1, 2))``), which the engine then
  visits.

Two kinds of registration are useful:

* a **custom predicate** (a name outside :data:`satassume.knowledge.rules.PREDICATES`)
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

from ..state.epoch import bump as _bump
from ..sat.formula import Formula, Not, P
from ..state.memos import adopt as _adopt_memo
from .rules import BASIS_OF, PRED_INDEX

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
        #: whether a vocabulary predicate has a function registered for a
        #: node class (:meth:`node_facts` can say anything); a plain
        #: attribute, read per node by the engine
        self.has_node_facts = False
        self._version = 0

    @property
    def version(self) -> int:
        """Bumped by every registration and unregistration; what depends on
        the registrations compares it instead of the handler lists.  Every
        assignment also starts a new registry epoch (:mod:`satassume.state.epoch`),
        which drops the caches of every engine."""
        return self._version

    @version.setter
    def version(self, value: int) -> None:
        self._version = value
        _bump()

    # -- registration --------------------------------------------------------
    def register(self, pred, *classes: type):
        """Decorator: register ``f(*args)`` for ``pred`` applied to arguments
        of the given classes (one class per argument)."""
        name = _name(pred)
        if not classes:
            raise TypeError("register() needs at least one argument class")
        if name in PRED_INDEX and not BASIS_OF[name]:
            # ``commutative``: true of every term in scope by definition
            # (rules.DEFINITIONS), with no variable a function could set
            raise ValueError(f"{name!r} is decided by definition and takes no registered function")

        def deco(f: Handler) -> Handler:
            self._handlers.setdefault(name, []).append((classes, f))
            self.version += 1
            if name in PRED_INDEX and len(classes) == 1:
                self._vocab.setdefault(name, []).append((classes, f))
                self._vocab_changed()
            return f

        return deco

    def unregister(self, pred) -> None:
        """Forget every function registered for ``pred``."""
        name = _name(pred)
        self._handlers.pop(name, None)
        self.version += 1
        if self._vocab.pop(name, None) is not None:
            self._vocab_changed()

    def _vocab_changed(self) -> None:
        self._node_cache.clear()
        self.has_node_facts = bool(self._vocab)

    def snapshot(self) -> Dict[str, List[Tuple[Tuple[type, ...], Handler]]]:
        """The registrations, ``{name: [(classes, function), ...]}`` in
        registration order, for :meth:`restore` (a test or the harness
        that registers temporarily)."""
        return {k: list(v) for k, v in self._handlers.items()}

    def restore(self, snap) -> None:
        """Make the registrations those of :meth:`snapshot` ``snap``; a new
        version, like any registration."""
        self._handlers = {k: list(v) for k, v in snap.items()}
        self._vocab = {}
        for name, lst in self._handlers.items():
            if name in PRED_INDEX:
                vocab = [e for e in lst if len(e[0]) == 1]
                if vocab:
                    self._vocab[name] = vocab
        self._vocab_changed()
        self.version += 1

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
        return self.is_scalar_class(type(obj))

    def is_scalar_class(self, cls: type) -> bool:
        """Whether a vocabulary predicate is registered for ``cls`` (or a
        base of it): :meth:`node_facts` may say something about its
        instances."""
        if not self._vocab:
            return False
        return bool(self._node_handlers(cls))

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
_adopt_memo(__name__, "extensions._node_cache", "extensions")


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
