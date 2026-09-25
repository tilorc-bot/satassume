"""Sessions by reason and time shares from a per-query log (tools/query_log.py).

    python agent-reports/2026-09-perf-rounds/scripts/log_census.py ~/.cache/satassume/log-747fb0e.jsonl
"""
import json, sys
from collections import Counter
from statistics import median
R = [json.loads(l) for l in open(sys.argv[1])]
tot = sum(r["ms"] for r in R)
print(f"{len(R)} queries, logged {tot:.0f} ms; built {sum(r['built'] for r in R)} sessions")
by = {}
for r in R:
    k = r["session_new"] or ("memo" if r["via"] == "memo" else "none")
    if r.get("session_error"):
        k += " (" + r["session_error"] + ")"
    by.setdefault(k, []).append(r["ms"])
print(f"{'session_new':28s} {'queries':>8s} {'ms':>8s} {'share':>7s} {'median':>7s}")
for k, v in sorted(by.items(), key=lambda kv: -sum(kv[1])):
    print(f"{k:28s} {len(v):8d} {sum(v):8.0f} {100 * sum(v) / tot:6.1f}% {median(v):7.2f}")
P = Counter(); M = Counter()
for r in R:
    p = ">".join(r["path"]) if r["via"] != "memo" else "memo"
    P[p] += 1; M[p] += r["ms"]
print(f"{'path':52s} {'queries':>8s} {'ms':>8s} {'share':>7s}")
for k, v in sorted(M.items(), key=lambda kv: -kv[1]):
    print(f"{k or '(empty)':52s} {P[k]:8d} {v:8.0f} {100 * v / tot:6.1f}%")
s = [x for r in R for x in r["solves"]]
print(f"solves {len(s)}, decisions {sum(x['decisions'] for x in s)}, conflicts {sum(x['conflicts'] for x in s)}")
