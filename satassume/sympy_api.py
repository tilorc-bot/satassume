"""SymPy-facing API: ``ask(proposition, assumptions)``.

Scope
-----
The engine answers ``ask`` for **unary scalar predicates on scalar
expressions**: propositions and assumptions that are Boolean combinations
(``And``, ``Or``, ``Not``, ``Implies``, ``Equivalent``) of applied
predicates ``Q.<name>(expr)`` where ``name`` is in the vocabulary of
:mod:`satassume.rules` (``PREDICATES``) and ``expr`` is a scalar
:class:`~sympy.core.expr.Expr`.  Everything is answered by the SAT engine
alone: the rule base, the structural templates and search.  The engine
never consults SymPy's ``_eval_is_*`` handlers or SymPy's own
``ask``/``satask``.

Routing rule
------------
Any query outside that scope makes :func:`ask` return ``None``.  This is
scoping, not a fallback: the caller (SymPy's ``ask``) is expected to route
such inputs to its existing path (``satask``, the LRA theory, the matrix
handlers).  :func:`out_of_scope` says whether, and why, a query is out of
scope so the caller can decide before asking.  The categories are

* ``"relation"``: a relational (``x < 0``, ``Eq(x, y)``), one of the binary
  predicates ``Q.eq``, ``Q.ne``, ``Q.lt``, ``Q.le``, ``Q.gt``, ``Q.ge``, or
  ``Q.is_true`` over a relational, anywhere in the proposition or the
  assumptions.  :func:`out_of_scope` always reports this category, but
  :func:`ask` answers relations when the engine has theory adapters
  (``Engine.relation_specs``, by default LRA and EUF when present; see
  :mod:`satassume.relations`) and returns None only when no theory
  interprets one of the relations;
* ``"matrix"``: a matrix predicate (``Q.invertible`` and friends from
  ``sympy.assumptions.predicates.matrices``) or a vocabulary predicate
  applied to a non-scalar argument (a ``MatrixSymbol``, ...);
* ``"custom"``: any other predicate outside the vocabulary (user-defined
  predicates, ``Q.is_true`` over a non-relational) for which no
  clause-generating function is registered (see :func:`register` and
  :mod:`satassume.extensions`); a registered predicate is in scope, with
  the arity it was registered for;
* ``"other"``: the proposition or the assumptions are not a Boolean
  combination of applied predicates at all (a bare ``Q.positive``, an
  ``Expr``, an ``ITE``, ...).

If several apply the first in this list is reported.

``to_formula`` translates a SymPy Boolean into a :mod:`satassume.formula`
formula and raises :class:`Unsupported` (carrying the category) for
out-of-scope input.

Not offered here
----------------
Replacing the old ``expr.is_*`` system is the long-term goal, not this
slice.  ``Engine.is_`` exists because the engine uses it internally for
context-free queries, and the corpus tools replay old-system records
through it for information, but nothing here hooks it into SymPy.
"""
from __future__ import annotations

from typing import Optional

from .engine import Engine, InconsistentAssumptions, DictCache  # noqa: F401
from .extensions import Args, extensions, register, unregister  # noqa: F401
from .formula import And, Equivalent, Formula, Implies, Not, Or, P, TRUE, FALSE  # noqa: F401
from .relations import Uninterpreted, relation_atom, relational_name

from sympy.assumptions.assume import AppliedPredicate as _Applied
from sympy.core.basic import Basic as _Basic
from sympy.core.expr import Expr as _Expr
from sympy.core.relational import Relational as _Relational
from sympy.core.numbers import Rational as _Rational
from sympy.core.singleton import S as _S
from sympy.logic.boolalg import (And as _SAnd, Or as _SOr, Not as _SNot,
                                 Implies as _SImplies, Equivalent as _SEquivalent,
                                 BooleanTrue as _BTrue, BooleanFalse as _BFalse)
from .rules import PRED_INDEX


CATEGORIES = ("relation", "matrix", "custom", "other")

RELATION_PREDICATES = frozenset({"eq", "ne", "lt", "le", "gt", "ge"})


class Unsupported(Exception):
    """The query is outside the engine's scope.  ``category`` is one of
    :data:`CATEGORIES`; see the module docstring."""

    def __init__(self, message: str, category: str = "other"):
        super().__init__(message)
        assert category in CATEGORIES
        self.category = category


