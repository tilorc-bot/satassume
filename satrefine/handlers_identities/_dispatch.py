"""The refine dispatcher for identity-based handlers.

This is the vendored driver (:func:`satrefine._upstream.refine`) with two
changes, and it replaces ``satrefine.refine`` whenever the
``handlers_identities`` package is selected (see the package ``__init__``):

* **re-refine after auto-evaluation.**  When a node is rebuilt from refined
  children, the constructor may auto-evaluate into a different structure
  (``im`` of a product becomes a sum of ``re``, ``im`` and ``arg`` terms).
  The vendored driver then dispatches on the new head without refining the
  children it just created; this one refines the rebuilt node again;
* **a termination guard** (see *Termination* below): handler results are
  re-refined until a fixed point, so two rules that undo each other loop
  forever in the vendored driver; here every top-level call terminates
  whatever ``ask`` answers;
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

Termination
-----------

A handler may fire whenever ``ask`` (or the engine's own reasoning on top of
it) says its condition holds.  Under inconsistent assumptions, or with an
``ask`` that answers a question and its negation both ``True``, two rows can
undo each other (``log(k) -> log(-k) + I*pi`` for ``k`` negative,
``log(-k) -> log(k) + I*pi`` for ``k`` positive: issue #10, B9).  When each
result puts the next firing one level deeper (a child of the ``Add``), every
firing is a new rewrite chain one Python stack level further down, so a
per-chain cap never trips and the call dies with Python's
``RecursionError``.  Within one top-level call the guard enforces three
limits, all counted on the call's :class:`_Call` record:

1. **nesting**: at most :data:`MAX_DEPTH` nested :func:`_refine` calls.
   Every recursion of the engine goes through :func:`_refine` (children in
   :func:`_step`; candidates, case splits and endpoint splits through
   :func:`refine`), so this bounds the stack the engine uses, far below
   Python's limit (the battery nests at most 25 deep);
2. **re-entry**: a node may not be refined again, under the same assumptions
   and engine state (the cache key), while its own refinement is still in
   progress.  A result depends only on that key (``ask`` is memoized per
   call), so a re-entry repeats the same computation below itself and can
   never finish; it is the B9 loop, caught at its second level, and the
   cycle ``X -> Y -> X`` inside one chain;
3. **work**: a chain of rewrites of one node is at most :data:`MAX_FIRINGS`
   steps, a call (not counting exploratory refinements) at most
   :data:`MAX_TOTAL_FIRINGS` firings, and the whole call, explorations
   included, at most :data:`MAX_CALL_FIRINGS`.

Argument: the calls of one top-level refine form a tree (a :func:`_refine`
calls :func:`_step`, which calls :func:`_refine` on children and handlers,
which call :func:`refine` on finitely many candidates).  Its depth is at most
:data:`MAX_DEPTH` (limit 1), and every handler firing counts against
:data:`MAX_CALL_FIRINGS` (limit 3), so the tree has finitely many firing
nodes; between two firings a :func:`_refine` does finitely much work (one
:func:`_step` refines finitely many children, each bounded the same way, and
a declining handler tries finitely many rows and bindings).  So every call
terminates, and its stack stays within :data:`MAX_DEPTH` levels whatever
``ask`` answers.  A Python ``RecursionError`` raised anyway (an input nested
deeper than the stack allows, a deep ``ask``) is handled like a tripped limit.

**When a limit trips** the guard raises :class:`RefineLoopError`, and every
later :func:`_refine` of the call raises it again at once (the call is
*poisoned*, so a handler that swallows the error cannot restart the work).
At the top level the outcome depends on :func:`strict`:

* by default ``refine`` returns its input unchanged and records the event
  in :data:`loop_events`.  That is always a correct refinement (refine
  promises an expression equal to the input under the assumptions), while a
  partly rewritten result would be only as good as the rows that looped, and
  a library call must not crash on assumptions the caller could not know
  were contradictory;
* with ``SATREFINE_STRICT_LOOPS=1`` (or inside :func:`strict_loops`) it
  raises :class:`RefineLoopError`, so a loop is a visible failure.  The test
  suite and the gate tools (scoreboard, differential) run strict: under
  consistent assumptions a trip is an engine bug (two rows undoing each
  other), and it must show up as a crash there, not as a quiet ``unchanged``.
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
"""Handler firings allowed in one top-level :func:`refine` call outside its explorations (a backstop)."""

MAX_CALL_FIRINGS = 4*MAX_TOTAL_FIRINGS
"""Handler firings allowed in one top-level call including its exploratory
refinements (:func:`exploring`), which otherwise count on their own: the
bound the termination argument rests on."""

MAX_DEPTH = 100
"""Nested :func:`_refine` calls allowed in one top-level call.  The battery
nests at most 25 deep (about 94 Python frames); a level costs 2 to 7 frames,
so 100 levels stay well inside Python's default limit of 1000."""

STRICT_ENV_VAR = "SATREFINE_STRICT_LOOPS"

loop_events: list = []
"""``(input, message)`` for every top-level call a guard stopped and that
returned its input unchanged (not strict); tools report it."""

_strict: list[bool] = []


