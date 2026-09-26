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

Predicate transfer
------------------
With the first equality atom that is not glue (a user or extension atom;
the links' ``eq(e, 0)`` and interface equalities do not count), the session
attaches a :class:`satassume.transfer.TransferTheory`: every node block is
registered with it under the node's EUF term, so terms in one EUF class
share all unary facts (``Q.prime(x)`` from ``Q.eq(x, 2)``).  See
:meth:`Relations._engage_transfer`.

A relation no theory interprets makes ``ask`` return None
(:class:`Uninterpreted`), unless the engine was built with
``uninterpreted="free"``: then it stays a free Boolean.

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
import weakref
from typing import Any, Callable, List, NamedTuple, Optional

from .extensions import Args
from .formula import Not, P
from .rules import NPRED, PRED_INDEX
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


_SYMPY_ATOMS: dict = {}


def sympy_atom(atom: P):
    """``Q.eq(a, b)`` / ``Q.lt(a, b)`` for a normalised relation atom
    (memoized: a pure function of the atom)."""
    r = _SYMPY_ATOMS.get(atom)
    if r is None:
        from sympy.assumptions.ask import Q
        r = {"eq": Q.eq, "lt": Q.lt}[atom.pred](*atom.expr)
        if len(_SYMPY_ATOMS) >= 100_000:
            _SYMPY_ATOMS.clear()
        _SYMPY_ATOMS[atom] = r
    return r


def _is_number(e) -> bool:
    return bool(getattr(e, "is_number", False)) and not getattr(e, "free_symbols", True)


def _number_basis(engine, c, facts=False) -> tuple:
    """The predicates to register with the transfer theory for the number
    ``c``: a small set of its decided facts whose unit propagation under the
    rule base gives all of them, plus every predicate its facts leave open.

    A term merged with ``c`` receives the basis and its own rule block
    derives the rest, exactly the facts of ``c`` (the rule block propagates
    ``RULE_INTERNAL``, the same clauses as ``RULE_INSTANTIATED`` used here);
    a contradiction with a non-basis fact shows up in that block.  The open
    predicates are transferred as they are.  Memoized per engine and
    number (a number's facts are context-free)."""
    memo = engine.__dict__.setdefault("_xbasis", {})
    r = memo.get(c)
    if r is not None:
        return r[1] if facts else r[0]
    from .rules import PREDICATES, RULE_INSTANTIATED, unit_propagate
    decided, open_ = [], []
    for k, p in enumerate(PREDICATES):
        v = engine.is_(c, p)
        if v is None:
            open_.append(k)
        else:
            decided.append(k + 1 if v else -(k + 1))
    want = set(decided)

    def closes(lits):
        d = unit_propagate(RULE_INSTANTIATED, lits)
        return d is not None and want <= set(d) | set(lits)
    basis = []
    for l in decided:
        d = unit_propagate(RULE_INSTANTIATED, basis)
        if d is None or l not in set(d) | set(basis):
            basis.append(l)
    for l in list(basis):
        rest = [m for m in basis if m != l]
        if closes(rest):
            basis = rest
    if not closes(basis):                 # defensive: fall back to all
        basis = decided
    r = (tuple(sorted({abs(l) - 1 for l in basis} | set(open_))),
         tuple((abs(l) - 1, l > 0) for l in basis))
    memo[c] = r
    return r[1] if facts else r[0]


def _number_facts(engine, c) -> tuple:
    """``[(pred index, value), ...]``: the basis of the facts of number
    ``c`` (see :func:`_number_basis`)."""
    return _number_basis(engine, c, facts=True)


# --------------------------------------------------------------------------
# per-session glue
# --------------------------------------------------------------------------

class Relations:
    """Relation atoms of one :class:`satassume.engine.Session`: their
    theories, guards, links and shared equalities."""

    def __init__(self, session, specs):
        # A weak proxy: the session owns this object and outlives every call
        # into it, and a strong back-reference would make session + solver +
        # clauses collectable only by a full garbage collection.
        self.session = weakref.proxy(session)
        self.specs = list(specs)
        self.adapters: dict = {}          # spec name -> adapter instance
        self.status: dict = {}            # atom -> interpreted by some theory
        self.queue: List[P] = []          # allocated, not yet interpreted
        self.linked: set = set()
        self.top: dict = {}               # vocabulary-atom arguments of user formulas
        self.active = False               # some relation atom exists
        self.sharing = EqualitySharing()
        self._pending_links: list = []
        #: eq atoms the glue made (links ``eq(e, 0)``, interface equalities);
        #: they do not engage predicate transfer by themselves
        self._aux_eq: set = set()
        self._link_eq: set = set()        # the links' eq(e, 0), of _aux_eq
        #: sides of the equality atoms EUF interprets -> 2 (a user or
        #: extension atom, or a number) or 1 (only a link's eq(e, 0));
        #: interface equalities add nothing (see sync_transfer)
        self._xside: dict = {}
        #: predicate transfer (satassume.transfer), engaged by the first
        #: user or template equality atom; None until then
        self.xfer = None
        self._xadapter = None
        self._xslot = 1                   # cursor into table.slots
        self._xterm = 0                   # cursor into the adapter's atom sides
        self._xnsides = -1                # _xside state seen by sync_transfer
        self._xnterms = -1                # EUF atom terms counted in _xheads
        self._xpart: set = set()          # link-only sides (polar registered)
        self._xheads: dict = {}           # (func, nargs) -> known expressions
        self._xseen: set = set()          # expressions counted in _xheads
        self._xpend: list = []            # (node, base) not yet candidates
        self._xcand: set = set()          # candidate nodes (registered)

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
        no theory (unless the engine leaves such atoms free Booleans,
        ``Engine(uninterpreted="free")``)."""
        s = self.session
        user = [a for a in user_atoms if a.pred in RELATION_ATOMS]
        for a in user:
            for side in a.expr:
                self._link_later(side)
        for a in user:
            if a.pred == "eq":
                self._want_transfer = True
                self._note_sides(a, 2)
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
            if self._want_transfer and self.xfer is None:
                self._engage_transfer()
            if self.xfer is not None and self._transfer_terms():
                continue
            break
        if self.xfer is not None:
            self.sync_transfer()
        if s.engine.uninterpreted == "free":
            return
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
                    if atom.pred == "eq" and hasattr(ad, "node_term"):
                        if atom not in self._aux_eq:
                            self._want_transfer = True
                            self._note_sides(atom, 2)
                        elif atom in self._link_eq:
                            self._note_sides(atom, 1)
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
        eqa = relation_atom("eq", e, S.Zero)
        if eqa not in self.session.table.custom:
            self._aux_eq.add(eqa)
            self._link_eq.add(eqa)
        eq = self._atom_var(eqa)
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
            eqa = relation_atom("eq", a, b)
            if eqa not in self.session.table.custom:
                self._aux_eq.add(eqa)
            self._atom_var(eqa)
        return bool(pairs)

    # -- predicate transfer (satassume.transfer) -------------------------
    #
    # Engaged explicitly, once per session, by the first equality atom that
    # is not glue (a user atom, or one a template or extension made); the
    # links' eq(e, 0) and the interface equalities alone do not engage it.
    # Engaging attaches the EUF adapter's theory (if not yet) and a
    # TransferTheory; from then on every node block of the session is
    # registered with it (its expression interned as an EUF term, so
    # congruence applies to it), and every expression EUF interns for an
    # atom is visited as a node (so x = 2 finds the facts of 2).

    _want_transfer = False

    def _congruent(self, node) -> bool:
        """``node`` may become congruent to another known application of
        the same head: argument by argument, the two are the same
        expression or both may be merged (a side or a candidate, and not
        two distinct Rationals: EUF keeps those apart, but a Float or an
        irrational number is an opaque term that may equal a Rational or
        another spelling of the same value), and at least one pair
        differs."""
        others = self._xheads.get((node.func, len(node.args)))
        if not others or len(others) < 2:
            return False
        cand, xside = self._xcand, self._xside
        args = node.args
        for o in others:
            if o is node or o == node:
                continue
            differ = False
            for a, b in zip(args, o.args):
                if a == b:
                    continue
                if not ((a in cand or a in xside) and (b in cand or b in xside)) \
                        or (a.is_Rational and b.is_Rational):
                    break
                differ = True
            else:
                if differ:
                    return True
        return False

    def _note_sides(self, atom, level) -> None:
        xs = self._xside
        for e in atom.expr:
            lv = 2 if _is_number(e) else level
            if xs.get(e, 0) < lv:
                xs[e] = lv

    def _engage_transfer(self) -> None:
        s = self.session
        if not s.engine.transfer:
            return
        ad = None
        for spec in self.specs:
            if not spec.guarded:
                a = self._adapter(spec)
                if hasattr(a, "node_term"):
                    ad = a
                    break
        if ad is None:
            return
        from .transfer import TransferTheory
        solver = s.solver
        ad.attach(solver)
        th = TransferTheory(ad.theory)
        solver.attach_theory(th)
        self._xadapter = ad
        self.xfer = th
        s.xfer = self

    def _transfer_terms(self) -> bool:
        """Visit the sides of the atoms EUF registered since the last call
        (numbers included); True if a node was visited."""
        from itertools import islice
        from sympy import Expr
        sides = self._xside
        n = len(sides)
        if self._xterm >= n:
            return False
        new = list(islice(sides, self._xterm, n))
        self._xterm = n
        from sympy import Rational
        s = self.session
        ad, th = self._xadapter, self.xfer
        visited = False
        for e in new:
            if isinstance(e, Rational):
                # a rational's facts are closed and context-free: the theory
                # holds a basis of them for its term instead of a node (no
                # visit, no variables, no change to the session's search)
                t = ad.term_of(e)
                if t is not None:
                    th.set_fixed(t, _number_facts(s.engine, e))
                continue
            if isinstance(e, Expr) and e not in s.base:
                s.ensure(e)
                visited = True
        return visited

    def sync_transfer(self) -> None:
        """Register with the transfer theory the predicate variables of the
        nodes whose terms EUF could put into a class with another term.

        A term joins a class only through a union: as the side of an atom,
        or as an application congruent to another one with the same head
        (function and arity) whose arguments were merged.  So a node is a
        *candidate* (all 33 variables registered) iff it is a side of a user
        or extension equality atom, a number side, or an application whose
        head occurs on at least two known expressions and one of whose
        arguments is a side or a candidate.  Two kinds of sides are left out
        on purpose:

        * a side ``e`` only of the link ``eq(e, 0)``: ``e`` joins the class
          of ``0`` only when that atom holds, and then the link clause makes
          ``zero(e)`` true, from which the rule base decides every predicate
          but ``polar`` exactly as the facts of the number ``0`` (itself a
          candidate) do; so only ``polar`` is registered for ``e``;
        * a side only of interface equalities (equality sharing): those are
          how equalities LRA derives reach EUF, which transfer leaves out.

        Candidacy only grows, so the nodes not (fully) registered are kept
        and looked at again on the next call.  This runs at root-safe points
        (the end of :meth:`process`, the start of ``Session.query_literal``).
        """
        s = self.session
        slots = s.table.slots
        ad = self._xadapter
        xside = self._xside
        i, n = self._xslot, len(slots)
        nside = len(xside) + sum(xside.values())
        nterms = len(ad._terms)
        if i >= n and nside == self._xnsides and nterms == self._xnterms:
            return
        from sympy import Basic, Rational, nan
        from .euf_adapter import _structural
        heads = self._xheads
        seen = self._xseen
        pend = self._xpend

        def count(e):
            if e not in seen:
                seen.add(e)
                if isinstance(e, Basic) and _structural(e):
                    k = (e.func, len(e.args))
                    h = heads.get(k)
                    if h is None:
                        heads[k] = [e]
                    else:
                        h.append(e)
        while i < n:
            e = slots[i]
            if type(e) is tuple and e[1] == i:
                node = e[0]
                if isinstance(node, Basic) and not node.has(nan):
                    count(node)
                    pend.append((node, i))
                i += NPRED
            else:
                i += 1
        self._xslot = n
        self._xnsides = nside
        if nterms != self._xnterms:
            self._xnterms = nterms
            for e in ad.terms():
                count(e)
        if not pend:
            return
        cand = self._xcand
        part = self._xpart
        solver, th = s.solver, self.xfer
        polar = PRED_INDEX["polar"]
        changed = True
        while changed and pend:
            changed = False
            keep = []
            for node, b in pend:
                lv = xside.get(node, 0)
                if lv == 2 or (_structural(node) and self._congruent(node)):
                    cand.add(node)
                    changed = True
                    t = ad.node_term(node)
                    solver.ensure_vars(b + NPRED - 1)     # one _grow, not 33
                    preds = (_number_basis(s.engine, node) if _is_number(node)
                             and isinstance(node, Rational) else range(NPRED))
                    for k in preds:
                        if k != polar or node not in part:
                            solver.register_atom(th, b + k, (t, k), False)
                    continue
                if lv == 1 and node not in part:
                    part.add(node)
                    solver.register_atom(th, b + polar, (ad.node_term(node), polar), False)
                keep.append((node, b))
            pend[:] = keep
