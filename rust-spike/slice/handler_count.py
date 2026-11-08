"""Counts the two places that turn any Exception into a quiet answer, without changing either or wrapping what they call.
  engine.Engine._build_context: `except Exception` round the complete check, which gives "unknown" from a fresh session.
  sympy_api._consistent: `except Exception: return False`.
A Rust or ported-theory bug raised there shows as a lost answer, not a crash. `sys.monitoring` reports each exception
handled in those two functions, filtered by code object; Uninterpreted is re-raised by `_build_context`, and a BaseException isn't caught, so
neither counts. Rows: {site, type, text, where}. `where` is the query index or test id.
  fresh.py --handlers FILE, or `-p handler_count` in a suite run (one handlers.PID.jsonl per worker in SLICE_SUITE_OUT).
"""
import json
import os
import sys

TOOL = 4
where = None
_out = None
_sites = set()


def _fired(code, offset, exc):
    if code not in _sites:
        return
    from satassume.engine import Uninterpreted
    if not isinstance(exc, Exception) or isinstance(exc, Uninterpreted):
        return
    here = where if where is not None else os.environ.get("PYTEST_CURRENT_TEST", "?").split(" ")[0]
    _out.write(json.dumps(dict(site=code.co_qualname, type=type(exc).__name__, text=str(exc)[:200], where=here)) + "\n")
    _out.flush()


def install(path):
    global _out
    from satassume import engine, sympy_api
    if _out is not None:        # live.py always installs; `--handlers` only says where to write
        _out.close()
        _out = open(path, "a")
        return
    _out = open(path, "a")
    mon = sys.monitoring
    mon.use_tool_id(TOOL, "handler_count")
    # 5c8: `_consistent` may already be relevance.rs's (no code object); Python's own copy is in session_live.PY_RELEVANCE
    cons = sympy_api._consistent
    if not hasattr(cons, "__code__"):
        cons = sys.modules["session_live"].PY_RELEVANCE["_consistent"]
    _sites.update(f.__code__ for f in (engine.Engine._build_context, cons))
    mon.register_callback(TOOL, mon.events.EXCEPTION_HANDLED, _fired)
    mon.set_events(TOOL, mon.events.EXCEPTION_HANDLED)  # 3.12 has it only as a global event, hence the filter above


def pytest_configure(config):
    install(os.path.join(os.environ["SLICE_SUITE_OUT"], f"handlers.{os.getpid()}.jsonl"))


def rust_handled(site, exc):
    """relevance.rs's `_consistent` caught `exc` (an Exception, as Python's handler): the same row, under Python's site name."""
    from satassume.engine import Uninterpreted
    if _out is None or isinstance(exc, Uninterpreted):     # as `_fired`
        return
    here = where if where is not None else os.environ.get("PYTEST_CURRENT_TEST", "?").split(" ")[0]
    _out.write(json.dumps(dict(site=site, type=type(exc).__name__, text=str(exc)[:200], where=here)) + "\n")
    _out.flush()
