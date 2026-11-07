"""What reaches `lra_cert`, by running: counts each of its functions at call, split by whether `sympy_api.ask` is on the
stack. `lra_cert_reach.py OUT WL MODE`: `live.py WL MODE --check plain`, shared memos. As a pytest plugin
(`-p lra_cert_reach`, LRA_CERT_OUT set): the same, with the test ids, one file per worker."""
import atexit
import json
import os
import sys

TOOL = 4
hits, tests, cur = {}, {}, [None]


def on_start(code, _offset):
    if not code.co_filename.endswith("lra/lra_cert.py"):
        return sys.monitoring.DISABLE
    f, via = sys._getframe(1), "direct"
    while f is not None:
        if f.f_code.co_name == "ask" and f.f_code.co_filename.endswith("sympy_api.py"):
            via = "ask"
            break
        f = f.f_back
    k = f"{via}:{code.co_qualname}"
    hits[k] = hits.get(k, 0) + 1
    if cur[0] is not None:
        tests.setdefault(cur[0], {}).setdefault(k, 0)
        tests[cur[0]][k] += 1


def start(out):
    sys.monitoring.use_tool_id(TOOL, "lra_cert_reach")
    sys.monitoring.register_callback(TOOL, sys.monitoring.events.PY_START, on_start)
    sys.monitoring.set_events(TOOL, sys.monitoring.events.PY_START)
    pid = os.getpid()
    atexit.register(lambda: os.getpid() == pid and json.dump(dict(hits=hits, tests=tests), open(out, "w")))


if os.environ.get("LRA_CERT_OUT"):
    start(f"{os.environ['LRA_CERT_OUT']}.{os.getpid()}.json")


def pytest_runtest_protocol(item, nextitem):
    cur[0] = item.nodeid


if __name__ == "__main__":
    start(sys.argv[1])
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    wl, mode = sys.argv[2:4]
    sys.argv = ["live.py", wl, mode, sys.argv[1] + ".rows", "--check", "plain"]
    import live
    live.main()
    print(json.dumps(hits))
