"""analyze.py COVERDIR OUT.jsonl: join cover-*.json, per-query medians (time passes) and samples (sample passes); print markdown."""
import collections as C, json, statistics as st, sys
cd, outf = sys.argv[1:3]
K = {"dev": (12.9, 16.6), "fuzz": (15.2, 22.1)}
rows = [json.loads(l) for l in open(outf)]
def part(fn, q):
    if fn.startswith("sat/solver"): return "sat"
    if fn.startswith("sat/"): return "other_sat"
    if fn.startswith("theories/lra/lra_adapter"): return "lra_adapter"
    if fn.startswith("theories/lra/constfield"): return "lra_constfield"
    if fn.startswith("theories/lra/"): return "lra_core"
    if fn.startswith("theories/euf/euf_adapter"): return "euf_adapter"
    if fn.startswith("theories/euf/"): return "euf"
    if fn.startswith("theories/transfer"): return "transfer"
    if fn.startswith("relations"): return "relations"
    if fn.startswith("engine"): return "session" if q == "Session" else "engine"
    if fn.startswith("knowledge"): return "knowledge"
    return "outside"
def qclass(c):
    ks = c["session_kinds"]
    if not ks: return "no session"
    if any("lra_const" in k for k in ks): return "constants"
    if any("transfer" in k for k in ks): return "rational+EUF+transfer"
    if any("euf" in k for k in ks): return "rational+EUF"
    if any("lra_rat" in k for k in ks): return "rational, no EUF"
    return "no theory"
CL = ["no session", "no theory", "rational, no EUF", "rational+EUF", "rational+EUF+transfer", "constants"]
SL = {"P plan as written: session, solver, rational LRA": {"no theory", "rational, no EUF"},
      "P+ plan plus EUF": {"no theory", "rational, no EUF", "rational+EUF"},
      "P++ plus EUF and transfer": {"no theory", "rational, no EUF", "rational+EUF", "rational+EUF+transfer"},
      "Q solver boundary: all sessions": {"no theory", "rational, no EUF", "rational+EUF", "rational+EUF+transfer", "constants"}}
