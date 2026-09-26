"""Worker plumbing: subprocess workers, per-case alarms, nested time limits, a forked task pool.

* :func:`run_json_worker` runs ``python -m <tool> ...`` in a fresh process
  (a handler package is fixed per process) and reads the JSON it writes;
* :func:`refine_case` refines one case under a per-case alarm
  (:class:`CaseTimeout`) and checks a rewrite, as a JSON-able record;
  ``NO_SWALLOW`` is the tuple of exceptions the checkers re-raise instead of
  counting a point as unevaluable, so a slow evaluation ends the case;
* :func:`timed`/:func:`attempt` are nested wall-clock limits (the tighter
  wins) raising :class:`Timeout`, a ``BaseException`` that SymPy's
  ``except Exception`` cannot swallow; :func:`install_timeouts` installs
  their signal handler;
* :func:`run_forked` runs one forked child per task, killing a child past a
  hard limit (``SIGALRM`` cannot interrupt long C-level computations);
* :func:`load_srepr` rebuilds an expression from the ``srepr`` a worker wrote.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class CaseTimeout(Exception):
    """The per-case alarm of :func:`refine_case` went off."""


NO_SWALLOW = (CaseTimeout,)


# ---------------------------------------------------------------------------
# JSON workers in a subprocess
# ---------------------------------------------------------------------------

def run_json_worker(module: str, args: list[str], out: str, env: dict | None = None, failure: str = "",
                    tail: int | None = None, cwd: Path | None = None) -> dict:
    """Run ``python -m module *args`` (which writes JSON to ``out``) and return the JSON.

    ``env`` is added to this process's environment, and the repository root to
    ``PYTHONPATH``.  On a non-zero exit (or no
    output) the worker's stderr (and, with ``tail``, the last ``tail``
    characters of its stdout and stderr) is written to stderr and the run
    ends with ``SystemExit(failure)``."""
    cmd = [sys.executable, "-m", module, *args]
    path = os.pathsep.join(p for p in (str(ROOT), os.environ.get("PYTHONPATH", "")) if p)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=cwd,
                          env=dict(os.environ, PYTHONPATH=path, **(env or {})))
    if proc.returncode != 0 or not os.path.exists(out):
        sys.stderr.write(proc.stderr if tail is None else proc.stdout[-tail:] + proc.stderr[-tail:])
        raise SystemExit(f"{failure} ({proc.returncode})")
    with open(out) as fh:
        return json.load(fh)


def _on_case_alarm(signum, frame):
    raise CaseTimeout


def install_case_alarm() -> None:
    signal.signal(signal.SIGALRM, _on_case_alarm)


def refine_case(e, assumptions, timeout: int, check) -> dict:
    """The record of refining ``e`` under ``assumptions`` within ``timeout`` seconds.

    ``status`` is "inconsistent", "unchanged", "fired", "timeout" or "crash"
    (with ``error``).  A rewrite ``r`` is recorded as ``result`` (srepr) and
    ``result_str``, and ``check(r, rec)`` returns (points checked,
    counterexample (point, input value, output value) or None); it may add
    fields to ``rec``.  A counterexample is recorded as ``unsound``.  A
    result that is not a SymPy object is recorded as ``nonbasic``.  Needs
    :func:`install_case_alarm`."""
    from sympy import Basic, srepr, sympify

    from satrefine import refine

    from .numeric import fmt
    rec: dict = {}
    signal.alarm(timeout)
    try:
        try:
            r = refine(e, assumptions)
            if not isinstance(r, Basic):
                rec["nonbasic"] = repr(r)
                r = sympify(r)
        except ValueError as ex:
            if "nconsistent" in str(ex):
                rec["status"] = "inconsistent"
                return rec
            raise
        if r == e:
            rec["status"] = "unchanged"
        else:
            rec["status"] = "fired"
            rec["result"] = srepr(r)
            rec["result_str"] = str(r)
            n_ok, ce = check(r, rec)
            rec["checked"] = n_ok
            if ce:
                pt, a, b = ce
                rec["unsound"] = {"point": {str(k): str(v).replace("\n", "") for k, v in pt.items()},
                                  "orig": fmt(a), "refined": fmt(b)}
    except CaseTimeout:
        rec["status"] = "timeout"
    except Exception as ex:  # noqa: BLE001 -- a crash is a finding, recorded
        rec["status"] = "crash"
        rec["error"] = f"{type(ex).__name__}: {str(ex)[:160]}"
    finally:
        signal.alarm(0)
    return rec


# ---------------------------------------------------------------------------
# nested wall-clock limits
# ---------------------------------------------------------------------------

class Timeout(BaseException):
    """BaseException, so SymPy's internal ``except Exception`` cannot swallow it."""


def _on_alarm(signum, frame):
    raise Timeout()


_DEADLINES: list[float] = []


def install_timeouts() -> None:
    signal.signal(signal.SIGALRM, _on_alarm)


