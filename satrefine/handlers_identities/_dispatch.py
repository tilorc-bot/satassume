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

MAX_SPLITS = 8
"""Case splits (:func:`._engine.case_split`) tried in one top-level call: each
explores its branches with the full engine, so their number bounds the cost
of a call whose bookkeeping never collapses (``log(k*x*y)`` for three real
symbols of unknown sign)."""

splits_left: list[int] = [MAX_SPLITS]
"""The budget of the current top-level call (reset on entry)."""

generated_handlers: dict = {}
"""Handlers from the generated rule tables (``generated/<family>.py``), by key.

Tried before ``handlers_dict`` when :func:`mode` is ``"generated"``; when the
table declines, the key's live handler runs with its identity rows off."""

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

identities_off: list[bool] = [False]
"""Set by the dispatcher while it calls a key's live handler after that key's
generated table declined: identity handlers then return ``None`` (see
:func:`._engine.identity_handler`); nested ``refine`` calls reset it."""


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


@contextmanager
def exploring() -> Iterator[None]:
    """Run the engine's exploratory refinements (case and endpoint splits) under
    a firing counter of their own: each is bounded by :data:`MAX_FIRINGS` by
    itself and must not exhaust the cap of the call that tries them."""
    _firings.append(0)
    try:
        yield
    finally:
        _firings.pop()


class RefineLoopError(RecursionError):
    """Raised when one top-level ``refine`` fires handlers more than :data:`MAX_FIRINGS` times."""


_firings: list[int] = []   # a stack entry per active top-level call


def _memoized(ask: Any) -> Any:
    """``ask`` with its answers remembered: one top-level call asks the same
    question many times (a node is refined in every pass of the fixed point and
    in every branch of a split), and the answer under the same assumptions is
    the same.  Exceptions are not remembered."""
    cache: dict = {}

    def memo_ask(proposition: Any, assumptions: Any = True) -> Any:
        key = (proposition, assumptions)
        try:
            return cache[key]
        except KeyError:
            pass
        except TypeError:
            return ask(proposition, assumptions)
        answer = ask(proposition, assumptions)
        cache[key] = answer
        return answer
    return memo_ask


def refine(expr: Any, assumptions: Any = True) -> Any:
    """Refine ``expr`` under ``assumptions`` with the handlers in ``handlers_dict``.

    For the duration of a top-level call ``_upstream.ask`` is memoized."""
    top = not _firings
    if top:
        _firings.append(0)
        splits_left[0] = MAX_SPLITS
        saved_ask = _upstream.ask
        _upstream.ask = _memoized(saved_ask)
    try:
        return _refine(expr, assumptions)
    finally:
        if top:
            _firings.pop()
            _upstream.ask = saved_ask


def _refine(expr: Any, assumptions: Any) -> Any:
    if not isinstance(expr, Basic):
        return expr
    identities_off[0] = False
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
    handler = _upstream.handlers_dict.get(name)
    generated = generated_handlers.get(name) if mode() == "generated" else None
    new = generated(expr, assumptions) if generated is not None else None
    if new is None or new == expr:
        if handler is None:
            return expr
        # the live handler: with a generated table for the key, its identity rows are
        # switched off (the table is their specialization) and only its rules run
        saved = identities_off[0]
        identities_off[0] = generated is not None
        try:
            new = handler(expr, assumptions)
        finally:
            identities_off[0] = saved
    else:
        handler = generated
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
