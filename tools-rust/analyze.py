"""analyze.py results/pinned.jsonl: tables for REPORT-rust-ceiling.md. Medians over rounds 1-6.

Rows of S (share of a pass that stays in Python, the rest gets k times faster):
  S0    outside the boundary timers (bdry).
  S1    as the code stands: S0 + SymPy frames inside the boundary + encoding the query (enc q).
        SymPy time: calibrated monitoring (the high estimate) and the sampler (the low one).
  S1x   S1 + a crossing charge per outermost SymPy ask inside (no Rust: stated, not measured).
  S2    resolved before the boundary, optimistic: S0 + enc cl; every ask inside is free.
  S3    resolved, realistic: S2 + the asks other than hash and eq, still run once in Python.
  S4    the fn groups stay in Python whole: S0 + groups + SymPy frames outside them + enc q.
"""
import json
import statistics as st
import sys
from collections import defaultdict

rows = [json.loads(x) for x in open(sys.argv[1]) if x.startswith("{")]
WANT = {"dev": "31cd0945c07f02a6", "fuzz": "173502b6ef285ad6"}
med = st.median
ROUNDS = {str(i) for i in range(1, 7)}
HASHEQ = ("hash", "eq")


def cat_of(name):
    """Category of an outermost SymPy entry (module path:qualname)."""
    q = name.split(":")[-1].split(".")[-1]
    if q == "__hash__":
        return "hash"
    if q in ("__eq__", "__ne__"):
        return "eq"
    if q in ("default_sort_key", "sort_key", "compare", "ordered", "_sorted_args", "cmp_to_key"):
        return "order"
    if q in ("__new__", "__call__", "_func", "__sympifyit_wrapper", "sympify", "_sympify", "_new_rawargs",
             "_from_args", "fromiter", "__neg__", "__pos__", "__abs__", "__add__", "__radd__", "__sub__",
             "__rsub__", "__mul__", "__rmul__", "__truediv__", "__rtruediv__", "__pow__", "__rpow__",
             "__floordiv__", "__mod__", "__rmod__", "__divmod__", "subs", "xreplace", "_new", "func_wrapper"):
        return "construct"
    if q in ("free_symbols", "atoms", "has", "is_number", "count", "_has", "preorder_traversal"):
        return "walk"
    if q in ("args", "func", "function", "arguments", "make_args", "accessor", "name", "as_coeff_Add",
             "as_coeff_Mul", "as_two_terms", "as_numer_denom", "as_base_exp", "expr", "base", "exp", "lhs",
             "rhs", "kind", "as_coeff_mul", "as_coeff_add", "_mhash", "as_expr", "assumptions0", "binary_symbols"):
        return "read"
    if q in ("getit", "__gt__", "__lt__", "__ge__", "__le__", "__bool__", "__int__", "__float__", "__index__",
             "evalf", "_eval_evalf", "_evalf", "n", "__nonzero__") or q.startswith(("_eval_", "is_")):
        return "evaluate"
    return "other"


CATS = ("hash", "eq", "read", "walk", "construct", "evaluate", "order", "other")


def categories(r, sides=(1,)):
    """Category -> (calls, interval s, calibrated s) of one mon run, for the sides given."""
    c = r["calib"]
    iv, nest = c["outer_iv_ns"] * 1e-9, c["nested_all_ns"] * 1e-9
    out = {k: [0, 0.0, 0.0] for k in CATS}
    others = {}
    wt = defaultdict(list)
    for s, n, calls, t in r["wt"]:
        wt[s].append((n, calls, t))

    def add(name, calls, t, nested):
        k = cat_of(name)
        if k == "other":
            others[name] = others.get(name, 0) + t
        o = out[k]
        o[0] += calls
        o[1] += t
        o[2] += max(0.0, t - calls * iv - nested * nest)
    for s, name, calls, t, nested in r["by"]:
        if s not in sides:
            continue
        if name.endswith("func_wrapper.<locals>.wrapper"):       # split by the wrapped function
            tot = sum(x[2] for x in wt[s]) or 1.0
            for n2, c2, t2 in wt[s]:
                add(n2, c2, t2, nested * t2 / tot)
        else:
            add(name, calls, t, nested)
    return out, others