for wl in ("dev", "fuzz"):
    R = json.load(open(f"{cd}/cover-{wl}.json"))
    n = len(R)
    tp = [r for r in rows if r["wl"] == wl and r["mode"] == "time" and r["round"] > 0]
    sp = [r for r in rows if r["wl"] == wl and r["mode"] == "sample" and r["round"] > 0]
    digs = {r["digest"] for r in tp + sp}
    pass_s = st.median(r["s"] for r in tp)
    t = [st.median(r["per"][i] for r in tp) for i in range(n)]
    T = sum(t)
    print(f"\n## {wl}: {n} queries, pass median {pass_s:.3f} s over {len(tp)} time rounds (range {min(r['s'] for r in tp):.3f} to {max(r['s'] for r in tp):.3f}), sampled {st.median(r['s'] for r in sp):.3f} s, digests {sorted(digs)}")
    cls = [qclass(x["c"]) for x in R]
    none = [x["ans"] is None for x in R]
    # samples per query part
    smp = C.defaultdict(C.Counter)
    for r in sp:
        for q, fn, qq, sym, v in r["samples"]:
            if q >= 0:
                smp[q][(part(fn, qq), bool(sym))] += v
    # normalise each query's samples to its measured time, so the shares weigh by the unsampled pass
    pt = C.Counter()   # (class, part, sym) -> seconds
    for q in range(n):
        tot = sum(smp[q].values())
        if tot == 0:
            pt[(cls[q], "unsampled", False)] += t[q]
            continue
        for (p, s), v in smp[q].items():
            pt[(cls[q], p, s)] += t[q] * v / tot
    print("\n| class | queries | None | definite | time % | None % of pass | definite % of pass |\n|---|---:|---:|---:|---:|---:|---:|")
    for c in CL:
        I = [i for i in range(n) if cls[i] == c]
        print(f"| {c} | {len(I)} | {sum(none[i] for i in I)} | {sum(not none[i] for i in I)} | {100*sum(t[i] for i in I)/T:.1f} | {100*sum(t[i] for i in I if none[i])/T:.1f} | {100*sum(t[i] for i in I if not none[i])/T:.1f} |")
    print(f"| all | {n} | {sum(none)} | {n-sum(none)} | 100 | {100*sum(t[i] for i in range(n) if none[i])/T:.1f} | {100*sum(t[i] for i in range(n) if not none[i])/T:.1f} |")
    parts = ["sat", "other_sat", "lra_core", "lra_constfield", "lra_adapter", "relations", "euf", "euf_adapter", "transfer", "session", "engine", "knowledge", "outside", "unsampled"]
    print("\nShare of pass, % (SymPy on stack in brackets), part by class:\n\n| part | " + " | ".join(CL) + " | all |\n|---|" + "---:|" * (len(CL) + 1))
    for p in parts:
        cells = []
        for c in CL + [None]:
            a = sum(v for (cc, pp, s), v in pt.items() if pp == p and (c is None or cc == c))
            b = sum(v for (cc, pp, s), v in pt.items() if pp == p and s and (c is None or cc == c))
            cells.append(f"{100*a/T:.1f} ({100*b/T:.1f})")
        print(f"| {p} | " + " | ".join(cells) + " |")
    # theories that ever said anything
    print("\nTheory activity: queries in class where the theory's assert/check/propagate returned a conflict or propagation:\n")
    for c in CL[2:]:
        I = [i for i in range(n) if cls[i] == c]
        print(f"- {c}: {len(I)} queries; EUF said {sum(1 for i in I if R[i]['c'].get('euf.said'))}; transfer said {sum(1 for i in I if R[i]['c'].get('transfer.said'))}; LRA said {sum(1 for i in I if R[i]['c'].get('lra.said'))}; none said {sum(1 for i in I if not any(R[i]['c'].get(k) for k in ('euf.said','transfer.said','lra.said')))}")
    # crossings
    tot = C.Counter(); 
    for x in R:
        for k, v in x["c"].items():
            if k != "session_kinds": tot[k] += v
    xs = {k: v for k, v in tot.items() if k.startswith("x.")}
    print(f"\nSolver methods called from outside the solver: total {sum(xs.values()):,}; " + ", ".join(f"{k[2:]} {v:,}" for k, v in sorted(xs.items(), key=lambda t: -t[1])[:14]))
    print(f"\nTheory calls from the solver: lra {tot['lra']:,} (assert {tot['lra.assert_lit']:,} check {tot['lra.check']:,}), euf {tot['euf']:,}, transfer {tot['transfer']:,}, sharing {tot['sharing']:,}. Python session or adapter frames entered during a solver call: " + str({k: v for k, v in tot.items() if k.endswith('_in_search')} or 0) + f". Sessions {tot['sessions']:,}, _visit {tot['session._visit']:,}, _compile_patterns {tot['session._compile_patterns']:,}, escalate {tot['session.escalate']:,}, discover {tot['session.discover']:,}, build_context {tot['engine._build_context']:,}, _is_custom {tot['engine._is_custom']}, facts-custom {tot.get('custom.facts_for',0)}")
    # the arithmetic
    ks, kl = K[wl]
    print(f"\nMost a timed pass could show, crossings free (k {ks}, k_lra {kl}, per class where measured):\n\n| slice | queries in Rust | None q | def q | time of those queries % | moved SAT % | moved LRA % | max speedup whole | None | definite | stays 1x, k_rest for 2x: outside only | outside + SymPy-on-stack |\n|---|" + "---:|" * 11)
    for name, H in SL.items():
        I = [i for i in range(n) if cls[i] in H]
        row = [len(I), sum(none[i] for i in I), sum(not none[i] for i in I), f"{100*sum(t[i] for i in I)/T:.1f}"]
        ms = sum(v for (c, p, s), v in pt.items() if c in H and p == "sat") / T
        rat = H - {"constants"}
        ml = sum(v for (c, p, s), v in pt.items() if c in rat and p == "lra_core") / T
        def speed(sel):
            Ts = sum(t[i] for i in range(n) if sel(i))
            mss = 0.0; mll = 0.0
            for q in range(n):
                if not sel(q) or cls[q] not in H: continue
                tt = sum(smp[q].values())
                if not tt: continue
                mss += t[q] * sum(v for (p, s), v in smp[q].items() if p == "sat") / tt
                if cls[q] in rat:
                    mll += t[q] * sum(v for (p, s), v in smp[q].items() if p == "lra_core") / tt
            return Ts / (Ts - mss * (1 - 1 / ks) - mll * (1 - 1 / kl))
        out = sum(v for (c, p, s), v in pt.items() if p in ("outside", "unsampled")) / T
        sym = sum(v for (c, p, s), v in pt.items() if s and p not in ("outside", "unsampled", "sat", "lra_core")) / T
        def krest(stay):
            left = 0.5 - stay - ms / ks - ml / kl
            rest = 1 - stay - ms - ml
            return "unreachable" if left <= 0 else f"{rest/left:.2f}"
        row += [f"{100*ms:.1f}", f"{100*ml:.1f}", f"{1/(1-ms*(1-1/ks)-ml*(1-1/kl)):.2f}", f"{speed(lambda i: none[i]):.2f}", f"{speed(lambda i: not none[i]):.2f}", krest(out), krest(out + sym)]
        print(f"| {name} | " + " | ".join(str(x) for x in row) + " |")
    print(f"\nStays: outside {100*out:.1f}%, SymPy on stack outside the moved parts {100*sym:.1f}%. Sum of per-query medians {T:.3f} s.")
