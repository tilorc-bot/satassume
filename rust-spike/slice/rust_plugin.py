"""pytest -p rust_plugin: the suite with the Rust solver behind every name a test can get `Solver` by, the planner's
ruling for step 4 (issue 323). Needs rust-spike/slice on PYTHONPATH and `sa_solver.so` built. No satassume source changes.

`SV.Solver`, `engine.Solver` and `ref.Solver` become `Solver` below, before collection, so a test's own
`from satassume.sat.solver import Solver` gets it too, and `class X(Solver)` subclasses Rust.

`Solver` adds two things to the crate's class and nothing else:
- `_to_int` and `_to_ext`, Python's own static functions. They hold no state: `tests/` calls them on the class to write
  literals. They are not ported private attributes.
- counts, and a log of writes to attributes the crate doesn't have. The class has a `__dict__`, so such a write
  succeeds and does nothing; a test that passes after one may have tested less than it says, so it is reported.

SLICE_SUITE_OUT=DIR: one JSON line per test per worker, written as each test ends, for suite_report.py.
SLICE_SUITE_BACKEND=python: load the same recording with no patch, for the baseline and the kept tests.
SLICE_SUITE_SHUFFLE=N: run the tests in a random order from seed N, the same on every xdist worker.
SLICE_SO=DIR: take sa_solver from DIR (a mutant).
"""
import json
import os
import sys
import weakref

import pytest

import satassume.engine as _engine
import satassume.ref as _ref
import satassume.sat.solver as SV

PySolver = SV.Solver
BACKEND = os.environ.get("SLICE_SUITE_BACKEND", "rust")
counts = dict(rust_made=0, rust_gone=0, py_made=0)
private_writes = set()


def _gone():
    counts["rust_gone"] += 1


if BACKEND == "rust":
    sys.path.insert(0, os.environ.get("SLICE_SO") or os.path.dirname(os.path.abspath(__file__)))
    import sa_solver

    class Solver(sa_solver.Solver):
        _to_int = staticmethod(PySolver._to_int)
        _to_ext = staticmethod(PySolver._to_ext)

        def __new__(cls, *args, **kwargs):
            s = super().__new__(cls)
            counts["rust_made"] += 1
            weakref.finalize(s, _gone).atexit = False
            return s

        def __setattr__(self, name, value):
            if not hasattr(sa_solver.Solver, name) and name.startswith("_"):
                private_writes.add(name)
            super().__setattr__(name, value)

    SV.Solver = _engine.Solver = _ref.Solver = Solver
else:
    _init = PySolver.__init__

    def _counted(self, *args, **kwargs):
        counts["py_made"] += 1
        _init(self, *args, **kwargs)

    PySolver.__init__ = _counted

_out = None


def _record(**row):
    global _out
    d = os.environ.get("SLICE_SUITE_OUT")
    if not d:
        return
    if _out is None:
        os.makedirs(d, exist_ok=True)
        _out = open(os.path.join(d, f"rows.{os.getpid()}.jsonl"), "a", buffering=1)
    _out.write(json.dumps(row) + "\n")


def _failure(rep):
    """What the report says of a failure, split so suite_report.py doesn't have to parse a traceback."""
    if not rep.failed:
        return None
    crash = getattr(rep.longrepr, "reprcrash", None)
    return dict(when=rep.when, crash=crash.message[:2000] if crash else str(rep.longrepr)[:2000],
                where=f"{crash.path}:{crash.lineno}" if crash else None, text=str(rep.longrepr)[-6000:])


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    before = dict(counts)
    private_writes.clear()
    reports = []
    item._slice_reports = reports
    yield
    outcome, fail = "passed", None
    for r in reports:
        if r.failed:
            outcome, fail = "failed", fail or _failure(r)
        elif r.skipped and outcome == "passed":
            # xfail is reported as a skip with `wasxfail`
            outcome = "xfailed" if hasattr(r, "wasxfail") else "skipped"
        elif r.passed and hasattr(r, "wasxfail"):
            outcome = "xpassed"
    _record(id=item.nodeid, backend=BACKEND, outcome=outcome, failure=fail,
            rust_made=counts["rust_made"] - before["rust_made"], py_made=counts["py_made"] - before["py_made"],
            private_writes=sorted(private_writes))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    o = yield
    item._slice_reports.append(o.get_result())


def pytest_collection_modifyitems(config, items):
    seed = os.environ.get("SLICE_SUITE_SHUFFLE")
    if seed:
        import random
        items.sort(key=lambda it: it.nodeid)
        random.Random(int(seed)).shuffle(items)


def pytest_collectreport(report):
    if report.failed:
        _record(id=report.nodeid, backend=BACKEND, outcome="collect-error", rust_made=0, py_made=0, private_writes=[],
                failure=dict(when="collect", crash=str(report.longrepr)[-2000:], where=None, text=str(report.longrepr)[-6000:]))
