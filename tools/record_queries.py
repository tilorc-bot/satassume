"""pytest plugin: record every assumption query SymPy's own test suite makes.

Usage (from a SymPy checkout, read-only)::

    RECORD_OUT=/path/queries.jsonl PYTHONPATH=/path/to/satassume/tools:. \
      python -m pytest -p record_queries -p no:cacheprovider sympy/assumptions/tests sympy/core/tests/test_assumptions.py

Three kinds of record are written as JSON lines, one per query, with SymPy
objects serialised through ``srepr`` so they can be rebuilt later:

* ``{"kind": "old", "expr": srepr, "fact": name, "value": bool|null}`` — an
  ``expr.is_<fact>`` cache miss answered by ``sympy.core.assumptions._ask``;
* ``{"kind": "ask", "prop": srepr, "assum": srepr, "value": ...}`` — a call
  to ``sympy.ask``; ``value`` is ``"error"`` when SymPy raised;
* ``{"kind": "rec", ...}`` — a call to the handler-only helper
  ``_ask_recursive`` used by the newer tests.

``tools/compare.py`` replays the file against satassume.
"""
import atexit
import json
import os
import sys

import sympy
from sympy import srepr

OUT = open(os.environ.get("RECORD_OUT", "queries.jsonl"), "w")
N = {"old": 0, "ask": 0, "rec": 0, "dropped": 0}


def _json_value(v):
    """True/False/None as-is; SymPy booleans coerced; anything else stringified."""
    if v is None or v is True or v is False or isinstance(v, str):
        return v
    try:
        from sympy.logic.boolalg import BooleanAtom
        if isinstance(v, BooleanAtom):
            return bool(v)
    except Exception:
        pass
    return "value:" + repr(v)

CA = sys.modules["sympy.core.assumptions"]
_orig_old = CA._ask
DEPTH = [0]


def _old(fact, obj):
    if DEPTH[0]:
        return _orig_old(fact, obj)
    DEPTH[0] += 1
    try:
        v = _orig_old(fact, obj)
    finally:
        DEPTH[0] -= 1
    try:
        OUT.write(json.dumps({"kind": "old", "expr": srepr(obj), "fact": fact, "value": _json_value(v)}) + "\n")
        N["old"] += 1
    except Exception:
        N["dropped"] += 1
    return v


CA._ask = _old

A = sys.modules["sympy.assumptions.ask"]
_orig_ask, _orig_rec = A.ask, A._ask_recursive
from sympy.assumptions.ask import global_assumptions


def _rec_wrap(name, orig):
    def w(*args, **kw):
        if DEPTH[0]:
            return orig(*args, **kw)
        DEPTH[0] += 1
        try:
            try:
                v = orig(*args, **kw)
            except Exception as e:
                v = "error:" + type(e).__name__
                raise
            finally:
                p = args[0] if args else kw["proposition"]
                a = args[1] if len(args) > 1 else kw.get("assumptions", True)
                ctx = args[2] if len(args) > 2 else kw.get("context", global_assumptions)
                if ctx is global_assumptions and not list(global_assumptions):
                    try:
                        OUT.write(json.dumps({"kind": name, "prop": srepr(p), "assum": srepr(sympy.sympify(a)), "value": _json_value(v)}) + "\n")
                        N[name] += 1
                    except Exception:
                        N["dropped"] += 1
        finally:
            DEPTH[0] -= 1
        return v
    return w


A.ask = _rec_wrap("ask", _orig_ask)
A._ask_recursive = _rec_wrap("rec", _orig_rec)
sympy.assumptions.ask = A.ask
sympy.ask = A.ask


@atexit.register
def _close():
    OUT.close()
    print("\nRECORDED", N, file=sys.stderr)
