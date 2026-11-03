"""protime.py LABEL WORKLOAD [ANS_OUT]: one cold replay of dev or fuzz 424242
with whatever satassume is on PYTHONPATH (SA_LAZY from the env); prints JSON."""
import sys, time, gc, json, hashlib, os
label, wl = sys.argv[1], sys.argv[2]
from evalbench.common import ask_all, workload
from satassume import sympy_api
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)
gc.collect(); gc.freeze()
per = []; t = time.perf_counter(); ans = ask_all(sympy_api.ask, pairs, time.perf_counter, per); T = time.perf_counter() - t
if len(sys.argv) > 3:
    json.dump(ans, open(sys.argv[3], "w"))
print(json.dumps(dict(label=label, lazy=os.environ.get("SA_LAZY"), wl=wl, s=round(T, 4),
                      none_s=round(sum(d for d, r in zip(per, ans) if r is None), 4),
                      def_s=round(sum(d for d, r in zip(per, ans) if r is not None), 4),
                      n=len(ans), n_none=sum(r is None for r in ans),
                      digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16])), flush=True)