_engine: Optional[Engine] = None


def default_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine


def set_default_engine(engine: Engine) -> None:
    global _engine
    _engine = engine


# --------------------------------------------------------------------------
# scope
# --------------------------------------------------------------------------

_MATRIX_PREDICATES: Optional[frozenset] = None


def matrix_predicates() -> frozenset:
    """Names of the predicates defined in ``sympy.assumptions.predicates.matrices``."""
    global _MATRIX_PREDICATES
    if _MATRIX_PREDICATES is None:
        from sympy.assumptions.assume import Predicate
        from sympy.assumptions.predicates import matrices
        _MATRIX_PREDICATES = frozenset(
            cls.name for cls in vars(matrices).values()
            if isinstance(cls, type) and issubclass(cls, Predicate) and cls is not Predicate
            and isinstance(getattr(cls, "name", None), str))
    return _MATRIX_PREDICATES


def _is_scalar(arg) -> bool:
    return isinstance(arg, _Expr) and bool(arg.is_scalar)


def _applied_category(expr) -> Optional[str]:
    """Category of one ``AppliedPredicate``, or None if it is in scope."""
    Relational = _Relational
    name = str(expr.function.name)
    args = expr.arguments
    if name in RELATION_PREDICATES:
        return "relation"
    if name == "is_true":
        return "relation" if any(isinstance(a, Relational) for a in args) else "custom"
    if name in matrix_predicates():
        return "matrix"
    if name not in PRED_INDEX:
        return None if extensions.is_registered(name, len(args)) else "custom"
    if len(args) != 1:
        return "other"
    if _is_scalar(args[0]) or extensions.is_scalar_like(args[0]):
        return None
    return "matrix"


def _categories(expr, acc: set) -> None:
    from sympy.assumptions.assume import AppliedPredicate
    from sympy.core.relational import Relational
    from sympy.logic.boolalg import (And as SAnd, Or as SOr, Not as SNot,
                                     Implies as SImplies, Equivalent as SEquivalent,
                                     BooleanTrue, BooleanFalse)
    if expr is True or expr is False or isinstance(expr, (BooleanTrue, BooleanFalse)):
        return
    if isinstance(expr, AppliedPredicate):
        c = _applied_category(expr)
        if c is not None:
            acc.add(c)
        return
    if isinstance(expr, Relational):
        acc.add("relation")
        return
    if isinstance(expr, (SAnd, SOr, SNot, SImplies, SEquivalent)):
        for a in expr.args:
            _categories(a, acc)
        return
    acc.add("other")


def out_of_scope(proposition, assumptions=True) -> Optional[str]:
    """``None`` if the query is in scope, else the category (first of
    :data:`CATEGORIES` that applies) explaining why :func:`ask` returns None."""
    acc: set = set()
    _categories(proposition, acc)
    _categories(assumptions, acc)
    for c in CATEGORIES:
        if c in acc:
            return c
    return None


# --------------------------------------------------------------------------
# SymPy Boolean -> satassume formula
# --------------------------------------------------------------------------

def relation_parts(expr):
    """``(name, lhs, rhs)`` for a relation (``Relational``, ``Q.eq/ne/lt/
    le/gt/ge(a, b)``, ``Q.is_true(a < b)``) with ``name`` in ``eq ne lt le
    gt ge``; None if ``expr`` is not a relation.  The one place where the
    engine side parses relations (``satassume.relations.relation_atom``
    normalises the result).  Raises :class:`Unsupported` for a relation
    predicate of the wrong arity."""
    if isinstance(expr, _Relational):
        return relational_name(expr), expr.lhs, expr.rhs
    if isinstance(expr, _Applied):
        name = str(expr.function.name)
        args = expr.arguments
        if name == "is_true":
            if len(args) == 1 and isinstance(args[0], _Relational):
                return relation_parts(args[0])
            return None
        if name in RELATION_PREDICATES:
            if len(args) != 2:
                raise Unsupported(f"{expr} is out of scope (relation)", "relation")
            return name, args[0], args[1]
    return None


