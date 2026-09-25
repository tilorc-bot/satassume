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
  a chain of rewrites of one node raises :class:`RefineLoopError` past
  :data:`MAX_FIRINGS` steps (and a whole call past
  :data:`MAX_TOTAL_FIRINGS` firings), so a bad ordering fails loudly in
  tests instead of hanging, while a wide input's independent rewrites do
  not add up;
* **a result cache.**  One top-level call refines the same node under the
  same assumptions many times (every pass of the fixed point re-refines the
  children of a result, every branch of a ``Piecewise`` or of a case split
  redoes the work below it).  Completed results are remembered for the
  call, keyed on the node, the assumptions, the mode and the engine state
  (:data:`state`: which identity handlers are switched off, whether a split
  is exploring), so a result is what recomputing it would give and repeated
  work neither costs time nor counts against the cap.  A node being refined
  is not in the cache yet, so a real loop still reaches the cap.

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
"""Rewrites allowed in one chain (a node rewritten, the result rewritten again, ...):
more is a loop.  Independent rewrites of many nodes do not add up."""

MAX_TOTAL_FIRINGS = 100*MAX_FIRINGS
"""Handler firings allowed in one top-level :func:`refine` call (a backstop)."""

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
table declines, the key's live handler runs in full (the table is a fast
path and an audit of the rows, not a replacement: the catalog specializes
them only in part)."""

non_basic_returns: dict = {}
"""``(key, handler) -> count`` of handler results that were not SymPy objects
(a Python ``int`` from the vendored ``refine_sin_cos``); the dispatcher
sympifies them, the scoreboard reports them."""

fallback_handlers: dict = {}
"""The simple rules (:mod:`._simple`), by key: tried after the key's handler
declines, so a family table that registers ``floor`` or ``im`` keeps them
without chaining explicitly."""

own_args: set = set()
"""Keys whose handler refines the node's arguments itself (``Piecewise``: each
branch under its condition); the dispatcher does not refine them first."""

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


@contextmanager
def tables() -> Iterator[None]:
    """Use the generated tables inside the block whatever ``SATREFINE_IDENTITIES`` says
    (a staged generation, :mod:`._stages`, installs the tables of earlier families)."""
    _forced.append("generated")
    try:
        yield
    finally:
        _forced.pop()


def staged() -> bool:
    """Whether a staged generation is running (:func:`tables` is the innermost mode)."""
    return bool(_forced) and _forced[-1] == "generated"


_trace: list[list] = []


def note(kind: str, row: Any) -> None:
    """Record a row that fired (``kind`` ``"rule"`` or ``"identity"``) for the active :func:`tracing` block."""
    if _trace:
        _trace[-1].append((kind, row))


@contextmanager
def tracing() -> Iterator[list]:
    """Collect the rows that fire and the ``ask`` queries answered ``True`` inside the
    block: a list of ``("rule" | "identity", row)`` and ``("ask", proposition)`` entries
    (the derivation record of a generated rule)."""
    log: list = []
    _trace.append(log)
    inner = _upstream.ask

    def recording_ask(proposition: Any, assumptions: Any = True) -> Any:
        answer = inner(proposition, assumptions)
        if answer is True and _trace:
            _trace[-1].append(("ask", proposition))
        return answer
    _upstream.ask = recording_ask
    try:
        yield log
    finally:
        _upstream.ask = inner
        _trace.pop()


consulted: list[set] = []
"""A stack of key sets: the keys whose generated table the dispatcher looked up (a
staged generation depends on the other families' tables through these keys only)."""


live_keys: set = set()
"""Keys whose generated table is ignored even in generated mode: the keys of the
family being generated (:func:`._stages.generate`), which must not read the table it
is producing while every other key uses the tables installed so far."""


@contextmanager
def live_for(keys: Any) -> Iterator[None]:
    """Run ``keys`` on their identity rows inside the block, every other key as :func:`mode` says."""
    saved = set(live_keys)
    live_keys.update(keys)
    try:
        yield
    finally:
        live_keys.clear()
        live_keys.update(saved)


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

_results: list[dict] = []  # the result cache of the active top-level call

state: list = []
"""Engine state a result depends on besides the node and the assumptions (a
stack of hashable tokens: the identity handlers switched off while their
candidate is evaluated, a case split exploring); part of the cache key."""


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
        _results.append({})
        splits_left[0] = MAX_SPLITS
        saved_ask = _upstream.ask
        _upstream.ask = _memoized(saved_ask)
    try:
        return _refine(expr, assumptions)
    finally:
        if top:
            _firings.pop()
            _results.pop()
            _upstream.ask = saved_ask


def _refine(expr: Any, assumptions: Any) -> Any:
    """Refine ``expr``: one step per node (:func:`_step`) until a step asks for no
    further refinement; every node of the chain gets the final result in the cache.
    Iterative, so a chain of firings does not deepen the Python stack."""
    if not isinstance(expr, Basic):
        return expr
    cache = _results[-1] if _results else {}
    context = (assumptions, mode(), tuple(state), frozenset(live_keys))
    chain = []
    steps = 0
    while True:
        key = (expr, context)
        try:
            expr = cache[key]
            break
        except KeyError:
            chain.append(key)
        except TypeError:                        # unhashable assumptions
            pass
        expr, again = _step(expr, assumptions)
        if not again:
            break
        steps += 1
        if steps > MAX_FIRINGS:
            raise RefineLoopError(f"a rewrite chain exceeded {MAX_FIRINGS} steps; last result {expr}")
    for key in chain:
        cache[key] = expr
    return expr


def _step(expr: Basic, assumptions: Any) -> tuple[Any, bool]:
    """``(result, again)``: the node's children refined and its handler applied;
    ``again`` when the result is a new expression still to be refined."""
    name = expr.__class__.__name__
    if not expr.is_Atom and name not in own_args:
        args = [_refine(a, assumptions) for a in expr.args]
        try:
            new = expr.func(*args)
        except (ValueError, TypeError):          # a child became nan (inconsistent assumptions) and
            return expr, False                   # the head refuses it (Max: "nan is not comparable")
        if new.is_Atom or new.func is not expr.func or new.args != tuple(args):
            return (new, True) if new != expr else (expr, False)
        expr = new
    if hasattr(expr, "_eval_refine"):
        ref = expr._eval_refine(assumptions)
        if ref is not None:
            return ref, False
    handler = _upstream.handlers_dict.get(name)
    generated = None
    if mode() == "generated" and name not in live_keys:
        generated = generated_handlers.get(name)
        if consulted:
            consulted[-1].add(name)
    new = generated(expr, assumptions) if generated is not None else None
    if new is None or new == expr:
        if handler is None:
            return expr, False
        # the table is a fast path: when it declines, the live handler runs in full
        # (its rules and its identity rows, which the catalog specializes only in part)
        new = handler(expr, assumptions)
    else:
        handler = generated
    if new is None or new == expr:
        fallback = fallback_handlers.get(name)
        if fallback is None or fallback is handler:
            return expr, False
        new = fallback(expr, assumptions)
        if new is None or new == expr:
            return expr, False
    if not isinstance(new, Basic):
        tag = (name, getattr(handler, "__qualname__", repr(handler)))
        non_basic_returns[tag] = non_basic_returns.get(tag, 0) + 1
        new = sympify(new)
        if new == expr:
            return expr, False
    _firings[-1] += 1
    if _firings[-1] > MAX_TOTAL_FIRINGS:
        raise RefineLoopError(
            f"refine fired handlers more than {MAX_TOTAL_FIRINGS} times; last rewrite {expr} -> {new}")
    return new, isinstance(new, Expr)
