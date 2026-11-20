"""pcby354.py OUT.json WL MODE [live.py args...] (sa-port-354, item 6; tools334/pcby334.py without its caller table; run
from rust-spike/slice): the count of Python calls (sys.monitoring PY_START per code object, `file.py:qualname`) for the
files in PYCALLS_FILE (':'-joined, paths under the tree). Nothing is wrapped or replaced, so witness_live._replaced
sees witness.py's own objects and the native path stays on. After the run, read from this process: whether
witness.NATIVE holds the native entry, the native counters 706-713 (witness_live.counts(): `wn:lookup` is the boundary
reads of q.ids), and len(witness_live._OWN), the dictionary reads one `_replaced` call makes.
"""
import json, os, runpy, sys
from collections import Counter


def main():
    out, rest = sys.argv[1], sys.argv[2:]
    root = os.path.realpath(os.path.join(os.getcwd(), "..", ".."))
    targets = {os.path.realpath(os.path.join(root, p)) for p in os.environ["PYCALLS_FILE"].split(":")}
    mon = sys.monitoring
    tool = mon.PROFILER_ID
    mon.use_tool_id(tool, "pcby354")
    calls, mine = Counter(), {}

    def start(code, offset):
        r = mine.get(code)
        if r is None:
            f = os.path.realpath(code.co_filename)
            r = mine[code] = os.path.basename(f) + ":" if f in targets else False
        if r is False:
            return mon.DISABLE
        calls[r + code.co_qualname] += 1

    mon.register_callback(tool, mon.events.PY_START, start)
    mon.set_events(tool, mon.events.PY_START)
    sys.argv = ["live.py"] + rest
    try:
        runpy.run_path(os.path.join(os.getcwd(), "live.py"), run_name="__main__")
    except SystemExit:
        pass
    finally:
        mon.set_events(tool, 0)
    queries = None
    try:
        with open(rest[2]) as f:
            for line in f:
                pass
        queries = json.loads(line).get("total", {}).get("queries")
    except Exception:
        pass
    w, wl = sys.modules.get("satassume.witness"), sys.modules.get("witness_live")
    native = getattr(w, "NATIVE", [None])[0]
    json.dump({"argv": rest, "queries": queries, "by_qualname": dict(calls.most_common()),
               "native": None if native is None else native.__module__ + "." + native.__name__,
               "enabled": None if w is None else w.ENABLED[0], "env": os.environ.get("SLICE_WITNESS_RUST"),
               "wn": None if wl is None else wl.counts(), "own": None if wl is None else len(wl._OWN),
               "certified": None if w is None else _certified()}, open(out, "w"), indent=1)
    print(json.dumps({"queries": queries, "calls": sum(calls.values())}))


def _certified():
    try:
        from satassume import sympy_api
        return sympy_api.default_engine().stats.get("witness_certified")
    except Exception as e:
        return "raise " + type(e).__name__


if __name__ == "__main__":
    main()
