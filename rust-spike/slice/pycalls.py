"""pycalls.py OUT.json WL MODE [live.py args...]: Python calls into satassume/sympy_api.py during one live.py pass.

For the 5c8 count ruling (planner, 8 Nov ~11:30): sympy_api.py counts once reach shows 0 Python calls per query outside
the ruled-conversion rows. `sys.monitoring` counts every PY_START of a code object whose file is sympy_api.py (Python's
copies in session_live.PY_RELEVANCE included, since their code objects come from that file). Each code object is filed
under its outermost function (`_relevant.<locals>.<genexpr>` under `_relevant`), and each outermost name is classed by
PORT-INVENTORY.md's sympy_api lists: conversion, port, or unlisted. OUT gets the counts by name and class, and the
query count from live.py's totals line.

`PYCALLS_FILE=satassume/theories/lra/lra_adapter.py` (any path under the clone) counts that file instead, every name
"unlisted" (the state step, part 1: the lra_adapter count ruling). Each call is also filed by the query it ran under, read
from term_live's stack top as adapters.rs `top_query` reads it: `kept:<reason>` (the query runs on Python), `noquery` (no
query on the stack) or `converted` (a Rust query): `by_state` and `by_name_state`. Several paths joined by ':' count them all,
each name filed as `file.py:name` (the state step, part 2: relations.py, term_live.py, session_live.py and lra_adapter.py in
one pass).
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
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    paths = os.environ.get("PYCALLS_FILE", "satassume/sympy_api.py").split(":")
    targets = {os.path.realpath(os.path.join(root, f)) for f in paths}
    many = len(paths) > 1
    tl = []
    states = Counter()

    def state():
        if not tl:
            m = getattr(sys.modules.get("term_live"), "_local", None)    # never imported from here
            if m is None:
                return "noquery"
            tl.append(m)
        st = getattr(tl[0], "stack", None)
        if not st:
            return "noquery"
        k = st[-1].kept
        return "converted" if k is None else "kept:" + str(k)
    mon = sys.monitoring
    tool = mon.PROFILER_ID
    mon.use_tool_id(tool, "pycalls")
    calls = Counter()
    mine = {}

    def start(code, offset):
        r = mine.get(code)
        if r is None:
            f = os.path.realpath(code.co_filename)
            r = mine[code] = (os.path.basename(f) + ":" if many else "") if f in targets else None
        if r is not None:
            calls[r + code.co_qualname] += 1
            states[(r + code.co_qualname.split(".")[0], state())] += 1
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
        cls["conversion" if top in CONVERSION and "PYCALLS_FILE" not in os.environ else
            "port" if top in PORT and "PYCALLS_FILE" not in os.environ else "unlisted"] += n
    by_state = Counter()
    for (top, stt), n in states.items():
        by_state[stt] += n
    queries = None
    try:
        with open(rest[2]) as f:
            for line in f:
                pass
        queries = json.loads(line).get("total", {}).get("queries")
    except Exception:
        pass
    json.dump({"argv": rest, "queries": queries, "by_class": cls, "by_name": dict(by.most_common()),
               "by_state": dict(by_state), "by_name_state": {f"{a} {b}": n for (a, b), n in states.most_common()},
               "by_qualname": dict(calls.most_common())}, open(out, "w"), indent=1)
    print(json.dumps({"queries": queries, "by_class": cls, "by_state": by_state}))


if __name__ == "__main__":
    main()
