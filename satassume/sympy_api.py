"""SymPy-facing API.

* ``is_(expr, 'positive')`` and ``ask(Q.positive(expr), assumptions)`` answer
  through one shared :class:`~satassume.engine.Engine`.
* ``install()`` routes SymPy's own ``expr.is_*`` properties through the
  engine by replacing ``sympy.core.assumptions._ask``, the function every
  ``is_*`` property calls on a cache miss.  The per-object ``_assumptions``
  dictionaries keep serving as the cache, so the hit path is unchanged.
"""
from __future__ import annotations

from typing import Optional

from .engine import Engine, InconsistentAssumptions, ObjectCache
from .formula import And, Equivalent, Formula, Implies, Not, Or, P, TRUE, FALSE
from .rules import PRED_INDEX


class Unsupported(Exception):
    """The proposition uses something the engine does not model (yet):
    binary relations, matrix predicates, unknown predicates."""


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
# SymPy Boolean -> satassume formula
# --------------------------------------------------------------------------

def to_formula(expr):
    from sympy.assumptions.assume import AppliedPredicate
    from sympy.logic.boolalg import (And as SAnd, Or as SOr, Not as SNot,
                                     Implies as SImplies, Equivalent as SEquivalent,
                                     BooleanTrue, BooleanFalse)
    if expr is True or isinstance(expr, BooleanTrue):
        return TRUE
    if expr is False or isinstance(expr, BooleanFalse):
        return FALSE
    if isinstance(expr, AppliedPredicate):
        name = str(expr.function.name)
        if name not in PRED_INDEX or len(expr.arguments) != 1:
            raise Unsupported(f"predicate {name} with {len(expr.arguments)} argument(s)")
        return P(name, expr.arguments[0])
    if isinstance(expr, SAnd):
        return And(*[to_formula(a) for a in expr.args])
    if isinstance(expr, SOr):
        return Or(*[to_formula(a) for a in expr.args])
    if isinstance(expr, SNot):
        return Not(to_formula(expr.args[0]))
    if isinstance(expr, SImplies):
        return Implies(to_formula(expr.args[0]), to_formula(expr.args[1]))
    if isinstance(expr, SEquivalent):
        return Equivalent(*[to_formula(a) for a in expr.args])
    raise Unsupported(f"cannot translate {type(expr).__name__}")


# --------------------------------------------------------------------------
# public queries
# --------------------------------------------------------------------------

def is_(expr, pred: str, engine: Optional[Engine] = None) -> Optional[bool]:
    """Context-free truth value of ``pred(expr)`` (replacement for ``expr.is_<pred>``)."""
    return (engine or default_engine()).is_(expr, pred)


def ask(proposition, assumptions=True, engine: Optional[Engine] = None) -> Optional[bool]:
    """Replacement for ``sympy.ask``.  Returns True, False or None; raises
    ``ValueError`` on inconsistent assumptions like SymPy does.  Propositions
    the engine cannot model yet (relations, matrices) return None."""
    eng = engine or default_engine()
    try:
        prop = to_formula(proposition)
        assum = None if assumptions is True else to_formula(assumptions)
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


# --------------------------------------------------------------------------
# installing into SymPy
# --------------------------------------------------------------------------

_saved_ask = None


def install(engine: Optional[Engine] = None) -> Engine:
    """Route every ``expr.is_*`` cache miss in SymPy through ``engine``."""
    global _saved_ask
    import sys
    mod = sys.modules['sympy.core.assumptions']
    eng = engine or default_engine()
    set_default_engine(eng)
    if _saved_ask is None:
        _saved_ask = mod._ask

    def _ask(fact, obj):
        return eng.is_(obj, fact)
    mod._ask = _ask
    return eng


def uninstall() -> None:
    import sys
    global _saved_ask
    if _saved_ask is not None:
        sys.modules['sympy.core.assumptions']._ask = _saved_ask
        _saved_ask = None
