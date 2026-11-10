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
             end_diff=0, stream_diff=0, lra_diff=0, stats_diff=0, moved_diff=0, moved_order_differs=0, moved_open_differs=0, moved_rows=0,
             moved_engine_points=0, group_counts={})
    # the engine memos' insertion order is comparable only under one hash seed (memo_check.py's em_order rule)
    seed = ta and tb and ta.get("hashseed") is not None and ta.get("hashseed") == tb.get("hashseed")
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
        # issue 323: the moved containers (moved_digest.py), absent in older rows. Per `Relations` of the query, one hash per
        # non-empty container; `moved_eng`, where taken, [content, order, len] per process and engine memo.
        mx, my = x.get("moved"), y.get("moved")
        n["moved_rows"] += len(mx or ()) if mx is not None and my is not None else 0
        if mx != my:
            n["moved_diff"] += 1
            names = ["relations %d != %d" % (len(mx or ()), len(my or ()))] if len(mx or ()) != len(my or ()) else sorted(
                {"%d:%s" % (i, k) for i, (u, v) in enumerate(zip(mx, my)) for k in set(u) | set(v) if u.get(k) != v.get(k)})
            first.setdefault("moved", (q, names[:12]))
        ex, ey = x.get("moved_eng"), y.get("moved_eng")
        n["moved_engine_points"] += ex is not None and ey is not None
        if (ex is None) != (ey is None):
            n["moved_diff"] += 1
            first.setdefault("moved_eng", (q, "taken on one side only"))
        elif ex is not None:
            names = sorted(k for k in set(ex) | set(ey) if (ex.get(k) or [None] * 3)[::2] != (ey.get(k) or [None] * 3)[::2])
            # OPEN, not in the verdict, printed every run: `_SPLIT` (5c9b) differs on the clean build of ba1ca22 (twin 2 rows
            # against 4, transfer:7:60 174 against 182); its keys are clause lists by identity. Cause not read (sa-port-238).
            opened = [k for k in names if ":satassume.engine._SPLIT:" in k]
            names = [k for k in names if k not in opened]
            if opened:
                n["moved_open_differs"] += 1
                first.setdefault("moved_open", (q, [(k, ex.get(k), ey.get(k)) for k in opened]))
            if names:
                n["moved_diff"] += 1
                first.setdefault("moved_eng", (q, [(k, ex.get(k), ey.get(k)) for k in names[:6]]))
            names = sorted(k for k in set(ex) & set(ey) if ex[k][1] != ey[k][1] and k not in names)
            if names and seed:
                n["moved_order_differs"] += 1
                first.setdefault("moved_order", (q, names[:6]))
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
    if ta and tb and (ta.get("moved") or tb.get("moved")):     # which containers the comparison saw non-empty: a zero is void
        fa, fb = (t.get("moved", {}).get("filled", {}) for t in (ta, tb))
        print("moved filled (a, b):", json.dumps({k: (fa.get(k, 0), fb.get(k, 0)) for k in sorted(set(fa) | set(fb))}))
        print("moved src:", json.dumps([t.get("moved", {}).get("src") for t in (ta, tb)]), "| unread",
              json.dumps([t.get("moved", {}).get("unread") for t in (ta, tb)]), "| names_differ",
              json.dumps(tb.get("moved", {}).get("names_differ")), "| order compared:", bool(seed))
    if ta and tb:
        print("answers_sha", ta["answers_sha"], tb["answers_sha"], "| python solvers made", ta["python_solvers_made"],
              tb["python_solvers_made"], "| reentry", len(ta["reentry"]), len(tb["reentry"]))
    print("MATCH" if not bad else "DIFFER")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
