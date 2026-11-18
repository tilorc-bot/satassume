"""sum325.py RUN_DIR COUNT_DIR TIME_JSONL [LISTS_OUT] (sa-port-325, issue 323): the tables of results/none-certify.md.

RUN_DIR: cap325.py's WL.jsonl rows (pure-Python pass, exact substitution). COUNT_DIR: sa-port-322's count rows (WL.jsonl),
classified by tools322/sum322.py's own ``klass``. TIME_JSONL: 322's quiet-lease S1 rows (12 rounds an arm); a query's time
is the median of its own seconds over the rounds, as in none-classes.md. No new timing is taken here.
LISTS_OUT: every class (i) query that is not certified both ways by its models, by workload and id.
"""
import json, os, statistics, sys
from collections import Counter as C

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools322"))
import sum322

run, cdir, tj = sys.argv[1:4]
lists_out = sys.argv[4] if len(sys.argv) > 4 else None
trows = [json.loads(l) for l in open(tj)]
ARM_ON, ARM_DEF = "5b1d96f+rust+frames", "5b1d96f"
lists = []


def pct(a, b):
    return "%.1f%%" % (100.0 * a / b) if b else "-"


def bucket(m):
    """The (a) row of a query from its two polarity verdicts."""
    t, f = m["T"]["v"], m["F"]["v"]
    vs = sorted((t, f))
    if vs == ["ok", "ok"]:
        return "both"
    if "unk" in vs:
        return "uncheckable"
    if vs == ["fail", "ok"]:
        return "one way"
    return "neither"


def faithful(m):
    return all(m[k].get("info") and m[k]["info"]["bad"] == 0 and m[k]["info"]["und"] == 0 for k in ("T", "F"))


