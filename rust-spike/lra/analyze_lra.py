"""analyze_lra.py RAW: rebuild results/tables-lra.md from a run-lra.sh log and cross/combine.py's model. Medians of per-round
ratios over rounds 1 to 6. "def" means "not None", as combine.py has it: definite + other (fuzz's other are raises and 'unknown'
shapes; meta["cls"] separates them, combine.py doesn't)."""
import contextlib
import io
import json
import os
import runpy
import statistics as st
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.argv, raw = [sys.argv[0]], sys.argv[1]
with contextlib.redirect_stdout(io.StringIO()):
    C = runpy.run_path(os.path.join(HERE, "..", "cross", "combine.py"))
M = C["M"]
get = {}
for line in open(raw):
    if line.startswith("{"):
        d = json.loads(line)
        get[(d["wl"], d["run"], d["round"])] = d
        if "digest" in d and d["digest"] != {"dev": "31cd0945c07f02a6", "fuzz": "173502b6ef285ad6"}[d["wl"]]:
            raise SystemExit(f"digest differs: {d}")
R = [str(i) for i in range(1, 7)]
WLS, CLS = ("dev", "fuzz"), ("all", "none", "def")
CN = {"all": "whole pass", "none": "None", "def": "definite"}
med = st.median
OUT = []
p = OUT.append


def cl(d, c):
    x = d["classes"]
    return d["T"] if c == "all" else x["none"] if c == "none" else x["definite"] + x["other"]


def tm(d, c, f):
    x = d["classes"]
    return sum(x[k][f] for k in ({"all": x, "none": ["none"], "def": ["definite", "other"]}[c]))


def rng(xs, f=".1f"):
    return f"{min(xs):{f}} to {max(xs):{f}}"


def kseries(w, c, run, net=True):
    out = []
    for r in R:
        a = cl(get[(w, "py", r)], c) - (cl(get[(w, "pyempty", r)], c) if net else 0)
        b = cl(get[(w, run, r)], c) - (cl(get[(w, "rsempty", r)], c) if net else 0)
        out.append(a / b)
    return out


p("## Replay, seconds, medians over six rounds\n")
p("| | class | py | pyempty | rs | rsfx | rslto | rsempty |\n|---|---|---:|---:|---:|---:|---:|---:|")
for w in WLS:
    for c in CLS:
        cells = [med(cl(get[(w, x, r)], c) for r in R) for x in ("py", "pyempty", "rs", "rsfx", "rslto", "rsempty")]
        p(f"| {w} | {CN[c]} | " + " | ".join(f"{x:.5f}" for x in cells) + " |")
p("\n## k_lra, median of per-round ratios (range)\n")
p("| | class | first port (rs), net | raw | fxhash, net | fxhash + LTO, net |\n|---|---|---:|---:|---:|---:|")
K = {}
for w in WLS:
    for c in CLS:
        ks = {x: kseries(w, c, x) for x in ("rs", "rsfx", "rslto")}
        K[w, c] = med(ks["rs"])
        K[w, c, "rslto"] = med(ks["rslto"])
        K[w, c, "lo"] = min(ks["rs"])
        raw_k = kseries(w, c, "rs", net=False)
        p(f"| {w} | {CN[c]} | **{med(ks['rs']):.1f}** ({rng(ks['rs'])}) | {med(raw_k):.1f} ({rng(raw_k)}) | "
          f"{med(ks['rsfx']):.1f} ({rng(ks['rsfx'])}) | {med(ks['rslto']):.1f} ({rng(ks['rslto'])}) |")

p("\n## Shares of the live pass, from `record_lra.py --timers`, medians (range)\n")
p("| | class | class s | rational sessions | sessions with constants | replay py net / base |\n|---|---|---:|---:|---:|---:|")
SH = {}
for w in WLS:
    for c in CLS:
        Ts = [tm(get[(w, "timers", r)], c, "T") for r in R]
        ra = [tm(get[(w, "timers", r)], c, "rational") / t for r, t in zip(R, Ts)]
        co = [tm(get[(w, "timers", r)], c, "constants") / t for r, t in zip(R, Ts)]
        key = {"all": "s", "none": "none_s", "def": "def_s"}[c]
        rep = [(cl(get[(w, "py", r)], c) - cl(get[(w, "pyempty", r)], c)) / get[(w, "base", r)][key] for r in R]
        SH[w, c] = (med(ra), med(co))
        p(f"| {w} | {CN[c]} | {med(Ts):.3f} | {100 * med(ra):.1f}% ({rng([100 * x for x in ra])}) | "
          f"{100 * med(co):.1f}% ({rng([100 * x for x in co])}) | {100 * med(rep):.1f}% |")
