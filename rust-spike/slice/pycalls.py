"""pycalls.py OUT.json WL MODE [live.py args...]: Python calls into satassume/sympy_api.py during one live.py pass.

For the 5c8 count ruling (planner, 8 Nov ~11:30): sympy_api.py counts once reach shows 0 Python calls per query outside
the ruled-conversion rows. `sys.monitoring` counts every PY_START of a code object whose file is sympy_api.py (Python's
copies in session_live.PY_RELEVANCE included, since their code objects come from that file). Each code object is filed
under its outermost function (`_relevant.<locals>.<genexpr>` under `_relevant`), and each outermost name is classed by
PORT-INVENTORY.md's sympy_api lists: conversion, port, or unlisted. OUT gets the counts by name and class, and the
query count from live.py's totals line.
"""
import json
import os
import runpy
import sys
from collections import Counter

CONVERSION = {
    "Unsupported", "AssumptionSymbolError", "_declared", "check_strict", "default_engine", "set_default_engine",
    "matrix_predicates", "_is_matrix_predicate", "_is_scalar", "_applied_category", "_categories", "out_of_scope",
    "relation_parts", "_relation_formula", "to_formula", "ask", "_formula", "_Failed", "is_constant_proposition",
    "_ask", "_ask_general", "_engine_ask",  # conversion by the planner's ownership ruling, 7 Nov
}
PORT = {
    "_const_base", "_const_free", "_closed_keys", "_expr_keys", "_arg_keys", "_keys", "_keys_rel", "_bool_keys",
    "_sides_keys", "_Split", "_relevant", "_vocab_blocks", "_part_consistent", "_consistent",
}


def main():
    out, rest = sys.argv[1], sys.argv[2:]
    target = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", "satassume", "sympy_api.py"))
    mon = sys.monitoring
    tool = mon.PROFILER_ID
    mon.use_tool_id(tool, "pycalls")
    calls = Counter()
    mine = {}

    def start(code, offset):
        r = mine.get(code)
        if r is None:
            r = mine[code] = os.path.realpath(code.co_filename) == target
        if r:
            calls[code.co_qualname] += 1
        else:
            return mon.DISABLE

    mon.register_callback(tool, mon.events.PY_START, start)
    mon.set_events(tool, mon.events.PY_START)
    sys.argv = ["live.py"] + rest
    try:
        runpy.run_path(os.path.join(os.path.dirname(__file__), "live.py"), run_name="__main__")
    except SystemExit:
        pass
    finally:
        mon.set_events(tool, 0)
    by = Counter()
    cls = Counter()
    for q, n in calls.items():
        top = q.split(".")[0]
        by[top] += n
        cls["conversion" if top in CONVERSION else "port" if top in PORT else "unlisted"] += n
    queries = None
    try:
        with open(rest[2]) as f:
            for line in f:
                pass
        queries = json.loads(line).get("total", {}).get("queries")
    except Exception:
        pass
    json.dump({"argv": rest, "queries": queries, "by_class": cls, "by_name": dict(by.most_common()),
               "by_qualname": dict(calls.most_common())}, open(out, "w"), indent=1)
    print(json.dumps({"queries": queries, "by_class": cls}))


if __name__ == "__main__":
    main()
