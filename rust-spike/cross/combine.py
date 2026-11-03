"""combine.py: rebuild results/tables-cross.md from results/pinned-cross.raw, results/pinned-k.raw and
tools-rust/results/pinned.jsonl. Nothing here is a timing of the combined system: it adds shares and costs measured apart."""
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
RES = os.path.join(HERE, "..", "results")
CEIL_RAW = os.path.join(HERE, "..", "..", "tools-rust", "results", "pinned.jsonl")
OUT = []


def p(*a):
    OUT.append(" ".join(str(x) for x in a))


def rows(path):
    for l in open(path):
        if l.startswith("{"):
            yield json.loads(l)


def med(xs):
    return st.median(xs)


XR = [d for d in rows(os.path.join(RES, "pinned-cross.raw")) if d["round"] != "0"]
KR = [d for d in rows(os.path.join(RES, "pinned-k.raw")) if d["round"] != "0"]
CR = [d for d in rows(CEIL_RAW) if d.get("round") not in ("0",)]

# REPORT-rust-ceiling.md, Tables by answer (lines 314-396).
CEIL = {
    "dev": {"all": dict(S0=.078, S1lo=.124, S1hi=.252, S4=.396), "none": dict(S0=.083, S1lo=.121, S1hi=.238, S4=.419),
            "def": dict(S0=.067, S1lo=.126, S1hi=.272, S4=.358)},
    "fuzz": {"all": dict(S0=.026, S1lo=.083, S1hi=.268, S4=.281), "none": dict(S0=.022, S1lo=.077, S1hi=.254, S4=.268),
             "def": dict(S0=.047, S1lo=.115, S1hi=.337, S4=.347)},
}
# REPORT-rust-ceiling.md lines 85-104: asks inside the boundary, (calls, calibrated s).
ASKS = {
    "dev": dict(hash=(249497, .036), eq=(3726, .003), read=(14596, .003), walk=(9759, .030), construct=(1215, .007),
                evaluate=(2112, .004), order=(2004, .011)),
    "fuzz": dict(hash=(5048969, .709), eq=(172391, .195), read=(410716, .066), walk=(230997, .539),
                 construct=(20607, .207), evaluate=(10764, .011), order=(52126, .210)),
}
# RESULT-k.md lines 178-183, and hash calls through P.__hash__ from REPORT-rust-ceiling.md line 107 / moncall.
COUNTS = {"dev": dict(public=46214, hooks=16088, phash=87624), "fuzz": dict(public=687993, hooks=584495, phash=1820950)}
FN_CALLS = {"dev": 4964 + 4340 + 3595 + 10113 + 3515, "fuzz": 33074 + 105863 + 93889 + 215896 + 19107}
BDRY = {"dev": 1115, "fuzz": 3296}
PAYLOAD = {"dev": "a_bytes132", "fuzz": "a_bytes267"}
WLS = ("dev", "fuzz")
CLS = ("all", "none", "def")
CLN = dict(all="whole pass", none="None", **{"def": "definite"})


# ---------------------------------------------------------------- crossing costs
def nsdict(run, wl=None):
    out = {}
    for d in XR:
        if d["run"] != run or (wl and d.get("wl") != wl):
            continue
        for k, v in d["ns"].items():
            out.setdefault(k, []).append(v)
    return out


MF, MA = nsdict("micro"), nsdict("microabi3")
RF = {w: nsdict("real", w) for w in WLS}
RA = {w: nsdict("realabi3", w) for w in WLS}


def m(tbl, k):
    return med(tbl[k])


def fmt(tbl, k, base=None):
    v = [a - b for a, b in zip(tbl[k], tbl[base])] if base else tbl[k]
    return f"{med(v):.1f} ({min(v):.1f} to {max(v):.1f})"


def net(tbl, k, base):
    return med([a - b for a, b in zip(tbl[k], tbl[base])])


