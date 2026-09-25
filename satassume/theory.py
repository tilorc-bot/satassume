"""The interface between the CDCL solver and theory solvers (DPLL(T)).

A *theory solver* decides consistency of a conjunction of theory atoms
(linear constraints for LRA, equalities between terms for EUF).  The SAT
solver (:class:`satassume.solver.Solver`) owns the search; it tells each
attached theory which of the theory's atoms it has assigned, and the theory
answers with a *conflict clause* when those assignments are inconsistent.

Literals are the solver's external literals: nonzero ints, ``v`` meaning the
atom registered for variable ``v`` holds, ``-v`` meaning its negation holds.
This module imports nothing from SymPy and the solver never looks inside a
payload, so the solver stays theory- and SymPy-agnostic.

Wiring (done by an adapter, e.g. ``satassume/lra_adapter.py``)::

    theory = MyTheory()
    solver.attach_theory(theory)
    solver.register_atom(theory, v, payload)   # once per theory atom

:meth:`Solver.register_atom` records that variable ``v`` belongs to
``theory`` and calls ``theory.register_atom(v, payload)``.  Only registered
variables are ever passed to :meth:`TheorySolver.assert_lit`.

Contract (all methods)
----------------------

*Conflict clause.*  A non-empty list of solver literals whose disjunction is
valid in the theory (true in every theory model) and each of which is false
under the current assignment, i.e. the negations of literals the theory has
been told through ``assert_lit`` (or root facts it was told earlier).
Returning ``[-a, -b]`` after ``a`` and ``b`` were asserted says "``a`` and
``b`` cannot both hold".  The solver adds the clause as a learnt clause and
runs ordinary conflict analysis on it; it may later delete it (learnt-clause
reduction), so the theory must be able to find the same conflict again.
Smaller clauses prune more; any valid clause is sound.  The solver raises
``RuntimeError`` if a literal of a conflict clause is not false.

*Soundness.*  A theory must never report a conflict for a theory-consistent
set of literals.  Every definite answer of the engine rests on this.

*Completeness.*  :meth:`check` on a total assignment should report a conflict
whenever the asserted literals are inconsistent.  A theory that cannot tell
(nonlinear terms, an unsupported atom) returns None there; the solver then
reports SAT, which ``Solver.entails`` only ever turns into "not entailed"
(None), so incompleteness costs definite answers, never correctness.

*Levels.*  The theory's level count always equals the solver's decision
level: ``push_level`` is called when a decision level opens (before any
literal of that level is asserted, including empty levels opened for
assumptions that are already true), ``pop_level`` once per level undone on
backtrack, innermost first.  Level 0 (root) is never pushed or popped:
literals asserted at level 0 are permanent facts.

*Order of calls* (what :mod:`tests.test_theory_hooks` checks):

* every assignment of a registered variable is reported by exactly one
  ``assert_lit`` call per level-lifetime: once when it is made, and again
  only if it is undone by a ``pop_level`` and made again later;
* after ``assert_lit`` returns a conflict the solver makes no further
  ``assert_lit`` or ``check`` call on any theory until it has backtracked
  (``pop_level``) or declared the problem unsatisfiable at root;
* ``check`` is called only when every solver variable is assigned and every
  assignment has been reported, just before the solver would answer SAT;
  a satisfiable answer may also reuse a model that passed ``check``
  earlier under the same theories and registered atoms (the solver's
  witness reuse), with no theory call at all;
* ``propagate`` (optional) is called after the theory has been told all
  current assignments without conflict.

A theory is informed consistently on every solver path: ``solve``,
``entails``, ``implied``, ``propagate`` and root-level unit clauses.
``implied`` and the unit-propagation stage of ``entails`` see ``assert_lit``
conflicts and ``propagate`` implications but never call ``check``.
"""
from __future__ import annotations

from typing import Any, Iterable, Protocol, runtime_checkable

#: ``(False, conflict_clause)``
Conflict = tuple  # tuple[bool, list[int]]