p("\nConstants sessions are outside k_lra: their time is in r - c, so k_rest has to cover them.\n")


def krest(S, X, Rs, r, c, k):
    """(the factor for 2x, or the non-positive denominator)"""
    d = .5 - S - X - Rs - c / k
    return ((r - c) / d, d) if d > 0 else (None, d)


def text(v):
    return f"{v[0]:.2f}" if v[0] is not None else f"impossible (den {v[1]:.3f})"


def sp(S, X, Rs, r, c, k, kr):
    return 1 / (S + X + Rs + c / k + (r - c) / kr)


for name, S, X in (("As the code stands", "St", "Xt"), ("Integer ids", "Si", "Xi")):
    p(f"\n## Whole-pass model, {name}: k = 12.9 / 15.2, k_lra first port by class; c = rational sessions; constants in k_rest\n")
    p("| | class | c | r low-high | k_lra | k_rest=1 | 3 | 5 | 10 | inf | k_rest for 2x, low end | high end | same, LTO k_lra |")
    p("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for w in WLS:
        for c in CLS:
            x = M[w][c]
            share, k = SH[w, c][0], K[w, c]
            lo = (x[S + "_hi"], x[X + "_hi"], x["rs_lo"], x["r_hi"])    # the low end of the speedup, as combine.py
            hi = (x[S + "_lo"], x[X + "_lo"], x["rs"], x["r_lo"])
            cells = []
            for kr in (1, 3, 5, 10, float("inf")):
                a, b = sp(*lo, share, k, kr), sp(*hi, share, k, kr)
                cells.append(f"{min(a, b):.2f}-{max(a, b):.2f}")
            kl, kh = krest(*lo, share, k), krest(*hi, share, k)
            kl2, kh2 = krest(*lo, share, K[w, c, "rslto"]), krest(*hi, share, K[w, c, "rslto"])
            p(f"| {w} | {CN[c]} | {100 * share:.1f}% | {100 * min(x['r_hi'], x['r_lo']):.1f}-{100 * max(x['r_hi'], x['r_lo']):.1f}% | "
              f"{k:.1f} | " + " | ".join(cells) + f" | {text(kl)} | {text(kh)} | {text(kl2)} to {text(kh2)} |")
p("\n## k_rest for 2x, low end to high end, three ways\n")
p("Earlier k_r: one factor on all of r, from combine.py. Constants in k_rest: as above. Constants stay in Python: their share at factor 1, k_rest on the remainder.\n")
p("| | class | as it stands: earlier k_r | constants in k_rest | constants stay in Python | ids: earlier k_r | constants in k_rest | constants stay in Python |")
p("|---|---|---:|---:|---:|---:|---:|---:|")
for w in WLS:
    for c in CLS:
        x, (share, con), k = M[w][c], SH[w, c], K[w, c]
        cells = []
        for S, X in (("St", "Xt"), ("Si", "Xi")):
            lo = (x[S + "_hi"], x[X + "_hi"], x["rs_lo"], x["r_hi"])
            hi = (x[S + "_lo"], x[X + "_lo"], x["rs"], x["r_lo"])
            cells.append(f"{text(krest(*lo, 0, 1))} to {text(krest(*hi, 0, 1))}")
            cells.append(f"{text(krest(*lo, share, k))} to {text(krest(*hi, share, k))}")
            stay = [krest(v[0] + con, v[1], v[2], v[3] - con, share, k) for v in (lo, hi)]
            cells.append(f"{text(stay[0])} to {text(stay[1])}")
        p(f"| {w} | {CN[c]} | " + " | ".join(cells) + " |")
text_out = "\n".join(OUT) + "\n"
open(os.path.join(HERE, "results", "tables-lra.md"), "w").write(text_out)
print(text_out)
