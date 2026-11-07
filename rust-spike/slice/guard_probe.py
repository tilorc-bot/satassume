"""guard_probe: pytest plugin for one question about one Hypothesis test: when test_lra's whole-test 120 s guard fires, what was running?

SLICE_GUARD_OUT=FILE gets a JSON summary: every example's outcome, when the first failure came, the longest single example, and the
guard's firing time and stack. SLICE_GUARD_INJECT=1 makes Recorder.check raise at its entry once it has a solver, where the borrow error
raises on Rust, as a control on pure Python. Diagnostic only: times are wall clock on a shared
machine and aren't timing results.
"""
import json
import os
import sys
import time
import traceback

import pytest

OUT = os.environ.get("SLICE_GUARD_OUT")
INJECT = os.environ.get("SLICE_GUARD_INJECT") == "1"
state = {"t0": None, "calls": [], "alarm": None}


def _now():
    return round(time.monotonic() - state["t0"], 3) if state["t0"] is not None else None


def pytest_collection_modifyitems(items):
    tl = sys.modules.get("test_lra")
    if tl is not None:
        fire = tl.deadline._fire

        def _fire(self, *a):
            frames = traceback.extract_stack()[:-1]
            state["alarm"] = {"at": _now(), "seconds": self.seconds, "calls_done": len(state["calls"]),
                              "stack": [f"{os.path.basename(f.filename)}:{f.lineno}:{f.name}" for f in frames[-12:]],
                              "paths": sorted({f.filename.split("/site-packages/")[-1].split("/")[0] for f in frames})}
            return fire(self, *a)
        tl.deadline._fire = _fire
    th = sys.modules.get("theory_harness")
    if INJECT and th is not None:
        check = th.Recorder.check

        def checked(self, *a, **k):
            if self.solver is not None:
                raise RuntimeError("injected: same place as the borrow error")
            return check(self, *a, **k)
        th.Recorder.check = checked


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    state["t0"] = time.monotonic()      # before the autouse guard starts
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    hyp = getattr(item.obj, "hypothesis", None)
    if hyp is not None:
        inner = hyp.inner_test

        def wrapped(*a, **k):
            start = _now()
            exc = None
            try:
                return inner(*a, **k)
            except BaseException as e:
                exc = type(e).__name__
                raise
            finally:
                state["calls"].append((start, round(_now() - start, 3), exc))
        hyp.inner_test = wrapped
    outcome = yield
    calls = state["calls"]
    fail = [i for i, c in enumerate(calls) if c[2] and c[2] not in ("UnsatisfiedAssumption", "StopTest")]
    kinds = {}
    for c in calls:
        kinds[c[2] or "ok"] = kinds.get(c[2] or "ok", 0) + 1
    summary = {"test": item.nodeid, "total": _now(), "examples": len(calls), "kinds": kinds,
               "first_failure_index": fail[0] if fail else None, "first_failure_at": calls[fail[0]][0] if fail else None,
               "examples_after_first_failure": len(calls) - fail[0] - 1 if fail else 0,
               "longest_example": max((c[1] for c in calls), default=None), "alarm": state["alarm"],
               "outcome": "failed" if outcome.excinfo else "passed",
               "error": repr(outcome.excinfo[1])[:200] if outcome.excinfo else None}
    if OUT:
        with open(OUT, "w") as f:
            json.dump(summary, f, indent=1)
