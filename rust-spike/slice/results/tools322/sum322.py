"""sum322.py COUNT_DIR TIME_JSONL [BB_DIR ...] (sa-port-323, issue 323): the None classes of results/none-classes.md, read
from nc322.py's rows (COUNT_DIR/{dev,fuzz}{,-py,-bbN}.jsonl; further BB_DIRs hold more WL-bbN.jsonl) and from time322.sh's
rows (TIME_JSONL: per-query seconds and answers of 12 unprofiled rounds per arm and workload).

Each query's event string (mkpatch322.py's token grammar) is parsed with a stack: `X<` opens a frame, `X>r` closes it with
result r, anything else is a leaf of the open frame. The DECIDING frame of a query is its last top-level frame when that is a Q (Engine.ask)
or I (Engine.is_) frame; inside an I frame the work is in its last D (Engine._decide) child. The deciding ENTAILMENT is the last
e (Solver.entails) or a (Solver.entails_all) frame directly under that.

Class of a None answer (the brief's (i)-(iv), with the cause named after the colon):
  memo:pA          no event, an earlier equal (p, A): the answer memo (spec.md s1 step 1). Counted apart, and also under
                   the class of the earlier row (column `with repeats`).
  memo:part        no event, first (p, A), not out of scope: the memo under (p, relevant part of A) (spec.md s1 step 3).
  memo:part+check  the last top-level frame is V: the set's complete check ran for the relevance split, then the same memo.
  iii:route:CAT    no event, first (p, A), sympy_api.out_of_scope says CAT: refused before the engine (spec.md s1 step 4).
  ii:discovery     B directly in the deciding frame (Engine._over_budget).
  iii:noncomm      N directly in the deciding frame.     iv:constructing  K directly in it.
  ii:branch:in     xb or xs inside the deciding entailment (a polarity solve's LRA check ran out of BRANCH_BUDGET).
  ii:branch:flag   not that, but the session's exhausted flag is set when the deciding frame ends (Tg1): a check elsewhere
                   in the query's session ran out (the set's check, or a solve outside the entailment).
  iii:gave_up      g inside the deciding entailment, or the gave_up flag at the end (T1e).
  iii:catch        C anywhere in the query (engine.py:1906's catch), none of the above.
  i                the rest with a deciding entailment answering N: its solves found a model each way.
  iv:other         anything else (shape printed).
"""
import collections, json, statistics, sys

C = collections.Counter


def load(path):
    rows = [json.loads(l) for l in open(path)]
    return rows[0], rows[1:]


def parse(ev):
    root = dict(k="", r=None, ch=[], leaves=[])
    st = [root]
    for t in ev.split(";"):
        if not t:
            continue
        if len(t) == 2 and t[1] == "<":
            f = dict(k=t[0], r=None, ch=[], leaves=[])
            st[-1]["ch"].append(f)
            st.append(f)
        elif len(t) >= 2 and t[1] == ">":
            if len(st) == 1 or st[-1]["k"] != t[0]:
                raise ValueError("unbalanced " + ev[:120])
            st[-1]["r"] = t[2:]
            st.pop()
        else:
            st[-1]["leaves"].append(t)
    if len(st) != 1:
        raise ValueError("open frame " + ev[:120])
    return root


def flat(f):
    out = list(f["leaves"])
    for c in f["ch"]:
        out += flat(c)
    return out


def has(f, k):
    return f["k"] == k or any(has(c, k) for c in f["ch"])


def deciding(row):
    """(frame, chain, entailment), or None when the query's last top-level frame is not a Q or I frame (the set's check
    ran, V, and nothing after it; an I frame before it is a sub-query of the route, not the answer)."""
    root = parse(row["ev"])
    if not root["ch"] or root["ch"][-1]["k"] not in "QI":
        return None
    d = root["ch"][-1]
    chain = d
    if d["k"] == "I":
        ds = [f for f in d["ch"] if f["k"] == "D"]
        chain = ds[-1] if ds else d
    ea = [f for f in chain["ch"] if f["k"] in "ea"]
    return d, chain, (ea[-1] if ea else None)