def pick(wl, mode):
    return [r for r in rows if r["wl"] == wl and r["mode"] == mode and r["round"] in ROUNDS]


def once(wl, mode):
    r = [r for r in rows if r["wl"] == wl and r["mode"] == mode and r["round"] == "once"]
    return r[0] if r else None


def amdahl(S, k):
    return 1 / (S + (1 - S) / k)


def k_for_2x(S):
    return (1 - S) / (0.5 - S) if S < 0.5 else float("inf")


def fmt(x, d=3):
    return f"{x:.{d}f}"


# ---- digests: every run of every mode
bad = [(r["wl"], r["mode"], r["round"]) for r in rows if r["digest"] != WANT[r["wl"]]]
print(f"runs {len(rows)}, digest mismatches: {bad if bad else 'none'}\n")

ALL = {}
for wl in ("dev", "fuzz"):
    base = pick(wl, "base")
    br = {r["round"]: r for r in base}
    T = {"all": med(r["s"] for r in base), "none": med(r["none_s"] for r in base),
         "def": med(r["def_s"] for r in base)}
    print(f"## {wl}: base {T['all']:.3f} s (range {min(r['s'] for r in base):.3f}-{max(r['s'] for r in base):.3f}), "
          f"None {T['none']:.3f} s, definite {T['def']:.3f} s; n {base[0]['n']}, None {base[0]['n_none']}\n")

    # ---- overhead of each mode, paired with base in the same round
    print("| mode | median s | vs base, paired | range s |\n|---|---:|---:|---|")
    OH = {}
    for m in ("base", "bdry", "fn", "enc", "dbl", "samp", "mon"):
        rs = pick(wl, m)
        OH[m] = med(r["s"] / br[r["round"]]["s"] - 1 for r in rs)
        print(f"| {m} | {med(r['s'] for r in rs):.3f} | {OH[m]*100:+.1f}% | "
              f"{min(r['s'] for r in rs):.3f}-{max(r['s'] for r in rs):.3f} |")
    print()

    # ---- S0
    bd = pick(wl, "bdry")
    S0 = {"all": med((r["s"] - r["inside_s"]) / r["s"] for r in bd),
          "none": med((r["none_s"] - r["inside"]["none"]) / r["none_s"] for r in bd),
          "def": med((r["def_s"] - r["inside"]["def"]) / r["def_s"] for r in bd)}
    calls = bd[0]["calls"]
    print(f"boundary calls {calls} = {sum(calls.values())}, {sum(calls.values())/base[0]['n']:.2f} per query\n")

    # ---- SymPy inside: monitoring, by class
    mo = pick(wl, "mon")
    def cal(r, c):
        k = r["calib"]
        return max(0.0, r["sym_in"][c] - r["n_outer_in"][c] * k["outer_iv_ns"] * 1e-9
                   - r["n_nested_in"][c] * k["nested_all_ns"] * 1e-9)
    sym_iv = {c: med(r["sym_in"][c] for r in mo) for c in ("none", "def")}
    sym_cal = {c: med(cal(r, c) for r in mo) for c in ("none", "def")}
    sym_cal["all"] = sym_cal["none"] + sym_cal["def"]
    sym_iv["all"] = sym_iv["none"] + sym_iv["def"]
    sym_ou = med(r["sym_out"]["none"] + r["sym_out"]["def"] for r in mo)
    k = mo[0]["calib"]
    print(f"mon: interval inside {sym_iv['all']:.3f} s, calibrated {sym_cal['all']:.3f} s; interval outside "
          f"{sym_ou:.3f} s. T(mon)-T(base) {med(r['s'] for r in mo)-T['all']:.3f} s. "
          f"calib ns: outer_iv {k['outer_iv_ns']:.0f}, outer_all {k['outer_all_ns']:.0f}, "
          f"nested_all {k['nested_all_ns']:.0f}. n_outer in {mo[0]['n_outer'][1]:,}, nested in {mo[0]['n_nested'][1]:,}; "
          f"n_outer out {mo[0]['n_outer'][0]:,}, unbalanced {mo[0]['unbalanced']}\n")

    # ---- does the calibration explain the slowdown? If not, the hot no-op undercharges and the
    # calibrated SymPy time is too high. Scaling the charge by the shortfall gives a second estimate.
    n = mo[0]
    model = (sum(n["n_outer"][:2]) * k["outer_all_ns"] + sum(n["n_nested"][:2]) * k["nested_all_ns"]) * 1e-9
    real = med(r["s"] for r in mo) - T["all"]
    charge = n["n_outer"][1] * k["outer_iv_ns"] * 1e-9 + n["n_nested"][1] * k["nested_all_ns"] * 1e-9
    print(f"overhead check: model {model:.3f} s, real {real:.3f} s, ratio {real/model:.2f}. Interval inside minus the "
          f"scaled charge: {sym_iv['all']-charge*real/model:.3f} s = {(sym_iv['all']-charge*real/model)/T['all']*100:.1f}% of base\n")

    # ---- by category
    cats = [categories(r)[0] for r in mo]
    print("| asked inside | calls | interval s | calibrated s | share of base |\n|---|---:|---:|---:|---:|")
    catcal = {}
    for c in CATS:
        n = med(x[c][0] for x in cats)
        catcal[c] = med(x[c][2] for x in cats)
        print(f"| {c} | {n:,.0f} | {med(x[c][1] for x in cats):.3f} | {catcal[c]:.3f} | {catcal[c]/T['all']*100:.1f}% |")
    print()
    oth = categories(mo[0])[1]
    if oth:
        print("other:", sorted(oth.items(), key=lambda kv: -kv[1])[:8], "\n")
    wr = sorted(mo[0]["wt"], key=lambda x: -x[3])[:6]
    print("behind the cache wrapper (side, function, calls, interval s):", wr, "\n")
    print("top entries inside (function, calls, interval s, nested):")
    for s, n, c, t, nest in [x for x in mo[0]["by"] if x[0] == 1][:12]:
        print(f"  {n} {c:,} {t:.3f} {nest:,}")
    print()
    nonhash = sum(v for c, v in catcal.items() if c not in HASHEQ)
    nonhash_share = nonhash / max(1e-9, sum(catcal.values()))

    # ---- thin-call floor
    db = pick(wl, "dbl")
    nl = once(wl, "dblc")
    hot = med(r["hot"]["basic_ns"] for r in db)
    hot_i = med(r["hot"]["integer_ns"] for r in db)
    dT = med(r["s"] - br[r["round"]]["s"] for r in db)
    hc = cats[0]["hash"][0]
    if nl:
        print(f"thin call: hash layer calls {nl['n_layer']:,}; T(dbl)-T(base) {dT*1e3:.1f} ms = "
              f"{dT/nl['n_layer']*1e9:.0f} ns per call (one extra Python layer). hot hash(e) net of hash(int): Basic "
              f"{hot:.0f} ns, Integer {hot_i:.0f} ns. Floor for hash inside: {hc:,} x {hot:.0f} ns = "
              f"{hc*hot*1e-9:.3f} s; calibrated {catcal['hash']:.3f} s\n")

    # ---- sampler, all rounds pooled
    tally = defaultdict(int)
    for r in pick(wl, "samp"):
        for cl, side, raw, corr, n in r["samples"]:
            tally[(cl, "all_")] += n
            tally[("all", "all_")] += n
            for c in (cl, "all"):
                if side:
                    tally[(c, "in")] += n
                    if raw:
                        tally[(c, "raw")] += n
                    if corr:
                        tally[(c, "corr")] += n
    samp = {c: {k2: tally[(c, k2)] / max(1, tally[(c, "all_")]) for k2 in ("in", "raw", "corr")}
            for c in ("all", "none", "def")}
    print(f"sampler, {tally[('all','all_')]:,} samples: inside the boundary {samp['all']['in']*100:.1f}%; SymPy frames "
          f"inside: raw {samp['all']['raw']*100:.1f}%, corrected {samp['all']['corr']*100:.1f}% "
          f"(None {samp['none']['raw']*100:.1f}/{samp['none']['corr']*100:.1f}, definite "
          f"{samp['def']['raw']*100:.1f}/{samp['def']['corr']*100:.1f})\n")

    # ---- fn groups
    fr = pick(wl, "fn")
    names = ("templates", "lra_read", "euf_read", "relation_read", "struct")
    gr = {g: {c: med(r["fn"][g][c] for r in fr) for c in ("none", "def")} for g in names}
    fn_tot = {c: sum(gr[g][c] for g in names) for c in ("none", "def")}
    fn_tot["all"] = fn_tot["none"] + fn_tot["def"]
    Tf = {"all": med(r["s"] for r in fr), "none": med(r["none_s"] for r in fr), "def": med(r["def_s"] for r in fr)}
    print("| group behind the boundary | calls (outermost) | None s | definite s | share of pass |\n|---|---:|---:|---:|---:|")
    for g in names:
        print(f"| {g} | {fr[0]['fn']['calls'][g]:,} | {gr[g]['none']:.3f} | {gr[g]['def']:.3f} | "
              f"{(gr[g]['none']+gr[g]['def'])/Tf['all']*100:.1f}% |")
    print(f"| total | | {fn_tot['none']:.3f} | {fn_tot['def']:.3f} | {fn_tot['all']/Tf['all']*100:.1f}% |\n")
    f0 = fr[0]["fn"]
    print(f"prepare_query all-in {med(r['fn']['prepare_query_all_in_s'] for r in fr):.3f} s "
          f"({med(r['fn']['prepare_query_all_in_s'] for r in fr)/Tf['all']*100:.1f}%, behind the boundary). "
          f"Callbacks: facts_for {f0['ext_facts_for']:,}, node_facts {f0['ext_node_facts']:,}; "
          f"Session._custom atoms {f0['session_custom_atoms']:,} (not callbacks)\n")

    # ---- SymPy entries under fn groups, so S4 does not double count
    mf = once(wl, "monfn")
    if mf:
        ck = mf["calib"]
        def cs(s):
            return max(0.0, mf["t_side"][s] - mf["n_outer"][s] * ck["outer_iv_ns"] * 1e-9
                       - mf["n_nested"][s] * ck["nested_all_ns"] * 1e-9)
        c1, c2 = cs(1), cs(2)
        not_fn = c1 / max(1e-9, c1 + c2)
        print(f"monfn: SymPy inside under fn groups {c2:.3f} s ({mf['n_outer'][2]:,} entries), not under them "
              f"{c1:.3f} s ({mf['n_outer'][1]:,} entries): {not_fn*100:.0f}% not under\n")
    else:
        not_fn = 1.0

    # ---- encoding
    en = pick(wl, "enc")
    enc = {m: {c: med(r["enc"][m][c] for r in en) for c in ("none", "def")} for m in ("q", "intern", "cl")}
    for m in enc:
        enc[m]["all"] = enc[m]["none"] + enc[m]["def"]
    e0 = en[0]["enc"]
    print("| encode what | s | share of base | per boundary call us | bytes per call | nodes per call |\n|---|---:|---:|---:|---:|---:|")
    for m in ("q", "intern", "cl"):
        print(f"| {m} | {enc[m]['all']:.4f} | {enc[m]['all']/T['all']*100:.2f}% | {enc[m]['all']/e0['calls']*1e6:.1f} | "
              f"{e0['bytes'][m]/e0['calls']:,.0f} | {e0['nodes'][m]/e0['calls']:,.1f} |")
    print()

    # ---- the S table
    def row(c):
        t = T[c]
        hi = S0[c] + sym_cal[c] / t + enc["q"][c] / t
        lo = S0[c] + samp[c]["corr"] + enc["q"][c] / t
        raw = S0[c] + samp[c]["raw"] + enc["q"][c] / t
        nout = med(r["n_outer_in"]["none"] + r["n_outer_in"]["def"] if c == "all" else r["n_outer_in"][c] for r in mo)
        r2 = S0[c] + enc["cl"][c] / t
        r3 = r2 + nonhash_share * sym_cal[c] / t
        r4 = S0[c] + fn_tot[c] / Tf[c] + not_fn * sym_cal[c] / t + enc["q"][c] / t
        return [("S0 outside the boundary only", S0[c]),
                ("S1 as it stands, low (sampler corrected)", lo),
                ("S1 as it stands, sampler raw", raw),
                ("S1 as it stands, high (calibrated)", hi),
                ("S1 high + 50 ns per ask", hi + nout * 50e-9 / t),
                ("S1 high + 200 ns per ask", hi + nout * 200e-9 / t),
                ("S2 resolved, all asks free", r2),
                ("S3 resolved, non-hash asks stay", r3),
                ("S4 fn groups stay in Python", r4)]
    for c, label in (("all", "whole pass"), ("none", "None answers"), ("def", "definite answers")):
        print(f"### {wl} {label}\n\n| row | S | ceiling 1/S | at 10x | at 50x | k for 2x |\n|---|---:|---:|---:|---:|---:|")
        for name, s in row(c):
            print(f"| {name} | {s*100:.1f}% | {1/s:.1f}x | {amdahl(s,10):.2f}x | {amdahl(s,50):.2f}x | {k_for_2x(s):.1f} |")
        print()
    ALL[wl] = dict(T=T, S0=S0, sym_cal=sym_cal, catcal=catcal, enc={m: enc[m]["all"] for m in enc})

