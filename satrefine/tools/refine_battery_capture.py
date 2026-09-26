"""pytest plugin: record every outermost ``refine`` / ``handlers_v3`` handler call.

Used to build ``tests/refine_identities/battery_v3.py``.  Run one v3 test
file at a time with this plugin and ``CAPTURE_OUT`` naming the JSON output::

    for f in trig hyperbolic inverse power_exp_log complex_parts integer_funcs \
             combinatorial minmax_deltas matrices; do
        CAPTURE_OUT=/tmp/cap/$f.json SATREFINE_HANDLERS=handlers_v3 \
        PYTHONPATH=.:/path/to/sympy python -m pytest -q -p no:cacheprovider \
            -p satrefine.tools.refine_battery_capture tests/refine_v3/test_$f.py
    done

then ``python -m satrefine.tools.refine_battery_generate /tmp/cap tests/refine_identities/battery_v3.py``.
Each record carries the test node id, the call (``refine`` or the handler's
name), srepr of the arguments and result, and whether ``ask`` was patched.
"""
import functools
import json
import os
import sys
import types

if __name__ == "__main__":                   # a pytest plugin (-p), not a command
    print(__doc__)
    sys.exit(0)

os.environ["SATREFINE_HANDLERS"] = "handlers_v3"
import importlib
import pkgutil

import pytest
from sympy import Basic, srepr

import satrefine
import satrefine.handlers_v3 as pkg
from satrefine.identities.compat import upstream as _upstream

ORIG_REFINE = _upstream.refine
ORIG_ASK = _upstream.ask
OUT = os.environ["CAPTURE_OUT"]
RECORDS = []
STATE = {"depth": 0, "nodeid": None}


def _s(v):
    try:
        return srepr(v)
    except Exception as e:  # noqa
        return "<unsrepr %r>" % (v,)


def _record(kind, expr, assumptions, fn, args, kwargs):
    if STATE["depth"] > 0:
        return fn(*args, **kwargs)
    STATE["depth"] += 1
    rec = {"nodeid": STATE["nodeid"], "kind": kind, "expr": _s(expr), "assumptions": _s(assumptions),
           "ask_patched": _upstream.ask is not ORIG_ASK,
           "ask_name": getattr(_upstream.ask, "__name__", repr(_upstream.ask)),
           "expr_is_basic": isinstance(expr, Basic)}
    try:
        try:
            res = fn(*args, **kwargs)
        except BaseException as e:
            rec["exc"] = repr(e)
            raise
        rec["result"] = _s(res)
        rec["result_is_none"] = res is None
        rec["unchanged"] = (res == expr) if res is not None else True
        return res
    finally:
        STATE["depth"] -= 1
        RECORDS.append(rec)


@functools.wraps(ORIG_REFINE)
def refine_wrapper(expr, assumptions=True, *a, **k):
    return _record("refine", expr, assumptions, ORIG_REFINE, (expr, assumptions) + a, k)


def make_handler_wrapper(name, fn):
    @functools.wraps(fn)
    def w(expr, assumptions=True, *a, **k):
        return _record(name, expr, assumptions, fn, (expr, assumptions) + a, k)
    return w


_upstream.refine = refine_wrapper
satrefine.refine = refine_wrapper

mods = [importlib.import_module(f"satrefine.handlers_v3.{i.name}") for i in pkgutil.iter_modules(pkg.__path__)]
orig_to_wrap = {}
for m in mods:
    for attr, val in list(vars(m).items()):
        if attr.startswith("refine_") and isinstance(val, types.FunctionType) and val.__module__ == m.__name__:
            orig_to_wrap[val] = make_handler_wrapper(f"{m.__name__.split('.')[-1]}.{attr}", val)
for m in mods + [pkg]:
    for attr, val in list(vars(m).items()):
        if isinstance(val, types.FunctionType) and val in orig_to_wrap:
            setattr(m, attr, orig_to_wrap[val])
for key, val in list(_upstream.handlers_dict.items()):
    if val in orig_to_wrap:
        _upstream.handlers_dict[key] = orig_to_wrap[val]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    STATE["nodeid"] = item.nodeid
    yield
    STATE["nodeid"] = None


def pytest_runtest_logreport(report):
    if report.when == "call":
        RECORDS.append({"report": report.nodeid, "outcome": report.outcome})


def pytest_sessionfinish(session):
    with open(OUT, "w") as f:
        json.dump(RECORDS, f)