def klass(row):
    if not row["ev"]:
        if row["dup"] != row["i"]:
            return "memo:pA"
        return ("iii:route:" + str(row["oos"])) if row.get("oos") else "memo:part"
    dc = deciding(row)
    if dc is None:
        return "memo:part+check"
    d, chain, e = dc
    direct = d["leaves"] + (chain["leaves"] if chain is not d else [])
    if d["r"] != "N":
        return "iv:other:deciding frame result " + str(d["r"])
    if "B" in direct:
        return "ii:discovery"
    if "N" in direct:
        return "iii:noncomm"
    if "K" in direct:
        return "iv:constructing"
    if e is None or e["r"] != "N":
        return "iv:other:no deciding entailment"
    inside = flat(e)
    flags = [t for t in direct if len(t) == 3 and t[0] == "T"]
    fl = flags[-1] if flags else "T??"
    if "xb" in inside or "xs" in inside:
        return "ii:branch:in"
    if fl[2] == "1":
        return "ii:branch:flag"
    if "g" in inside or fl[1] == "1":
        return "iii:gave_up"
    if "C" in row["ev"].split(";"):
        return "iii:catch"
    return "i"


def solves(toks):
    return [tuple(int(x) for x in t.split(":")[1:]) for t in toks if t.startswith("s:")]


def table(title, cols, rows):
    print("\n" + title)
    print("| " + " | ".join(cols) + " |")
    print("|" + "|".join("---" for _ in cols) + "|")
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")


