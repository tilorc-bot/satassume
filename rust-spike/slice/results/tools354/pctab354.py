"""pctab354.py PC-NEW PC-BASE (sa-port-354, item 6; offline): pc354.sh's rows read together.
  1  per cell of NEW (d0, w1, nat): calls per probed file over the 20 workloads, and the queries
  2  NEW d0 against BASE d0, per file and per workload: the default path's counts (the probe count against 21/32)
  3  witness.py and witness_live.py by function, w1 against nat, over the 20 and on dev, fuzz, budget, wiring
  5  the other probed files: functions called more or less often in nat than in w1 (the table's symbol reads)
  4  per workload in nat: calls of the check (witness.py:witnesses), native calls, counters 706-713, the fallbacks as
     a share of the native calls, wn:lookup (boundary reads of q.ids) and `_replaced`'s dictionary reads (its calls
     times len(_OWN)), witness.py's calls per call of the check and per query; whether the hook was in place."""
import glob, json, os, sys
from collections import Counter
new, base = sys.argv[1:3]


def cell(d):
    out = {}
    for f in sorted(glob.glob(d + "/*.json")):
        out[os.path.basename(f)[:-5]] = json.load(open(f))
    return out


def files(rows):
    c = Counter()
    for r in rows.values():
        for k, v in r["by_qualname"].items():
            c[k.split(":")[0]] += v
    return c


N = {c: cell(f"{new}/{c}") for c in ("d0", "w1", "nat")}
B = cell(f"{base}/d0")
print("1 calls per file over the workloads; cells d0 w1 nat of NEW")
print("  workloads", {c: len(v) for c, v in N.items()}, "queries", {c: sum(r["queries"] for r in v.values()) for c, v in N.items()})
fc = {c: files(v) for c, v in N.items()}
for f in sorted(set().union(*fc.values())):
    print(f"  {f} {fc['d0'][f]} {fc['w1'][f]} {fc['nat'][f]}")
print("2 NEW d0 against BASE d0")
fb = files(B)
for f in sorted(set(fb) | set(fc["d0"])):
    print(f"  {f} base {fb[f]} new {fc['d0'][f]} {'equal' if fb[f] == fc['d0'][f] else 'DIFFER'}")
diff = [(wl, k) for wl in sorted(set(B) | set(N["d0"])) for k in set(B.get(wl, {}).get("by_qualname", {})) | set(N["d0"].get(wl, {}).get("by_qualname", {}))
        if B.get(wl, {}).get("by_qualname", {}).get(k) != N["d0"].get(wl, {}).get("by_qualname", {}).get(k)]
print("  per workload and function, rows that differ:", len(diff), diff[:20])
print("  queries base", sum(r["queries"] for r in B.values()), "new", sum(r["queries"] for r in N["d0"].values()),
      "hook in d0", sorted({str(r.get("native")) for r in N["d0"].values()}))
print("3 witness.py and witness_live.py by function: w1 / nat")
for label, wls in (("the 20", None), ("dev", ["dev"]), ("fuzz", ["fuzz"]), ("budget", ["budget"]), ("wiring", ["wiring"])):
    c = {}
    for k in ("w1", "nat"):
        c[k] = Counter()
        for wl, r in N[k].items():
            if wls is None or wl in wls:
                for q, v in r["by_qualname"].items():
                    if q.startswith(("witness.py:", "witness_live.py:")):
                        c[k][q] += v
    tot = {k: (sum(v for q, v in c[k].items() if q.startswith("witness.py:")), sum(v for q, v in c[k].items() if q.startswith("witness_live.py:"))) for k in c}
    print(f"  {label}: witness.py {tot['w1'][0]} / {tot['nat'][0]}; witness_live.py {tot['w1'][1]} / {tot['nat'][1]}; functions of witness.py called {sum(1 for q in c['w1'] if q.startswith('witness.py:'))} / {sum(1 for q in c['nat'] if q.startswith('witness.py:'))}")
    top = sorted(set(c["w1"]) | set(c["nat"]), key=lambda q: -c["nat"][q])
    for q in top[:12 if wls is None else 8]:
        print(f"    {q} {c['w1'][q]} / {c['nat'][q]}")
print("4 nat per workload: wl queries checks native(calls of witness_live.native) witness.py-calls per-check per-query | counters | fallback share | lookups | _replaced reads | hook")
T = Counter()
for wl, r in N["nat"].items():
    bq = r["by_qualname"]
    chk, nat = bq.get("witness.py:witnesses", 0), bq.get("witness_live.py:native", 0)
    wp = sum(v for q, v in bq.items() if q.startswith("witness.py:"))
    wn = r["wn"] or {}
    fall = sum(v for k, v in wn.items() if k.startswith("wn:fallback"))
    rep = bq.get("witness_live.py:_replaced", 0)
    # `_replaced` runs only past the no-table and plant tests, and a False from it is followed by witness_compile
    # (wn:compile): its calls minus wn:compile is how often it returned True, and the native calls minus its calls is
    # the rest of wn:fallback:off (no query, no table).
    T.update(queries=r["queries"], chk=chk, nat=nat, wp=wp, fall=fall, rep=rep, lookup=wn.get("wn:lookup", 0), compile=wn.get("wn:compile", 0),
             replaced=rep - wn.get("wn:compile", 0), notable=nat - rep, off=wn.get("wn:fallback:off", 0))
    print(f"  {wl} {r['queries']} {chk} {nat} {wp} {wp / chk if chk else 0:.2f} {wp / r['queries']:.2f} | " + " ".join(f"{k}={v}" for k, v in sorted(wn.items()) if v)
          + f" | {fall} of {nat} {100 * fall / nat if nat else 0:.1f}% | {wn.get('wn:lookup', 0)} | {rep} x {r['own']} = {rep * (r['own'] or 0)} | {r['native']} certified {r['certified']}")
print("  total", dict(T), f"witness.py per check {T['wp'] / T['chk']:.2f} per query {T['wp'] / T['queries']:.2f}")
T = Counter()
for wl, r in N["w1"].items():
    bq = r["by_qualname"]
    T.update(queries=r["queries"], chk=bq.get("witness.py:witnesses", 0), wp=sum(v for q, v in bq.items() if q.startswith("witness.py:")))
print("  w1 total", dict(T), f"witness.py per check {T['wp'] / T['chk']:.2f} per query {T['wp'] / T['queries']:.2f}", "hook", sorted({str(r.get('native')) for r in N['w1'].values()}))
print("5 the other probed files, functions whose count differs between w1 and nat (over the 20): function w1 nat")
o = {k: Counter() for k in ("w1", "nat")}
pw = Counter()
for k in o:
    for wl, r in N[k].items():
        for q, v in r["by_qualname"].items():
            if not q.startswith(("witness.py:", "witness_live.py:")):
                o[k][q] += v
                pw[wl] += v if k == "nat" else -v
for q in sorted(set(o["w1"]) | set(o["nat"]), key=lambda q: o["w1"][q] - o["nat"][q]):
    if o["w1"][q] != o["nat"][q]:
        print(f"  {q} {o['w1'][q]} {o['nat'][q]} {o['nat'][q] - o['w1'][q]:+d}")
print("  per workload, nat minus w1:", {k: v for k, v in sorted(pw.items()) if v}, "sum", sum(pw.values()))
print("  certified per workload w1 == nat:", all(N["w1"][wl]["certified"] == N["nat"][wl]["certified"] for wl in N["nat"]),
      "sum", sum(r["certified"] or 0 for r in N["nat"].values()))