# ---- second batch: the items outside the boundary, and construction at any depth
if len(sys.argv) > 2:
    rows2 = [json.loads(x) for x in open(sys.argv[2]) if x.startswith("{")]
    bad = [(r["wl"], r["mode"], r["round"]) for r in rows2 if r["digest"] != WANT[r["wl"]]]
    print(f"second batch: runs {len(rows2)}, digest mismatches: {bad if bad else 'none'}\n")
    for wl in ("dev", "fuzz"):
        o = [r for r in rows2 if r["wl"] == wl and r["mode"] == "out" and r["round"] in ROUNDS]
        b = {r["round"]: r for r in rows2 if r["wl"] == wl and r["mode"] == "base"}
        Ts = med(r["s"] for r in o)
        print(f"### {wl}: out {Ts:.3f} s, vs base paired {med(r['s']/b[r['round']]['s']-1 for r in o)*100:+.1f}%\n")
        print("| outside the boundary | calls | None s | definite s | share of pass |\n|---|---:|---:|---:|---:|")
        tot = 0.0
        for g in ("conversion", "relevance", "consistency", "precheck"):
            x, y = med(r["out"][g]["none"] for r in o), med(r["out"][g]["def"] for r in o)
            tot += x + y
            print(f"| {g} | {o[0]['out']['calls'][g]:,} | {x:.4f} | {y:.4f} | {(x+y)/Ts*100:.2f}% |")
        outside = med(r["s"] - r["inside_s"] for r in o)
        print(f"| rest (ask, memo lookups, replay loop) | | | | {(outside-tot)/Ts*100:.2f}% |")
        print(f"| total outside | | | | {outside/Ts*100:.2f}% |\n")
        mc = [r for r in rows2 if r["wl"] == wl and r["mode"] == "moncall"][0]
        ins = [x for x in mc["any_depth"] if x[0] == 1]
        print("inside, any depth:", [(n, c) for _, n, c in ins[:10]], "\n")
        print("top callers inside:", [(c[1], c[2].split(":")[-1], c[3]) for c in mc["callers"] if c[0] == 1][:8], "\n")