p("## Crossing costs, ns per call: median over rounds 1 to 6 (range), net of the empty loop for Python-side rows\n")
p("### (a) Python into Rust\n")
p("| call | PyO3 full API | PyO3 abi3-py39 | same call to a Python function |\n|---|---:|---:|---:|")
for k, ref, name in (("a_noop", "a_noop_py", "no args, returns None"), ("a_int", "a_int_py", "one int in, one out"),
                     ("a_bytes132", None, "132 bytes by reference, Option<bool> out"),
                     ("a_bytes267", None, "267 bytes, same"), ("a_bytes538", None, "538 bytes, same"),
                     ("a_method267", "a_method267_py", "267 bytes, method on a #[pyclass]")):
    r = fmt(MF, ref, "py_empty") if ref else ""
    p(f"| {name} | {fmt(MF, k, 'py_empty')} | {fmt(MA, k, 'py_empty')} | {r} |")
p("\n### (b) Rust into Python\n")
p("| call | PyO3 full API | PyO3 abi3-py39 | same call from Python, net of its loop |\n|---|---:|---:|---:|")
for k, ref, name in (("b_call0", "b_call0_py", "`f()` returning None"), ("b_call1_int", "b_call1_py", "`f(i)`: int out, int back, converted"),
                     ("b_call1_obj", "b_callo_py", "`f(o)`: object out, None/bool back"), ("b_method", "b_method_py", "`o.m(i)` by interned name"),
                     ("b_reattach", None, "`f(i)`, lock taken and released per call")):
    r = fmt(MF, ref, "py_empty") if ref else ""
    p(f"| {name} | {fmt(MF, k)} | {fmt(MA, k)} | {r} |")
p(f"| `f(i)` through raw `PyObject_Vectorcall` | {fmt(MF, 'b_raw')} | n/a | |")
p("\n### (c) SymPy objects, called from Rust and from Python\n")
for w in WLS:
    d0 = [d for d in XR if d["run"] == "real" and d.get("wl") == w][0]
    p(f"**{w}**: {d0['seen']['hash']:,} outermost hash entries seen, {d0['kept']:,} kept ({d0['distinct']:,} distinct objects, "
      f"{d0['interned']:,} distinct by ==); {d0['eq']:,} eq entries, {d0['eq_same']:,} identical. Top types: "
      + ", ".join(f"{a} {b:,}" for a, b in d0["kinds"][:5]) + ".\n")
    p("| operation, warm | from Rust | from Rust, abi3 | from Python, net of loop | Rust minus Python |\n|---|---:|---:|---:|---:|")
    T, A = RF[w], RA[w]
    for rs, py, base, name in (("rs_hash", "py_hash", "py_loop", "hash(o)"), ("rs_eq", "py_eq", "py_zip", "a == b"),
                               ("rs_intern", "py_intern", "py_loop", "id from a Python dict: d[o]"),
                               ("rs_args", "py_args", "py_loop", "o.args, handle on each element"),
                               ("rs_isnum", "py_isnum", "py_loop", "o.is_number as bool"),
                               ("rs_cold", "py_cold", "py_loop", "first hash of an object (_mhash cleared)")):
        pyn = med([a - b for a, b in zip(T[py], T[base])])
        p(f"| {name} | {fmt(T, rs)} | {fmt(A, rs)} | {pyn:.1f} | {m(T, rs) - pyn:+.1f} |")
    p("")

# per-ask charges, ns. Low: what a callback adds over the same call from Python. High: gross abi3 method call.
NET_CB = max(0.0, m(MF, "b_call1_int") - net(MF, "b_call1_py", "py_empty"))
HI_CB = m(MA, "b_method")
A_LO = {w: max(0.0, net(MF, PAYLOAD[w], "py_empty") - net(MF, "a_noop_py", "py_empty")) for w in WLS}
A_HI = {w: net(MA, "a_method267", "py_empty") for w in WLS}
PUB_LO = max(0.0, net(MF, "a_int", "py_empty") - net(MF, "a_int_py", "py_empty"))
PUB_HI = net(MA, "a_int", "py_empty")
HOOK_LO, HOOK_HI = NET_CB, m(MA, "b_call1_int")
p(f"Charges used: per ask low {NET_CB:.1f} ns (callback minus the same call in Python), high {HI_CB:.1f} ns (gross abi3 method call, "
  f"which also counts entry time the calibrated ask already holds). Per public solver call {PUB_LO:.1f} to {PUB_HI:.1f} ns, per theory hook "
  f"{HOOK_LO:.1f} to {HOOK_HI:.1f} ns, per query {min(A_LO.values()):.1f} to {max(A_HI.values()):.1f} ns.\n")


