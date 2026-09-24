"""Relation atoms (``Q.eq``, ``Q.lt``, ``x < y``, ...) and theory solvers.

A relation reaches the engine as one of two atom kinds, after
normalisation by :func:`relation_atom`:

* ``P('eq', Args((a, b)))`` for ``a == b`` (arguments in ``default_sort_key``
  order, so ``Eq(a, b)`` and ``Eq(b, a)`` share a variable);
* ``P('lt', Args((a, b)))`` for ``a < b``;

and ``a > b`` is ``lt(b, a)``, ``a <= b`` is ``Not(lt(b, a))``, ``a >= b`` is
``Not(lt(a, b))``, ``a != b`` is ``Not(eq(a, b))``.  Treating ``<=`` as the
complement of the reversed ``<`` is SymPy's own definition, not an
assumption about the arguments: ``~(x < 0)`` *is* ``x >= 0`` in SymPy
(``Relational.negated``, ``BinaryRelation.negated``), for any ``x``, and
``ask(Q.le(x, y), Q.gt(x, y))`` is False for a plain symbol.  Each atom gets
one solver variable like any non-vocabulary atom (``VarTable.custom``).

Meaning
-------
``eq`` is equality of values; it holds or fails in every domain (complex,
extended reals) and is given to theories that interpret it unconditionally
(EUF).  ``lt`` has its usual meaning when both sides are finite reals;
SymPy gives it no meaning otherwise (``is_ge`` returns None for
non-real arguments, ``lra_satask`` refuses anything that is not
``is_real``), so for other arguments the atom is left uninterpreted: a free
Boolean.  A *guarded* theory (LRA) therefore never sees the atom's
variable ``r`` itself.  The engine registers a fresh variable ``t`` with the
theory and adds

    real(u1) & ... & real(uk)  ->  (r <-> t)

for the opaque terms ``u`` of the atom's linear form (``real`` implies
``finite`` in the vocabulary).  When a term may be non-real, ``t`` floats
free and can never cause a conflict involving ``r``, which is sound under
any semantics SymPy might later adopt for such arguments.  ``eq`` atoms go
to guarded theories the same way (LRA's ``a - b = 0``) and to unguarded
ones (EUF) directly.

Links to the unary vocabulary
-----------------------------
For every argument ``e`` of a relation in the query or the assumptions,
and every argument of a vocabulary atom of the query or the assumptions
once the session has relations, the engine adds (``gt(e, 0)`` is the atom
``lt(0, e)``):

====================================  ======================================
clause                                why it is sound
====================================  ======================================
``positive(e) -> gt(e, 0)``           positive means real, finite, > 0
``gt(e, 0) & real(e) -> positive(e)`` for a finite real, ``> 0`` is positive
``negative(e) -> lt(e, 0)``           as above
``lt(e, 0) & real(e) -> negative(e)`` as above
``zero(e) <-> eq(e, 0)``              ``Eq(e, 0)`` holds iff ``e`` is zero,
                                      in any domain (``Eq(nan, 0)`` is False
                                      and ``nan`` is not zero)
====================================  ======================================

The rule base derives ``nonnegative``, ``nonzero``, ``extended_*`` and the
rest from these three.  Numbers are not linked (their unary facts are
closed already).

Combining theories
------------------
Theories are kept apart by atom kind (each adapter accepts what it can
interpret; ``eq`` may go to several) and share equalities through
interface atoms: whenever a term becomes known to two adapters
(``shared_terms()``), the atom ``eq(a, b)`` is created for it and every
other shared term, and registered like any other relation atom, so each
theory sees the same Boolean (delayed theory combination; see
:class:`satassume.theory.EqualitySharing`).

Adapters
--------
An adapter spec is ``(name, factory, guarded)``; ``factory()`` returns an
object with

* ``register(solver, var, atom) -> bool``: interpret the SymPy atom
  (``Q.lt(a, b)`` or ``Q.eq(a, b)``) and register ``var``
  with its theory (attaching the theory on first use); False if the atom
  is not interpreted;
* ``terms(atom) -> list`` (guarded adapters): the opaque terms of the
  atom, for the guard;
* ``shared_terms() -> set``: every term the adapter's theory knows.

The default specs are the LRA and EUF adapters when their modules exist
(:func:`default_specs`).  With no spec at all the engine behaves exactly
as without relation support: ``sympy_api.ask`` returns None for relations.
"""
from __future__ import annotations

import importlib
from typing import Any, Callable, List, NamedTuple, Optional

from .extensions import Args
from .formula import Not, P
from .rules import PRED_INDEX
from .theory import EqualitySharing

#: atom predicates the engine gives to theories
RELATION_ATOMS = frozenset({"eq", "lt"})

_OPS = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}


class AdapterSpec(NamedTuple):
    name: str
    factory: Callable[[], Any]
    guarded: bool


def _optional(module: str, attr: str):
    """``module.attr`` if ``module`` exists; a broken module raises."""
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError as e:
        if e.name == module:
            return None
        raise
    return getattr(mod, attr)


def default_specs() -> List[AdapterSpec]:
    specs = []
    lra = _optional("satassume.lra_adapter", "LRAAdapter")
    if lra is not None:
        specs.append(AdapterSpec("lra", lra, True))
    euf = _optional("satassume.euf_adapter", "EUFAdapter")
    if euf is not None:
        specs.append(AdapterSpec("euf", euf, False))
    return specs


class Uninterpreted(Exception):
    """A relation of the query or the assumptions is interpreted by no
    theory; ``ask`` returns None (as without relation support)."""


# --------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------

