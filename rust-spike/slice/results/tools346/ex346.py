# which exit makes Engine._ends_without_session True, per workload (orion, counts)
import sys, os, importlib
S = os.environ["SLICE_DIR"]; sys.path.append(S)
from satassume import sympy_api, witness
from satassume.engine import Engine, INCONSISTENT
wl = sys.argv[1]
if wl == "fuzz":
    from evalbench.fuzz import queries; pairs = queries(424242)
elif wl == "dev":
    from evalbench.common import workload; pairs = workload(wl)
else:
    import live; pairs = live.load(wl)
cnt = dict(asked=0, inconsistent=0, failed=0, over=0)
real = Engine._ends_without_session
def ns(self, p, a):
    cnt["asked"] += 1
    r = real(self, p, a)
    if r:
        k = "inconsistent" if self._verdict.get(a) is INCONSISTENT else "failed" if self._failed.get(a) is not None else "over"
        cnt[k] += 1
    return r
Engine._ends_without_session = ns
for p, a in pairs:
    try: sympy_api.ask(p, a)
    except Exception: pass
print(wl, cnt)