def quant(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


for wl in ("dev", "fuzz"):
    head322, rows322 = sum322.load(os.path.join(cdir, wl + ".jsonl"))
    rows = [json.loads(l) for l in open(os.path.join(run, wl + ".jsonl"))]
    head = json.load(open(os.path.join(run, wl + ".jsonl.head")))
    n = len(rows)
    assert n == len(rows322) == head["n"]
    print("=" * 110)
    print(f"{wl}: {n} queries; pure-Python digest {head['digest']} against the count build's {head322['digest']}: "
          f"{'EQUAL' if head['digest'] == head322['digest'] else 'DIFFERENT'}; search cap {head['cap']}; "
          f"rows with an error: {sum(1 for r in rows if r.get('error'))}; queries with a declared symbol: "
          f"{sum(1 for r in rows if r.get('declared'))}")
    for r, r2 in zip(rows, rows322):
        assert r["i"] == r2["i"] and (r["ans"] is None) == (r2["ans"] is None), r["i"]
    kl = [sum322.klass(r2) if r2["ans"] is None else None for r2 in rows322]
    med = {}
    for arm in (ARM_ON, ARM_DEF):
        ts = [t for t in trows if t["wl"] == wl and t["sha"] == arm]
        assert len(ts) == 12 and all(t["digest"] == head322["digest"] for t in ts)
        med[arm] = [statistics.median(t["per"][i] for t in ts) for i in range(n)]
    tot = {arm: sum(med[arm]) for arm in med}
    ci = [i for i in range(n) if kl[i] == "i"]
    print(f"class (i) own rows (322's klass): {len(ci)}; time both on {1e3 * sum(med[ARM_ON][i] for i in ci):.1f} ms "
          f"({pct(sum(med[ARM_ON][i] for i in ci), tot[ARM_ON])} of {1e3 * tot[ARM_ON]:.1f}), default "
          f"{1e3 * sum(med[ARM_DEF][i] for i in ci):.1f} ms ({pct(sum(med[ARM_DEF][i] for i in ci), tot[ARM_DEF])})")
    # ---- sanity: the pure-Python pass sees a deciding entailment with a model each way for the same queries
    hasm = [i for i in ci if rows[i].get("model") and rows[i]["model"].get("ent")]
    shape = C((rows[i]["model"]["ent"], rows[i]["model"]["r"], rows[i]["model"]["solves"], rows[i]["model"]["sat"]) for i in hasm)
    print(f"  with a deciding entailment in the pure-Python pass: {len(hasm)}; (kind, result, solves, satisfiable): "
          f"{dict(shape.most_common(8))}")
    other = [i for i in range(n) if rows[i]["ans"] is None and kl[i] != "i" and rows[i].get("model") and rows[i]["model"].get("ent")]
    print(f"  None queries of other classes with a deciding entailment here: {len(other)} {dict(C(kl[i] for i in other))}")

    # ---- (a) the two polarity models
    print(f"\n(a) {wl}: class (i), each polarity's model point substituted exactly into the original p and A")
    bk = {i: bucket(rows[i]["model"]) for i in hasm}
    cnt = C(bk.values())
    for b in ("both", "one way", "neither", "uncheckable"):
        ids = [i for i in hasm if bk[i] == b]
        t = sum(med[ARM_ON][i] for i in ids)
        extra = ""
        if b == "both":
            fa = sum(1 for i in ids if faithful(rows[i]["model"]))
            ar = sum(1 for i in ids if rows[i].get("arith"))
            extra = f"; the point reproduces every block of the model: {fa}, not: {len(ids) - fa}; field arithmetic only: {ar}"
        print(f"  {b:12s} {len(ids):5d} {pct(len(ids), len(hasm)):>6s}  time {1e3 * t:8.1f} ms {pct(t, tot[ARM_ON]):>6s}{extra}")
    pair = C((rows[i]["model"]["T"]["v"], rows[i]["model"]["F"]["v"]) for i in hasm)
    print("  (True-side, False-side) verdict pairs:", dict(pair.most_common()))
    why = C()
    for i in hasm:
        for k in ("T", "F"):
            d = rows[i]["model"][k]
            if d["v"] != "ok":
                why[(bk[i], d["v"], d["why"][:75])] += 1
    print("  reasons, per polarity not certified (row, verdict, reason): count")
    for (b, v, w), c in sorted(why.items(), key=lambda kv: (kv[0][0], -kv[1])):
        print(f"    {b:12s} {v:5s} {c:5d}  {w}")
    how = C()
    for i in hasm:
        for k in ("T", "F"):
            inf = rows[i]["model"][k].get("info")
            if inf:
                for key in ("lra", "rep", "relaxed", "norep", "missing", "lra_nonq", "filled"):
                    how[key] += inf.get(key, 0)
    print("  how the symbols of the chosen points got their values (symbol count):", dict(how))

    # ---- the remainder against the session-free search: is there ANY exact witness pair?
    def srch(i):
        s = rows[i].get("search") or {}
        return s.get("T") is not None, s.get("F") is not None
    print(f"\n  {wl}: the same queries, any exact witness (a model's point or a searched simple point), per polarity")
    fin = C()
    left = []
    for i in hasm:
        m = rows[i]["model"]
        st, sf = srch(i)
        okT, okF = m["T"]["v"] == "ok" or st, m["F"]["v"] == "ok" or sf
        fin[(bk[i], "both" if okT and okF else "one" if okT or okF else "none")] += 1
        if not (okT and okF):
            left.append(i)
    for b in ("both", "one way", "neither", "uncheckable"):
        print(f"    model row {b:12s}: exact pair exists {fin[(b, 'both')]:5d}, one side only {fin[(b, 'one')]:4d}, no side {fin[(b, 'none')]:4d}")
    tl = sum(med[ARM_ON][i] for i in left)
    print(f"    class (i) with no exact witness pair from either source: {len(left)} of {len(hasm)} ({pct(len(left), len(hasm))}), "
          f"time {1e3 * tl:.1f} ms {pct(tl, tot[ARM_ON])}")
    # the rows with no exact pair: is the missing side undecided somewhere (uncheckable), or decided the other way at
    # every point tried (a candidate wrong-or-incomplete None)?
    cand, unck = [], []
    whyu = C()
    for i in left:
        m, s = rows[i]["model"], rows[i]["search"]
        st, sf = srch(i)
        und = None
        for k, found in (("T", st), ("F", sf)):
            if m[k]["v"] == "ok" or found:
                continue
            if m[k]["v"] == "unk":
                und = und or ("model point: " + m[k]["why"])
        if s["punk"]:
            und = und or ("searched point, proposition: " + str(s["pwhy"]))
        if s["aunk"] and und is None and s["sat"] == 0:
            und = "searched point, assumptions: " + str(s["awhy"])
        if und:
            unck.append(i); whyu[und[:90]] += 1
        else:
            cand.append(i)
    tc, tu = sum(med[ARM_ON][i] for i in cand), sum(med[ARM_ON][i] for i in unck)
    print(f"    of these, UNCHECKABLE (the missing side is undecided at some point tried): {len(unck)}, time {1e3 * tu:.1f} ms {pct(tu, tot[ARM_ON])}")
    for w, c in whyu.most_common(12):
        print(f"      {c:4d}  {w}")
    print("      ids:", " ".join(str(i) for i in unck))
    print(f"    CANDIDATES (every point tried that satisfies A gives p the same decided value): {len(cand)}, time {1e3 * tc:.1f} ms {pct(tc, tot[ARM_ON])}")
    for i in cand:
        s = rows[i]["search"]
        st, sf = srch(i)
        m = rows[i]["model"]
        side = "always True" if (st or m["T"]["v"] == "ok") else "always False" if (sf or m["F"]["v"] == "ok") else "no point satisfies A"
        print(f"      {wl} {i}: p {side} at {s['sat']} of {s['n']} points (A undecided at {s['aunk']}) | {rows[i].get('q')} | {rows[i].get('a')}"[:250])
    for i in hasm:
        if bk[i] != "both":
            m = rows[i]["model"]
            st, sf = srch(i)
            lists.append(dict(wl=wl, i=i, row=bk[i], T=m["T"]["v"], F=m["F"]["v"], whyT=m["T"]["why"], whyF=m["F"]["why"],
                              searchT=st, searchF=sf, q=rows[i].get("q"), a=rows[i].get("a"),
                              end="pair" if i not in left else "candidate" if i in cand else "uncheckable"))

    # ---- (b) before any session: simple points only
    print(f"\n(b) {wl}: session-free search (simple points from p and A alone, cap {head['cap']} substitutions)")
    sb = [i for i in ci if all(srch(i))]
    t_on, t_def = sum(med[ARM_ON][i] for i in sb), sum(med[ARM_DEF][i] for i in sb)
    ci_on = sum(med[ARM_ON][i] for i in ci)
    print(f"  class (i) with both witnesses found: {len(sb)} of {len(ci)} ({pct(len(sb), len(ci))}); their session time: both on "
          f"{1e3 * t_on:.1f} ms = {pct(t_on, ci_on)} of class (i), {pct(t_on, tot[ARM_ON])} of the workload; default "
          f"{1e3 * t_def:.1f} ms = {pct(t_def, tot[ARM_DEF])} of the workload")
    need = [max(rows[i]["search"]["atT"], rows[i]["search"]["atF"]) for i in sb]
    print(f"  substitutions until both were found: median {quant(need, .5)}, 90% {quant(need, .9)}, 99% {quant(need, .99)}, max {max(need) if need else None}; "
          f"within 8: {sum(1 for x in need if x <= 8)}, within 32: {sum(1 for x in need if x <= 32)}, within 128: {sum(1 for x in need if x <= 128)}")
    for capn in (8, 32, 128):
        ids = [i for i, x in zip(sb, need) if x <= capn]
        t = sum(med[ARM_ON][i] for i in ids)
        print(f"    at a cap of {capn:4d} substitutions: {len(ids)} queries ({pct(len(ids), len(ci))}), {1e3 * t:.1f} ms = {pct(t, tot[ARM_ON])} of the workload")
    miss = [i for i in ci if not all(srch(i))]
    print(f"  not found: {len(miss)}: {dict(C(('T' if srch(i)[0] else '-') + ('F' if srch(i)[1] else '-') for i in miss))} "
          f"(T-: only the True side found, and so on); with no point satisfying A at all: {sum(1 for i in miss if rows[i]['search']['sat'] == 0)}")
    # the check's own model
    ck = [i for i in hasm if rows[i].get("check")]
    dec = [i for i in ck if rows[i]["check"]["ta"] is True and rows[i]["check"]["tp"] in (True, False)]
    oth = [i for i in dec if srch(i)[0 if rows[i]["check"]["tp"] is False else 1]]
    print(f"  the set check's own point: held for {len(ck)} of {len(hasm)}; satisfies A and decides p exactly: {len(dec)} "
          f"({dict(C(str(rows[i]['check']['tp']) for i in dec))}); the other side then found by search: {len(oth)}")
    ckw = C()
    for i in ck:
        c = rows[i]["check"]
        if not (c["ta"] is True and c["tp"] in (True, False)):
            ckw["A false at the point" if c["ta"] is False else ("A: " + str(c["ta"])[:50]) if c["ta"] is not True else "p: " + str(c["tp"])[:50]] += 1
    print("    check point not usable:", dict(ckw.most_common(6)))

    # ---- every query: does the search contradict an answer?
    print(f"\n  {wl}: the search over EVERY query against the answer")
    con = C()
    bad = []
    for i, r in enumerate(rows):
        s = r.get("search")
        if not s:
            con[(str(r["ans"]), "no search row")] += 1
            continue
        st, sf = s["T"] is not None, s["F"] is not None
        a = r["ans"]
        if a is True:
            key = "CONTRADICTED: a point with A true and p false" if sf else "consistent"
        elif a is False:
            key = "CONTRADICTED: a point with A true and p true" if st else "consistent"
        elif a == "ValueError":
            key = "CONTRADICTED: a point with A true" if s["sat"] else "consistent"
        elif a is None:
            key = "both found" if st and sf else "one side" if st or sf else "no side"
        else:
            key = "other"
        con[(str(a), key)] += 1
        if key.startswith("CONTRA"):
            bad.append(i)
    for k, c in sorted(con.items()):
        print(f"    answer {k[0]:10s} {c:5d}  {k[1]}")
    for i in bad[:40]:
        print("      contradicted:", wl, i, rows[i]["ans"], rows[i]["search"]["T"], "|", rows[i]["search"]["F"], "| sat", rows[i]["search"]["sat"])
    # None by 322 class
    print(f"  {wl}: None answers by 322's class, search finds both sides / all")
    byc = C(); byc2 = C()
    for i, r in enumerate(rows):
        if r["ans"] is None:
            byc[kl[i]] += 1
            if all(srch(i)):
                byc2[kl[i]] += 1
    for k in sorted(byc):
        print(f"    {k:28s} {byc2[k]:5d} / {byc[k]:5d}")
    ev = [r["search"]["n"] for r in rows if r.get("search")]
    secs = sum(r["search"]["s"] for r in rows if r.get("search"))
    print(f"  substitutions made in all: {sum(ev)}; this script's own Python time for them {secs:.1f} s (orion, shared, not a wall time)")

if lists_out:
    with open(lists_out, "w") as fh:
        fh.write("# class (i) queries NOT certified both ways by their own models (sa-port-325). Columns: workload, id, row, "
                 "True-side verdict, False-side verdict, search found True side, search found False side, end state (pair: an exact "
                 "witness pair exists from either source; uncheckable; candidate), reasons, query\n")
        for d in lists:
            fh.write(f"{d['wl']}\t{d['i']}\t{d['row']}\tT={d['T']}\tF={d['F']}\tsT={int(d['searchT'])}\tsF={int(d['searchF'])}\t{d['end']}\t"
                     f"{d['whyT'][:60]} / {d['whyF'][:60]}\t{d['q']} | {d['a']}\n")
    print("\nlists:", lists_out, len(lists), "rows")
