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

import os
from contextlib import contextmanager
from typing import Any, Iterator

from sympy.core import Basic, Expr
from sympy.core.sympify import sympify

from .. import _upstream

MAX_FIRINGS = 500
"""Handler firings allowed in one top-level :func:`refine` call."""

generated_handlers: dict = {}
"""Handlers from the generated rule tables (``generated/<family>.py``), by key.

Preferred over ``handlers_dict`` when :func:`mode` is ``"generated"``."""

non_basic_returns: dict = {}
"""``(key, handler) -> count`` of handler results that were not SymPy objects
(a Python ``int`` from the vendored ``refine_sin_cos``); the dispatcher
sympifies them, the scoreboard reports them."""

fallback_handlers: dict = {}
"""The simple rules (:mod:`._simple`), by key: tried after the key's handler
declines, so a family table that registers ``floor`` or ``im`` keeps them
without chaining explicitly."""

MODE_ENV_VAR = "SATREFINE_IDENTITIES"


_forced: list[str] = []


def mode() -> str:
    """``"generated"`` (default) or ``"live"``, from ``SATREFINE_IDENTITIES`` unless :func:`live` is active."""
    if _forced:
        return _forced[-1]
    value = os.environ.get(MODE_ENV_VAR, "generated")
    if value not in ("generated", "live"):
        raise ValueError(f"{MODE_ENV_VAR} must be 'generated' or 'live', not {value!r}")
    return value


@contextmanager
def live() -> Iterator[None]:
    """Run the identity rows rather than the generated tables inside the block
    (generation itself must never read the tables it is producing)."""
    _forced.append("live")
    try:
        yield
    finally:
        _forced.pop()


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
    name = expr.__class__.__name__
    handler = generated_handlers.get(name) if mode() == "generated" else None
    if handler is None:
        handler = _upstream.handlers_dict.get(name)
    if handler is None:
        return expr
    new = handler(expr, assumptions)
    if new is None or new == expr:
        fallback = fallback_handlers.get(name)
        if fallback is None or fallback is handler:
            return expr
        new = fallback(expr, assumptions)
        if new is None or new == expr:
            return expr
    if not isinstance(new, Basic):
        tag = (name, getattr(handler, "__qualname__", repr(handler)))
        non_basic_returns[tag] = non_basic_returns.get(tag, 0) + 1
        new = sympify(new)
        if new == expr:
            return expr
    _firings[-1] += 1
    if _firings[-1] > MAX_FIRINGS:
        raise RefineLoopError(
            f"refine fired handlers more than {MAX_FIRINGS} times; last rewrite {expr} -> {new}")
    if not isinstance(new, Expr):
        return new
    return _refine(new, assumptions)
