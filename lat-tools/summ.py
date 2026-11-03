"""Summarise cost.jsonl: per workload, medians over rounds."""
import json
import sys
from statistics import median
from collections import defaultdict

rows = [json.loads(l) for l in open(sys.argv[1])]
by = defaultdict(lambda: defaultdict(list))
for r in rows:
    by[r["spec"]][r["mode"]].append(r)
for w, d in by.items():
    B, P = d["base"], d.get("latds", [])
    tot = median(r["total_s"] for r in B)
    out = {"workload": w, "rounds": len(B), "base_s": round(tot, 3),
           "none_frac": round(median(r["none_s"] / r["total_s"] for r in B), 3),
           "exh_checks": B[0]["exh"], "exh_queries": B[0]["exh_queries"],
           "exh_check_frac": round(median(r["exh_s"] / r["total_s"] for r in B), 4),
           "all_check_frac": round(median(r["check_s"] / r["total_s"] for r in B), 4),
           "exh_query_frac": round(median(r["exhq_s"] / r["total_s"] for r in B), 4)}
    if P:
        flags = B[0]["exh_flags"]
        # per-query paired saving on base's exhausting queries, round by round
        sav, rest = [], []
        for b, p in zip(sorted(B, key=lambda r: r["round"]), sorted(P, key=lambda r: r["round"])):
            s = sum(bq - pq for bq, pq, f in zip(b["perq_us"], p["perq_us"], flags) if f) / 1e6
            o = sum(bq - pq for bq, pq, f in zip(b["perq_us"], p["perq_us"], flags) if not f) / 1e6
            sav.append(s / b["total_s"])
            rest.append(o / b["total_s"])
        out.update(proto_s=round(median(r["total_s"] for r in P), 3),
                   speedup=round(tot / median(r["total_s"] for r in P), 3),
                   proto_exh=P[0]["exh"],
                   saved_on_exh_queries=[round(x, 4) for x in sav],
                   delta_other_queries=[round(x, 4) for x in rest],
                   answers_same=len({r["answers_sha"] for r in B + P}) == 1)
    print(json.dumps(out))