def strict() -> bool:
    """Whether a tripped guard raises :class:`RefineLoopError` (rather than
    returning the input unchanged): :func:`strict_loops` or ``SATREFINE_STRICT_LOOPS=1``."""
    if _strict:
        return _strict[-1]
    return os.environ.get(STRICT_ENV_VAR, "") not in ("", "0")


@contextmanager
def strict_loops(on: bool = True) -> Iterator[None]:
    """Raise (``on``) or return the input unchanged (not ``on``) when a guard trips inside the block."""
    _strict.append(on)
    try:
        yield
    finally:
        _strict.pop()

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
    """A termination guard tripped (see *Termination* in the module docstring):
    too deep a nesting, a node re-entering its own refinement, or too many
    firings.  Raised by a top-level ``refine`` only when :func:`strict`."""


class _Call:
    """The guard state of one top-level call: the :func:`_refine` nesting depth,
    the cache keys being refined, the firings of the whole call, and the
    message of the guard that tripped (the call is poisoned from then on)."""
    __slots__ = ("active", "depth", "firings", "tripped")

    def __init__(self) -> None:
        self.depth = 0
        self.active: set = set()
        self.firings = 0
        self.tripped: str | None = None

    def trip(self, message: str) -> RefineLoopError:
        if self.tripped is None:
            self.tripped = message
        return RefineLoopError(self.tripped)


_calls: list[_Call] = []   # the guard of the active top-level call (one entry)

_firings: list[int] = []   # a stack entry per active top-level call and exploration

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

    For the duration of a top-level call ``_upstream.ask`` is memoized.  The
    call always terminates; when a termination guard trips it returns ``expr``
    unchanged, or raises :class:`RefineLoopError` if :func:`strict` (see
    *Termination* in the module docstring).  When ``ask`` raises on
    inconsistent assumptions (a ``ValueError`` saying so, as SymPy's backend
    does), ``expr`` is returned unchanged: every result is correct then, and
    how far the engine got before a query happened to expose the
    contradiction must not decide between a result and a crash.  Inside the
    call the error still propagates (a case split drops an inconsistent
    branch that way)."""
    if _calls:
        return _refine(expr, assumptions)
    call = _Call()
    _calls.append(call)
    _firings.append(0)
    _results.append({})
    splits_left[0] = MAX_SPLITS
    saved_ask = _upstream.ask
    _upstream.ask = _memoized(saved_ask)
    try:
        result = _refine(expr, assumptions)
    except RecursionError as error:          # RefineLoopError, or Python's own limit
        call.trip(f"{type(error).__name__}: {error}")
        cause: BaseException | None = error
    except ValueError as error:
        if "nconsistent" not in str(error):
            raise
        return expr                          # ask found the assumptions inconsistent: any result is
    else:                                    # correct, and refine does not raise for them (v3 does not)
        cause = None                         # a trip a handler swallowed still counts
    finally:
        _calls.pop()
        _firings.pop()
        _results.pop()
        _upstream.ask = saved_ask
    if call.tripped is None:
        return result
    if strict():
        raise RefineLoopError(call.tripped) from cause
    loop_events.append((expr, call.tripped))
    return expr


def _refine(expr: Any, assumptions: Any) -> Any:
    """Refine ``expr``: one step per node (:func:`_step`) until a step asks for no
    further refinement; every node of the chain gets the final result in the cache.
    Iterative, so a chain of firings does not deepen the Python stack."""
    if not isinstance(expr, Basic):
        return expr
    call = _calls[-1]
    if call.tripped is not None:
        raise RefineLoopError(call.tripped)
    if call.depth >= MAX_DEPTH:
        raise call.trip(f"refine nested more than {MAX_DEPTH} levels deep at {_short(expr)}")
    cache = _results[-1]
    active = call.active
    context = (assumptions, mode(), tuple(state), frozenset(live_keys))
    chain = []
    steps = 0
    call.depth += 1
    try:
        while True:
            key = (expr, context)
            try:
                expr = cache[key]
                break
            except KeyError:
                if key in active:
                    raise call.trip(f"{_short(expr)} re-entered its own refinement") from None
                chain.append(key)
                active.add(key)
            except TypeError:                        # unhashable assumptions
                pass
            expr, again = _step(expr, assumptions)
            if not again:
                break
            steps += 1
            if steps > MAX_FIRINGS:
                raise call.trip(f"a rewrite chain exceeded {MAX_FIRINGS} steps; last result {_short(expr)}")
    finally:
        call.depth -= 1
        for key in chain:
            active.discard(key)
    for key in chain:
        cache[key] = expr
    return expr


def _short(expr: Any) -> str:
    text = str(expr)
    return text if len(text) <= 200 else text[:200] + "..."


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
    call = _calls[-1]
    call.firings += 1
    if _firings[-1] > MAX_TOTAL_FIRINGS or call.firings > MAX_CALL_FIRINGS:
        raise call.trip(f"refine fired handlers more than {MAX_TOTAL_FIRINGS} times "
                        f"({MAX_CALL_FIRINGS} with explorations); last rewrite {_short(expr)} -> {_short(new)}")
    return new, isinstance(new, Expr)
