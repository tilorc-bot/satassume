"""pair317.py TIME.JSONL A H (sa-port-317): pinned wall per arm (median, min-max, n) and the paired per-round change
between arms of the same round (median, min-max of the per-round percentages), dev and fuzz. Checks digests and that
each row's process had the frames its arm names."""
import json, statistics as st, sys, collections
rows = [json.loads(l) for l in open(sys.argv[1])]; A, H = sys.argv[2], sys.argv[3]
DIG = dict(dev="31cd0945c07f02a6", fuzz="173502b6ef285ad6")
bad = [r for r in rows if r["digest"] != DIG[r["wl"]]]
fr = collections.Counter((("+frames" in r["sha"]), str(r.get("term_frames"))) for r in rows)
print(f"rows {len(rows)}; digest mismatches {len(bad)}; (arm has +frames, term_frames recorded): {dict(fr)}")
g = collections.defaultdict(dict)
for r in rows: g[r["sha"], r["wl"]][r["round"]] = r["s"]
arms = [f"{A}+frames", f"{H}+frames", f"{A}+rust+frames", f"{H}+rust+frames", H, f"{H}+rust"]
for wl in ("dev", "fuzz"):
    print(f"\n### {wl}\n| arm | median s (min-max, n) |\n|---|---|")
    for a in arms:
        v = list(g[a, wl].values())
        if v: print(f"| {a} | {st.median(v):.3f} ({min(v):.3f}-{max(v):.3f}, {len(v)}) |")
    print(f"\n| paired per round ({wl}) | median | min to max | rounds better/worse |\n|---|---|---|---|")
    for b, a in ((f"{A}+frames", f"{H}+frames"), (f"{A}+rust+frames", f"{H}+rust+frames"), (H, f"{H}+frames"), (f"{H}+rust", f"{H}+rust+frames")):
        x, y = g[b, wl], g[a, wl]; d = [100 * (y[r] - x[r]) / x[r] for r in sorted(x) if r in y]
        if d: print(f"| {b} -> {a} | {st.median(d):+.2f}% | {min(d):+.2f}% to {max(d):+.2f}% | {sum(v < 0 for v in d)}/{sum(v > 0 for v in d)} of {len(d)} |")