# ---------------------------------------------------------------- shares
def bases(rowsrc, run_key, wl):
    rs = [d for d in rowsrc if d.get(run_key) == "base" and d.get("wl") == wl]
    return dict(all=med([d["s"] for d in rs]), none=med([d["none_s"] for d in rs]), **{"def": med([d["def_s"] for d in rs])})


B_K = {w: bases(KR, "run", w) for w in WLS}
B_C = {w: bases(CR, "mode", w) for w in WLS}
B_X = {w: bases(XR, "run", w) for w in WLS}
p("Base (live pass) medians from the three batches, s: " + "; ".join(
    f"{w} ceiling {B_C[w]['all']:.3f}, k {B_K[w]['all']:.3f}, this batch {B_X[w]['all']:.3f}" for w in WLS) + ".\n")
digests = {(d.get("wl") or "", d["digest"]) for d in XR if "digest" in d}
p(f"Digests in this batch: {sorted(digests)}; runs {len(XR)}.\n")


def krow(run, wl):
    return [d for d in KR if d.get("run") == run and d.get("wl") == wl]


def s_parts(wl, c):
    key = dict(all="T", none="T_none", **{"def": "T_def"})[c]
    py = med([d[key] for d in krow("py", wl)])
    rs = med([d[key] for d in krow("rs", wl)])
    pyT = med([d["T"] for d in krow("py", wl)])
    # RESULT-k.md's net = 0.1771/0.1832 and 2.6475/2.7527 of the raw replay.
    nf = dict(dev=.1771 / .1832, fuzz=2.6475 / 2.7527)[wl]
    return py * nf, rs, pyT


MON = {w: [d for d in CR if d.get("mode") == "mon" and d.get("wl") == w] for w in WLS}
ENC = {w: [d for d in CR if d.get("mode") == "enc" and d.get("wl") == w] for w in WLS}
SAMP = {w: [d for d in CR if d.get("mode") == "samp" and d.get("wl") == w] for w in WLS}


def enc_q(w, c):
    if c == "all":
        v = [d["enc"]["q"]["none"] + d["enc"]["q"]["def"] for d in ENC[w]]
    else:
        v = [d["enc"]["q"][c] for d in ENC[w]]
    return med(v) / B_C[w][c]


def n_asks(w, c):
    d = MON[w][0]["n_outer_in"]
    return d["none"] + d["def"] if c == "all" else d[c]


def corr_hasheq_frac(w, c):
    """Of the corrected sampler's SymPy samples inside the boundary, the fraction in __hash__ and __eq__."""
    fr = []
    for d in SAMP[w]:
        a = h = 0
        for cl, side, raw, corr, n in d["samples"]:
            if side != 1 or not corr or (c != "all" and cl != c):
                continue
            a += n
            if corr.endswith("__hash__") or corr.endswith("__eq__"):
                h += n
        fr.append(h / a if a else 0)
    return med(fr)


CL_NODES = {w: med([d["enc"]["nodes"]["cl"] for d in ENC[w]]) for w in WLS}


