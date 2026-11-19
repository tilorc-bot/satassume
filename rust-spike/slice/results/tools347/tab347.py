"""tab347.py BASE NEW DIR... (sa-port-347): time347.sh's rows as a markdown table: the median wall time (s) of the 12
rounds per workload, mode and arm, and each switch-on arm of NEW against BASE on and against NEW off (ratio of the
medians; * where med347.py's rule calls it beyond the spread)."""
import json, statistics as st, sys
base, new, dirs = sys.argv[1], sys.argv[2], sys.argv[3:]
by = {}
for d in dirs:
    for l in open(d + "/time.jsonl"):
        r = json.loads(l)
        by.setdefault((r["wl"], r["arm"]), {})[r["round"]] = r["s"]


def iq(v):
    q = st.quantiles(sorted(v), n=4)
    return (q[2] - q[0]) / st.median(v)


def rel(wl, a, b):
    xa, xb = by[(wl, a)], by[(wl, b)]
    m = st.median(xa.values()) / st.median(xb.values())
    slower = sum(1 for r in xa if xa[r] > xb[r])
    star = "*" if abs(m - 1) > max(iq(xa.values()), iq(xb.values())) and (slower >= len(xa) - 2 or slower <= 2) else ""
    return f"{100 * (m - 1):+.1f}%{star}"


print("| workload, mode | base off | base on | head off | head on (2500) | head cf | head 8400 | head on / base on | cf / base on | 8400 / base on | head on / head off | base on / base off | largest iqr |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for wl in ("dev", "fuzz", "budget", "wiring"):
    for m in ("py", "rust"):
        arms = [f"{base}:{m}-off", f"{base}:{m}-on32"] + [f"{new}:{m}-{w}" for w in ("off", "on32", "cf", "w8400")]
        med = [f"{st.median(by[(wl, a)].values()):.4f}" for a in arms]
        cells = [rel(wl, arms[3], arms[1]), rel(wl, arms[4], arms[1]), rel(wl, arms[5], arms[1]), rel(wl, arms[3], arms[2]), rel(wl, arms[1], arms[0])]
        print(f"| {wl} {m} | " + " | ".join(med + cells) + f" | {100 * max(iq(by[(wl, a)].values()) for a in arms):.1f}% |")