def _relation_formula(expr, parts, relations: bool):
    name, lhs, rhs = parts
    if not relations or not (_is_scalar(lhs) and _is_scalar(rhs)):
        raise Unsupported(f"{expr} is out of scope (relation)", "relation")
    return relation_atom(name, lhs, rhs)


def to_formula(expr, relations: bool = False):
    """Translate a SymPy Boolean over applied predicates into a formula.
    Raises :class:`Unsupported` for anything out of scope.  With
    ``relations`` (the engine has theory adapters, see
    :mod:`satassume.relations`) relations become relation atoms."""
    if expr is True or isinstance(expr, _BTrue):
        return TRUE
    if expr is False or isinstance(expr, _BFalse):
        return FALSE
    if isinstance(expr, _Applied):
        name = str(expr.function.name)
        if name in RELATION_PREDICATES or name == "is_true":
            parts = relation_parts(expr)
            if parts is not None:
                return _relation_formula(expr, parts, relations)
        c = _applied_category(expr)
        if c is not None:
            raise Unsupported(f"{expr} is out of scope ({c})", c)
        args = expr.arguments
        return P(name, args[0] if len(args) == 1 else Args(args))
    if isinstance(expr, _SAnd):
        return And(*[to_formula(a, relations) for a in expr.args])
    if isinstance(expr, _SOr):
        return Or(*[to_formula(a, relations) for a in expr.args])
    if isinstance(expr, _SNot):
        return Not(to_formula(expr.args[0], relations))
    if isinstance(expr, _SImplies):
        return Implies(to_formula(expr.args[0], relations), to_formula(expr.args[1], relations))
    if isinstance(expr, _SEquivalent):
        return Equivalent(*[to_formula(a, relations) for a in expr.args])
    if isinstance(expr, _Relational):
        return _relation_formula(expr, relation_parts(expr), relations)
    raise Unsupported(f"cannot translate {type(expr).__name__} (other)", "other")


# --------------------------------------------------------------------------
# the public query
# --------------------------------------------------------------------------

def ask(proposition, assumptions=True, engine: Optional[Engine] = None) -> Optional[bool]:
    """Truth value of ``proposition`` under ``assumptions``: True, False or
    None, computed by the SAT engine alone.

    * In-scope input (see the module docstring) is answered from the rule
      base, the templates and search; None means the engine cannot decide.
    * Out-of-scope input (relations, matrix predicates, unregistered custom
      predicates, non-scalar arguments, non-Boolean propositions) returns
      None without touching the engine.  The caller is expected to route it
      to SymPy's existing path; :func:`out_of_scope` tells which category
      applies.
    * Custom predicates with a registered clause-generating function
      (:func:`register`, the counterpart of ``Predicate.register``) are in
      scope: their atoms take part in propagation and search.
    * Inconsistent assumptions raise ``ValueError`` like ``sympy.ask``,
      except for a proposition about constants only (every argument a
      number without free symbols), which is answered without the
      assumptions and so never raises.
      A query is answered under the conjuncts of the assumptions connected
      to it (by shared symbols, undefined functions and irrational
      constants, transitively), once the whole set is known consistent,
      if neither holds a relation; see ``_relevant``.
      Assumptions contradicting a fact declared on a symbol
      (``ask(Q.commutative(x), ~Q.commutative(x))``) count as inconsistent
      here, where SymPy trusts the assumption.
    """
    eng = engine or default_engine()
    # answer memo (see Engine.answers): keyed by the SymPy objects
    # themselves, valid while the registrations that decide scope and add
    # facts are unchanged
    key = None
    if isinstance(proposition, _Basic) and (assumptions is True or isinstance(assumptions, _Basic)):
        key = (proposition, assumptions)
        memo = eng.answers
        state = _registry_state(eng)
        if memo.state != state:
            memo.clear()
            memo.state = state
            eng.splits.clear()
        r = memo.get(key, _MISS)
        if r is not _MISS:
            eng.stats["cache_hits"] += 1
            return r
    r = _ask(proposition, assumptions, eng)
    if key is not None:
        memo.put(key, r)
    return r


_MISS = object()


def _registry_state(eng: Engine):
    """What an answer depends on besides the query and the engine's
    history: the registered clause-generating functions (they decide the
    scope of custom predicates and add facts), identified by the registry
    and its version counter (bumped by every (un)registration), and the
    theory adapters."""
    ext = eng.extensions
    return (ext, ext.version if ext is not None else 0, tuple(eng.relation_specs))


