"""pytest -p knowledge_suite (with -p handler_count, after -p rust_plugin): the atoms family in the suite, per worker.

SLICE_KNOWLEDGE=atoms installs `knowledge_live` before collection, =shadow with its field comparison; unset, it's a recording-only run for the same comparison.
At session end, each worker plants one raise at each call in the two tries, so its handler rows are from a counter shown to
fire in that process (`where` = plant:<site>), and writes knowledge.PID.json with COUNTS and the plant result. No test is added,
so the suite's numbers stay comparable. In its own plugin so `rust_plugin.py`, a shared file, needn't change.
"""
import json
import os
import sys

sys.path.insert(0, os.environ.get("SLICE_SO") or os.path.dirname(os.path.abspath(__file__)))
K = None


def pytest_configure(config):
    global K
    if os.environ.get("SLICE_KNOWLEDGE") in ("atoms", "shadow"):
        import knowledge_live as K
        K.install(shadow=os.environ["SLICE_KNOWLEDGE"] == "shadow")


def pytest_sessionfinish(session, exitstatus):
    import handler_count as H
    import knowledge_quiet
    from satassume.engine import Engine
    from satassume import sympy_api
    out = dict(pid=os.getpid(), mode=os.environ.get("SLICE_KNOWLEDGE") or "off")
    H.where = "sessionfinish"
    if H._out is None:
        out["plants"] = "handler_count not installed"
    else:
        out["plants"] = knowledge_quiet.plant_check(H)
    out["counts"] = dict(K.COUNTS) if K else {}
    if K:
        import sa_solver
        out.update(so=sa_solver.__file__, mismatches=K.MISMATCHES, order_diffs=K.ORDER_DIFFS)
    with open(os.path.join(os.environ["SLICE_SUITE_OUT"], f"knowledge.{os.getpid()}.json"), "w") as fh:
        json.dump(out, fh, indent=1)
