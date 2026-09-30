"""Relation atoms (``Q.eq``, ``Q.lt``, ``x < y``, ...) and theory solvers.

A relation reaches the engine as one of two atom kinds, after
normalisation by :func:`relation_atom`:

* ``P('eq', Args((a, b)))`` for ``a == b`` (arguments in ``default_sort_key``
  order, so ``Eq(a, b)`` and ``Eq(b, a)`` share a variable);
* ``P('lt', Args((a, b)))`` for ``a < b``;

and ``a > b`` is ``lt(b, a)``, ``a != b`` is ``Not(eq(a, b))``,

    a <= b   is   extended_real(a) & extended_real(b) & ~lt(b, a),
    a >= b   is   extended_real(a) & extended_real(b) & ~lt(a, b)

(an ``extended_real`` conjunct is left out for a Rational, ``oo`` or
``-oo`` side, and the formula is False for a ``nan`` side, which is no
extended real although the rule base cannot say so).  Each atom gets one
solver variable like any non-vocabulary atom (``VarTable.custom``).

Meaning
-------
Order relations are over the extended reals and assert that their sides
are extended reals: ``a < b`` holds iff ``a`` and ``b`` are extended reals
and ``a < b`` there (``-oo`` < every finite real < ``oo``).  So
``Q.lt(x, 1)`` implies ``extended_real(x)``, ``x < oo`` is
``extended_real(x) & ~positive_infinite(x)``, ``x < zoo`` and ``I < 1``
are false, and ``~(a < b)`` is *not* ``a >= b``: it also holds when a side
is not an extended real (hence the ``extended_real`` conjuncts of ``<=``).
``Q.gt(x, 0)`` gives ``extended_positive(x)`` but not ``positive(x)``
(``x = oo``).

``eq`` is equality of values; it holds or fails in every domain (complex,
extended reals: ``Eq(I, I)`` is True, ``Eq(oo, oo)`` is True) and asserts
nothing about the sides; ``ne`` is its negation.  An equality with ``oo``
or ``-oo`` is linked to the unary vocabulary: ``eq(e, oo) <->
positive_infinite(e)``, ``eq(e, -oo) <-> negative_infinite(e)``
(:meth:`Relations._eq_infinity`); two sides at the same infinity, or with
a zero difference, are equal, and sides with a nonzero difference are not
(:meth:`Relations._eq_links`).  It is given to theories
that interpret it unconditionally (EUF) and, for finite real terms, to
LRA (below).

An ``lt`` atom ``r`` for ``a < b`` gets these clauses
(:meth:`Relations._order_sides`, :meth:`Relations._order_infinite`):

1. *sides*: ``r -> extended_real(a)`` and ``r -> extended_real(b)``; a
   closed side the engine knows is no extended real (``zoo``, ``I``,
   ``1 + I``, ``nan``) makes ``r`` false outright.  This reads the node
   facts of the sides, so it is only as sound as the templates'
   ``extended_real`` rules (a sum or product of extended reals need not
   be one: ``oo - oo`` and ``0*oo`` are nan).
2. *infinite terms* (when the guarded adapter can split both sides into
   linear forms, :func:`satassume.lra_adapter.order_sides`): each side is
   ``sum(c_i * u_i) + k`` (rational ``c_i``, opaque terms ``u_i``, a
   rational ``k``, and possibly one ``oo`` or ``-oo`` summand).  A term
   pushes its side *up* if it is ``positive_infinite`` with ``c > 0`` or
   ``negative_infinite`` with ``c < 0`` (the ``oo`` summand always does),
   *down* in the other two cases.  In the extended reals a side with an
   up push is ``+oo`` or undefined (``oo - oo``), and with any non-real
   term it is no extended real either, so:

   * a push up in ``a`` -> ``~r``;  a push down in ``b`` -> ``~r``;
   * a push down in ``a``, no push up in ``a``, no push down in ``b``, every
     term an extended real -> ``r`` (``a = -oo``, ``b > -oo``);
   * a push up in ``b``, no push down in ``b``, no push up in ``a``, every
     term an extended real -> ``r`` (``b = +oo``, ``a < +oo``).

   The last two need every coefficient nonzero (a cancelling term would be
   ``oo - oo``); without that they are left out (incomplete, sound).
3. *finite terms* (LRA, unchanged): a *guarded* theory never sees ``r``
   itself.  The engine registers a fresh variable ``t`` with the theory
   and adds

       real(u1) & ... & real(uk)  ->  (r <-> t)

   for the opaque terms ``u`` of the linear form of ``a - b`` (``real``
   implies ``finite``).  With every term a finite real both sides are
   finite reals, where ``t`` is exact.  An atom with an ``oo`` summand has
   no finite case and gets no ``t``.  Closed real constants (``pi``) are
   terms with bounds (below) and never infinite.

When no term is ``+-oo`` and every term is real the atom is exactly ``t``;
when some term is infinite, clauses 2 decide it as far as the signs allow;
with a non-real term only clause 1 applies (the side may still be real:
``x + y`` with ``x = I``, ``y = 1 - I``).  ``eq`` atoms go to guarded
theories with the guard of clause 3 (LRA's ``a - b = 0``) and to unguarded
ones (EUF) directly.

An ``lt`` atom is *interpreted* when clause 1 decides it, when it has an
``oo`` summand and clauses 2 apply, or when a guarded theory registers it
(clause 3); otherwise it keeps clause 1 but is uninterpreted (below).

Links to the unary vocabulary
-----------------------------
For every argument ``e`` of a relation in the query or the assumptions,
and every argument of a vocabulary atom of the query or the assumptions
once the session has relations, the engine adds (``gt(e, 0)`` is the atom
``lt(0, e)``):

======================================  ======================================
clause                                  why it is sound
======================================  ======================================
``extended_positive(e) <-> gt(e, 0)``   ``0 < e`` in the extended reals
``extended_negative(e) <-> lt(e, 0)``   as above
``zero(e) <-> eq(e, 0)``                ``Eq(e, 0)`` holds iff ``e`` is zero,
                                        in any domain (``Eq(nan, 0)`` is
                                        False and ``nan`` is not zero)
======================================  ======================================

The rule base derives ``positive`` (``extended_positive & finite``),
``nonnegative``, ``nonzero`` and the rest from these three.  Numbers are
not linked (their unary facts are closed already).

Integrality
-----------
Each linked ``e`` whose linear form a guarded adapter reads
(:func:`satassume.lra_adapter.integer_form`: ``sum(c_i*u_i) + k`` with
rational ``c_i``, ``k`` and opaque or constant terms ``u_i``, as a side of
an LRA atom) also gets an integrality atom ``i`` ("the form is an
integer", :class:`satassume.lra.Integral`) and, with the guard of
clause 3,

    real(u1) & ... & real(uk)  ->  (integer(e) <-> i)

Sound: with every term a finite real, ``e`` is the form's value, a finite
real, and ``integer(e)`` holds iff that value is an integer (SymPy's
``integer`` implies finite, so ``oo`` is no integer, and an infinite term
fails the guard).  The theory rounds bounds and branches (see
:mod:`satassume.lra`, "Integrality"), so ``Q.integer(t)`` is False under
``0 < t < 1`` and ``Q.ge(n, 1)`` is True for an integer ``n > 0``; the
``<-`` half gives True where the bounds pin ``e`` to an integer
(``Q.integer(x)`` under ``2 <= x <= 2``).  The opaque terms themselves
are not linked (a declared-integer ``n`` inside ``2*n + 1`` counts through
the linked sides only).  ``INTEGERS = False`` turns the link off.

Constant terms
--------------
A closed real constant in a linear position (``pi`` of ``x <= 3*pi/2``) is
a term of the LRA form (see :mod:`satassume.lra_adapter`); its guard
``real(pi)`` is decided at the root by the rule base, and the first atom
that brings it in has the adapter register its rational bounds
``lo < pi < hi`` as two theory atoms asserted by unit clauses, once per
session (:meth:`Relations._bound`).  A constant the engine knows to be
real context-free (``Engine.is_``) gets no guard literal and hence no node
of its own: its ``real`` literal would be false at the root anyway.

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
:class:`satassume.theory.EqualitySharing`).  A pair with a constant term
that is not rational (``eq(pi, x)``) gets no interface atom.  Such an
atom passes an equality with the constant between the theories, e.g.
``x = pi`` derived by LRA from ``x <= pi <= x`` reaching EUF, where it
would give ``f(x) = f(pi)``; on the refine stream these atoms decided no
query and cost search (about 10% of the decisions under the assumption
sets with ``pi``).  Leaving them out is a relaxation, never unsound.

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
* optionally ``order_sides(atom)`` (guarded adapters): the linear forms of
  the two sides of ``Q.lt(a, b)`` with their ``oo`` summands, for
  clauses 2 (see :func:`satassume.lra_adapter.order_sides`);
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
from .formula import And, Not, P
from .rules import NPRED, PRED_INDEX
from .theory import EqualitySharing

#: atom predicates the engine gives to theories
RELATION_ATOMS = frozenset({"eq", "lt"})

#: link ``integer(e)`` to an integrality atom of the guarded theories (see
#: "Integrality")
INTEGERS = True

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


def _ext_atoms(*sides) -> list:
    """``extended_real(e)`` for each side that is not a Rational, ``oo`` or
    ``-oo`` (those are extended reals)."""
    from sympy import S
    return [P("extended_real", e) for e in sides
            if not (getattr(e, "is_Rational", False) or e is S.Infinity
                    or e is S.NegativeInfinity)]


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
    if name in ("le", "ge"):
        a, b = (lhs, rhs) if name == "le" else (rhs, lhs)     # a <= b
        from sympy import S
        if a is S.NaN or b is S.NaN:
            return False                  # nan is no extended real
        f = Not(P("lt", Args((b, a))))
        ext = _ext_atoms(a, b)
        return And(*ext, f) if ext else f
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


def _constant_term(e) -> bool:
    """``e`` is a closed constant that is not a rational number (``pi``,
    ``sqrt(2)``): an LRA term with bounds, left out of equality sharing."""
    return _is_number(e) and not e.is_Rational


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
        self._bounded: set = set()        # constant terms whose bounds are asserted
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
        order = atom.pred == "lt"
        if order and self._order_sides(var, atom):
            return True                       # false: a side is no extended real
        if atom.pred == "eq":
            self._eq_infinity(var, atom)
            if atom not in self._aux_eq:
                self._eq_links(var, atom)
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
            if order and hasattr(ad, "order_sides"):
                sides = ad.order_sides(sat)
                if sides is not None:
                    self._order_infinite(var, sides)
                    if sides[0][1] or sides[1][1]:
                        ok = True             # an oo summand: no finite case
                        continue
            terms = ad.terms(sat)
            if terms is None:                 # not interpreted: no variable
                continue
            t = s.table.aux()
            solver.ensure_vars(t)
            if not ad.register(solver, t, sat):
                continue
            ok = True
            guard = self._guard(ad, terms)
            s._emit(guard + [-var, t])
            s._emit(guard + [var, -t])
        return ok

    def _guard(self, ad, terms) -> list:
        """``[-real(u), ...]`` for the opaque terms ``u`` of a guarded
        theory atom (clause 3); a constant term gets its bounds asserted
        (once per session) and no literal when it is real at the root."""
        s = self.session
        guard = []
        for u in terms:
            if _is_number(u):
                if u not in self._bounded:
                    self._bounded.add(u)
                    self._bound(ad, u)
                if s.engine.is_(u, "real") is True:
                    # real(u) holds at the root: its guard literal is
                    # false everywhere, and u needs no node here
                    continue
            s.ensure(u, {"real"})
            guard.append(-s.var("real", u))
        return guard

    def _link_integer(self, ad, e) -> None:
        """``guard -> (integer(e) <-> i)`` for the integrality atom ``i`` of
        ``e``'s linear form in the guarded adapter ``ad`` (see
        "Integrality"); called once per linked expression."""
        form = ad.integer_form(e)
        if form is None:
            return
        s = self.session
        i = s.table.aux()
        s.solver.ensure_vars(i)
        ad.register_integer(s.solver, i, form)
        guard = self._guard(ad, form[1])
        z = s.var("integer", e)
        s._emit(guard + [-z, i])
        s._emit(guard + [z, -i])

    def _eq_infinity(self, var: int, atom: P) -> None:
        """``eq(e, oo) <-> positive_infinite(e)`` and ``eq(e, -oo) <->
        negative_infinite(e)``: ``Eq(e, oo)`` holds iff ``e`` is ``+oo``, in
        any domain (``Eq(zoo, oo)`` is False)."""
        from sympy import S
        a, b = atom.expr
        for inf, pred in ((S.Infinity, "positive_infinite"),
                          (S.NegativeInfinity, "negative_infinite")):
            if b is inf:
                e = a
            elif a is inf:
                e = b
            else:
                continue
            s = self.session
            if _is_number(e):
                v = s.engine.is_(e, pred)
                if v is not None:
                    s._emit([var] if v else [-var])
                    return
            s.ensure(e, {pred})
            p = s.var(pred, e)
            s._emit([-var, p])
            s._emit([var, -p])
            return

    def _eq_links(self, var: int, atom: P) -> None:
        """Two sufficient conditions of ``eq(a, b)`` and one of its negation, for
        a user or extension atom (not the glue's):

        * ``positive_infinite(a) & positive_infinite(b) -> eq(a, b)``, and the
          same for ``negative_infinite`` (``Eq(oo, oo)`` is True);
        * ``zero(a - b) -> eq(a, b)``: a zero difference is finite, so both
          sides are finite and equal (``oo - oo`` is nan, not zero);
        * ``nonzero(a - b) -> ~eq(a, b)``: equal finite sides have a zero
          difference and equal infinite ones a nan difference, neither
          nonzero.

        These hold in every domain (the sides may be complex).  The
        difference is taken as ``a - b``, and also as ``b - a`` when the
        session already has that term (``Q.zero(j - i)`` for ``Eq(i, j)``),
        and only for sides without a common symbol: SymPy cancels common
        terms (``x - (x + y)`` is ``-y``), which is not the difference at
        ``x = oo`` (nan).  Not for a side that is a number: an infinite one
        is :meth:`_eq_infinity`'s, and ``eq(e, 0)`` is ``zero(e)`` by the links."""
        a, b = atom.expr
        if _is_number(a) or _is_number(b):
            return
        s = self.session
        emit = s._emit
        s.ensure(a, {"positive_infinite", "negative_infinite"})
        s.ensure(b, {"positive_infinite", "negative_infinite"})
        for pred in ("positive_infinite", "negative_infinite"):
            emit([-s.var(pred, a), -s.var(pred, b), var])
        if a.free_symbols & b.free_symbols:
            return
        for d, needed in ((a - b, False), (b - a, True)):
            if _is_number(d) or needed and d not in s.base:
                continue
            s.ensure(d, {"zero", "nonzero"})
            emit([-s.var("zero", d), var])
            emit([-s.var("nonzero", d), -var])

    # -- order atoms over the extended reals (clauses 1 and 2) ----------
    def _closed_extended_real(self, e):
        """``extended_real`` of a closed side, context-free (``nan`` is
        none); None if unknown or not closed."""
        if not _is_number(e):
            return None
        from sympy import S
        if e is S.NaN:
            return False
        return self.session.engine.is_(e, "extended_real")

    def _order_sides(self, var: int, atom: P) -> bool:
        """Clause 1 for the ``lt`` atom ``var``: ``var -> extended_real``
        of each side.  True if a side is known to be no extended real
        (``var`` is then false and the atom decided)."""
        s = self.session
        need = []
        for e in atom.expr:
            v = self._closed_extended_real(e)
            if v is False:
                s._emit([-var])
                return True
            if v is None:
                need.append(e)
        for e in need:
            s.ensure(e, {"extended_real"})
            s._emit([-var, s.var("extended_real", e)])
        return False

    def _order_infinite(self, var: int, sides) -> None:
        """Clauses 2 for the ``lt`` atom ``var`` with side forms
        ``((form_a, inf_a), (form_b, inf_b))`` (``form``: term ->
        coefficient; ``inf``: +1/-1 for an ``oo``/``-oo`` summand, else 0)."""
        s = self.session
        emit = s._emit
        push = []                             # per side: (up lits, down lits, const up, const down)
        ext = []                              # -extended_real(u) for every term
        exact = True
        seen = set()
        for form, inf in sides:
            up, down = [], []
            for u, c in form.items():
                if _is_number(u):
                    continue                  # a bounded real constant: finite
                if not c:
                    exact = False             # cancels: oo - oo if infinite
                    continue
                s.ensure(u, {"extended_real", "positive_infinite", "negative_infinite"})
                p, n = s.var("positive_infinite", u), s.var("negative_infinite", u)
                (up if c > 0 else down).append(p)
                (down if c > 0 else up).append(n)
                if u not in seen:
                    seen.add(u)
                    ext.append(-s.var("extended_real", u))
            push.append((up, down, inf > 0, inf < 0))
        (up_a, down_a, cup_a, cdown_a), (up_b, down_b, cup_b, cdown_b) = push
        if cup_a or cdown_b:                  # a = +oo or b = -oo: nothing is below/above
            emit([-var])
            return
        for l in up_a:                        # a is +oo or undefined
            emit([-l, -var])
        for l in down_b:                      # b is -oo or undefined
            emit([-l, -var])
        if not exact:
            return
        # a = -oo (a push down, none up), b > -oo, everything extended real
        rest = up_a + down_b + ext + [var]
        if cdown_a:
            emit(rest)
        else:
            for l in down_a:
                emit([-l] + rest)
        # b = +oo, a < +oo
        rest = down_b + up_a + ext + [var]
        if cup_b:
            emit(rest)
        else:
            for l in up_b:
                emit([-l] + rest)

    def _bound(self, ad, c) -> None:
        """Assert the rational bounds of the constant term ``c`` (``pi``,
        ``sqrt(2)``) as root facts of the theory: true for its value, so
        unconditional (no guard)."""
        register = getattr(ad, "register_bounds", None)
        if register is None:
            return
        s = self.session

        def new_var():
            v = s.table.aux()
            s.solver.ensure_vars(v)
            return v
        for v in register(s.solver, c, new_var):
            s._emit([v])

    # -- links to the unary vocabulary ----------------------------------
    def _atom_var(self, f) -> int:
        """Variable of a normalised relation atom (allocated if new; its
        interpretation is queued by the session)."""
        return self.session.table.var(f)

    def _link(self, e) -> None:
        from sympy import S
        s = self.session
        s.ensure(e, {"extended_positive", "extended_negative", "zero"})
        pos, neg = s.var("extended_positive", e), s.var("extended_negative", e)
        zero = s.var("zero", e)
        gt = self._atom_var(relation_atom("lt", S.Zero, e))
        lt = self._atom_var(relation_atom("lt", e, S.Zero))
        eqa = relation_atom("eq", e, S.Zero)
        if eqa not in self.session.table.custom:
            self._aux_eq.add(eqa)
            self._link_eq.add(eqa)
        eq = self._atom_var(eqa)
        emit = s._emit
        emit([-pos, gt])
        emit([-gt, pos])
        emit([-neg, lt])
        emit([-lt, neg])
        emit([-zero, eq])
        emit([-eq, zero])
        if INTEGERS:
            for spec in self.specs:
                if spec.guarded:
                    ad = self._adapter(spec)
                    if hasattr(ad, "integer_form"):
                        self._link_integer(ad, e)

    # -- equality sharing -------------------------------------------------
    def _share(self) -> bool:
        if len(self.adapters) < 2:
            return False
        sets = [set(ad.shared_terms()) for ad in self.adapters.values()]
        pairs = self.sharing.update(sets)
        for a, b in pairs:
            if _is_number(a) and _is_number(b):
                continue
            if _constant_term(a) or _constant_term(b):
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
                    if _is_number(node) and isinstance(node, Rational):
                        preds = _number_basis(s.engine, node)
                        full = len(preds) == NPRED
                    else:
                        preds = range(NPRED)
                        full = True
                    for k in preds:
                        if k != polar or node not in part:
                            solver.register_atom(
                                th, b + k, (t, k) if full else (t, k, True), False)
                    continue
                if lv == 1 and node not in part:
                    part.add(node)
                    solver.register_atom(th, b + polar, (ad.node_term(node), polar, True),
                                         False)
                keep.append((node, b))
            pend[:] = keep