def model(w, c):
    """Everything for one workload and answer class. Shares of that class's base time."""
    C = CEIL[w][c]
    A = ASKS[w]
    pyc, rsc, _ = s_parts(w, c)
    T = B_X[w][c]    # crossing ns are divided by this batch's base, the machine state they were measured in
    Tk = B_K[w][c]
    Tmax = max(B_C[w][c], Tk, T)
    s, rs = pyc / Tk, rsc / Tk
    s_lo, rs_lo = pyc / Tmax, rsc / Tmax
    qs = {"dev": dict(all=1985, none=892, **{"def": 1093}), "fuzz": dict(all=3000, none=2387, **{"def": 613})}[w]
    fq = qs[c] / qs["all"]
    N = n_asks(w, c)
    tot = sum(v[0] for v in A.values())
    he_cnt = (A["hash"][0] + A["eq"][0]) / tot
    N_other = N * (1 - he_cnt)
    enc = enc_q(w, c)
    A_hi = C["S1hi"] - C["S0"] - enc
    A_lo = C["S1lo"] - C["S0"] - enc
    cal = sum(v[1] for v in A.values())
    f_hi = (A["hash"][1] + A["eq"][1]) / cal
    f_lo = corr_hasheq_frac(w, c)
    f_p = (A["hash"][1] * COUNTS[w]["phash"] / A["hash"][0]) / cal
    a_lo, a_hi = A_LO[w] * BDRY[w] * fq * 1e-9 / T, A_HI[w] * BDRY[w] * fq * 1e-9 / T

    x = dict(s=s, rs=rs, s_lo=s_lo, rs_lo=rs_lo, enc=enc, N=N, N_other=N_other, T=T)
    # As the code stands: every ask a callback.
    x["St_hi"], x["St_lo"] = C["S1hi"], C["S1lo"]
    x["Xt_hi"] = a_hi + N * HI_CB * 1e-9 / T
    x["Xt_lo"] = a_lo + N * NET_CB * 1e-9 / T
    # Integer ids: hash and eq asks gone; everything else still a callback; ids looked up in a Python dict.
    rint_lo, rint_hi = m(RF[w], "rs_intern"), m(RA[w], "rs_intern")
    cold = m(RF[w], "rs_cold")
    cl = CL_NODES[w] * fq
    x["Si_hi"], x["Si_lo"] = C["S1hi"] - A_hi * f_hi, C["S1lo"] - A_lo * f_lo
    x["Xi_hi"] = a_hi + (N_other * HI_CB + 2 * N_other * rint_hi + cl * cold) * 1e-9 / T
    x["Xi_lo"] = a_lo + (N_other * NET_CB + cl * (rint_lo + cold)) * 1e-9 / T
    x["Sp_hi"] = C["S1hi"] - A_hi * f_p      # only P.__hash__ goes
    x["r_hi"] = 1 - C["S1hi"] - s_lo
    x["r_lo"] = 1 - C["S1lo"] - s
    x["f_hi"], x["f_lo"], x["A_hi"], x["A_lo"] = f_hi, f_lo, A_hi, A_lo
    x["S4"] = C["S4"]
    x["fn_calls"] = FN_CALLS[w] * fq
    # Solver crossings by class, in proportion to the class's solver time.
    solver_frac = pyc / s_parts(w, "all")[0]
    x["public"], x["hooks"] = COUNTS[w]["public"] * solver_frac, COUNTS[w]["hooks"] * solver_frac
    x["N_nonp"] = N - COUNTS[w]["phash"] * N / tot
    x["sol_lo"] = (x["public"] * PUB_HI + x["hooks"] * HOOK_HI) * 1e-9 / T
    x["sol_hi"] = (x["public"] * PUB_LO + x["hooks"] * HOOK_LO) * 1e-9 / T
    return x


def sp(S, X, rs, r, kr):
    return 1 / (S + X + rs + r / kr)


def k2(S, X, rs, r):
    d = .5 - S - X - rs
    return r / d if d > 0 else float("inf")


KRS = (1, 1.5, 2, 3, 5, 10, 15)
M = {w: {c: model(w, c) for c in CLS} for w in WLS}

