"""livecmp.py A.jsonl B.jsonl [--end-only]: compare two `live.py` runs query by query. Prints the counts and the first
difference of each kind. Exit 0 only if every answer and every session matches and both runs cover the same queries.
--end-only skips the call streams, for a `--check raw` run, which has none."""
import json
import sys


def read(path):
    rows, total = {}, None
    for line in open(path):
        r = json.loads(line)
        if "total" in r:
            total = r["total"]
        else:
            rows[r["q"]] = r
    return rows, total


def main():
    a, ta = read(sys.argv[1])
    b, tb = read(sys.argv[2])
    first = {}
    end_only = "--end-only" in sys.argv
    n = dict(queries_a=len(a), queries_b=len(b), both=0, answer_diff=0, msg_diff=0, session_count_diff=0, sessions=0,
             end_diff=0, stream_diff=0, lra_diff=0, stats_diff=0, group_counts={})
    for q in sorted(set(a) & set(b)):
        x, y = a[q], b[q]
        n["both"] += 1
        if x["ans"] != y["ans"]:
            n["answer_diff"] += 1
            first.setdefault("answer", (q, x["ans"], y["ans"]))
        if x["msg"] != y["msg"]:
            n["msg_diff"] += 1
            first.setdefault("msg", (q, x["msg"][:200], y["msg"][:200]))
        # step 5c10d: the engine's stats view and last_budget_limited after the query (absent in older rows)
        if x.get("eng") != y.get("eng"):
            n["stats_diff"] += 1
            first.setdefault("stats", (q, x.get("eng"), y.get("eng")))
        sx, sy = x.get("sessions", []), y.get("sessions", [])
        if len(sx) != len(sy):
            n["session_count_diff"] += 1
            first.setdefault("session_count", (q, len(sx), len(sy)))
        for i, (u, v) in enumerate(zip(sx, sy)):
            n["sessions"] += 1
            if u["end"] != v["end"]:
                n["end_diff"] += 1
                first.setdefault("end", (q, i))
            if u.get("lra") != v.get("lra"):
                n["lra_diff"] += 1
                first.setdefault("lra", (q, i, v.get("group")))
            g = v.get("group")
            if g:
                g = g.split(":")[0]
                n["group_counts"][g] = n["group_counts"].get(g, 0) + 1
            if not end_only and u["stream"] != v["stream"]:
                n["stream_diff"] += 1
                first.setdefault("stream", (q, i, u["entries"], v["entries"], u["hooks"], v["hooks"]))
    bad = any(v for k, v in n.items() if k.endswith("_diff")) or n["queries_a"] != n["queries_b"] or ta is None or tb is None
    print(json.dumps(n))
    print("first:", json.dumps(first))
    if ta and tb:
        print("answers_sha", ta["answers_sha"], tb["answers_sha"], "| python solvers made", ta["python_solvers_made"],
              tb["python_solvers_made"], "| reentry", len(ta["reentry"]), len(tb["reentry"]))
    print("MATCH" if not bad else "DIFFER")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
