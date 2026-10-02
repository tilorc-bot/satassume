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

Zero is an equality (#107).  A ``zero(t)`` atom (``t`` no number; or a
split zero, ``nonnegative(t) & nonpositive(t)`` and the other sign pairs
of :func:`satassume.relations.zero_args`) whose
``t`` occurs as an argument, at any depth, of an application of an
undefined function in either formula is read by the glue as its twin
``eq(t, 0)`` (:func:`satassume.relations.glue_atoms`; "Zero is an
equality" in that module's docstring): the session allocates the twin
with the formula (``Session._ensure_twins``) and the glue treats it as a
user equality.  The scope counts the twins of ``a`` and ``p`` together
(:func:`scope_of_atoms` folds ``glue_atoms`` over the atoms of both
before the tests above), so such a query has ``glue`` and ``transfer``
and ``t`` is in ``linked_terms``.  Without that the session built for
the query would create the glue at the twin (``Session._custom``) and
engage transfer at it (``Relations.process``): the counted fallback,
taken by every family-A shape at the rebase onto #107 (two misses per
query) and by none since (``tests/test_scope.py``).  A ``zero(t)`` with
no application over ``t`` is a sign atom and starts nothing: #107's
condition, chosen for its cost (the unconditional twin cost +56% on the
refine stream), and the same answers outside it.

Why this is sound (monotonicity).  Every clause the glue adds is a valid
statement about the extended reals or about equality (the tables in the
module docstring of :mod:`satassume.relations`), and every lemma of
predicate transfer is an instance of Leibniz's law over EUF's congruence
closure; none of them is a hypothesis.  So the clause set of a session
with more theory is the clause set with less plus valid clauses: every
model of the larger set is a model of the smaller one, and the smaller
set's consequences are consequences of the larger.  An answer the
relation-free session gives (``p`` entailed, or ``~p`` entailed) is
therefore given by the session with the glue or transfer too.  Under the
hypothesis that the set with the smaller theory, ``A`` with the clauses
``C(S)``, has a model in the intended structure (the extended reals with
equality: the set is consistent), the valid clauses keep that model for
``C(S')``, so ``S'`` cannot entail both ``p`` and ``~p``: the extra
theory can turn None into True or False, never True into False or the
reverse.  Without the hypothesis (an inconsistent set whose budgeted
check did not establish it) both answers are vacuous, and in practice
the query with the glue raises ``InconsistentAssumptions`` where the
smaller scope answers (#97 P3 review 2).  The scope only chooses how
much of this valid theory a query pays for; the answer with the whole of
it is the ceiling, and no scope reaches a definite value the ceiling
does not have.

That is an argument about entailment, not about the engine, which is
budgeted (``Engine._exhausted``, ``_gave_up``, the discovery budget): more
valid clauses can exhaust a branch budget the smaller clause set did not,
and turn a definite answer into None (the set's check showed the mechanism
when the query's glue linked the set's terms before it, #97 P3 review
finding 1; hence ``Session.link_set``).  What the validity of the clause
families gives is "never the other definite value"; "same or more
definite" is an empirical property, checked by ``tools/relevance_fuzz.py``
and the harness profiles of gate G5, not a corollary of clause validity.

Resolution of the three differences of the spec (``docs/spec.md``,
"Theory scope", open point 1) between this function and the code it
replaces:

1. ``Relations.wants_transfer`` counted a ``_trichotomy`` pair through the
   session's ``_tri_of`` table, which is filled when both atoms are
   allocated.  In a session built for one query both are allocated iff
   both are atoms of ``a`` or ``p``, so :func:`transfer_wanted` tests the
   pair syntactically (an atom and its reverse among the atoms) and gives
   the same value with no session state; ``wants_transfer`` delegates.
   It over-approximates: the pair is counted even when
   ``uninterpreted="free"`` leaves the atoms opaque and ``_trichotomy``
   never relates them (harmless: every transfer lemma is guarded).
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

from typing import Any, Dict, Iterable, NamedTuple

from .formula import P, atoms_of
from .relations import RELATION_ATOMS, _is_number, glue_atoms
from .rules import PRED_INDEX

#: the predicates whose atoms the relation glue links to order atoms
#: (``extended_positive``, ``extended_negative``, ``zero``) and those that
#: imply or refute them for a finite argument
SIGN_PREDS = frozenset({
    "positive", "negative", "nonnegative", "nonpositive", "nonzero", "zero",
    "extended_positive", "extended_negative", "extended_nonnegative",
    "extended_nonpositive", "extended_nonzero"})


class Scope(NamedTuple):
    """The theory scope of a query (:func:`theory_scope`)."""
    glue: bool
    transfer: bool
    linked_terms: frozenset


#: the scope of a query without relations or sign-on-sum pairs
EMPTY = Scope(False, False, frozenset())


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
    (those of ``a`` and ``p`` together).  The twins ``eq(t, 0)`` of the
    ``zero(t)`` atoms with ``t`` under an application of either formula
    count as relation atoms (``relations.glue_atoms``, #107)."""
    atoms = glue_atoms(tuple(atoms))
    rel = any(a.pred in RELATION_ATOMS for a in atoms)
    glue = rel or affine_pair(atoms)
    if not glue:
        return EMPTY
    return Scope(True, rel and transfer_wanted(atoms), linked_terms(atoms))


def theory_scope(assumptions, proposition, extensions=None) -> Scope:
    """The theory scope of ``proposition`` under ``assumptions`` (formulas
    over ``P`` atoms, or None): ``(glue, transfer, linked_terms)`` as the
    module docstring defines them.  A function of the two formulas' atoms
    and, with ``extensions`` (the engine's :class:`Extensions`), of the
    facts it generates for their custom atoms (:func:`extension_atoms`)."""
    atoms = []
    for f in (assumptions, proposition):
        if f is not None and f is not True:
            atoms.extend(atoms_of(f))
    if extensions is not None:
        atoms.extend(extension_atoms(atoms, extensions))
    return scope_of_atoms(atoms)


def _custom_pred(a: P) -> bool:
    return a.pred not in PRED_INDEX and a.pred not in RELATION_ATOMS


def extension_atoms(atoms: Iterable[P], extensions) -> list:
    """The atoms of the facts ``extensions`` generates for the custom
    atoms among ``atoms``, transitively (a fact may hold custom atoms of
    its own): what ``Session._custom`` compiles for them, so a relation
    atom among them is in the scope (spec open point 2).  Not foreseen:
    the facts of a vocabulary predicate registered for a class
    (``Extensions.node_facts``), which fire over the cone as the session
    visits its nodes; a relation atom among those creates the glue outside
    the scope (``Session._custom``, counted in ``stats["scope_misses"]``)."""
    out: list = []
    seen: set = set()
    stack = [a for a in atoms if _custom_pred(a)]
    while stack:
        a = stack.pop()
        if a in seen:
            continue
        seen.add(a)
        for f in extensions.facts_for(a):
            for b in atoms_of(f):
                out.append(b)
                if _custom_pred(b):
                    stack.append(b)
    return out