#: ``(expr, relations) -> formula``, or the ``Unsupported`` category, of
#: :func:`to_formula` on SymPy Booleans; valid while the default registry's
#: version (which decides the scope of custom predicates) is ``_FORMULAS_STATE``
_FORMULAS: dict = {}
_FORMULAS_STATE = [None]
FORMULAS_SIZE = 100_000


def _formula(expr, relations: bool):
    """Memoized :func:`to_formula` (raises :class:`Unsupported` like it)."""
    if not isinstance(expr, _Basic):
        return to_formula(expr, relations)
    state = extensions.version
    if _FORMULAS_STATE[0] != state:
        _FORMULAS.clear()
        _FORMULAS_STATE[0] = state
    key = (expr, relations)
    f = _FORMULAS.get(key)
    if f is None:
        try:
            f = to_formula(expr, relations)
        except Unsupported as e:
            f = _Failed(str(e), e.category)
        if len(_FORMULAS) >= FORMULAS_SIZE:
            _FORMULAS.clear()
        _FORMULAS[key] = f
    if type(f) is _Failed:
        raise Unsupported(f.message, f.category)
    return f


class _Failed:
    __slots__ = ("message", "category")

    def __init__(self, message, category):
        self.message, self.category = message, category


# --------------------------------------------------------------------------
# constants: answered without the assumptions
# --------------------------------------------------------------------------

def _is_constant_proposition(prop) -> bool:
    """Every predicate in the proposition is built in, and every expression
    it is applied to has no free symbols, is a number and holds no undefined
    function (so not ``f(1)`` or ``Integral(f(x), (x, 0, 1))``, about which
    the assumptions may say something).  A custom predicate is excluded
    because the assumptions may be all that is known about it.

    Such a proposition (``Q.negative(-1)``, ``~Q.zero(pi)``,
    ``Q.eq(zoo, 1)``) is answered by the engine without the assumptions
    (its context-free path): the facts of a constant do not depend on them.
    So it never raises for inconsistent assumptions, and a relation no
    theory interprets in the assumptions no longer sinks it."""
    from sympy.logic.boolalg import BooleanFunction
    from sympy.assumptions.relation.binrel import AppliedBinaryRelation
    from sympy.core.function import AppliedUndef
    if isinstance(prop, (_Applied, AppliedBinaryRelation)):
        name = str(prop.function.name)
        if name not in PRED_INDEX and name not in RELATION_PREDICATES:
            return False
        args = prop.arguments
        return bool(args) and all(isinstance(a, _Expr) and not a.free_symbols and a.is_number
                                  and not a.has(AppliedUndef) for a in args)
    if isinstance(prop, BooleanFunction):
        return bool(prop.args) and all(_is_constant_proposition(a) for a in prop.args)
    return False


def _ask(proposition, assumptions, eng: Engine) -> Optional[bool]:
    if isinstance(proposition, _Basic):
        if _is_constant_proposition(proposition):
            return _engine_ask(proposition, True, eng)
        if eng.relevance and isinstance(assumptions, (_SAnd, _Applied, _Relational, _SOr,
                                                      _SNot, _SImplies, _SEquivalent)):
            f = _relevant(proposition, assumptions, eng)
            if f is not assumptions:
                # answered under the conjuncts connected to the query; the
                # answer memo is shared by every set with the same part
                eng.stats["relevant"] += 1
                key = (proposition, f)
                memo = eng.answers
                r = memo.get(key, _MISS)
                if r is not _MISS:
                    eng.stats["cache_hits"] += 1
                    return r
                r = _engine_ask(proposition, f, eng)
                memo.put(key, r)
                return r
    return _engine_ask(proposition, assumptions, eng)