def main():
    cdir, tj = sys.argv[1:3]
    bbdirs = [cdir] + sys.argv[3:]
    trows = [json.loads(l) for l in open(tj)]
    for wl in ("dev", "fuzz"):
        head, rows = load(f"{cdir}/{wl}.jsonl")
        hpy, rpy = load(f"{cdir}/{wl}-py.jsonl")
        n = len(rows)
        print(f"\n## {wl}: {n} queries, digest {head['digest']}, .so {head['so']}, BRANCH_BUDGET {head['bb']}")
        print("both switches off: digest", hpy["digest"], "rows whose events differ from both-on:",
              sum(a["ev"] != b["ev"] for a, b in zip(rows, rpy)))
        sess = {k: v for k, v in head.get("session", {}).items() if k in ("ctx:caught", "ctx:fallback")}
        print("existing counters ctx:caught / ctx:fallback in the header:", sess or "absent (0)")
        ans = C("None" if r["ans"] is None else str(r["ans"]) for r in rows)
        # ---- classes ----
        cl = [None] * n
        bad = 0
        for r in rows:
            if r["ans"] is None:
                cl[r["i"]] = klass(r)
        eff = list(cl)                       # memo:pA resolved to the earlier row's class
        for r in rows:
            if cl[r["i"]] == "memo:pA":
                eff[r["i"]] = cl[r["dup"]] if cl[r["dup"]] is not None else "iv:other:repeat of a non-None"
        with_ev = [r for r in rows if r["ans"] is None and r["ev"] and deciding(r) is not None]
        bad = sum(deciding(r)[0]["r"] != "N" for r in with_ev)
        print(f"None answers {ans['None']}; with a Q or I frame {len(with_ev)}; deciding frame's result not N: {bad}")
        own, wrep = C(cl[i] for i in range(n) if cl[i]), C(eff[i] for i in range(n) if eff[i])
        # anywhere-in-the-session counts
        anyw = C()
        for r in rows:
            if r["ans"] is None and r["ev"]:
                toks = set(r["ev"].split(";"))
                for t in ("xb", "xs", "g", "C", "F", "B", "N", "K", "V>u", "V>i", "T01", "T10", "T11"):
                    if t in toks:
                        anyw[t] += 1
        print("None queries with the token anywhere in their events:", dict(anyw))
        xbq = [r for r in rows if "xb" in r["ev"].split(";")]
        print("all queries with xb anywhere:", len(xbq), "by answer", dict(C(str(r["ans"]) for r in xbq)),
              "| with T?1 at any frame end:", sum(any(t in ("T01", "T11") for t in r["ev"].split(";")) for r in rows),
              "| T?1 without xb:", sum(any(t in ("T01", "T11") for t in r["ev"].split(";")) and "xb" not in r["ev"].split(";") for r in rows))
        # ---- times ----
        arms = {}
        for t in trows:
            if t["wl"] == wl:
                arms.setdefault(t["sha"], []).append(t)
        med = {}
        for arm, ts in sorted(arms.items()):
            same = all(t["digest"] == head["digest"] and t["n"] == n for t in ts)
            eq = all((a is None) == (r["ans"] is None) for a, r in zip(ts[0]["ans"], rows))
            med[arm] = [statistics.median(t["per"][i] for t in ts) for i in range(n)]
            ss = sorted(t["s"] for t in ts)
            print(f"arm {arm}: {len(ts)} rounds, digests equal the count pass: {same}, None rows equal: {eq}, "
                  f"S1 s median {statistics.median(ss):.4f} min {ss[0]:.4f} max {ss[-1]:.4f}, sum of per-query medians {sum(med[arm]):.4f}")
        armn = sorted(med)

        def cells(idx):
            out = [len(idx)]
            for a in armn:
                tot = sum(med[a])
                s = sum(med[a][i] for i in idx)
                out += [f"{1e3 * s:.1f}", f"{100 * s / tot:.1f}", f"{1e6 * s / len(idx):.0f}" if idx else "-"]
            return out
        cols = ["n"] + [f"{a} {x}" for a in armn for x in ("ms", "%", "us/query")]
        byans = collections.defaultdict(list)
        for r in rows:
            byans["None" if r["ans"] is None else str(r["ans"])].append(r["i"])
        table(f"(a) {wl}: time by answer (sum of each query's median over the rounds; % of the arm's summed medians)",
              ["answer"] + cols, [[k] + cells(v) for k, v in sorted(byans.items(), key=lambda kv: -len(kv[1]))])
        # the same split for every answer by the work done, so a None is compared with a definite answer of equal work
        bywork = collections.defaultdict(list)
        for r in rows:
            a = "None" if r["ans"] is None else str(r["ans"])
            if not r["ev"]:
                w = "no event"
            else:
                dc = deciding(r)
                if dc is None:
                    w = "the set's check, then no Q or I frame"
                else:
                    ctx = "contextual" if has(parse(r["ev"]), "V") else "context-free"
                    ns = len(solves(flat(dc[2]))) if dc[2] is not None else 0
                    w = ctx + (", entailment with solves" if ns else ", no entailment solve")
            bywork[(w, a)].append(r["i"])
        table(f"(a) {wl}: time by work and answer", ["work", "answer"] + cols,
              [[w, a] + cells(v) for (w, a), v in sorted(bywork.items())])
        bycl = collections.defaultdict(list)
        for i in range(n):
            if cl[i]:
                bycl[cl[i]].append(i)
        table(f"(b) {wl}: None answers by class (own row; `with repeats` adds the memo:pA rows of that class)",
              ["class", "with repeats"] + cols, [[k, wrep.get(k, 0)] + cells(v) for k, v in sorted(bycl.items())])
        groups = collections.defaultdict(list)
        for i in range(n):
            if cl[i]:
                k = cl[i]
                g = "no engine work (memo:pA, memo:part, iii:route)" if (k.startswith("memo:p") and k != "memo:part+check") or k.startswith("iii:route") else \
                    "the set's check only (memo:part+check)" if k == "memo:part+check" else "(" + k.split(":")[0] + ") engine"
                groups[g].append(i)
        table(f"(b) {wl}: None answers grouped", ["group"] + cols, [[k] + cells(v) for k, v in sorted(groups.items())])
        # ---- (c) class (i): the work per query ----
        ci = [r for r in rows if cl[r["i"]] == "i"]
        pat = C(); nsol = C(); wit = C(); unsat = 0; kinds = C(); first = C()
        for r in ci:
            d, chain, e = deciding(r)
            ctx = "contextual" if has(parse(r["ev"]), "V") else "context-free"
            ss = solves(flat(e))
            unsat += any(s[2] == 0 for s in ss)
            pat[(ctx, e["k"], "".join("R" if s[1] else "S" for s in ss))] += 1
            alls = solves(r["ev"].split(";"))
            nsol[(ctx, len(alls))] += 1
            kinds[(ctx, "searches")] += sum(1 for s in alls if not s[1]); kinds[(ctx, "ring hits")] += sum(1 for s in alls if s[1])
            kinds[(ctx, "queries")] += 1
            for t in r["ev"].split(";"):
                if t in ("w0", "w1"):
                    wit[(ctx, t)] += 1
            if ctx == "contextual" and len(ss) >= 2:
                first[("ring holds a model before the entailment (k>=1)", ss[0][3] >= 1)] += 1
        print(f"\n(c) {wl}: class (i) queries {len(ci)}; with an unsatisfiable solve inside the deciding entailment: {unsat}")
        table(f"(c) {wl}: class (i), solves inside the deciding entailment (S a search, R a ring hit, in order)",
              ["session", "frame", "pattern", "queries"], [[a, b, c, v] for (a, b, c), v in sorted(pat.items(), key=lambda kv: (kv[0][0], -kv[1]))])
        table(f"(c) {wl}: class (i), solve_int calls in the whole query", ["session", "solves", "queries"],
              [[a, b, v] for (a, b), v in sorted(nsol.items())])
        print("totals:", {f"{a} {b}": v for (a, b), v in sorted(kinds.items())}, "| witness_satisfies:", {f"{a} {b}": v for (a, b), v in sorted(wit.items())},
              "|", {f"{a}: {b}": v for (a, b), v in first.items()})
        allq = C()
        for r in rows:
            for s in solves(r["ev"].split(";")):
                allq["ring hits" if s[1] else "searches"] += 1
                allq["unsat"] += s[2] == 0
            for t in r["ev"].split(";"):
                if t in ("w0", "w1", "H"):
                    allq[t] += 1
        print("whole workload:", dict(allq))
        # ---- (c) class (ii): larger and smaller budgets ----
        ii = [i for i in range(n) if cl[i] and cl[i].startswith("ii:")]
        out = []
        import glob, re
        for bd in bbdirs:
            for f in sorted(glob.glob(f"{bd}/{wl}-bb*.jsonl"), key=lambda p: int(re.search(r"bb(\d+)", p).group(1))):
                h, rr = load(f)
                mv = [(a["i"], a["ans"], b["ans"]) for a, b in zip(rows, rr) if a["ans"] != b["ans"]]
                tr = C(f"{a}->{b}" for _, a, b in mv)
                out.append([h["bb"], h["digest"], len(mv), dict(tr) or "-", sum(a["ev"] != b["ev"] for a, b in zip(rows, rr)),
                            sum(rows[i]["ans"] != rr[i]["ans"] for i in ii), sum(rows[i]["ev"] != rr[i]["ev"] for i in ii),
                            sum("xb" in r["ev"].split(";") for r in rr)])
        table(f"(c) {wl}: the pass at another BRANCH_BUDGET against the pass at {head['bb']} (class (ii) queries: {len(ii)})",
              ["budget", "digest", "answers moved", "moves", "event rows differing", "class (ii) answers moved", "class (ii) event rows differing", "queries with xb"], out)
        oth = C(k for k in (cl[i] for i in range(n)) if k and k.startswith("iv:other"))
        if oth:
            print("iv:other shapes:", dict(oth))
            for r in rows:
                if cl[r["i"]] and cl[r["i"]].startswith("iv:other"):
                    print("  e.g.", r["i"], r["q"][:60], "|", r["a"][:60], "|", r["ev"][:200])
                    break


if __name__ == "__main__":
    main()
