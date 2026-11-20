"""mods367.py WL (sa-port-367): what is loaded on the default path. One pass of WL as tools342/qt342.py's MODE py runs it
(the package alone, no install), then every module in sys.modules whose file is under the tree's rust-spike/slice, and
every SLICE_ variable in the environment. With sys.monitoring: PY_START counted per file under rust-spike/slice while
the timed loop runs (a module that is loaded but runs nothing in the loop shows 0). Prints one JSON line."""
import collections, json, os, sys
wl = sys.argv[1]
S = os.environ["SLICE_DIR"]
from evalbench.common import workload
from satassume import sympy_api
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
elif wl in ("budget", "wiring"):
    import importlib
    if S not in sys.path:
        sys.path.append(S)
    pairs = importlib.import_module({"budget": "budget_wl", "wiring": "knowledge_wiring_wl"}[wl]).queries()
else:
    pairs = workload(wl)
started = collections.Counter()
M = sys.monitoring
M.use_tool_id(3, "mods367")


def on_start(code, off):
    fn = code.co_filename
    if "/rust-spike/" in fn or "/slice/" in fn:
        started[os.path.basename(fn)] += 1
    else:
        return M.DISABLE
M.register_callback(3, M.events.PY_START, on_start)
M.set_events(3, M.events.PY_START)
n = 0
for p, a in pairs:
    try:
        sympy_api.ask(p, a)
    except Exception:
        n += 1
M.set_events(3, 0)
mods = sorted((k, getattr(m, "__file__", None)) for k, m in sys.modules.items()
              if "/rust-spike/" in (getattr(m, "__file__", None) or ""))
print(json.dumps(dict(wl=wl, n=len(pairs), raised=n, slice_modules=mods, slice_py_starts_in_loop=dict(started),
                      slice_env=sorted(k for k in os.environ if k.startswith("SLICE_")),
                      sa_solver_loaded="sa_solver" in sys.modules,
                      satassume_modules=sorted(k for k in sys.modules if k.startswith("satassume")))))
