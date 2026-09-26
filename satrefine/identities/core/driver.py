"""The refine dispatcher for identity-based handlers.

This is the vendored driver (:func:`satrefine.identities.compat.upstream.refine`) with two
changes, and it replaces ``satrefine.refine`` whenever the
``handlers_identities`` package is selected (see :func:`satrefine.identities.load`):

* **re-refine after auto-evaluation.**  When a node is rebuilt from refined
  children, the constructor may auto-evaluate into a different structure
  (``im`` of a product becomes a sum of ``re``, ``im`` and ``arg`` terms).
  The vendored driver then dispatches on the new head without refining the
  children it just created; this one refines the rebuilt node again;
* **a termination guard** (:mod:`.guard`, *Termination*): handler results are
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

``upstream.refine`` itself is untouched (it must stay behavior-identical
to SymPy's); handlers written for the vendored driver keep working here.

What other code plugs in (the SymPy workarounds, the simple rules'
fallbacks, an observer while a table is generated) is in :mod:`.hooks`;
:func:`observing` pushes an observer.
"""
from __future__ import annotations

from typing import Any

from sympy.core import Basic, Expr

from .. import config
from . import hooks
from .guard import (MAX_CALL_FIRINGS, MAX_DEPTH, MAX_FIRINGS, MAX_TOTAL_FIRINGS, RefineLoopError,  # noqa: F401
                    _Call, _short, loop_events, pushed, strict, strict_loops)

MAX_SPLITS = 8
"""Case splits (:func:`.split.case_split`) tried in one top-level call: each
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

_forced: list[str] = []


def mode() -> str:
    """``"generated"`` (default) or ``"live"``, from ``SATREFINE_IDENTITIES`` unless :func:`live` is active."""
    if _forced:
        return _forced[-1]
    return config.env_mode()


def live() -> Any:
    """Run the identity rows rather than the generated tables inside the block
    (generation itself must never read the tables it is producing)."""
    return pushed(_forced, "live")


def tables() -> Any:
    """Use the generated tables inside the block whatever ``SATREFINE_IDENTITIES`` says."""
    return pushed(_forced, "generated")


def observing(on_fire: Any = None, tables: Any = None) -> Any:
    """Push an observer (:data:`.hooks.observer`) for the block: ``on_fire(kind, row)``
    is called on each table-row firing, ``tables(key)`` gives the generated table used
    for ``key`` (``None``: none) whatever the mode.  What is not given is inherited
    from the enclosing observer."""
    outer = hooks.observer[-1] if hooks.observer else None
    if outer is not None:
        on_fire = outer.on_fire if on_fire is None else on_fire
        tables = outer.tables if tables is None else tables
    return pushed(hooks.observer, hooks.Observer(on_fire, tables))


def exploring() -> Any:
    """Run the engine's exploratory refinements (case and endpoint splits) under
    a firing counter of their own: each is bounded by :data:`MAX_FIRINGS` by
    itself and must not exhaust the cap of the call that tries them."""
    return pushed(_firings, 0)


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

    For the duration of a top-level call the dispatcher's ``ask`` is memoized.  The
    call always terminates; when a termination guard trips it returns ``expr``
    unchanged, or raises :class:`RefineLoopError` if :func:`strict` (see
    *Termination* in :mod:`.guard`).  When ``ask`` raises on
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
    saved_ask = hooks.dispatcher.ask
    hooks.dispatcher.ask = _memoized(saved_ask)
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
        hooks.dispatcher.ask = saved_ask
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
    context = (assumptions, mode(), tuple(state), hooks.observer[-1].tables if hooks.observer else None)
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


def _step(expr: Basic, assumptions: Any) -> tuple[Any, bool]:
    """``(result, again)``: the node's children refined and its handler applied;
    ``again`` when the result is a new expression still to be refined."""
    name = expr.__class__.__name__
    if not expr.is_Atom and name not in hooks.own_args:
        args = [_refine(a, assumptions) for a in expr.args]
        try:
            new = hooks.rebuild(expr.func, args, assumptions)   # acot/acoth keep their value at 0 (B8)
        except (ValueError, TypeError):          # a child became nan (inconsistent assumptions) and
            return expr, False                   # the head refuses it (Max: "nan is not comparable")
        if new.is_Atom or new.func is not expr.func or new.args != tuple(args):
            return (new, True) if new != expr else (expr, False)
        expr = new
    own = hooks.eval_refine.get(getattr(type(expr), "_eval_refine", None))
    if own is not None or hasattr(expr, "_eval_refine"):
        ref = own(expr, assumptions) if own is not None else expr._eval_refine(assumptions)
        if ref is not None:
            return ref, False
    handler = hooks.dispatcher.handlers_dict.get(name)
    if hooks.observer and hooks.observer[-1].tables is not None:
        generated = hooks.observer[-1].tables(name)
    else:
        generated = generated_handlers.get(name) if mode() == "generated" else None
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
        fallback = hooks.fallback.get(name)
        if fallback is None or fallback is handler:
            return expr, False
        new = fallback(expr, assumptions)
        if new is None or new == expr:
            return expr, False
    _firings[-1] += 1
    call = _calls[-1]
    call.firings += 1
    if _firings[-1] > MAX_TOTAL_FIRINGS or call.firings > MAX_CALL_FIRINGS:
        raise call.trip(f"refine fired handlers more than {MAX_TOTAL_FIRINGS} times "
                        f"({MAX_CALL_FIRINGS} with explorations); last rewrite {_short(expr)} -> {_short(new)}")
    return new, isinstance(new, Expr)
