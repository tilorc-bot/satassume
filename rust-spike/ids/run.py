"""run.py MODE WL ORDER [--out F] [--only I] [--audit]: one replay. MODE base|shadow|eqonly|live.
ORDER recorded | shuffled:SEED | fork (each query in a fork of a parent that has only imported; 12 at a time) |
only (one query, --only I). Answers are put back in recorded order before the digest."""
import hashlib
import json
import multiprocessing as mp
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
mode, wl, order = sys.argv[1:4]
arg = lambda n, d=None: sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
from evalbench.common import workload  # noqa: E402
from satassume import sympy_api  # noqa: E402

if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)
if mode != "base":
    import ids_core
    ids_core.install(mode)


def one(i):
    p, a = pairs[i]
    try:
        r = sympy_api.ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:  # noqa: BLE001
        r = "raise " + type(e).__name__
    return r


t0 = time.time()
n = len(pairs)
if order == "only":
    print(json.dumps(one(int(arg("--only")))))
    sys.exit(0)
if order == "fork":
    with mp.get_context("fork").Pool(12, maxtasksperchild=1) as pool:
        ans = pool.map(one, range(n), chunksize=1)
else:
    seq = list(range(n))
    if order.startswith("shuffled"):
        random.Random(int(order.split(":")[1])).shuffle(seq)
    ans = [None] * n
    for i in seq:
        ans[i] = one(i)
d = hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]
out = dict(mode=mode, wl=wl, order=order, digest=d, s=round(time.time() - t0, 1))
if mode != "base":
    out.update(ids_core.report())
    if "--audit" in sys.argv:
        out["audit"], out["audit_samples"] = ids_core.audit()
if arg("--out"):
    json.dump(dict(out, answers=ans), open(arg("--out"), "w"))
out["bad"] = [(b["kind"], b["site"], b["count"], b["sample"][0]) for b in out.get("bad", [])][:12]
print(json.dumps(out)[:2500])
