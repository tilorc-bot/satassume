"""Termination of the identities engine whatever ``ask`` answers (issue #10, B9).

The dispatcher's guard (``_dispatch``, *Termination*) promises that every
top-level ``refine`` returns, with no Python ``RecursionError``, for any
``ask``: consistent, contradictory or adversarial.  The documented outcomes
of a call are:

* a result (with ``SATREFINE_STRICT_LOOPS`` off, a tripped guard returns the
  input unchanged and records it in ``_dispatch.loop_events``);
* :class:`RefineLoopError` when a guard trips and :func:`_dispatch.strict`;
* never an error from ``ask`` finding the assumptions inconsistent (SymPy's
  backend raises ``ValueError`` for some): refine returns its input then.

The property test runs the engine, in both identity modes, against
adversarial oracles over a sample of the battery and of the differential's
random cases, and checks those outcomes and a time bound per call.  It is
small by default (a few seconds); ``SATREFINE_TERMINATION_FUZZ=N`` runs N
random cases per oracle and the whole battery instead, for manual runs::

    SATREFINE_TERMINATION_FUZZ=1500 pytest tests/refine_identities/test_engine_termination.py
"""
from __future__ import annotations

import os
import random
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from sympy import Function, Q, Symbol, factorial, log, pi

from satrefine import refine
from satrefine.identities.compat import upstream as _upstream
from satrefine.identities.core import driver as _dispatch
from satrefine.identities.core.driver import RefineLoopError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

LARGE = int(os.environ.get("SATREFINE_TERMINATION_FUZZ", "0"))
CALL_SECONDS = 60 if LARGE else 20
"""The time bound of one call (far above any call's cost: a loop that the
guard does not stop shows up as a timeout, not as a slow test)."""

k = Symbol("k")
MODES = {"generated": _dispatch.tables, "live": _dispatch.live}


# ---------------------------------------------------------------------------
# oracles: functions (proposition, assumptions) -> True | False | None
# ---------------------------------------------------------------------------

def _none(proposition, assumptions):
    return None


def _true(proposition, assumptions):
    return True


def _random(seed):
    def oracle(proposition, assumptions):
        return random.Random(f"{seed}|{proposition}").choice((True, False, None))
    return oracle


def _both(real):
    """The real answer, except that a refuted proposition is proved: ``P`` and
    ``~P`` (``Q.positive(x)`` and ``Q.nonpositive(x)``) are both ``True``."""
    def oracle(proposition, assumptions):
        answer = real(proposition, assumptions)
        return True if answer is False else answer
    return oracle


def oracles(real):
    return {"none": _none, "true": _true, "random": _random(0), "both": _both(real), "real": real}


def _contradicted(expr, assumptions, n):
    """``assumptions`` with contradictory sign facts on a free symbol of ``expr``:
    stated signs, stated bounds, or a stated sign against a stated bound (B9)."""
    syms = sorted((s for s in expr.free_symbols if isinstance(s, Symbol)), key=str)   # not matrices
    if not syms:
        return assumptions
    s = syms[n % len(syms)]
    extra = (Q.positive(s) & Q.negative(s), Q.gt(s, 1) & Q.lt(s, -1), Q.negative(s) & Q.gt(s, pi/2),
             Q.nonnegative(s) & Q.lt(s, -3))[n % 4]
    return assumptions & extra


# ---------------------------------------------------------------------------
# the property
# ---------------------------------------------------------------------------

class _Timeout(Exception):
    pass


@contextmanager
def _deadline(seconds):
    def on_alarm(signum, frame):
        raise _Timeout
    previous = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


@contextmanager
def _oracle(ask):
    saved = _upstream.ask
    _upstream.ask = ask
    try:
        yield
    finally:
        _upstream.ask = saved


def outcome(expr, assumptions, ask, mode, strict):
    """``"ok"``, ``"loop"`` (a guard tripped) or a failure message."""
    events = len(_dispatch.loop_events)
    t0 = time.perf_counter()
    try:
        with _deadline(CALL_SECONDS), _oracle(ask), MODES[mode](), _dispatch.strict_loops(strict):
            refine(expr, assumptions)
    except RefineLoopError:
        return "loop" if strict else "RefineLoopError raised although not strict"
    except _Timeout:
        return f"no result in {CALL_SECONDS} s"
    except ValueError as error:
        return f"ValueError: {error}"
    except Exception as error:  # noqa: BLE001 -- anything else is a failure, reported
        return f"{type(error).__name__}: {str(error)[:200]}"
    if time.perf_counter() - t0 > CALL_SECONDS:
        return "too slow"
    return "loop" if len(_dispatch.loop_events) > events else "ok"


def _battery_sample():
    from battery_v3 import BATTERY
    step = 1 if LARGE else 97
    return [(e, a) for e, a, _expected, _source in BATTERY[::step]]


def _random_cases(n):
    """``n`` differential cases, taken in turn from seeds 2, 3 and 7."""
    from satrefine.tools.refine_differential import generate
    out, case = [], 0
    while len(out) < n:
        for seed in (2, 3, 7):
            g = generate(seed, case)
            if g is not None and len(out) < n:
                out.append((g[1], g[2]))
        case += 1
    return out


def _cases():
    return _battery_sample() + _random_cases(LARGE or 12)