# --------------------------------------------------------------------------
# relevance: only the assumptions connected to the query
# --------------------------------------------------------------------------
#
# The conjuncts of the assumptions split into components by shared *keys*
# (transitively).  A query is answered under the components whose keys meet
# its own, once the whole set is known to be consistent (checked once per
# set); see agent-reports/2026-09-25-relevance-1-build.md for the argument.
#
# Keys of an expression: its free symbols, the classes of its undefined
# function applications (EUF congruence connects f(x) and f(y)), and every
# closed subterm that is not a Rational (pi, sqrt(2), 2*pi, a Float, oo,
# f(1)): such a term may carry facts the assumptions decide (pi is a bounded
# LRA variable, a Float's rationality is open, f(1) is a free EUF term).
# Rationals have all their facts decided context-free (except ``polar``),
# so without relations a Rational inside a term connects nothing; a Rational
# that is itself the argument of a predicate (``Q.polar(2)``) is a key.  A
# relation's keys are those of both sides, so ``Q.eq(x, y)`` and ``x < y``
# connect x and y.  With a relation in the set or the query, terms pinned
# to a common value connect as well; by default (``RELATIONAL``) such a set
# is not split at all.
#
# Opaque (never split): a predicate outside the vocabulary (a custom
# predicate: its registered function may mention any term), ``Q.is_true``
# of a non-relational, anything that is not a Boolean over applied
# predicates and relations; also any set when a vocabulary predicate is
# registered for a class (its function may mention any term).

_OPAQUE = None  # keys of an opaque expression
_KEYS: dict = {}
KEYS_SIZE = 100_000


def _expr_keys(e, acc: set) -> bool:
    """Add the keys of the expression ``e`` to ``acc``; True if ``e`` is
    closed (no symbol inside)."""
    from sympy.core.function import AppliedUndef
    if e.is_Symbol:
        acc.add(e)
        return False
    if e.is_Rational:
        return True
    closed = True
    for a in e.args:
        if not _expr_keys(a, acc):
            closed = False
    if isinstance(e, AppliedUndef):
        acc.add(type(e))
    if closed:
        acc.add(e)
        if RELATIONAL == "rationals":
            # sin(2) is congruent to sin(x) once x = 2
            acc.update(a for a in e.atoms(_Rational))
    return closed


#: marker added by a relation while collecting keys (removed again)
_RELATION = object()


def _keys(e):
    """Frozenset of the keys of the Boolean ``e``, or ``_OPAQUE``."""
    return _keys_rel(e)[0]


def _keys_rel(e):
    """``(keys, has a relation)`` of the Boolean ``e`` (keys as :func:`_keys`)."""
    k = _KEYS.get(e)
    if k is not None:
        return k
    acc: set = set()
    try:
        ok = _bool_keys(e, acc)
    except RecursionError:
        ok = False
    rel = _RELATION in acc
    acc.discard(_RELATION)
    k = (frozenset(acc) if ok else _OPAQUE, rel)
    if len(_KEYS) >= KEYS_SIZE:
        _KEYS.clear()
    _KEYS[e] = k
    return k


def _bool_keys(e, acc: set) -> bool:
    if e is True or e is False or isinstance(e, (_BTrue, _BFalse)):
        return True
    if isinstance(e, (_SAnd, _SOr, _SNot, _SImplies, _SEquivalent)):
        return all(_bool_keys(a, acc) for a in e.args)
    if isinstance(e, _Relational):
        return _sides_keys((e.lhs, e.rhs), acc, e.rel_op in ("==", "!="))
    if isinstance(e, _Applied):
        name = str(e.function.name)
        args = e.arguments
        if name in RELATION_PREDICATES:
            return _sides_keys(args, acc, name in ("eq", "ne"))
        if name == "is_true":
            return (len(args) == 1 and isinstance(args[0], _Relational)
                    and _bool_keys(args[0], acc))
        if name not in PRED_INDEX:
            return False
        if name == "zero" and RELATIONAL == "rationals":
            acc.add(_S.Zero)            # zero(e) <-> eq(e, 0)
        for a in args:
            if not isinstance(a, _Basic):
                return False
            if a.is_Rational:
                acc.add(a)
            else:
                _expr_keys(a, acc)
        return True
    return False


def _sides_keys(args, acc: set, eq: bool = False) -> bool:
    acc.add(_RELATION)
    for a in args:
        if not isinstance(a, _Basic):
            return False
        if eq and a.is_Rational and RELATIONAL == "rationals":
            acc.add(a)                  # x = 2, y = 2: x ~ y in EUF
        else:
            _expr_keys(a, acc)
    return True


