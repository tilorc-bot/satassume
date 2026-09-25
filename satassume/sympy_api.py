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
from sympy.core.expr import Expr as _Expr
from sympy.core.relational import Relational as _Relational
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
    * Inconsistent assumptions raise ``ValueError`` like ``sympy.ask``.
      Assumptions contradicting a fact declared on a symbol
      (``ask(Q.commutative(x), ~Q.commutative(x))``) count as inconsistent
      here, where SymPy trusts the assumption.
    """
    eng = engine or default_engine()
    rel = bool(eng.relation_specs)
    try:
        prop = to_formula(proposition, rel)
        assum = None if assumptions is True else to_formula(assumptions, rel)
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
