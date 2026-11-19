"""bs347.py GATEDIR... (sa-port-347, issue 323): the budget workload's rows of gate330.sh (live.py --check entry: after
each query the default engine's stats and last_budget_limited, and the state comparison's moved ids). Per directory and
mode, switch on against off: the over-budget queries (budget_limited rose in that query with the switch off), and on
them whether the answer, the message, last_budget_limited, the stats' rise in the query, the whole of the stats and the
moved ids are the same. Then the same counts over all rows, and the stats keys that differ anywhere."""
import collections, json, os, sys


def rows(f):
    out, prev = [], {}
    for l in open(f):
        r = json.loads(l)
        if "eng" not in r:      # the trailer rows (totals)
            continue
        st = dict(r["eng"][0])
        r["st"], r["lim"] = st, r["eng"][1]
        r["rise"] = {k: v - prev.get(k, 0) for k, v in st.items()}
        prev = st
        out.append(r)
    return out


bad = 0
for d in sys.argv[1:]:
    for m in ("py", "rust"):
        f0, f1 = f"{d}/budget-{m}-0.jsonl", f"{d}/budget-{m}-1.jsonl"
        if not (os.path.exists(f0) and os.path.exists(f1)):
            print(os.path.basename(d), m, "NO ROWS"); bad += 1; continue
        off, on = rows(f0), rows(f1)
        over = [i for i, r in enumerate(off) if r["rise"].get("budget_limited", 0) > 0]
        over_on = [i for i, r in enumerate(on) if r["rise"].get("budget_limited", 0) > 0]
        keys = collections.Counter()

        def same(idx):
            c = collections.Counter()
            for i in idx:
                a, b = off[i], on[i]
                c["ans"] += a["ans"] == b["ans"]; c["msg"] += a["msg"] == b["msg"]; c["limited"] += a["lim"] == b["lim"]
                c["rise"] += a["rise"] == b["rise"]; c["stats"] += a["st"] == b["st"]; c["moved"] += a.get("moved") == b.get("moved")
                for k in a["st"]:
                    if a["st"][k] != b["st"].get(k):
                        keys[k] += 1
            return " ".join(f"{k} {c[k]}/{len(idx)}" for k in ("ans", "msg", "limited", "rise", "stats", "moved"))

        ok = len(off) == len(on) and over == over_on
        s_over = same(over)
        if not ok or not over or s_over.count(f" {len(over)}/{len(over)}") != 6:
            bad += 1
        print(os.path.basename(d), m, f"rows {len(off)}/{len(on)}; over budget off {over} on {over_on}; limited True off {sum(r['lim'] for r in off)} on {sum(r['lim'] for r in on)}")
        print("   over-budget rows, on == off:", s_over)
        keys.clear()
        print("   all rows, on == off:        ", same(range(min(len(off), len(on)))), "| stats keys that differ (rows):", dict(keys))
        print("   last row's stats off:", off[-1]["st"]); print("   last row's stats on: ", on[-1]["st"])
print("BS", "every over-budget row equal on against off in every directory and mode" if not bad else f"{bad} cells with a difference on an over-budget row (or no rows)")
