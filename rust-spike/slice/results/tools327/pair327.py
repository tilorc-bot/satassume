"""pair327.py TIME.JSONL A H (sa-port-327, from 317's pair317.py): pinned wall per arm (median, min-max, n) and the
paired per-round change A -> H of the same round (median, min-max of the per-round percentages), dev and fuzz. Checks
digests and that each row's process had the switches its arm names."""
import json, statistics as st, sys, collections
rows = [json.loads(l) for l in open(sys.argv[1])]; A, H = sys.argv[2], sys.argv[3]
DIG = dict(dev="31cd0945c07f02a6", fuzz="173502b6ef285ad6")
bad = [r for r in rows if r["digest"] != DIG[r["wl"]]]
sw = collections.Counter((r["sha"], str(r.get("slice_convert_env")) + ":" + str(r.get("walk"))[:40], str(r.get("term_frames"))) for r in rows)
print(f"rows {len(rows)}; digest mismatches {len(bad)}; (arm, convert recorded, term_frames recorded): {dict(sw)}")
g = collections.defaultdict(dict)
for r in rows: g[r["sha"], r["wl"]][r["round"]] = r["s"]
for wl in ("dev", "fuzz"):
    print(f"\n### {wl}\n| arm | median s (min-max, n) |\n|---|---|")
    for a in (A, H):
        v = list(g[a, wl].values())
        if v: print(f"| {a} | {st.median(v):.3f} ({min(v):.3f}-{max(v):.3f}, {len(v)}) |")
    x, y = g[A, wl], g[H, wl]; d = [100 * (y[r] - x[r]) / x[r] for r in sorted(x) if r in y]
    print(f"\n| paired per round ({wl}) | median | min to max | rounds better/worse |\n|---|---|---|---|")
    if d: print(f"| {A} -> {H} | {st.median(d):+.2f}% | {min(d):+.2f}% to {max(d):+.2f}% | {sum(v < 0 for v in d)}/{sum(v > 0 for v in d)} of {len(d)} |")
