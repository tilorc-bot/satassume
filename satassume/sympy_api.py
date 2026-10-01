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
  :mod:`satassume.relations`).  A relation no theory interprets (a Float
  or ``AccumBounds`` bound) is a free Boolean atom by default, so the rest
  of the assumptions still answers; ``Engine(uninterpreted="none")`` (the
  old behaviour, opt-in) returns None instead;
* ``"matrix"``: a matrix predicate (``Q.invertible`` and friends from
  ``sympy.assumptions.predicates.matrices``) or a vocabulary predicate
  applied to a non-scalar argument (a ``MatrixSymbol``, ...) or to an
  argument with a non-commutative subterm (``Symbol('A',
  commutative=False)``, ``re(A)``, ``g(x)`` for a non-commutative ``g``):
  the templates are about numbers, ``A`` may be a matrix (issue #62);
* ``"custom"``: any other predicate outside the vocabulary (user-defined
  predicates, ``Q.is_true`` over a non-relational) for which no
  clause-generating function is registered (see :func:`register` and
  :mod:`satassume.extensions`); a registered predicate is in scope, with
  the arity it was registered for;
* ``"other"``: the proposition or the assumptions are not a Boolean
  combination of applied predicates at all (a bare ``Q.positive``, an
  ``Expr``, an ``ITE``, ...).

If several apply the first in this list is reported.

Opaque conjuncts: in the *assumptions*, an applied predicate of category
``"matrix"`` or ``"custom"`` is not out of scope.  It translates to an
opaque atom (``P(OPAQUE, applied predicate)``): a free Boolean that no
template, rule, theory, link or registered function reads, so keeping it
only drops what it says (sound).  Equal conjuncts are one atom and
``A & ~A`` is inconsistent (ValueError).  Its relevance keys are those of
its arguments, so it does not sink unrelated components.  In the
*proposition* these categories still give None (``ask(Q.invertible(M),
Q.invertible(M))`` is None), and ``"other"`` is out of scope on both sides.
:func:`out_of_scope` keeps reporting the categories of the input as such.

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
from .engine import INCONSISTENT as _INCONSISTENT
from .engine import affine_glue as _affine_glue
from .epoch import EPOCH as _EPOCH
from .extensions import Args, extensions, register, unregister  # noqa: F401
from .formula import And, Equivalent, Formula, Implies, Not, Or, P, TRUE, FALSE  # noqa: F401
from .relations import Uninterpreted, relation_atom, relational_name

from sympy.assumptions.assume import AppliedPredicate as _Applied
from sympy.core.add import Add as _SAdd
from sympy.core.basic import Basic as _Basic
from sympy.core.mul import Mul as _SMul
from sympy.core.power import Pow as _SPow
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


#: memo of :func:`_noncommutative` (a function of the expression only:
#: SymPy equality distinguishes ``Symbol('A')`` from the non-commutative
#: ``A`` and ``Function('g')`` from ``Function('g', commutative=False)``)
_NONCOMM: dict = {}
NONCOMM_SIZE = 4096


def _fixed_noncommutative(t) -> bool:
    """Whether ``t`` is non-commutative by construction, read without
    evaluating any assumption (``t.is_commutative`` would compute and cache
    ``commutative`` in SymPy's ``_assumptions`` of compound expressions,
    and the engine must never write SymPy's assumption caches).  Symbols
    (``Dummy``, ``Wild``) carry their given assumptions in ``_assumptions0``;
    undefined functions (``Function('g', commutative=False)``) and atom
    types such as quantum operators fix ``is_commutative`` as a class
    attribute; anything else is decided by its arguments."""
    from sympy.core.symbol import Symbol
    if isinstance(t, Symbol):
        return dict(getattr(t, "_assumptions0", ())).get("commutative") is False
    for k in type(t).__mro__:
        v = k.__dict__.get("is_commutative", None)
        if v is not None:
            return v is False
    return False


def _noncommutative(e) -> bool:
    """Whether ``e`` has a non-commutative subterm (fixed non-commutative
    by construction anywhere, see :func:`_fixed_noncommutative`, ``e`` itself included, matrix expressions not
    descended into).  The whole expression is not
    enough (``re(A)`` claims to be commutative), so this walks the tree;
    memoized, since it runs for every applied vocabulary predicate."""
    r = _NONCOMM.get(e)
    if r is not None:
        return r
    r = False
    stack = [e]
    while stack:
        t = stack.pop()
        if not isinstance(t, _Basic) or getattr(t, "is_Matrix", False):
            # a matrix expression reaches a scalar argument only through a
            # scalar-valued function of it (Trace(M), M[0, 0]): a number
            continue
        if _fixed_noncommutative(t):
            r = True
            break
        stack.extend(t.args)
    if len(_NONCOMM) >= NONCOMM_SIZE:
        _NONCOMM.clear()
    _NONCOMM[e] = r
    return r


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
        # a non-commutative argument (a value that may be a matrix) is out
        # of scope like a matrix one: the templates assume numbers (#62)
        return "matrix" if _noncommutative(args[0]) else None
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


#: predicate name of an opaque atom (see :func:`to_formula`): not an
#: identifier, so never the name of a registered predicate
OPAQUE = "<opaque>"

#: categories of an applied predicate that an assumption keeps as an opaque atom
OPAQUE_CATEGORIES = frozenset({"matrix", "custom"})


def to_formula(expr, relations: bool = False, opaque: bool = False):
    """Translate a SymPy Boolean over applied predicates into a formula.
    Raises :class:`Unsupported` for anything out of scope.  With
    ``relations`` (the engine has theory adapters, see
    :mod:`satassume.relations`) relations become relation atoms.  With
    ``opaque`` (the assumptions side) an applied predicate of category
    ``"matrix"`` or ``"custom"`` becomes the opaque atom
    ``P(OPAQUE, expr)``: a free Boolean that no template, rule, theory,
    link or registered function reads, identified by the applied predicate
    itself (equal conjuncts are one atom, ``A & ~A`` is a conflict).
    Keeping it only drops what it says, which is sound."""
    if expr is True or isinstance(expr, _BTrue):
        return TRUE
    if expr is False or isinstance(expr, _BFalse):
        return FALSE
    if isinstance(expr, _Applied):
        name = str(expr.function.name)
        if name == "is_true" and len(expr.arguments) == 1:
            # Q.is_true of a Boolean constant is that constant (not an atom)
            a = expr.arguments[0]
            if a is True or isinstance(a, _BTrue):
                return TRUE
            if a is False or isinstance(a, _BFalse):
                return FALSE
        if name in RELATION_PREDICATES or name == "is_true":
            parts = relation_parts(expr)
            if parts is not None:
                return _relation_formula(expr, parts, relations)
        c = _applied_category(expr)
        if c is not None:
            if opaque and c in OPAQUE_CATEGORIES:
                return P(OPAQUE, expr)
            raise Unsupported(f"{expr} is out of scope ({c})", c)
        args = expr.arguments
        return P(name, args[0] if len(args) == 1 else Args(args))
    if isinstance(expr, _SAnd):
        return And(*[to_formula(a, relations, opaque) for a in expr.args])
    if isinstance(expr, _SOr):
        return Or(*[to_formula(a, relations, opaque) for a in expr.args])
    if isinstance(expr, _SNot):
        return Not(to_formula(expr.args[0], relations, opaque))
    if isinstance(expr, _SImplies):
        return Implies(to_formula(expr.args[0], relations, opaque),
                       to_formula(expr.args[1], relations, opaque))
    if isinstance(expr, _SEquivalent):
        return Equivalent(*[to_formula(a, relations, opaque) for a in expr.args])
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
    * An out-of-scope proposition (matrix predicates, unregistered custom
      predicates, non-scalar arguments, non-Boolean propositions; relations
      without theory adapters) returns None without touching the engine.
      The caller is expected to route it to SymPy's existing path;
      :func:`out_of_scope` tells which category applies.
    * In the assumptions, matrix and unregistered custom predicates are
      opaque atoms, and a relation no theory interprets is a free atom
      (unless ``Engine(uninterpreted="none")``): see the module docstring,
      "Opaque conjuncts".  Non-Boolean assumptions return None.
    * Custom predicates with a registered clause-generating function
      (:func:`register`, the counterpart of ``Predicate.register``) are in
      scope: their atoms take part in propagation and search.
    * Inconsistent assumptions raise ``ValueError`` like ``sympy.ask``,
      except for a proposition about constants only (every argument a
      number without free symbols), which is answered without the
      assumptions and so never raises.
      A query is answered under the conjuncts of the assumptions connected
      to it (by shared symbols, undefined functions and closed terms
      whose facts are not decided context-free, transitively; a common
      value such as ``x = 2``, ``y = 2`` does not connect), unless the
      whole set is inconsistent; see ``_relevant``.
      Assumptions contradicting a fact declared on a symbol
      (``ask(Q.commutative(x), ~Q.commutative(x))``) count as inconsistent
      here, where SymPy trusts the assumption.
    """
    eng = engine or default_engine()
    # answer memo (see Engine.answers): keyed by the SymPy objects
    # themselves, valid while the registry epoch (satassume.epoch: the
    # registrations that decide the scope and add facts, the templates,
    # the adapters) is the one it was filled under
    key = None
    if isinstance(proposition, _Basic) and (assumptions is True or isinstance(assumptions, _Basic)):
        key = (proposition, assumptions)
        memo = eng.answers
        if eng._epoch != _EPOCH[0]:
            eng._check_version()
        r = memo.get(key, _MISS)
        if r is not _MISS:
            eng.stats["cache_hits"] += 1
            return r
    r = _ask(proposition, assumptions, eng)
    if key is not None:
        memo.put(key, r)
    return r


_MISS = object()


#: ``(expr, relations) -> formula``, or the ``Unsupported`` category, of
#: :func:`to_formula` on SymPy Booleans; valid while the default registry's
#: version (which decides the scope of custom predicates) is ``_FORMULAS_STATE``
_FORMULAS: dict = {}
_FORMULAS_STATE = [None]
FORMULAS_SIZE = 100_000


def _formula(expr, relations: bool, opaque: bool = False):
    """Memoized :func:`to_formula` (raises :class:`Unsupported` like it).
    ``opaque``: translating assumptions (see :func:`to_formula`)."""
    if not isinstance(expr, _Basic):
        return to_formula(expr, relations, opaque)
    state = extensions.version
    if _FORMULAS_STATE[0] != state:
        _FORMULAS.clear()
        _FORMULAS_STATE[0] = state
    key = (expr, relations, opaque)
    f = _FORMULAS.get(key)
    if f is None:
        try:
            f = to_formula(expr, relations, opaque)
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
# its own, unless the whole set is inconsistent (checked once per set: per
# component without relations, as a whole with them); see docs/design.md,
# "Why splitting is sound", for the argument.
#
# Keys of an expression: its free symbols, the classes of its undefined
# function applications (EUF congruence connects f(x) and f(y)), and the
# closed terms that may carry a fact the assumptions decide (see "Closed
# terms" below).  Rationals have all their facts decided context-free
# (except ``polar``), so without relations a Rational inside a term
# connects nothing; a Rational that is itself the argument of a predicate
# (``Q.polar(2)``) is a key.  A relation's keys are those of both sides,
# so ``Q.eq(x, y)`` and ``x < y`` connect x and y; a Rational or ``K``
# side is no key, so terms pinned to a common value (``x = 2``, ``y = 2``)
# do not connect: a set or query with a relation splits like one without
# (``RELATIONAL = "components"``), and only the raising of a set with a
# relation (or a keyless conjunct, ``Q.lt(1, 2)``) is decided by the whole
# set's verdict rather than per component (see ``RELATIONAL``).
#
# Closed terms (no symbol inside).  Rule: a maximal closed subterm ``c`` of
# a predicate argument (its parent has a symbol) is no key if it lies in
# the class ``K`` of :func:`_const_free` (Rationals; ``pi``, ``E``,
# ``GoldenRatio``, ``TribonacciConstant``, ``I``, ``oo``, ``-oo``,
# ``zoo``; ``b**r`` for ``b`` a positive Rational, ``pi`` or ``E`` and
# ``r`` Rational; ``q*k`` for a Rational ``q`` and such a ``k``); else it
# is a key together with every non-Rational closed subterm of it and the
# classes of the undefined functions in it (``f(1)``: a free EUF term;
# ``1.5``: rationality open; ``pi + E``: rationality open; ``pi - 3`` and
# ``cos(1)``: the rule base does not decide their sign; anything else, out
# of conservatism).  A closed term that is itself a predicate argument, or
# inside an application of ``polar``, is always keyed that way; a closed
# relation side follows the rule (``x = 2``, ``x < pi``: no key; ``x = 1.5``,
# ``y = f(1)``: keys) unless ``RELATIONAL`` is ``"whole"`` or
# ``"rationals"``, which key it (as ``"rationals"`` keys every closed term).
#
# Why dropping the key of a ``K`` term is sound.  The engine's own
# context-free clauses of a ``K`` term fix every predicate of its block but
# ``polar`` (``tests/test_relevance.py::test_unkeyed_constants_are_decided``),
# and templates derive closed nodes only from closed nodes (``b - 1``,
# ``2*e`` need a non-number base or exponent; a Mul's coefficient-free
# rest and the ``s`` of ``I*pi*c*s`` keep the Mul's symbols), while a ``K``
# term derives none; so the solver variables two components can share
# through ``K`` terms are fixed, and an assumption about such a term is
# either already implied (nothing to carry) or contradicts its own
# context-free facts (the component holding it is inconsistent by itself,
# which the per-component consistency check reports).  What only a
# relation could say about it (its *value*: ``x = pi``) needs no such
# argument: a set with a relation is not checked per component but as a
# whole, and answering under a part of a set that is not inconsistent is
# sound by monotonicity (see ``RELATIONAL``).  ``polar`` is undecided
# for numbers, but its clauses are definite Horn with ``polar`` of the node
# as the only positive literal: with no ``polar`` application keyed to a
# component, setting every ``polar`` the component does not force to True
# satisfies them whatever another component says about a closed ``polar``;
# an application of ``polar`` keys every closed term inside it.
#
# An out-of-scope applied predicate of the assumptions (category
# ``"matrix"`` or ``"custom"``: ``Q.invertible(M)``, ``Q.positive(M)``, an
# unregistered predicate, ``Q.is_true`` of a non-relational) is an opaque
# atom there (see ``to_formula``): its keys are those of its arguments, so
# it is a component of its own (or joins the one sharing its symbols) and
# no longer sinks the other components; a component of opaque atoms is
# consistent unless it holds an atom and its negation.  As a proposition
# it stays out of scope (None).
#
# Opaque (never split): a registered custom predicate (its function may
# mention any term), anything that is not a Boolean over applied
# predicates and relations; also a set or query with a term of a class a
# vocabulary predicate is registered for in the engine's registry (its
# function may mention any term), or with any term when one is registered
# for a class of the nodes templates derive (Add, Mul, Pow or a base of
# them); see ``_vocab_blocks``.

_OPAQUE = None  # keys of an opaque expression
#: Boolean -> ``(keys, has a relation)``; valid while the registry epoch
#: (:mod:`satassume.epoch`: the default registry decides whether a custom
#: predicate is registered, so opaque, or unregistered, keyed by its
#: arguments; the templates decide what a closed term's block fixes) is
#: ``_KEYS_STATE``.  ``_CONST`` (closed term -> in ``K``) shares it.
_KEYS: dict = {}
_CONST: dict = {}
_KEYS_STATE = [None]
KEYS_SIZE = 100_000


#: the closed atoms of ``K`` (see "Closed terms" above)
_K_ATOMS = frozenset([_S.Pi, _S.Exp1, _S.GoldenRatio, _S.TribonacciConstant,
                      _S.ImaginaryUnit, _S.Infinity, _S.NegativeInfinity,
                      _S.ComplexInfinity])


def _const_base(c) -> bool:
    """``c`` is a ``K`` atom or a power ``b**r`` (``b`` a positive Rational,
    ``pi`` or ``E``; ``r`` Rational)."""
    if c in _K_ATOMS:
        return True
    if c.is_Pow:
        b, r = c.args
        return r.is_Rational and ((b.is_Rational and b.is_positive)
                                  or b is _S.Pi or b is _S.Exp1)
    return False


def _const_free(c) -> bool:
    """Whether the closed term ``c`` is in ``K``: no key (see "Closed
    terms" above).  Structural, so a function of ``c`` alone; memoized per
    registry epoch with ``_KEYS``."""
    v = _CONST.get(c)
    if v is None:
        if c.is_Rational or _const_base(c):
            v = True
        elif c.is_Mul:
            rest = [a for a in c.args if not a.is_Rational]
            v = len(rest) == 1 and len(c.args) <= 2 and _const_base(rest[0])
        else:
            v = False
        if len(_CONST) >= KEYS_SIZE:
            _CONST.clear()
        _CONST[c] = v
    return v


def _closed_keys(c, acc: set, force: bool) -> None:
    """Keys of the maximal closed term ``c``: none if it is in ``K`` (and
    not ``force``), else every non-Rational closed subterm and the classes
    of the undefined functions inside."""
    from sympy.core.function import AppliedUndef
    if c.is_Rational or (not force and RELATIONAL != "rationals" and _const_free(c)):
        return
    stack = [c]
    while stack:
        e = stack.pop()
        if e.is_Rational:
            continue
        acc.add(e)
        if isinstance(e, AppliedUndef):
            acc.add(type(e))
        stack.extend(e.args)
    if RELATIONAL == "rationals":
        # sin(2) is congruent to sin(x) once x = 2
        acc.update(a for a in c.atoms(_Rational))


def _expr_keys(e, acc: set, force: bool = False) -> bool:
    """Add the keys of the expression ``e`` to ``acc``; True if ``e`` is
    closed (no symbol inside), in which case nothing was added: the caller
    keys it with :func:`_closed_keys` (a maximal closed term).  ``force``:
    key every closed subterm (inside ``polar``)."""
    from sympy.core.function import AppliedUndef
    if e.is_Symbol:
        acc.add(e)
        return False
    if e.is_Rational:
        return True
    args = e.args
    flags = [_expr_keys(a, acc, force) for a in args]
    if all(flags):
        return True
    for a, closed in zip(args, flags):
        if closed:
            _closed_keys(a, acc, force)
    if isinstance(e, AppliedUndef):
        acc.add(type(e))
    return False


def _arg_keys(a, acc: set, force: bool = False) -> None:
    """Keys of a predicate argument or relation side ``a``: a closed one is
    always keyed (like a Rational argument, ``Q.polar(2)``)."""
    if _expr_keys(a, acc, force):
        _closed_keys(a, acc, True)


#: marker added by a relation while collecting keys (removed again)
_RELATION = object()


def _keys(e):
    """Frozenset of the keys of the Boolean ``e``, or ``_OPAQUE``."""
    return _keys_rel(e)[0]


def _keys_rel(e):
    """``(keys, has a relation)`` of the Boolean ``e`` (keys as :func:`_keys`)."""
    state = _EPOCH[0]
    if _KEYS_STATE[0] != state:
        _KEYS.clear()
        _CONST.clear()
        _KEYS_STATE[0] = state
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
        if name == "is_true" and len(args) == 1 and isinstance(args[0], _Relational):
            return _bool_keys(args[0], acc)
        if name not in PRED_INDEX or name in matrix_predicates():
            if _applied_category(e) not in OPAQUE_CATEGORIES:
                return False            # a registered custom predicate, or "other"
            # an opaque atom in the assumptions: keyed by its arguments
            for a in args:
                if not isinstance(a, _Basic):
                    return False
                _arg_keys(a, acc)
            return True
        if name == "zero" and RELATIONAL == "rationals":
            acc.add(_S.Zero)            # zero(e) <-> eq(e, 0)
        polar = name == "polar"
        for a in args:
            if not isinstance(a, _Basic):
                return False
            if a.is_Rational:
                acc.add(a)
            else:
                _arg_keys(a, acc, polar)
        return True
    return False


def _sides_keys(args, acc: set, eq: bool = False) -> bool:
    acc.add(_RELATION)
    for a in args:
        if not isinstance(a, _Basic):
            return False
        if RELATIONAL == "components":
            # a side keys like a term inside a predicate argument: a
            # Rational or a ``K`` constant (``x = 2``, ``x < pi``) is no
            # key, so ``x = 2`` and ``y = 2`` stay apart (see RELATIONAL)
            if _expr_keys(a, acc):
                _closed_keys(a, acc, False)
        elif eq and a.is_Rational and RELATIONAL == "rationals":
            acc.add(a)                  # x = 2, y = 2: x ~ y in EUF
        else:
            # "whole": not split anyway; "rationals" keys every closed
            # term
            _arg_keys(a, acc, True)
    return True


class _Split:
    """The components of one set of assumptions."""
    __slots__ = ("whole", "conjuncts", "comps", "opaque", "relational", "keyless",
                 "parts", "consistent", "vocab")

    def __init__(self, a):
        self.whole = a
        #: a term of the set has a vocabulary predicate registered for its
        #: class (``_vocab_blocks``; None: not computed).  The split lives
        #: in ``Engine.splits``, dropped with the registry epoch, and an
        #: engine has one registry, so the flag cannot go stale
        self.vocab = None
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
    and ``a`` is not found inconsistent.  Three-valued: a set whose verdict
    is inconsistent answers under ``a`` (which raises); consistent or
    unknown, under the part (sound by monotonicity).  The verdict is the
    whole set's (:func:`_consistent`) when the set has a relation, a
    keyless conjunct or sign atoms on sums that start the relation glue
    (``engine.affine_glue``); otherwise the conjunction of the components'
    verdicts, which equals it there (docs/design.md, "Why components are
    independent")."""
    splits = eng.splits
    sp = splits.get(a)
    if sp is None:
        sp = _Split(a)
        splits.put(a, sp)
    if sp.opaque:
        return a
    ext = eng.extensions
    if ext is not None and ext._vocab:
        v = sp.vocab
        if v is None:
            v = sp.vocab = _vocab_blocks(a, ext)
        if v or _vocab_blocks(p, ext):
            return a
    pk, prel = _keys_rel(p)
    if not pk:
        # opaque, or no key at all: nothing to split by
        return a
    if RELATIONAL == "whole" and (prel or sp.relational or sp.keyless):
        # (ablation) a relation brings in the theories, which connect terms
        # of different components (see RELATIONAL)
        return a
    mine = tuple(j for j, (k, _) in enumerate(sp.comps) if not k.isdisjoint(pk))
    f = sp.part(mine)
    if f is a:
        return a
    ok = sp.consistent
    if ok is None:
        if sp.relational or sp.keyless:
            # the whole set's verdict decides raising; the part answers
            # unless it is inconsistent (see RELATIONAL)
            ok = _consistent(a, eng)
        else:
            # no relation: the components share no solver variable, so the
            # set is consistent iff each component is.  Out of scope as a
            # whole (an "other" conjunct, a vocabulary predicate of the
            # wrong arity): as before, the whole set answers (None).  Matrix
            # and unregistered custom predicates are opaque atoms here and
            # translate
            rel = bool(eng.relation_specs)
            try:
                g = _formula(a, rel, True)
            except Unsupported:
                ok = False
            else:
                if rel and _affine_glue(g):
                    # sign atoms on sums sharing a symbol start the relation
                    # glue in the whole set's session (#51), which then
                    # links terms of every component: the per-component
                    # checks could miss an inconsistency, so the whole
                    # set's verdict decides, as for a relational set
                    ok = _consistent(a, eng)
                else:
                    ok = all(_part_consistent(sp.part((j,)), eng)
                             for j in range(len(sp.comps)))
        sp.consistent = ok
    return f if ok else a


#: classes of the nodes templates derive from a term (``b - 1``, ``2*e``, a
#: Mul's rest): no subterm of the query or the set, so a vocabulary
#: predicate registered for one of them (or a base) may apply to any set
_DERIVED_CLASSES = (_SAdd, _SMul, _SPow)


def _vocab_blocks(e, ext) -> bool:
    """Whether the vocabulary predicates registered in ``ext`` (non-empty
    ``_vocab``) may apply to a node of ``e`` (a SymPy Boolean): a subterm of
    ``e`` is an instance of a registered class, or a registered class is a
    base of a class of derived nodes.  Such a predicate's function may
    mention any term, so ``e`` is not split (an unrelated registration no
    longer disables the split of every set, W2A1).  Uses
    ``Extensions.is_scalar_like`` (its per-class cache is cleared by every
    vocabulary registration)."""
    for c in _DERIVED_CLASSES:
        if ext._node_handlers(c):
            return True
    stack = [e]
    seen = set()
    while stack:
        n = stack.pop()
        if ext.is_scalar_like(n):
            return True
        for a in getattr(n, "args", ()):
            if isinstance(a, _Basic) and a not in seen:
                seen.add(a)
                stack.append(a)
    return False


#: how a set or query with a relation splits.  With a relation, the session
#: has the theories and links every vocabulary argument ``e`` by
#: ``zero(e) <-> eq(e, 0)``; terms of different components can then be
#: merged in EUF through a common value (``x = 2`` and ``y = 2``, ``zero(x)``
#: and ``y = 0``, but also values LRA derives, ``x + 1 = 3`` or ``2 <= x <= 2``,
#: meeting through interface equalities, and a zero the rule base derives
#: from ``nonnegative & nonpositive``), and congruence merges ``sin(x)`` with
#: ``sin(y)`` or ``sin(2)``, which carries facts across.
#:
#: ``"components"`` (the default): such a set or query splits by key
#: connectivity like a relation-free one, with the keys of "Closed terms"
#: above (a Rational or ``K`` side is no key): ``Q.positive(sin(x))`` under
#: ``Q.eq(x, 2) & Q.eq(y, 2) & Q.positive(sin(y))`` is answered under
#: ``Q.eq(x, 2)`` (None; a common value no longer merges across
#: components).  Whether the set raises is decided by the whole set's
#: verdict (:func:`_consistent`, ``Engine.verdict``): inconsistent, the
#: query is answered under the whole set (which raises); consistent or
#: unknown, under the part, which is sound by monotonicity whatever the
#: verdict (a consequence of a sub-conjunction is one of the set).  The
#: part's session holds only its component, so each part gets its own
#: theories, LRA branch budget, give-up and transfer engagement, and an
#: unrelated relation, undecidable constant or integer block no longer
#: changes the answer (K1, K5, W2B3b/c, W2B4).
#: ``"whole"`` (ablation): a set or query with a relation is not split (the
#: answers are those of the whole set); ``"rationals"`` (ablation): it
#: splits, with a Rational that is a side of an equality, the 0 of
#: ``zero``, and the Rationals of a closed term as keys (connects ``x = 2``
#: with ``y = 2``, ``sin(2)``, ``polar(2)``, but not the values LRA or the
#: rule base derive).
#: The key memo ``_KEYS`` depends on it, and so do the splits memoized in
#: ``Engine.splits`` (``_Split``: the components and the consistency flag)
#: and the answer memo.  A module constant, not a setting: changing it at
#: run time is unsupported (answers, keys and splits memoized under the
#: old value are kept); a test that switches it must clear ``_KEYS`` and
#: use fresh engines.
#: See docs/design.md, "What connects".
RELATIONAL = "components"


_OK = object()


def _part_consistent(f, eng: Engine) -> bool:
    """:func:`_consistent` for a component without relations, memoized per
    component (shared by every set it is part of)."""
    key = (_OK, f)
    splits = eng.splits
    ok = splits.get(key)
    if ok is None:
        ok = _consistent(f, eng)
        splits.put(key, ok)
    return ok


def _consistent(a, eng: Engine) -> bool:
    """``a`` may be answered under a part: its verdict, from the one
    complete check of the set (``Engine.verdict``: the whole cone,
    propagation and search, memoized per formula in the engine; built like
    the contextual session of a query under ``a`` but not kept, since the
    queries of a split set run in their parts' sessions), is consistent or
    unknown.
    False if it is inconsistent, and also when the set cannot be checked
    (out of scope, a relation no theory reads, an error): the caller then
    answers under ``a`` as a whole, so whatever that does (None,
    ValueError) stays as it was."""
    eng.stats["consistency_checks"] += 1
    try:
        g = _formula(a, bool(eng.relation_specs), True)
        if g is TRUE:
            return True
        if g is FALSE:
            return False
        return eng.verdict(g) is not _INCONSISTENT
    except Exception:
        return False


def _engine_ask(proposition, assumptions, eng: Engine) -> Optional[bool]:
    rel = bool(eng.relation_specs)
    try:
        prop = _formula(proposition, rel)
        assum = None if assumptions is True else _formula(assumptions, rel, True)
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