@runtime_checkable
class TheorySolver(Protocol):
    """The required surface of a theory solver: four methods plus atom
    registration.  See the module docstring for the full contract."""

    def register_atom(self, literal: int, payload: Any) -> None:
        """Declare that positive solver literal ``literal`` stands for the
        theory atom ``payload``.

        ``payload`` is an opaque object built by the adapter (for LRA a
        linear-constraint record, for EUF an equation between terms); the
        solver never inspects it.  Called at root level, possibly after
        other atoms were asserted (the solver immediately asserts the new
        atom too if its variable is already fixed at root).  A literal is
        registered at most once per theory.
        """
        ...

    def assert_lit(self, literal: int) -> Conflict | None:
        """The solver has made ``literal`` true (``-v``: the atom of ``v``
        is false).

        Returns None if the assertion is consistent as far as the theory
        checks eagerly, or ``(False, conflict_clause)``.  Cheap incomplete
        checks are fine here; :meth:`check` is where completeness is due.
        A theory handed a literal it does not interpret returns None.
        """
        ...

    def check(self) -> tuple[bool, Any] | None:
        """Full consistency check of everything asserted so far.

        Called only on a total assignment (of every variable except the
        rule-block variables nothing outside their block mentions, which
        the solver leaves to the block's closure; never a theory atom).
        Returns ``(True, model)`` when
        consistent (``model`` is theory-specific, e.g. values for the
        variables; it is kept by :meth:`Solver.theory_models`),
        ``(False, conflict_clause)`` when not, or None when the theory has
        nothing to say (treated as consistent).  Must not change what
        ``pop_level`` restores.
        """
        ...

    def push_level(self) -> None:
        """A new decision level opens; remember enough to undo it."""
        ...

    def pop_level(self) -> None:
        """Undo every ``assert_lit`` made since the matching ``push_level``
        (and anything derived from them), restoring the state exactly as it
        was when that ``push_level`` was called."""
        ...


class PropagatingTheory(TheorySolver, Protocol):
    """Optional extension: theory propagation.

    A theory that defines ``propagate`` is called after it has been told
    all current assignments without conflict.  It returns an iterable of
    ``(literal, reason)`` pairs, ``reason`` being a theory-valid clause that
    contains ``literal`` and otherwise only literals false under the current
    assignment (so the clause implies ``literal``).  The solver assigns the
    literal with that clause as its reason (or treats the clause as a
    conflict if ``literal`` is already false) and then tells every theory
    about it through ``assert_lit`` as usual, including the propagating
    theory itself.  Returning an empty iterable is always allowed;
    implementers may skip this method entirely.  Reasons are eager (no
    ``provide_reason`` callback as in SymPy PR 30098): a theory that only
    propagates cheap implications (bound refinement in LRA, congruence in
    EUF) has the explanation at hand when it propagates.
    """

    def propagate(self) -> Iterable[tuple[int, list[int]]]:
        ...


class EqualitySharing:
    """Bookkeeping for delayed theory combination.

    Theories are kept apart by atom kind; they meet on *shared terms*,
    terms known to at least two theories.  For each pair of shared terms
    the engine creates one interface atom ``a == b`` and registers it with
    every theory that interprets it, so the SAT solver decides the
    arrangement of the shared terms and each theory checks it.  For
    stably infinite theories with disjoint signatures (LRA over the
    rationals/reals and EUF are) this is complete; without the interface
    atoms, combined reasoning such as ``x <= y, y <= x |- f(x) = f(y)`` is
    lost (but nothing unsound is derived).

    :meth:`update` takes the current term sets of the theories and returns
    the pairs not returned before, in a deterministic order.
    """

    def __init__(self):
        self.shared: list = []
        self._seen: set = set()

    def update(self, term_sets) -> list:
        count: dict = {}
        order: list = []
        for ts in term_sets:
            for t in ts:
                if t not in count:
                    count[t] = 0
                    order.append(t)
                count[t] += 1
        new = [t for t in order if count[t] >= 2 and t not in self._seen]
        pairs = []
        for t in new:
            for u in self.shared:
                pairs.append((u, t))
            self.shared.append(t)
            self._seen.add(t)
        return pairs


__all__ = ["TheorySolver", "PropagatingTheory", "EqualitySharing"]
