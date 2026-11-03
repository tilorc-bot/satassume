"""ceilw.py MODE WORKLOAD: one cold replay with links (and transfer) disabled per MODE."""
import sys, time, gc, json, hashlib
mode, wl = sys.argv[1], sys.argv[2]
from satassume import relations as R
if "nolink" in mode:
    R.Relations._link = lambda self, e: None
if "noxfer" in mode:
    R.Relations.sync_transfer = lambda self: None
    R.Relations._engage_transfer = lambda self: None
from evalbench.common import ask_all, workload
from satassume import sympy_api
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)
gc.collect(); gc.freeze()
per = []; t = time.perf_counter(); ans = ask_all(sympy_api.ask, pairs, time.perf_counter, per); T = time.perf_counter() - t
print(json.dumps(dict(mode=mode, wl=wl, s=round(T, 4), none_s=round(sum(d for d, r in zip(per, ans) if r is None), 4),
                      n_none=sum(r is None for r in ans), digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:12])))
