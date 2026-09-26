"""The termination guard of the driver (:mod:`.driver`).

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

from contextlib import contextmanager
from typing import Any, Iterator

from .. import config

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

loop_events: list = []
"""``(input, message)`` for every top-level call a guard stopped and that
returned its input unchanged (not strict); tools report it."""

_strict: list[bool] = []


def strict() -> bool:
    """Whether a tripped guard raises :class:`RefineLoopError` (rather than
    returning the input unchanged): :func:`strict_loops` or ``SATREFINE_STRICT_LOOPS=1``."""
    if _strict:
        return _strict[-1]
    return config.env_strict()


@contextmanager
def strict_loops(on: bool = True) -> Iterator[None]:
    """Raise (``on``) or return the input unchanged (not ``on``) when a guard trips inside the block."""
    _strict.append(on)
    try:
        yield
    finally:
        _strict.pop()


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


def _short(expr: Any) -> str:
    text = str(expr)
    return text if len(text) <= 200 else text[:200] + "..."
