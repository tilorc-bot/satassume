"""pcby334.py OUT.json WL MODE [live.py args...] (sa-port-334; run from rust-spike/slice): pycalls.py's count of Python
calls (PY_START per code object, `file.py:qualname`) for the files in PYCALLS_FILE (':'-joined, paths under the clone),
plus, for satassume/knowledge/templates/__init__.py only, each call filed by its caller: the first Python frame outside
that file (`qualname<-file.py:function`), so `_may_be_nan`'s recursion and generator expressions fold into the caller.
A call made from Rust through a handle shows the Python frame that entered Rust. OUT keeps pycalls.py's `queries` and
`by_qualname` keys (pccmp317.py reads them) and adds `init_callers`.
"""
import json, os, runpy, sys
from collections import Counter


def main():
    out, rest = sys.argv[1], sys.argv[2:]
    root = os.path.realpath(os.path.join(os.getcwd(), "..", ".."))
    targets = {os.path.realpath(os.path.join(root, p)) for p in os.environ["PYCALLS_FILE"].split(":")}
    init = os.path.realpath(os.path.join(root, "satassume/knowledge/templates/__init__.py"))
    mon = sys.monitoring
    tool = mon.PROFILER_ID
    mon.use_tool_id(tool, "pcby334")
    calls, callers, mine = Counter(), Counter(), {}

    def start(code, offset):
        r = mine.get(code)
        if r is None:
            f = os.path.realpath(code.co_filename)
            r = mine[code] = (os.path.basename(f) + ":", f == init) if f in targets else False
        if r is False:
            return mon.DISABLE
        calls[r[0] + code.co_qualname] += 1
        if r[1]:
            f = sys._getframe(1)
            while f is not None and f.f_code.co_filename == code.co_filename:
                f = f.f_back
            callers[code.co_qualname.split(".")[0] + "<-" + ("?" if f is None else
                    os.path.basename(f.f_code.co_filename) + ":" + f.f_code.co_qualname)] += 1

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
    json.dump({"argv": rest, "queries": queries, "by_qualname": dict(calls.most_common()),
               "init_callers": dict(callers.most_common())}, open(out, "w"), indent=1)
    print(json.dumps({"queries": queries, "calls": sum(calls.values()), "init": sum(callers.values())}))


if __name__ == "__main__":
    main()
