"""Persistent-solver plan, stage 0: search cost against session size.

    python gs0_search_cost.py LOG [LOG ...]

For each per-query log (``refine_replay.py --log`` / ``gs0_pollution.py``):
top-level queries whose path includes "search" (``nested == 0``), bucketed
by the answering session's variable count at the search (largest ``nvars``
of its solves); per bucket the number of queries, median query ms, median
decisions per query (both searches of ``entails`` summed), and the
decisions per variable.  Also totals: ms in searching queries, ms in all
queries, and a least-squares line ms = a + b * nvars over searching
queries.
"""
import json
import statistics
import sys

BUCKETS = [0, 100, 200, 400, 800, 1600, 3200, 10**9]


def load(path):
    return [json.loads(line) for line in open(path)]


for path in sys.argv[1:]:
    rows = load(path)
    total = sum(r["ms"] for r in rows)
    srch = [r for r in rows if "search" in r["path"] and r.get("nested", 0) == 0 and r["solves"]]
    print(f"\n{path}: {len(rows)} queries, {total:.0f} ms logged; {len(srch)} searching, "
          f"{sum(r['ms'] for r in srch):.0f} ms")
    print(f"  {'vars':>11s} {'queries':>8s} {'ms med':>8s} {'ms mean':>8s} {'dec med':>8s} {'dec/var':>8s}")
    for lo, hi in zip(BUCKETS, BUCKETS[1:]):
        b = [r for r in srch if lo <= max(s["nvars"] for s in r["solves"]) < hi]
        if not b:
            continue
        ms = [r["ms"] for r in b]
        dec = [sum(s["decisions"] for s in r["solves"]) for r in b]
        dv = [d / max(s["nvars"] for s in r["solves"]) for d, r in zip(dec, b)]
        print(f"  {lo:>5d}-{hi if hi < 10**9 else 'inf':<5} {len(b):8d} {statistics.median(ms):8.2f} "
              f"{sum(ms)/len(ms):8.2f} {statistics.median(dec):8.0f} {statistics.median(dv):8.2f}")
    xs = [max(s["nvars"] for s in r["solves"]) for r in srch]
    ys = [r["ms"] for r in srch]
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    print(f"  fit: ms = {my - b * mx:.3f} + {b * 1000:.3f} * nvars / 1000; nvars median {statistics.median(xs):.0f}, max {max(xs)}")
