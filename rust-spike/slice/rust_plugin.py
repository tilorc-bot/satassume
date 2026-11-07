"""pytest -p rust_plugin: the suite with the Rust solver behind every name a test can get `Solver` by, the planner's
ruling for step 4 (issue 323). Needs rust-spike/slice on PYTHONPATH and `sa_solver.so` built. No satassume source changes.

`SV.Solver`, `engine.Solver` and `ref.Solver` become `Solver` below, before collection, so a test's own
`from satassume.sat.solver import Solver` gets it too, and `class X(Solver)` subclasses Rust.

`Solver` adds three things to the crate's class and nothing else:
- `_to_int` and `_to_ext`, Python's own static functions. They hold no state: `tests/` calls them on the class to write
  literals. They are not ported private attributes.
- `_n_conflicts`, read-only, from the crate's public `stats()`, whose "conflicts" is that same counter in Python. Two
  files read it after the search, to bound the search. A view of a public number, not a ported attribute.
- counts, and a log of writes to attributes the crate doesn't have. The class has a `__dict__`, so such a write
  succeeds and does nothing; a test that passes after one may have tested less than it says, so it is reported.

SLICE_SUITE_OUT=DIR: one JSON line per test per worker, written as each test ends, for suite_report.py.
SLICE_SUITE_BACKEND=python: load the same recording with no patch, for the baseline and the kept tests.
SLICE_SUITE_SHUFFLE=N: run the tests in a random order from seed N, the same on every xdist worker.
SLICE_SO=DIR: take sa_solver from DIR (a mutant).
SLICE_AUDIT_OFF=1: `tests/theory_harness.py`'s Recorder doesn't see the solver, so its audit of solver internals from
inside a hook is off and the rest of the test runs. Not part of the planner's numbers: see the results file.
SLICE_AUDIT_OFF=2: also no `check_protocol`, whose level checks need the hidden solver, so a test that stopped there goes
on to its answer comparisons. Both backends take the same patch.
"""
import json
import os
import sys
import weakref

import pytest

# Component 3's `P` on Rust: before the first import of satassume. SLICE_TRANSFER=py or SLICE_P=py keeps Python's.
if os.environ.get("SLICE_SUITE_BACKEND", "rust") == "rust" and os.environ.get("SLICE_TRANSFER") != "py":
    sys.path.insert(0, os.environ.get("SLICE_SO") or os.path.dirname(os.path.abspath(__file__)))
    import p_install
    p_install.install()

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
        _n_conflicts = property(lambda self: self.stats()["conflicts"])

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

    # EUF on Rust too, before collection, so a test's own `from ...euf import EUFTheory` gets it. SLICE_EUF=py keeps Python's.
    if os.environ.get("SLICE_EUF") != "py":
        import satassume.theories.euf.euf as _euf
        import satassume.theories.euf.euf_adapter as _euf_adapter

        class EUFTheory(sa_solver.EUFTheory):
            pass

        _euf.EUFTheory = _euf_adapter.EUFTheory = EUFTheory
    # Component 3 on Rust too, before collection, so a test's own `from ...transfer import TransferTheory` gets it.
    # SLICE_TRANSFER=py keeps Python's.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import backend as _backend
    _backend.install_transfer()

    # Before collection, so that a test module's `from ... import LRATheory` gets it. SLICE_LRA=python: solver only.
    if os.environ.get("SLICE_LRA", "rust") == "rust":
        import lra_backend
        lra_backend.install()

    # Component 4 slice A: the per-query table, the Kept route and a refusal reaching the top. SLICE_TERM=py keeps it off.
    import term_live
    term_live.from_env()

# Rust EUF on Python's solver: the tests whose harness reads Solver internals fail on the crate's solver before any EUF
# answer is read (the 77 and 46), so this is the only way they check the Rust EUF. SLICE_EUF=rust asks for it.
if BACKEND != "rust" and os.environ.get("SLICE_EUF") == "rust":
    sys.path.insert(0, os.environ.get("SLICE_SO") or os.path.dirname(os.path.abspath(__file__)))
    import sa_solver
    import satassume.theories.euf.euf as _euf
    import satassume.theories.euf.euf_adapter as _euf_adapter

    class EUFTheory(sa_solver.EUFTheory):
        pass

    _euf.EUFTheory = _euf_adapter.EUFTheory = EUFTheory

import catch_count   # noqa: E402 (on both backends: the row's `caught`, what the two `except Exception` sites got)
catch_count.install()

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


def pytest_unconfigure(config):
    """Component 4 slice A: `term_live`'s counts for this worker, so the suite reports refusals by reason and reads."""
    d, tl = os.environ.get("SLICE_SUITE_OUT"), sys.modules.get("term_live")
    if d and tl is not None:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"term.{os.getpid()}.json"), "w") as f:
            json.dump(tl.report(), f)


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
    lb = sys.modules.get("lra_backend")
    lra_before = dict(lb.counts) if lb else None
    private_writes.clear()
    os.environ["PROBE_TEST"] = item.nodeid      # probe_build.py's counters read it; nothing else does
    h = sys.modules.get("theory_harness") if os.environ.get("SLICE_AUDIT_OFF") else None
    if h and not isinstance(vars(h.Recorder).get("solver"), property):
        h.Recorder.solver = property(lambda self: None, lambda self, v: None)
    if h and os.environ["SLICE_AUDIT_OFF"] == "2":
        for m in (h, sys.modules.get("real_theory_fuzz"), getattr(item, "module", None)):
            if m is not None and hasattr(m, "check_protocol"):
                m.check_protocol = lambda rec, *a, **k: {}
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
            private_writes=sorted(private_writes),
            lra={k: v - lra_before[k] for k, v in lb.counts.items()} if lb else None,
            caught=catch_count.take())


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