class _Split:
    """The components of one set of assumptions."""
    __slots__ = ("whole", "conjuncts", "comps", "opaque", "relational", "keyless",
                 "parts", "consistent")

    def __init__(self, a):
        self.whole = a
        cs = a.args if isinstance(a, _SAnd) else (a,)
        self.conjuncts = cs
        self.opaque = False
        #: some conjunct holds a relation / has no key
        self.relational = self.keyless = False
        #: [(keys, conjunct indices)], disjoint keys
        comps: list = []
        for i, c in enumerate(cs):
            k, rel = _keys_rel(c)
            if k is _OPAQUE:
                self.opaque = True
                return
            if rel:
                self.relational = True
            if not k:
                # only Rationals inside relations (``Q.lt(1, 2)``): decided,
                # connected to nothing; the consistency check covers it
                self.keyless = True
                continue
            ks, idx = set(k), [i]
            rest = []
            for comp in comps:
                if comp[0].isdisjoint(ks):
                    rest.append(comp)
                else:
                    ks |= comp[0]
                    idx += comp[1]
            rest.append((ks, idx))
            comps = rest
        self.comps = comps
        #: (indices of components) -> their conjunction (a SymPy Boolean,
        #: True if empty, the whole set itself if all)
        self.parts: dict = {}
        #: whether the whole set is known consistent (None: not checked)
        self.consistent = None

    def part(self, mine: tuple):
        f = self.parts.get(mine)
        if f is None:
            idx = sorted(i for j in mine for i in self.comps[j][1])
            cs = self.conjuncts
            if len(idx) == len(cs):
                f = self.whole
            elif not idx:
                f = True
            elif len(idx) == 1:
                f = cs[idx[0]]
            else:
                f = _SAnd(*[cs[i] for i in idx])
            self.parts[mine] = f
        return f


def _relevant(p, a, eng: Engine):
    """The assumptions ``p`` is asked under: ``a`` itself, or the part of
    ``a`` (a SymPy Boolean, or True) connected to ``p`` if that is smaller
    and ``a`` is consistent as a whole."""
    splits = eng.splits
    sp = splits.get(a)
    if sp is None:
        sp = _Split(a)
        splits.put(a, sp)
    if sp.opaque:
        return a
    ext = eng.extensions
    if ext is not None and ext._vocab:
        return a
    pk, prel = _keys_rel(p)
    if not pk:
        # opaque, or no key at all: nothing to split by
        return a
    if RELATIONAL == "whole" and (prel or sp.relational or sp.keyless):
        # a relation brings in the theories, which connect terms of
        # different components (see RELATIONAL)
        return a
    mine = tuple(j for j, (k, _) in enumerate(sp.comps) if not k.isdisjoint(pk))
    f = sp.part(mine)
    if f is a:
        return a
    ok = sp.consistent
    if ok is None:
        if sp.relational or sp.keyless:
            ok = _consistent(a, eng, search=CHECK_SEARCH or CHECK_SEARCH_RELATIONS)
        else:
            # no relation: the components share no solver variable, so the
            # set is consistent iff each component is.  Out of scope as a
            # whole (a matrix predicate in another component): as before,
            # the whole set answers (None)
            try:
                _formula(a, bool(eng.relation_specs))
            except Unsupported:
                ok = False
            else:
                ok = all(_part_consistent(sp.part((j,)), eng) for j in range(len(sp.comps)))
        sp.consistent = ok
    return f if ok else a


#: how a set or query with a relation splits.  With a relation, the session
#: has the theories and links every vocabulary argument ``e`` by
#: ``zero(e) <-> eq(e, 0)``; terms of different components can then be
#: merged in EUF through a common value (``x = 2`` and ``y = 2``, ``zero(x)``
#: and ``y = 0``, but also values LRA derives, ``x + 1 = 3`` or ``2 <= x <= 2``,
#: meeting through interface equalities, and a zero the rule base derives
#: from ``nonnegative & nonpositive``), and congruence merges ``sin(x)`` with
#: ``sin(y)`` or ``sin(2)``, which carries facts across.
#: ``"whole"``: a set or query with a relation is not split (the answers
#: are those of the whole set); ``"rationals"``: it splits, with a Rational
#: that is a side of an equality, the 0 of ``zero``, and the Rationals of
#: a closed term as keys (connects ``x = 2`` with ``y = 2``, ``sin(2)``,
#: ``polar(2)``, but not the values LRA or the rule base derive).
#: The key memo ``_KEYS`` depends on it: clear it when changing it.
#: See agent-reports/2026-09-26-relevance-2-connect.md.
RELATIONAL = "whole"

