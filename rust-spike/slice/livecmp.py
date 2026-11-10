"""livecmp.py A.jsonl B.jsonl [--end-only]: compare two `live.py` runs query by query. Prints the counts and the first
difference of each kind. Exit 0 only if every answer and every session matches and both runs cover the same queries.
--end-only skips the call streams, for a `--check raw` run, which has none."""
import json
import os
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
             end_diff=0, stream_diff=0, lra_diff=0, stats_diff=0, moved_diff=0, moved_order_differs=0, moved_rows=0,
             moved_engine_points=0, moved_known_diff=0, moved_native_diff=0, moved_lra_python_only=0, group_counts={})
    # The known differences (the planner's (A) ruling of 10 Nov, corrected by sa-port-239's read): Rust's atom templates
    # bypass the pattern cache, so `_SPLIT` holds second copies on Rust and `_CACHE` fewer keys. known_moved.json lists, per
    # workload and engine point, `[_SPLIT python, rust, _CACHE python, rust]`; any other counts are a DIFFER, and a workload
    # with no row must have equal counts.
    known_all = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_moved.json")))
    py_rust = (ta or {}).get("mode") == "py" and (tb or {}).get("mode") == "rust"
    # a row holds for one order of the queries and one hash seed: "<wl>", "<wl>@seed1", "<wl>@shuffle3"
    wl = None
    if py_rust and ta.get("hashseed") == tb.get("hashseed") and ta.get("shuffle") == tb.get("shuffle") and ta.get("wl") == tb.get("wl"):
        wl = ta["wl"] + ("" if ta.get("hashseed") in (None, "0") else "@seed" + ta["hashseed"]) + (
            "@shuffle%d" % ta["shuffle"] if ta.get("shuffle") else "")
    known = known_all.get(wl, [])
    known_seen = []
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
                {"%d:%s" % (i, k) for i, (u, v) in enumerate(zip(mx or (), my or ())) for k in set(u) | set(v) if u.get(k) != v.get(k)})
            first.setdefault("moved", (q, names[:12]))
        # the extension's per-query row: the query's sessions (state part 3's containers, scalars, handles), the LRA slot's
        # entries and the engines built in the query
        qx, qy = dict(x.get("moved_q") or {}), dict(y.get("moved_q") or {})
        n["moved_lra_python_only"] += len(set(qx.get("lra", ())) - set(qy.get("lra", ())))
        if py_rust and set(qy.get("lra", ())) <= set(qx.get("lra", ())):
            qx.pop("lra", None), qy.pop("lra", None)        # Rust's slot entries are all among Python's calls of the query
        if qx != qy:
            n["moved_diff"] += 1
            names = []
            for part in sorted(set(qx) | set(qy)):
                u, v = qx.get(part), qy.get(part)
                if u == v:
                    continue
                if part == "lra":
                    names.append("lra: %d entries on b only (a %d, b %d)" % (len(set(v or ()) - set(u or ())), len(u or ()), len(v or ())))
                elif u is None or v is None or len(u) != len(v):
                    names.append("%s %s != %s" % (part, len(u or ()), len(v or ())))
                else:
                    names += ["%s%d:%s" % (part, i, k) for i, (c, d) in enumerate(zip(u, v)) for k in sorted(set(c) | set(d))
                              if c.get(k) != d.get(k)]
            first.setdefault("moved_q", (q, names[:12]))
        ex, ey = x.get("moved_eng"), y.get("moved_eng")
        n["moved_engine_points"] += ex is not None and ey is not None
        if (ex is None) != (ey is None):
            n["moved_diff"] += 1
            first.setdefault("moved_eng", (q, "taken on one side only"))
        elif ex is not None:
            # `_SPLIT` by its distinct rows and their number, `_CACHE` by its keys only where no difference is known; their
            # counts against the known row of this engine point. Everything else by content (a multiset) and length.
            sk = [k for k in set(ex) | set(ey) if ":satassume.engine._SPLIT:" in k]
            got = [(ex.get(k) or [None] * 3)[2] for k in sk[:1]] + [(ey.get(k) or [None] * 3)[2] for k in sk[:1]] + [
                (ex.get("process:_CACHE") or [None] * 3)[2], (ey.get("process:_CACHE") or [None] * 3)[2]]
            at = n["moved_engine_points"] - 1
            want = known[at] if at < len(known) else None
            known_seen.append(got)
            if got != want and (want is not None or got[0] != got[1] or got[2] != got[3]):
                n["moved_known_diff"] += 1
                first.setdefault("moved_known", (q, "point %d: _SPLIT python, rust, _CACHE python, rust" % at, got, "known", want))
            skip = set(sk) | ({"process:_CACHE"} if got[2] != got[3] else set())
            names = sorted(k for k in set(ex) | set(ey) if k not in skip and (ex.get(k) or [None] * 3)[::2] != (ey.get(k) or [None] * 3)[::2])
            names += sorted(k for k in sk if (ex.get(k) or [None] * 4)[::3] != (ey.get(k) or [None] * 4)[::3])
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
    if len(known_seen) < len(known) and ta.get("moved") and tb.get("moved"):       # a known row whose engine point never came
        n["moved_known_diff"] += len(known) - len(known_seen)
        first.setdefault("moved_known", ("end", "engine points", len(known_seen), "known rows", len(known)))
    # 5c9a's native tables: rows that differ from what they cache (moved_digest._native)
    n["moved_native_diff"] = sum(len((t or {}).get("moved", {}).get("native_bad", ())) for t in (ta, tb))
    bad = any(v for k, v in n.items() if k.endswith("_diff")) or n["queries_a"] != n["queries_b"] or ta is None or tb is None
    print(json.dumps(n))
    print("first:", json.dumps(first))
    if ta and tb and (ta.get("moved") or tb.get("moved")):     # which containers the comparison saw non-empty: a zero is void
        fa, fb = (t.get("moved", {}).get("filled", {}) for t in (ta, tb))
        print("moved filled (a, b):", json.dumps({k: (fa.get(k, 0), fb.get(k, 0)) for k in sorted(set(fa) | set(fb))}))
        print("moved src:", json.dumps([t.get("moved", {}).get("src") for t in (ta, tb)]), "| unread",
              json.dumps([t.get("moved", {}).get("unread") for t in (ta, tb)]), "| names_differ",
              json.dumps(tb.get("moved", {}).get("names_differ")), "| order compared:", bool(seed))
        print("moved known differences, inside the verdict (_SPLIT python, rust, _CACHE python, rust per engine point):",
              json.dumps(known_seen), "| known rows (%s):" % wl, json.dumps(known), "| native rows checked, bad:",
              json.dumps([[t.get("moved", {}).get(k) for k in ("native_checked", "native_bad")] for t in (ta, tb)]),
              "| sessions, engines in queries, lra entries:",
              json.dumps([[t.get("moved", {}).get(k) for k in ("sessions", "engines", "lra_entries")] for t in (ta, tb)]))
    if ta and tb:
        print("answers_sha", ta["answers_sha"], tb["answers_sha"], "| python solvers made", ta["python_solvers_made"],
              tb["python_solvers_made"], "| reentry", len(ta["reentry"]), len(tb["reentry"]))
    print("MATCH" if not bad else "DIFFER")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
