"""step5_report.py OUT.jsonl: the tables for results/step5-timing.md from `run-slice.sh`'s output. Round 0 of each seed is a warmup and is dropped.
Each ratio is Python over Rust within one round of one seed (the runs next to each other), then the median, with the range over rounds."""
import collections
import json
import statistics as st
import sys

PIN = {"dev": "31cd0945c07f02a6", "fuzz": "173502b6ef285ad6"}
# Measured counts from step 3 (results/step3-live.md): theory hooks, and outermost solver calls. Costs in ns from ../results/tables-cross.md, gross.
HOOKS = {"dev": 34788, "fuzz": 1241630}
CALLS = {"dev": 46214, "fuzz": 687993}
COST = {"full": (37.1, 27.4), "abi3": (80.1, 54.9)}  # o.m(i) by interned name; one int in, one out
SAME_PY = (14.0, 12.5)  # the same two calls made from Python, net of the loop

rows = [json.loads(line) for line in open(sys.argv[1])]
print(f"runs {len(rows)}")
bad = [(r["seed"], r["round"], r["backend"], r["wl"], r["digest"]) for r in rows if r["digest"] != PIN[r["wl"]]]
print("digests off the pin:", bad or "none")
print("modules:", sorted({(r["backend"], r["so"]) for r in rows}, key=str))
print("runs per seed, backend, wl (warmups included):", sorted(collections.Counter((r["seed"], r["backend"], r["wl"]) for r in rows).items())[:3], "...")
ans = {}
for r in rows:
    a = ans.setdefault(r["wl"], r["ans"])
    if a != r["ans"]:
        print("ANSWERS DIFFER", r["seed"], r["round"], r["backend"], r["wl"])


def klass(a):
    return "None" if a is None else "definite" if a is True or a is False else "other"


idx = {wl: {c: [i for i, x in enumerate(a) if klass(x) == c] for c in ("None", "definite", "other")} for wl, a in ans.items()}
for wl in idx:
    print(wl, {c: len(v) for c, v in idx[wl].items()}, "non-bool answers:", collections.Counter(x for x in ans[wl] if klass(x) == "other"))

T = collections.defaultdict(dict)
for r in rows:
    if r["round"] == 0:
        continue
    per = r["per"]
    s = {"whole": r["s"]}
    for c, v in idx[r["wl"]].items():
        s[c] = sum(per[i] for i in v)
    T[(r["wl"], r["seed"], r["round"])][r["backend"]] = s


def summary(wl, cls, seeds):
    keys = [k for k in T if k[0] == wl and k[1] in seeds]
    out = {}
    for b in ("py", "full", "abi3"):
        out[b] = st.median(T[k][b][cls] for k in keys)
    for b in ("full", "abi3"):
        q = [T[k]["py"][cls] / T[k][b][cls] for k in keys]
        out["x" + b] = (st.median(q), min(q), max(q))
    out["n"] = len(keys)
    return out


def row(label, wl, cls, seeds):
    x = summary(wl, cls, seeds)
    f, a = x["xfull"], x["xabi3"]
    print(f"| {label} | {x['n']} | {x['py']:.3f} | {x['full']:.3f} | {x['abi3']:.3f} | **{f[0]:.3f}** ({f[1]:.3f} to {f[2]:.3f}) | **{a[0]:.3f}** ({a[1]:.3f} to {a[2]:.3f}) |")


print("\n| class | rounds | Python, s | Rust full API, s | Rust abi3, s | speedup full API | speedup abi3 |\n|---|---:|---:|---:|---:|---:|---:|")
for wl in ("dev", "fuzz"):
    for cls in ("whole", "None", "definite"):
        row(f"{wl}, {cls}", wl, cls, {0})
print("\nBy seed, whole pass:\n\n| wl | seed | rounds | Python, s | Rust full API, s | Rust abi3, s | speedup full API | speedup abi3 |\n|---|---:|---:|---:|---:|---:|---:|---:|")
for wl in ("dev", "fuzz"):
    for seed in (0, 1, 2):
        x = summary(wl, "whole", {seed})
        f, a = x["xfull"], x["xabi3"]
        print(f"| {wl} | {seed} | {x['n']} | {x['py']:.3f} | {x['full']:.3f} | {x['abi3']:.3f} | {f[0]:.3f} ({f[1]:.3f} to {f[2]:.3f}) | {a[0]:.3f} ({a[1]:.3f} to {a[2]:.3f}) |")

print("\nCrossings, seed 0 medians:\n\n| wl | backend | hooks | solver calls | charge, s (gross) | % of that Rust pass | net of the same calls in Python, s | time removed, s (% of Python pass) |\n|---|---|---:|---:|---:|---:|---:|---:|")
for wl in ("dev", "fuzz"):
    x = summary(wl, "whole", {0})
    for b in ("full", "abi3"):
        h, c = COST[b]
        gross = (HOOKS[wl] * h + CALLS[wl] * c) * 1e-9
        net = (HOOKS[wl] * (h - SAME_PY[0]) + CALLS[wl] * (c - SAME_PY[1])) * 1e-9
        print(f"| {wl} | {b} | {HOOKS[wl]:,} | {CALLS[wl]:,} | {gross:.4f} | {100 * gross / x[b]:.1f} | {net:.4f} | {x['py'] - x[b]:.3f} ({100 * (x['py'] - x[b]) / x['py']:.1f}) |")
print("\nabi3 minus full API, live, paired per round:\n")
for wl in ("dev", "fuzz"):
    keys = [k for k in T if k[0] == wl and k[1] == 0]
    d = [T[k]["abi3"]["whole"] - T[k]["full"]["whole"] for k in keys]
    m = st.median(d)
    n = HOOKS[wl] + CALLS[wl]
    pred = (HOOKS[wl] * (COST["abi3"][0] - COST["full"][0]) + CALLS[wl] * (COST["abi3"][1] - COST["full"][1])) * 1e-9
    print(f"- {wl}: {m:.4f} s ({min(d):.4f} to {max(d):.4f}) over {n:,} crossings, {m / n * 1e9:.0f} ns each; the micro table predicts {pred:.4f} s")
