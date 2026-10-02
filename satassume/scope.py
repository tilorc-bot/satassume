"""The theory scope of a query: a pure function of its syntax (#97 P3).

A query is a proposition ``p`` under an assumption formula ``a`` (either
may be None).  Which theory machinery its session has is decided here,
once, from the atoms of the two formulas, before the session is built
(``Session(engine, scope)``), instead of being switched on by the first
atom of a kind that the session meets:

* ``glue``: the relation glue (:class:`satassume.relations.Relations`:
  the theories, the links ``extended_positive(e) <-> gt(e, 0)``,
  ``extended_negative(e) <-> lt(e, 0)``, ``zero(e) <-> eq(e, 0)`` of the
  linked terms, equality sharing).  On iff ``a`` or ``p`` holds a relation
  atom, or two sign atoms of ``a`` and ``p`` together (:data:`SIGN_PREDS`;
  the pair may be one atom of each formula) are on different ``Add`` nodes
  sharing a free symbol: only the links connect a sign fact to its linear
  form, so without them LRA never compares ``x - 1`` with ``1 - x``;
* ``transfer``: predicate transfer (:mod:`satassume.transfer`: the terms
  of one EUF class share their unary facts).  On iff the relation atoms of
  ``a`` and ``p`` make an equality: an ``eq`` atom (``ne`` is its
  negation), or an order atom and its reverse (``lt(x, y)`` and
  ``lt(y, x)``: ``Q.le(x, y) & Q.ge(x, y)`` gives ``eq(x, y)`` by
  :meth:`satassume.relations.Relations._trichotomy`, so it answers as
  ``Q.eq(x, y)`` does).  ``transfer`` implies ``glue``;
* ``linked_terms``: the terms the glue links, the arguments of the
  vocabulary atoms and the sides of the relation atoms of both formulas,
  numbers excluded (their unary facts are closed already; a structural
  number argument of a vocabulary atom gets a congruence selector of its
  own instead, ``Relations._mention_number``).  Empty without ``glue``.

Why this is sound (monotonicity).  Every clause the glue adds is a valid
statement about the extended reals or about equality (the tables in the
module docstring of :mod:`satassume.relations`), and every lemma of
predicate transfer is an instance of Leibniz's law over EUF's congruence
closure; none of them is a hypothesis.  So the clause set of a session
with more theory is the clause set with less plus valid clauses: every
model of the larger set is a model of the smaller one, and the smaller
set's consequences are consequences of the larger.  An answer the
relation-free session gives (``p`` entailed, or ``~p`` entailed) is
therefore given by the session with the glue or transfer too; the extra
theory can turn None into True or False, never True into False or the
reverse.  The scope only chooses how much of this valid theory a query
pays for; the answer with the whole of it is the ceiling, and no scope
reaches a definite value the ceiling does not have.

Resolution of the three differences of the spec (``docs/spec.md``,
"Theory scope", open point 1) between this function and the code it
replaces:

1. ``Relations.wants_transfer`` counted a ``_trichotomy`` pair through the
   session's ``_tri_of`` table, which is filled when both atoms are
   allocated.  In a session built for one query both are allocated iff
   both are atoms of ``a`` or ``p``, so :func:`transfer_wanted` tests the
   pair syntactically (an atom and its reverse among the atoms) and gives
   the same value with no session state; ``wants_transfer`` delegates.
2. The discovery budget's link test (``Engine._within_budget``) counts
   sign-atom sums over disjoint symbols too, a conservative over-estimate
   of the cone's weight.  It is a budget, not a scope: it decides whether
   a query is answered at all, never what its session contains, so it is
   left as it is (``engine.py``, P2's file).
3. The sign-on-sum pair is taken across both formulas, as
   ``engine._links_wanted`` already did for the selectors (the old
   ``Session._affine_links`` kept the assumptions' sums and tested the
   query's against them, the same pairs).
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, NamedTuple, Optional

from .formula import P, atoms_of
from .rules import PRED_INDEX

#: the predicates whose atoms the relation glue links to order atoms
#: (``extended_positive``, ``extended_negative``, ``zero``) and those that
#: imply or refute them for a finite argument
SIGN_PREDS = frozenset({
    "positive", "negative", "nonnegative", "nonpositive", "nonzero", "zero",
    "extended_positive", "extended_negative", "extended_nonnegative",
    "extended_nonpositive", "extended_nonzero"})

#: the predicates of relation atoms (``satassume.relations.RELATION_ATOMS``;
#: repeated here so that this module imports nothing of the theories)
RELATION_ATOMS = frozenset({"eq", "lt"})


class Scope(NamedTuple):
    """The theory scope of a query (:func:`theory_scope`)."""
    glue: bool
    transfer: bool
    linked_terms: frozenset


#: the scope of a query without relations or sign-on-sum pairs
EMPTY = Scope(False, False, frozenset())


def _is_number(e) -> bool:
    return bool(getattr(e, "is_number", False)) and not getattr(e, "free_symbols", True)


def affine_pair(atoms: Iterable[P]) -> bool:
    """Whether two sign atoms among ``atoms`` are on different sums sharing
    a free symbol (``Q.positive(x - 1)`` and ``Q.negative(1 - x)``)."""
    sums: Dict[Any, frozenset] = {}
    for a in atoms:
        e = a.expr
        if a.pred not in SIGN_PREDS or not getattr(e, "is_Add", False) or e in sums:
            continue
        symbols = e.free_symbols
        if not symbols:
            continue
        if any(symbols & other for other in sums.values()):
            return True
        sums[e] = symbols
    return False


def transfer_wanted(atoms: Iterable[P]) -> bool:
    """Whether the relation atoms among ``atoms`` make an equality: an
    ``eq`` atom, or an order atom and its reverse (see the module
    docstring, resolution 1)."""
    atoms = tuple(atoms)
    for a in atoms:
        if a.pred == "eq":
            return True
    lts = {a.expr for a in atoms if a.pred == "lt"}
    for x, y in lts:
        if (y, x) in lts:
            return True
    return False


def linked_terms(atoms: Iterable[P]) -> frozenset:
    """The terms the glue links for ``atoms``: the arguments of the
    vocabulary atoms and the sides of the relation atoms, numbers
    excluded."""
    out = set()
    for a in atoms:
        if a.pred in PRED_INDEX:
            if not _is_number(a.expr):
                out.add(a.expr)
        elif a.pred in RELATION_ATOMS:
            out.update(e for e in a.expr if not _is_number(e))
    return frozenset(out)


def scope_of_atoms(atoms: Iterable[P]) -> Scope:
    """:func:`theory_scope` of the formulas whose atoms are ``atoms``
    (those of ``a`` and ``p`` together)."""
    atoms = tuple(atoms)
    rel = any(a.pred in RELATION_ATOMS for a in atoms)
    glue = rel or affine_pair(atoms)
    if not glue:
        return EMPTY
    return Scope(True, rel and transfer_wanted(atoms), linked_terms(atoms))


def theory_scope(assumptions, proposition) -> Scope:
    """The theory scope of ``proposition`` under ``assumptions`` (formulas
    over ``P`` atoms, or None): ``(glue, transfer, linked_terms)`` as the
    module docstring defines them.  A function of the two formulas'
    atoms."""
    atoms = []
    for f in (assumptions, proposition):
        if f is not None and f is not True:
            atoms.extend(atoms_of(f))
    return scope_of_atoms(atoms)