def _arm():
    if _DEADLINES:
        left = max(min(_DEADLINES) - time.monotonic(), 0.001)
        # keep re-firing once expired, in case library code swallows one signal
        signal.setitimer(signal.ITIMER_REAL, left, 0.5)
    else:
        signal.setitimer(signal.ITIMER_REAL, 0)


def timed(fn, secs, *a, **kw):
    """Run fn with a wall-clock limit; nested limits are honoured (the tighter wins).

    A Timeout propagates out of this frame only when this frame's own deadline
    has passed or an outer one has; it is raised as ``Timeout``.
    """
    deadline = time.monotonic() + secs
    _DEADLINES.append(deadline)
    _arm()
    try:
        return fn(*a, **kw)
    finally:
        _DEADLINES.remove(deadline)
        _arm()


def outer_expired():
    now = time.monotonic()
    return any(d <= now for d in _DEADLINES)


def attempt(fn, secs, *a, **kw):
    """(value, None) or (None, error string); an outer deadline is re-raised."""
    try:
        return timed(fn, secs, *a, **kw), None
    except Timeout:
        if outer_expired():
            raise
        return None, "timeout"
    except RecursionError:
        return None, "RecursionError"
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"[:200]


# ---------------------------------------------------------------------------
# forked task pool
# ---------------------------------------------------------------------------

def _child(task, conn, fn, on_error):
    try:
        res = fn(task)
    except BaseException as e:  # noqa: BLE001
        res = on_error(task, e)
    try:
        conn.send(res)
    finally:
        conn.close()
    os._exit(0)


def run_forked(tasks, jobs, fn, label, hard_timeout, on_timeout, on_error):
    """Run fn(task) (a list of records) in one forked child per task; kill children past hard_timeout.

    ``on_timeout(task, why)`` gives the records of a killed or dead child,
    ``on_error(task, exception)`` those of a task that raised.  SIGALRM cannot
    interrupt long C-level computations (big-integer arithmetic), so a
    wall-clock kill from the parent is the only reliable guard against a
    stuck case.
    """
    import multiprocessing as mp
    from multiprocessing.connection import wait
    ctx = mp.get_context("fork")
    pending = list(tasks)
    pending.reverse()
    running = {}
    out = []
    done = 0
    start = time.time()
    while pending or running:
        while pending and len(running) < jobs:
            task = pending.pop()
            r, w = ctx.Pipe(duplex=False)
            proc = ctx.Process(target=_child, args=(task, w, fn, on_error))
            proc.start()
            w.close()
            running[r] = (proc, time.time(), task)
        ready = wait(list(running), timeout=1.0)
        for conn in ready:
            proc, t0, task = running.pop(conn)
            try:
                out.extend(conn.recv())
            except (EOFError, OSError):
                out.extend(on_timeout(task, "child died"))
            conn.close()
            proc.join()
            done += 1
        now = time.time()
        for conn, (proc, t0, task) in list(running.items()):
            if now - t0 > hard_timeout:
                proc.kill()
                proc.join()
                conn.close()
                running.pop(conn)
                out.extend(on_timeout(task, f"hard timeout {hard_timeout}s"))
                done += 1
        if ready and (done % 25 == 0 or not (pending or running)):
            print(f"  [{label}] {done}/{len(tasks)} tasks, {len(out)} records, "
                  f"{time.time() - start:.0f}s", file=sys.stderr, flush=True)
    return out


# ---------------------------------------------------------------------------
# srepr round trip
# ---------------------------------------------------------------------------

_NS = None


def srepr_namespace() -> dict:
    """The names ``srepr`` output uses: SymPy's, the matrix expressions and a few classes it does not export."""
    global _NS
    if _NS is None:
        import sympy
        import sympy.matrices.expressions as mexpr
        from sympy.assumptions.relation.binrel import AppliedBinaryRelation
        from sympy.calculus.accumulationbounds import AccumulationBounds
        from sympy.core.symbol import Str
        from sympy.functions.elementary.piecewise import ExprCondPair
        from sympy.matrices.expressions.matexpr import MatrixElement
        ns = {k: getattr(sympy, k) for k in dir(sympy) if not k.startswith("_")}
        ns.update(AppliedBinaryRelation=AppliedBinaryRelation, Str=Str)
        ns.update(ExprCondPair=ExprCondPair, AccumulationBounds=AccumulationBounds)
        ns.update({k: getattr(mexpr, k) for k in dir(mexpr) if not k.startswith("_")}, MatrixElement=MatrixElement)
        _NS = ns
    return _NS


def load_srepr(s: str):
    """The expression whose ``srepr`` is ``s``: evaluated, or built with ``evaluate(False)``
    when only that reproduces ``s``."""
    from sympy import srepr
    from sympy.core.parameters import evaluate
    ns = srepr_namespace()
    v = eval(s, dict(ns))
    if srepr(v) != s:
        with evaluate(False):
            w = eval(s, dict(ns))
        if srepr(w) == s:
            v = w
    return v
