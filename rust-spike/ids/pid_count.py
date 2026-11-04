"""pid_count.py WL ORDER: not timed. The workload against the package on PYTHONPATH (base or the P-id copy), recorded
or shuffled:SEED. Counts P instances, hash and eq calls, first-time id lookups, table size. Prints JSON with the digest."""
import hashlib, json, random, sys
wl, order = sys.argv[1], sys.argv[2]
from evalbench.common import workload
from satassume import sympy_api
from satassume.sat import formula as fm
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)
C = dict(new=0, hash=0, eq=0, first=0)
P = fm.P
oi, oh, oe = P.__init__, P.__hash__, P.__eq__
def i(self, *a, **k):
    C["new"] += 1
    oi(self, *a, **k)
def h(self):
    C["hash"] += 1
    return oh(self)
def e(self, o):
    C["eq"] += 1
    return oe(self, o)
P.__init__, P.__hash__, P.__eq__ = i, h, e
if hasattr(P, "__getattr__"):
    og = P.__getattr__
    def g(self, name):
        if name == "_pid":
            C["first"] += 1
        return og(self, name)
    P.__getattr__ = g
seq = list(range(len(pairs)))
if order.startswith("shuffled"):
    random.Random(int(order.split(":")[1])).shuffle(seq)
ans = [None] * len(pairs)
for n in seq:
    p, a = pairs[n]
    try:
        r = sympy_api.ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as ex:
        r = "raise " + type(ex).__name__
    ans[n] = r
out = dict(wl=wl, order=order, file=fm.__file__, digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16], **C)
if hasattr(fm, "_P_IDS"):
    t = fm._P_IDS
    out.update(table=len(t), exprs=len({id(k[1]) for k in t}), preds=len({k[0] for k in t}))
print(json.dumps(out))