#: every consistency check also searches (``Solver.solve``, in a session of
#: its own), not only propagates.  On: a Boolean conflict that propagation
#: does not see (``(p | i) & (p | ~i) & (~p | i) & (~p | ~i)`` over the
#: atoms of one symbol) makes the old path raise for every query that goes
#: to search, including queries about other components
CHECK_SEARCH = True

#: the whole-set check of a set with relations searches: theory conflicts
#: (``Q.eq(y, u) & Q.negative(u*y)``) often surface only in search, and the
#: old path raises for any query that goes to search
CHECK_SEARCH_RELATIONS = True

#: a check whose session is incomplete (discovery left nodes or formulas
#: parked) escalates once, as a query undecided by propagation does, before
#: it certifies the set: the old path raises for such a query
CHECK_ESCALATE = True


_OK = object()


def _part_consistent(f, eng: Engine) -> bool:
    """:func:`_consistent` for a component without relations, memoized per
    component (shared by every set it is part of), in the contextual session
    the component's queries use (``Engine._context_session``)."""
    key = (_OK, f)
    splits = eng.splits
    ok = splits.get(key)
    if ok is None:
        eng.stats["consistency_checks"] += 1
        try:
            g = _formula(f, bool(eng.relation_specs))
            s, lits = eng._context_session(g)
            if s.xfer is not None:
                s.xfer.sync_transfer()
            solver = s.solver
            ok = bool(solver.propagate()) and solver.implied(lits) is not None
            if ok and (CHECK_SEARCH or CHECK_ESCALATE and s.incomplete):
                # in a fresh session: the nodes escalation adds and what the
                # search learns stay out of the session the queries use
                ok = _consistent(f, eng, count=False)
        except Exception:
            ok = False
        splits.put(key, ok)
    return ok


def _consistent(a, eng: Engine, count: bool = True, search: Optional[bool] = None) -> bool:
    """``a`` is consistent as far as propagation in a session of its own
    tells (what ``Session.query_literal`` checks before answering), after
    escalation if the session is incomplete, and search with ``search``
    (default :data:`CHECK_SEARCH`).  False
    also when that cannot be decided (out of scope, a relation no theory
    reads, an error): the caller then answers under ``a`` as a whole, so
    whatever that does (None, ValueError) stays as it was."""
    if count:
        eng.stats["consistency_checks"] += 1
    if search is None:
        search = CHECK_SEARCH
    rel = bool(eng.relation_specs)
    try:
        g = _formula(a, rel)
        if g is TRUE:
            return True
        if g is FALSE:
            return False
        s = eng._fresh_session()
        lits = s.assume_formula(g)
        if s.xfer is not None:
            s.xfer.sync_transfer()
        solver = s.solver
        if not solver.propagate() or solver.implied(lits) is None:
            return False
        if CHECK_ESCALATE and s.incomplete:
            s.escalate()
            if s.xfer is not None:
                s.xfer.sync_transfer()
            if not solver.propagate() or solver.implied(lits) is None:
                return False
        return not search or solver.solve(lits)
    except Exception:
        return False


def _engine_ask(proposition, assumptions, eng: Engine) -> Optional[bool]:
    rel = bool(eng.relation_specs)
    try:
        prop = _formula(proposition, rel)
        assum = None if assumptions is True else _formula(assumptions, rel)
    except Unsupported:
        return None
    if prop is TRUE:
        return True
    if prop is FALSE:
        return False
    if assum is TRUE:
        assum = None
    if assum is FALSE:
        raise ValueError("inconsistent assumptions")
    try:
        if assum is None and isinstance(prop, P):
            return eng.is_(prop.expr, prop.pred)
        return eng.ask(prop, assum)
    except InconsistentAssumptions as e:
        raise ValueError(f"inconsistent assumptions {assumptions}") from e
    except Uninterpreted:
        # a relation no theory interprets: out of scope, as without theories
        return None