p("## Inputs\n")
p("| | class | S1 low | S1 high | enc q | s, solver | s, drift low | Rust solver | r at S1 high | r at S1 low | asks | crossing low | crossing high | hash+eq of asks low / high |")
p("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for w in WLS:
    for c in CLS:
        x = M[w][c]
        p(f"| {w} | {CLN[c]} | {x['St_lo']:.1%} | {x['St_hi']:.1%} | {x['enc']:.2%} | {x['s']:.1%} | {x['s_lo']:.1%} | {x['rs']:.2%} | {x['r_hi']:.1%} | {x['r_lo']:.1%} "
          f"| {x['N']:,.0f} | {x['Xt_lo']:.2%} | {x['Xt_hi']:.2%} | {x['f_lo']:.0%} / {x['f_hi']:.0%} |")
p("")

p("## Overall speedup, low to high, against k_r (the assumed factor on moved code outside the SAT solver)\n")
for name, S, X in (("As the code stands", "St", "Xt"), ("Integer ids for hash and equality", "Si", "Xi")):
    p(f"### {name}\n")
    p("| | class | " + " | ".join(f"k_r={k}" for k in KRS) + " | k_r=inf | k_r for 2x |")
    p("|---|---|" + "---:|" * (len(KRS) + 2))
    for w in WLS:
        for c in CLS:
            x = M[w][c]
            cells = []
            for kr in KRS:
                lo = sp(x[S + "_hi"], x[X + "_hi"], x["rs_lo"], x["r_hi"], kr)
                hi = sp(x[S + "_lo"], x[X + "_lo"], x["rs"], x["r_lo"], kr)
                cells.append(f"{min(lo, hi):.2f}-{max(lo, hi):.2f}")
            cap_lo = 1 / (x[S + "_hi"] + x[X + "_hi"] + x["rs_lo"])
            cap_hi = 1 / (x[S + "_lo"] + x[X + "_lo"] + x["rs"])
            k_lo = k2(x[S + "_hi"], x[X + "_hi"], x["rs_lo"], x["r_hi"])
            k_hi = k2(x[S + "_lo"], x[X + "_lo"], x["rs"], x["r_lo"])
            p(f"| {w} | {CLN[c]} | " + " | ".join(cells) + f" | {min(cap_lo, cap_hi):.2f}-{max(cap_lo, cap_hi):.2f} | {min(k_hi, k_lo):.2f} to {max(k_hi, k_lo):.2f} |")
    p("")

p("## Sensitivity, on the low end (S1 high)\n")
p("| | class | row | k_r=1 | k_r=3 | k_r=5 | k_r=10 | k_r for 2x |\n|---|---|---|---:|---:|---:|---:|---:|")


def sens(w, c, name, S, X, rs, r):
    x = [f"{sp(S, X, rs, r, k):.2f}" for k in (1, 3, 5, 10)]
    p(f"| {w} | {CLN[c]} | {name} | " + " | ".join(x) + f" | {k2(S, X, rs, r):.2f} |")


for w in WLS:
    for c in CLS:
        x = M[w][c]
        T, N, No = x["T"], x["N"], x["N_other"]
        rs, r = x["rs_lo"], x["r_hi"]
        sens(w, c, "as it stands, the low end itself", x["St_hi"], x["Xt_hi"], rs, r)
        sens(w, c, "ids, the low end itself", x["Si_hi"], x["Xi_hi"], rs, r)
        sens(w, c, "as it stands, solver k halved in live use", x["St_hi"], x["Xt_hi"], 2 * rs, r)
        if c == "all":
            st_ = dict(dev=.434, fuzz=.458)[w]    # RESULT-k.md line 76: live timers as timed
            sens(w, c, "as it stands, solver share at the live timers' figure", x["St_hi"], x["Xt_hi"], rs * st_ / x["s_lo"], 1 - x["St_hi"] - st_)
        sens(w, c, "as it stands, per ask 200 ns", x["St_hi"], N * 200e-9 / T, rs, r)
        sens(w, c, "as it stands, per ask 500 ns", x["St_hi"], N * 500e-9 / T, rs, r)
        sens(w, c, "ids, only P.__hash__ goes", x["Sp_hi"], x["N_nonp"] * HI_CB * 1e-9 / T, rs, r)
        sens(w, c, "ids, per other ask 500 ns", x["Si_hi"], No * 500e-9 / T, rs, r)
        s4_r = 1 - x["S4"] - x["s_lo"]
        sens(w, c, "SymPy-reading functions stay in Python (S4), each call at the high charge", x["S4"], x["fn_calls"] * HI_CB * 1e-9 / T, rs, s4_r)
        sens(w, c, "solver only in Rust, rest Python (no assumed factor)", 1 - x["s_lo"], x["sol_lo"], rs, 1e-12)
    p("| | | | | | | | |")
p("")
p("Solver-only high end, crossings net of a Python call: " + "; ".join(
    f"{w} {CLN[c]} {1 / (1 - M[w][c]['s'] + M[w][c]['sol_hi'] + M[w][c]['rs']):.2f}x" for w in WLS for c in CLS) + ".\n")

# worked example
w, c = "dev", "all"
x = M[w][c]
p("## Worked example: dev, whole pass, as the code stands, k_r = 5, low end\n")
p(f"S1 high {x['St_hi']:.3f} + crossing ({x['N']:,.0f} asks x {HI_CB:.1f} ns + {BDRY[w]} calls x {A_HI[w]:.1f} ns) / {x['T']:.3f} s = {x['Xt_hi']:.4f} "
  f"+ Rust solver {x['rs_lo']:.4f} + r/k_r {x['r_hi']:.3f}/5 = {x['r_hi'] / 5:.4f}, total "
  f"{x['St_hi'] + x['Xt_hi'] + x['rs_lo'] + x['r_hi'] / 5:.4f}, speedup {sp(x['St_hi'], x['Xt_hi'], x['rs_lo'], x['r_hi'], 5):.2f}x\n")

# ---------------------------------------------------------------- what k does not cover
MAP = (("sat/solver.py", "SAT solver: k covers this"), ("sat/", "other sat/: theory dispatch, EqualitySharing, formula"),
       ("theories/lra/constfield.py", "LRA: constfield"), ("theories/lra/", "LRA: tableau, bounds, adapter"),
       ("theories/euf/", "EUF"), ("theories/transfer.py", "transfer"), ("theories/", "other theories"),
       ("relations.py", "Relations"), ("knowledge/", "knowledge: templates, rules"), ("ref.py", "ref.py"))


def place(file, fn):
    if file == "engine.py":
        cl = fn.split(".")[0]
        return "Session" if cl == "Session" else "Engine and other engine.py"
    for pre, name in MAP:
        if file.startswith(pre):
            return name
    return "other satassume" if file else "no satassume frame"


p("## Sampled split of a pass, by the innermost satassume frame\n")
p("In the boundary with no SymPy frame on the stack, as a share of all samples, median over rounds 1 to 6. Shares, not times.\n")
p("| code | dev | dev None | dev definite | fuzz | fuzz None | fuzz definite |\n|---|---:|---:|---:|---:|---:|---:|")
tabs = {}
leafs = {}
for w in WLS:
    for d in [d for d in XR if d["run"] == "samp" and d.get("wl") == w]:
        tot = dict(all=0, none=0, **{"def": 0})
        cnt = {}
        for key, n in d["tally"].items():
            cl, depth, sym, file, fn, leaf = key.split("|")
            tot["all"] += n
            tot[cl] += n
            if depth == "0":
                nm = "outside the boundary"
            elif sym == "1":
                nm = "SymPy on the stack, inside"
            else:
                nm = place(file, fn)
                if leaf and nm != "SAT solver: k covers this":
                    leafs.setdefault(w, {}).setdefault(leaf, 0)
                    leafs[w][leaf] += n
            for cc in ("all", cl):
                cnt[(nm, cc)] = cnt.get((nm, cc), 0) + n
        for (nm, cc), n in cnt.items():
            tabs.setdefault((w, nm, cc), []).append(n / tot[cc])
names = sorted({k[1] for k in tabs}, key=lambda n: -med(tabs.get(("fuzz", n, "all"), [0])))
for nm in names:
    cols = [tabs.get((w, nm, c), [0]) for w in WLS for c in CLS]
    p(f"| {nm} | " + " | ".join(f"{med(v):.1%}" for v in cols) + " |")
p("")
for w in WLS:
    t = sum(leafs[w].values())
    top = sorted(leafs[w].items(), key=lambda kv: -kv[1])[:8]
    p(f"{w}, moved code outside the solver, samples with the leaf in another file: " + ", ".join(f"{a} {b}" for a, b in top) + f" (of {t}).\n")

for w in WLS:
    agg = {}
    tot = 0
    for d in [d for d in XR if d["run"] == "samp" and d.get("wl") == w]:
        for key, n in d["tally"].items():
            cl, depth, sym, file, fn, leaf = key.split("|")
            tot += n
            if depth == "1" and sym == "0" and file != "sat/solver.py":
                agg[f"{file}:{fn}"] = agg.get(f"{file}:{fn}", 0) + n
    p(f"{w}, largest functions in moved code outside the solver, share of all samples: " + ", ".join(
        f"{k} {v / tot:.1%}" for k, v in sorted(agg.items(), key=lambda kv: -kv[1])[:16]) + ".\n")
    frac = sum(n for key, n in leafs[w].items() if key in ("fractions.py", "<frozen abc>"))
    p(f"{w}, Fraction and ABC checks under moved code: {frac / tot:.1%} of all samples; <string> (generated dataclass methods): {leafs[w].get('<string>', 0) / tot:.1%}; import machinery: {sum(n for k, n in leafs[w].items() if 'importlib' in k) / tot:.1%}.\n")

open(os.path.join(RES, "tables-cross.md"), "w").write("\n".join(OUT) + "\n")
print(len(OUT), "lines")
