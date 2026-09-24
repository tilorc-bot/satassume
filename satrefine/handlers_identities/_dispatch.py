"""The refine dispatcher for identity-based handlers.

This is the vendored driver (:func:`satrefine._upstream.refine`) with two
changes, and it replaces ``satrefine.refine`` whenever the
``handlers_identities`` package is selected (see the package ``__init__``):

* **re-refine after auto-evaluation.**  When a node is rebuilt from refined
  children, the constructor may auto-evaluate into a different structure
  (``im`` of a product becomes a sum of ``re``, ``im`` and ``arg`` terms).
  The vendored driver then dispatches on the new head without refining the
  children it just created; this one refines the rebuilt node again;
* **a firing cap.**  Handler results are re-refined until a fixed point, so
  two rules that undo each other loop forever in the vendored driver.  Here
  every top-level call counts handler firings and raises
  :class:`RefineLoopError` past :data:`MAX_FIRINGS`, so a bad ordering fails
  loudly in tests instead of hanging.

``_upstream.refine`` itself is untouched (it must stay behavior-identical
to SymPy's); handlers written for the vendored driver keep working here.
"""
from __future__ import annotations

from typing import Any

from sympy.core import Basic, Expr

from .. import _upstream

MAX_FIRINGS = 500
"""Handler firings allowed in one top-level :func:`refine` call."""


class RefineLoopError(RecursionError):
    """Raised when one top-level ``refine`` fires handlers more than :data:`MAX_FIRINGS` times."""


_firings: list[int] = []   # a stack entry per active top-level call


def refine(expr: Any, assumptions: Any = True) -> Any:
    """Refine ``expr`` under ``assumptions`` with the handlers in ``handlers_dict``."""
    top = not _firings
    if top:
        _firings.append(0)
    try:
        return _refine(expr, assumptions)
    finally:
        if top:
            _firings.pop()


def _refine(expr: Any, assumptions: Any) -> Any:
    if not isinstance(expr, Basic):
        return expr
    if not expr.is_Atom:
        args = [_refine(a, assumptions) for a in expr.args]
        new = expr.func(*args)
        if new.is_Atom or new.func is not expr.func or new.args != tuple(args):
            return _refine(new, assumptions) if new != expr else expr
        expr = new
    if hasattr(expr, "_eval_refine"):
        ref = expr._eval_refine(assumptions)
        if ref is not None:
            return ref
    handler = _upstream.handlers_dict.get(expr.__class__.__name__)
    if handler is None:
        return expr
    new = handler(expr, assumptions)
    if new is None or new == expr:
        return expr
    _firings[-1] += 1
    if _firings[-1] > MAX_FIRINGS:
        raise RefineLoopError(
            f"refine fired handlers more than {MAX_FIRINGS} times; last rewrite {expr} -> {new}")
    if not isinstance(new, Expr):
        return new
    return _refine(new, assumptions)