def _key(e):
    from sympy.core.sorting import default_sort_key
    return default_sort_key(e)


def relation_atom(name: str, lhs, rhs):
    """The formula for relation ``name`` (``eq ne lt le gt ge``)."""
    if name in ("eq", "ne"):
        a, b = sorted((lhs, rhs), key=_key)
        atom = P("eq", Args((a, b)))
        return atom if name == "eq" else Not(atom)
    if name == "lt":
        return P("lt", Args((lhs, rhs)))
    if name == "gt":
        return P("lt", Args((rhs, lhs)))
    if name == "le":
        return Not(P("lt", Args((rhs, lhs))))
    if name == "ge":
        return Not(P("lt", Args((lhs, rhs))))
    raise ValueError(f"unknown relation {name!r}")


def relational_name(rel) -> str:
    """``eq ne lt le gt ge`` for a SymPy ``Relational``."""
    return _OPS[rel.rel_op]


def sympy_atom(atom: P):
    from sympy.assumptions.ask import Q
    return {"eq": Q.eq, "lt": Q.lt}[atom.pred](*atom.expr)


def _is_number(e) -> bool:
    return bool(getattr(e, "is_number", False)) and not getattr(e, "free_symbols", True)


# --------------------------------------------------------------------------
# per-session glue
# --------------------------------------------------------------------------

class Relations:
    """Relation atoms of one :class:`satassume.engine.Session`: their
    theories, guards, links and shared equalities."""

    def __init__(self, session, specs):
        self.session = session
        self.specs = list(specs)
        self.adapters: dict = {}          # spec name -> adapter instance
        self.status: dict = {}            # atom -> interpreted by some theory
        self.queue: List[P] = []          # allocated, not yet interpreted
        self.linked: set = set()
        self.top: dict = {}               # vocabulary-atom arguments of user formulas
        self.active = False               # some relation atom exists
        self.sharing = EqualitySharing()
        self._pending_links: list = []

    # -- entry points used by the session ------------------------------
    def enqueue(self, atom: P) -> None:
        self.queue.append(atom)

    def note_formula(self, atoms) -> None:
        """Remember the vocabulary-atom arguments of a user formula."""
        for a in atoms:
            if a.pred in PRED_INDEX and a.expr not in self.linked:
                self.top[a.expr] = None

    def process(self, user_atoms=()) -> None:
        """Interpret queued atoms, add guards, links and shared equalities;
        raise :class:`Uninterpreted` if a relation among ``user_atoms`` has
        no theory."""
        s = self.session
        user = [a for a in user_atoms if a.pred in RELATION_ATOMS]
        for a in user:
            for side in a.expr:
                self._link_later(side)
        while True:
            s._flush()
            s._discover()
            if self.queue:
                atom = self.queue.pop()
                self.status[atom] = self._interpret(atom)
                self.active = True
                continue
            if self.active and self.top:
                top, self.top = self.top, {}
                for e in top:
                    self._link_later(e)
            if self._pending_links:
                self._link(self._pending_links.pop())
                continue
            if self._share():
                continue
            break
        for a in user:
            if not self.status.get(a):
                raise Uninterpreted(f"no theory interprets {a}")

    def _link_later(self, e) -> None:
        if e not in self.linked and not _is_number(e):
            self.linked.add(e)
            self._pending_links.append(e)

    # -- interpretation ------------------------------------------------
    def _adapter(self, spec):
        ad = self.adapters.get(spec.name)
        if ad is None:
            ad = self.adapters[spec.name] = spec.factory()
        return ad

    def _interpret(self, atom: P) -> bool:
        s = self.session
        solver = s.solver
        var = s.table.custom[atom]
        sat = sympy_atom(atom)
        ok = False
        for spec in self.specs:
            ad = self._adapter(spec)
            if not spec.guarded:
                if ad.register(solver, var, sat):
                    ok = True
                continue
            terms = ad.terms(sat)
            if terms is None:                 # not interpreted: no variable
                continue
            t = s.table.aux()
            solver.ensure_vars(t)
            if not ad.register(solver, t, sat):
                continue
            ok = True
            guard = []
            for u in terms:
                s.ensure(u, {"real"})
                guard.append(-s.var("real", u))
            s._emit(guard + [-var, t])
            s._emit(guard + [var, -t])
        return ok

    # -- links to the unary vocabulary ----------------------------------
    def _atom_var(self, f) -> int:
        """Variable of a normalised relation atom (allocated if new; its
        interpretation is queued by the session)."""
        return self.session.table.var(f)

    def _link(self, e) -> None:
        from sympy import S
        s = self.session
        s.ensure(e, {"positive", "negative", "zero", "real"})
        pos, neg = s.var("positive", e), s.var("negative", e)
        zero, real = s.var("zero", e), s.var("real", e)
        gt = self._atom_var(relation_atom("lt", S.Zero, e))
        lt = self._atom_var(relation_atom("lt", e, S.Zero))
        eq = self._atom_var(relation_atom("eq", e, S.Zero))
        emit = s._emit
        emit([-pos, gt])
        emit([-gt, -real, pos])
        emit([-neg, lt])
        emit([-lt, -real, neg])
        emit([-zero, eq])
        emit([-eq, zero])

    # -- equality sharing -------------------------------------------------
    def _share(self) -> bool:
        if len(self.adapters) < 2:
            return False
        sets = [set(ad.shared_terms()) for ad in self.adapters.values()]
        pairs = self.sharing.update(sets)
        for a, b in pairs:
            if _is_number(a) and _is_number(b):
                continue
            self._atom_var(relation_atom("eq", a, b))
        return bool(pairs)
