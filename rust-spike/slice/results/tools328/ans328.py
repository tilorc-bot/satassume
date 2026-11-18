"""ans328.py OUT WL... (sa-port-328): per workload and mode, live.py's rows with SLICE_WITNESS=1 against =0: queries,
answers that differ (the gate: 0), messages that differ, rows whose engine stats differ (expected: a certified query
is counted nowhere in Engine.stats), and the queries the last stats row counts (off -> on)."""
import json, os, sys
out, wls = sys.argv[1], sys.argv[2:]
bad = 0
print("workload mode queries answer_diff msg_diff stats_rows_differ engine_queries_off->on")
for wl in wls:
    for m in ("py", "rust"):
        fa, fb = (f"{out}/{wl}-{m}-{sw}.jsonl" for sw in (0, 1))
        if not (os.path.exists(fa) and os.path.exists(fb)):
            continue
        a = [json.loads(l) for l in open(fa) if l.startswith('{"q"')]
        b = [json.loads(l) for l in open(fb) if l.startswith('{"q"')]
        ad = [(x["q"], x["ans"], y["ans"]) for x, y in zip(a, b) if x["ans"] != y["ans"]]
        md = sum(x.get("msg") != y.get("msg") for x, y in zip(a, b))
        sd = sum(x.get("eng") != y.get("eng") for x, y in zip(a, b))
        qs = [dict(r[-1]["eng"][0]).get("queries") if r and r[-1].get("eng") else None for r in (a, b)]
        ok = len(a) == len(b) and len(a) > 0 and not ad
        bad += not ok
        print(wl, m, f"{len(a)}/{len(b)}", len(ad), md, sd, f"{qs[0]}->{qs[1]}", "" if ok else "DIFFER " + repr(ad[:5]))
print("GATE", "answers equal" if not bad else f"{bad} rows differ")