def run(cases, modes=("generated", "live"), strict_every=3):
    """Every case under every oracle and mode; also under contradicted assumptions
    with the ``none`` and real oracles.  Returns (counts, failures)."""
    real = _upstream.ask
    counts: dict = {}
    failures = []
    for i, (expr, assumptions) in enumerate(cases):
        for mode in modes:
            runs = [(name, ask, assumptions) for name, ask in oracles(real).items()]
            bad = _contradicted(expr, assumptions, i)
            runs += [("none+contradiction", _none, bad), ("real+contradiction", real, bad)]
            for name, ask, facts in runs:
                strict = i % strict_every == 0
                result = outcome(expr, facts, ask, mode, strict)
                documented = result in ("ok", "loop")
                tag = (name, result if documented else "fail")
                counts[tag] = counts.get(tag, 0) + 1
                if not documented:
                    failures.append((name, mode, strict, expr, facts, result))
    return counts, failures


def test_refine_terminates_under_adversarial_oracles():
    counts, failures = run(_cases())
    if LARGE:
        print(f"\ntermination fuzz: {counts}")
    assert not failures, "\n".join(map(str, failures[:10]))


# ---------------------------------------------------------------------------
# B9 and the guard itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", sorted(MODES))
def test_b9_contradictory_signs_with_an_undecided_ask(mode):
    # satassume answers None to both signs of k; the stated bounds are empty and prove nothing
    with _oracle(_none), MODES[mode](), _dispatch.strict_loops():
        assert refine(factorial(log(k)), Q.negative(k) & Q.gt(k, pi/2)) == factorial(log(k))


def test_b9_with_the_satassume_backend():
    code = ("from sympy import *\nfrom satrefine import refine\nfrom satrefine.identities.core import driver as _dispatch\n"
            "k = Symbol('k')\nfor mode in (_dispatch.tables, _dispatch.live):\n"
            "    with mode():\n        print(refine(factorial(log(k)), Q.negative(k) & Q.gt(k, pi/2)))\n")
    env = dict(os.environ, SATREFINE_BACKEND="satassume", SATREFINE_HANDLERS="handlers_identities",
               SATREFINE_STRICT_LOOPS="1", PYTHONPATH=os.pathsep.join(sys.path))
    out = subprocess.run([sys.executable, "-c", code], env=env, cwd=ROOT, capture_output=True, text=True, timeout=300, check=False)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.split() == ["factorial(log(k))"] * 2


class Swing(Function):
    """``Swing(x) -> Swing(-x) + 1``: each result nests the next firing one level
    deeper, as the B9 rows do, whatever the argument."""


class Deeper(Function):
    """``Deeper(x) -> Deeper(x + 1) + 1``: a new node at every level (no re-entry),
    so only the nesting limit stops it."""


@contextmanager
def _handlers(**handlers):
    _upstream.handlers_dict.update(handlers)
    try:
        yield
    finally:
        for key in handlers:
            del _upstream.handlers_dict[key]


def test_reentry_trips_at_once():
    x = Symbol("x")
    with _handlers(Swing=lambda e, a: Swing(-e.args[0]) + 1):
        with _dispatch.strict_loops(), pytest.raises(RefineLoopError, match="re-entered"):
            refine(Swing(x))
        before = len(_dispatch.loop_events)
        with _dispatch.strict_loops(False):
            assert refine(Swing(x)) == Swing(x)          # the input, unchanged
        assert len(_dispatch.loop_events) == before + 1


def test_nesting_limit_trips_below_the_python_limit():
    x = Symbol("x")
    with _handlers(Deeper=lambda e, a: Deeper(e.args[0] + 1) + 1):
        with _dispatch.strict_loops(), pytest.raises(RefineLoopError, match=f"nested more than {_dispatch.MAX_DEPTH}"):
            refine(Deeper(x))
        with _dispatch.strict_loops(False):
            assert refine(Deeper(x)) == Deeper(x)
        # Python's own limit first (a call starting with little stack left): handled the same way
        limit = sys.getrecursionlimit()
        sys.setrecursionlimit(len(_frames()) + _dispatch.MAX_DEPTH)
        try:
            with _dispatch.strict_loops(False):
                assert refine(Deeper(x)) == Deeper(x)
        finally:
            sys.setrecursionlimit(limit)


def _frames():
    f, out = sys._getframe(), []
    while f:
        out.append(f)
        f = f.f_back
    return out


def test_a_swallowed_trip_still_counts():
    x = Symbol("x")

    def swallowing(e, a):
        try:
            return refine(Swing(-e.args[0]), a) + 1
        except RefineLoopError:
            return x                                  # carries on as if nothing happened
    with _handlers(Swing=swallowing):
        with _dispatch.strict_loops(), pytest.raises(RefineLoopError):
            refine(Swing(x))
        with _dispatch.strict_loops(False):
            assert refine(Swing(x) + 2) == Swing(x) + 2


def test_the_guard_leaves_no_state_behind():
    x = Symbol("x")
    with _handlers(Swing=lambda e, a: Swing(-e.args[0]) + 1), _dispatch.strict_loops(False):
        refine(Swing(x))
    assert not _dispatch._calls and not _dispatch._firings and not _dispatch._results
    assert refine(abs(x), Q.positive(x)) == x
