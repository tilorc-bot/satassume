"""analyze_k.py RAW: rebuild the tables of RESULT-k.md from a run-k.sh log. Medians over rounds 1 to 6, round 0 a warmup."""
import json
import statistics as st
import sys

rows = []
for line in open(sys.argv[1]):
    if line.startswith("{"):
        rows.append(json.loads(line))
get = {}
for r in rows:
    get[(r["wl"], r["run"], r["round"])] = r
ROUNDS = [str(i) for i in range(1, 7)]
DIGEST = {"dev": "31cd0945c07f02a6", "fuzz": "173502b6ef285ad6"}
for r in rows:
    if "digest" in r and r["digest"] != DIGEST[r["wl"]]:
        raise SystemExit(f"digest differs: {r}")


def series(wl, run, f="T"):
    return [get[(wl, run, x)][f] for x in ROUNDS]


def med(xs):
    return st.median(xs)


def rng(xs):
    return f"{min(xs):.4g} to {max(xs):.4g}"


for wl in ("dev", "fuzz"):
    print(f"\n## {wl}\n")
    base = series(wl, "base", "s")
    print("| run | median s | range s |\n|---|---:|---:|")
    print(f"| base (live pass) | {med(base):.4f} | {rng(base)} |")
    for run in ("py", "pynogc", "pyempty", "rs", "rsfx", "rslto", "rsempty"):
        xs = series(wl, run)
        print(f"| {run} | {med(xs):.5f} | {rng(xs)} |")
    tt, tp, nc = series(wl, "pytape", "T_tape"), series(wl, "pytape", "T_plain"), get[(wl, "pytape", "1")]["calls"]
    print(f"| pytape: tape / plain ({nc} hooks) | {med(tt):.5f} / {med(tp):.5f} | |")
    rt = series(wl, "rstape", "T_tape")
    print(f"| rstape | {med(rt):.6f} | {rng(rt)} |")
    print("\n| | Python s | Rust s | k, median of per-round ratios | range |\n|---|---:|---:|---:|---:|")
    py, rs = series(wl, "py"), series(wl, "rs")
    pe, re_ = series(wl, "pyempty"), series(wl, "rsempty")

    def line(name, a, b):
        ks = [x / y for x, y in zip(a, b)]
        print(f"| {name} | {med(a):.4f} | {med(b):.4f} | **{med(ks):.1f}** | {min(ks):.1f} to {max(ks):.1f} |")
    line("first port: raw", py, rs)
    pnet = [a - e - (t - p) for a, e, t, p in zip(py, pe, tt, tp)]
    rnet = [a - e - t for a, e, t in zip(rs, re_, rt)]
    line("first port: without dispatch and tape bodies", pnet, rnet)
    for run, name in (("rsfx", "memos on a multiplicative hash"), ("rslto", "that + fat LTO, 1 CGU, panic=abort")):
        b = series(wl, run)
        bnet = [a - e - t for a, e, t in zip(b, re_, rt)]
        line(f"tuned, {name}: net", pnet, bnet)
    line("None queries, raw", series(wl, "py", "T_none"), series(wl, "rs", "T_none"))
    line("definite queries, raw", series(wl, "py", "T_def"), series(wl, "rs", "T_def"))
    b = series(wl, "base", "s")
    ts, th, tT = series(wl, "timers", "t_solver"), series(wl, "timers", "t_theory"), series(wl, "timers")
    print("\n| share of a pass | s | of base, median per round |\n|---|---:|---:|")
    print(f"| replay net of dispatch and tape | {med(pnet):.4f} | {med([x / y for x, y in zip(pnet, b)]):.1%} |")
    print(f"| replay raw | {med(py):.4f} | {med([x / y for x, y in zip(py, b)]):.1%} |")
    tn = [s - t for s, t in zip(ts, th)]
    print(f"| live timers: solver minus theories (includes wrapper cost) | {med(tn):.4f} | {med([x / y for x, y in zip(tn, b)]):.1%} |")
    print(f"| live timers: run time, against base | {med(tT):.4f} | {med([x / y for x, y in zip(tT, b)]):.3f}x |")
    print(f"| live timers: theories, for scale | {med(th):.4f} | {med([x / y for x, y in zip(th, b)]):.1%} |")
    gc = [(a - c) / a for a, c in zip(py, series(wl, "pynogc"))]
    print(f"\nCycle collector in the Python replay (timed vs nogc, same round): {med(gc):.1%}.")
