"""pctab361.py PC-NEW PC-BASE (sa-port-361; offline): pc354.sh's rows of both trees read together.
  1  calls per probed file over the 20 workloads, per cell (d0 w1 nat), BASE and NEW, and the queries
  2  NEW d0 against BASE d0 per workload and function: the default path's counts (the probe count against 21 of 32)
  3  convert.py under SLICE_CONVERT=rust (w1): calls per workload, BASE and NEW, and by function over the 20
  4  the other probed files in w1 and nat: functions whose count differs between BASE and NEW, over the 20"""
import glob, json, os, sys
from collections import Counter
new, base = sys.argv[1:3]
CELLS = ("d0", "w1", "nat")


def cell(d):
    return {os.path.basename(f)[:-5]: json.load(open(f)) for f in sorted(glob.glob(d + "/*.json"))}


def files(rows):
    c = Counter()
    for r in rows.values():
        for k, v in r["by_qualname"].items():
            c[k.split(":")[0]] += v
    return c


def funcs(rows, only=None):
    c = Counter()
    for r in rows.values():
        for k, v in r["by_qualname"].items():
            if only is None or k.split(":")[0] == only:
                c[k] += v
    return c


N = {c: cell(f"{new}/{c}") for c in CELLS}
B = {c: cell(f"{base}/{c}") for c in CELLS}
print("1 calls per file over the workloads: d0 base new | w1 base new | nat base new")
for nm, D in (("base", B), ("new", N)):
    print(f"  {nm}: workloads", {c: len(v) for c, v in D.items()}, "queries", {c: sum(r["queries"] for r in v.values()) for c, v in D.items()})
fn, fb = {c: files(N[c]) for c in CELLS}, {c: files(B[c]) for c in CELLS}
for f in sorted(set().union(*fn.values(), *fb.values())):
    print(f"  {f} | " + " | ".join(f"{fb[c][f]} {fn[c][f]}{'' if fb[c][f] == fn[c][f] else ' *'}" for c in CELLS))
print("2 NEW d0 against BASE d0, per workload and function")
diff = [(wl, k) for wl in sorted(set(B["d0"]) | set(N["d0"])) for k in sorted(set(B["d0"].get(wl, {}).get("by_qualname", {})) | set(N["d0"].get(wl, {}).get("by_qualname", {})))
        if B["d0"].get(wl, {}).get("by_qualname", {}).get(k, 0) != N["d0"].get(wl, {}).get("by_qualname", {}).get(k, 0)]
print(f"  rows that differ: {len(diff)}", diff[:12])
print("3 convert.py under SLICE_CONVERT=rust (cell w1): calls per workload, base new, per query")
for wl in sorted(N["w1"]):
    b = sum(v for k, v in B["w1"].get(wl, {}).get("by_qualname", {}).items() if k.startswith("convert.py:"))
    n = sum(v for k, v in N["w1"][wl]["by_qualname"].items() if k.startswith("convert.py:"))
    q = N["w1"][wl]["queries"]
    print(f"  {wl} queries {q} base {b} new {n} per query {b / max(q, 1):.1f} -> {n / max(q, 1):.1f}")
cb, cn = funcs(B["w1"], "convert.py"), funcs(N["w1"], "convert.py")
print("  by function over the 20 (base new), the 25 largest of either:")
for k in sorted(set(cb) | set(cn), key=lambda k: -max(cb[k], cn[k]))[:25]:
    print(f"    {k} {cb[k]} {cn[k]}")
print(f"  functions of convert.py called: base {len(cb)} new {sum(1 for v in cn.values() if v)}; no longer called: {sorted(k for k in cb if not cn[k])[:40]}")
print("4 other probed files, functions whose count differs base/new")
for c in ("w1", "nat"):
    ob, on = funcs(B[c]), funcs(N[c])
    d = [(k, ob[k], on[k]) for k in sorted(set(ob) | set(on)) if ob[k] != on[k] and not k.startswith("convert.py:")]
    print(f"  {c}: {len(d)}", d[:30])
