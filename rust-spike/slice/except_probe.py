"""except_probe.py WL REF COUNTS OUT [--stride N] [--py]: what becomes of an exception from an LRA hook.

Plants a RuntimeError at the G-th hook call of each query, forked per item, and records the answer that comes out of
`ask`, whether it raised, and which of the two handlers saw it (catch_count.py). REF is the unfaulted fresh row for the
answers. This is the brief's question about `engine.py:1906` and `sympy_api.py:1107`, asked by running.
"""
import argparse
import collections
import json
import os
import sys

import catch_count
import live
from move_every_call import HOOKS

ap = argparse.ArgumentParser()
ap.add_argument("wl")
ap.add_argument("ref")
ap.add_argument("counts")
ap.add_argument("out")
ap.add_argument("--stride", type=int, default=5)
ap.add_argument("--py", action="store_true")
ap.add_argument("--persist", action="store_true", help="raise at every hook call from G on, as a real bug would")
a = ap.parse_args()


class Planted(RuntimeError):
    pass


class S:
    g, n, fired = -1, 0, False
    site = None


def fault_class(base):
    def hook(name):
        f = getattr(base, name)

        def w(self, *args):
            if S.n == S.g and not S.fired or (a.persist and S.fired):
                S.fired, S.site = True, S.site or name
                raise Planted("planted")
            S.n += 1
            return f(self, *args)
        w.__name__ = name
        return w
    return type("LRATheory", (base,), {n: hook(n) for n in HOOKS})


from satassume import sympy_api  # noqa: E402
from satassume.theories.lra import lra as _lra, lra_adapter  # noqa: E402
if a.py:
    cls = fault_class(_lra.LRATheory)
    _lra.LRATheory = lra_adapter.LRATheory = cls
else:
    import backend
    import lra_backend
    backend.install()
    lra_backend.install()
    cls = fault_class(lra_backend.LRATheory)
    _lra.LRATheory = lra_adapter.LRATheory = cls
catch_count.install()

ref = {r["q"]: r["ans"] for r in map(json.loads, open(a.ref)) if "q" in r}
pairs = live.load(a.wl)
items = []
for q, c in sorted(json.loads(x) for x in open(a.counts)):
    items += [(q, g) for g in range(0, c, a.stride)]

tally = collections.Counter()
with open(a.out, "w") as out:
    for q, g in items:
        out.flush()
        if os.fork():
            os.wait()
            continue
        S.g = g
        p, assum = pairs[q]
        try:
            r, exc = sympy_api.ask(p, assum), None
        except BaseException as e:
            r, exc = "raise", type(e).__name__
        rec = dict(q=q, g=g, fired=S.fired, hook=S.site, ans=str(r), exc=exc, ref=str(ref.get(q)),
                   caught=[c[:2] for c in catch_count.take()])
        out.write(json.dumps(rec) + "\n")
        out.flush()
        os._exit(0)
rows = [json.loads(x) for x in open(a.out)]
for r in rows:
    sites = ",".join(sorted({c[0] for c in r["caught"]})) or "none"
    how = "raised" if r["exc"] else ("same" if r["ans"] == r["ref"] else f"answer {r['ref']}->{r['ans']}")
    tally[(r["fired"], sites, how)] += 1
for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
    print(v, *k)
print("items", len(rows), "of", len(items), file=sys.stderr)
