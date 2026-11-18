"""ana329.py CNT_DIR RUN325 COUNT322 TOOLS322 [COST_JSONL] (sa-port-329, issue 323): the planner's items (3) and (4).

CNT_DIR: cnt329.py's uncapped `reasons` rows, WL-new-reasons.json (pure Python). RUN325: sa-port-325's run3 rows
(its simple-point search per query). COUNT322, TOOLS322: sa-port-322's count rows and its sum322.py, whose `klass`
names class (i). COST_JSONL: the pinned per-call times of time329.sh (cost.jsonl), if given.
(3) 325's class (i) Nones with both witnesses found by its search (dev 368, fuzz 2157): certified here or not, and the
    ones not certified by reason; the same for every None answer.
(4) certified at caps 4, 8, 16, 32 and with no cap (a pair found at the t-th point is found under every cap >= t);
    with COST_JSONL the check's own time split by what the call did: certified, fell through with no point tried
    (an undecided atom), fell through after a search. Median over the rounds of each call's own seconds."""
import json, os, statistics, sys
from collections import Counter
cnt, run325, c322, t322 = sys.argv[1:5]
cost = sys.argv[5] if len(sys.argv) > 5 else None
sys.path.insert(0, t322)
import sum322
CAPS = (4, 8, 16, 32)


def group(w):
    if w.startswith("atom: function") or w.startswith("atom: undefined"):
        return "undecided atom: a function"
    if w.startswith("atom: ") or w.startswith("own: "):
        return "undecided atom: " + w.split(": ", 1)[1]
    return w


for wl in ("dev", "fuzz"):
    d = json.load(open(f"{cnt}/{wl}-new-reasons.json"))
    assert d["cap"] == 0 and d["witness"] and d["reasons"]
    n, ans = d["n"], d["ans"]
    last = {}                       # query -> its last call's (why, points tried, points available)
    for (i, w, tried, prod), c in zip(d["why"], d["calls"]):
        assert i == c[0]
        last[i] = (w, c[3] if c[2] else tried, prod)
    ncalls = Counter(c[0] for c in d["calls"])
    cert = {i: t for i, (w, t, p) in last.items() if w == "certified"}
    assert all(ans[i] is None for i in cert) and len(cert) == d["certified"]
    nones = [i for i in range(n) if ans[i] is None]
    print(f"== {wl}: {n} queries, digest {d['digest']}; None answers {len(nones)}; queries with a call of the check "
          f"{len(ncalls)} (calls {d['fires']}, at most {max(ncalls.values())} a query); certified with no cap {len(cert)}")
    print("   certified by cap: " + ", ".join(f"cap {c}: {sum(1 for t in cert.values() if t <= c)}" for c in CAPS)
          + f", no cap (limit 2000): {len(cert)}")
    print(f"   derived predicates asked for: {d['used']}")

    def why32(i):
        if i not in last:
            if not d["ctx"][i]:
                return "no call: not contextual (asked without assumptions)"
            e = d["entry"][i]
            return ("no call: the answer memo of the relevant part answered (no engine call)" if e is None else
                    "no call: not contextual at the engine (no conjunct of the assumptions is relevant, or a constant proposition)"
                    if e == "without assumptions" else "no call: the formula is out of scope, or constant")
        w, t, prod = last[i]
        if w == "certified":
            return "certified" if t <= 32 else "no pair within the cap of 32 (found at a later point)"
        if w.startswith("no pair"):
            sides = {"T": "only the True side", "F": "only the False side", "none": "neither side"}[w.split(": ")[1]]
            return f"no rational pair: {sides} found, " + ("every candidate point tried" if t < 2000 else "limit 2000 reached")
        return group(w)

    head322, rows322 = sum322.load(os.path.join(c322, wl + ".jsonl"))
    rows = [json.loads(l) for l in open(os.path.join(run325, wl + ".jsonl"))]
    assert len(rows) == len(rows322) == n and all((r["ans"] is None) == (ans[r["i"]] is None) for r in rows)
    ci = [i for i in range(n) if rows322[i]["ans"] is None and sum322.klass(rows322[i]) == "i"]
    sb = [i for i in ci if (rows[i].get("search") or {}).get("T") is not None and (rows[i].get("search") or {}).get("F") is not None]
    for name, ids in (("325's class (i) Nones with both witnesses from its search", sb), ("class (i) Nones (322's klass)", ci),
                      ("all None answers", nones)):
        c = Counter(why32(i) for i in ids)
        nc = sum(1 for i in ids if i in cert)
        print(f"   {name}: {len(ids)}; certified here at cap 32: {c['certified']} ({100 * c['certified'] / len(ids):.1f}%), "
              f"with no cap: {nc} ({100 * nc / len(ids):.1f}%); not certified at cap 32, by reason:")
        for k, v in c.most_common():
            if k != "certified":
                print(f"      {v:5d}  {k}")
    print(f"   certified here but not in 325's set: {len(set(cert) - set(sb))} (class (i): {len(set(cert) & set(ci) - set(sb))})")
    if not cost:
        continue
    rows_c = [json.loads(l) for l in open(cost) if l.strip()]
    for arm in sorted(set(r["arm"] for r in rows_c)):
        rs = [r for r in rows_c if r["arm"] == arm and r["wl"] == wl]
        if not rs:
            continue
        assert len(set(r["digest"] for r in rs)) == 1 and rs[0]["digest"] == d["digest"], (arm, wl)
        k = len(rs[0]["calls"])
        assert all(len(r["calls"]) == k == len(d["calls"]) for r in rs)
        cap = rs[0]["cap"] or 2000
        sec = [statistics.median(r["calls"][j][1] for r in rs) for j in range(k)]
        cls = []
        for j in range(k):
            c = rs[0]["calls"][j]
            assert all(r["calls"][j][2] == c[2] and r["calls"][j][0] == d["calls"][j][0] for r in rs)
            w = d["why"][j][1]
            cls.append("certified" if c[2] else "fell through, no point tried" if not (w.startswith("no pair") or w == "certified")
                       else "fell through after a search")
        tot = statistics.median(r["s"] for r in rs)
        print(f"   {arm} ({len(rs)} rounds, so {rs[0]['so']}): calls {k}, check {1e3 * sum(sec):.1f} ms of a {1e3 * tot:.0f} ms pass")
        for name in ("certified", "fell through, no point tried", "fell through after a search"):
            xs = [sec[j] for j in range(k) if cls[j] == name]
            if xs:
                print(f"      {name}: {len(xs)} calls, {1e3 * sum(xs):.1f} ms, median {1e6 * statistics.median(xs):.0f} us, "
                      f"mean {1e6 * sum(xs) / len(xs):.0f} us, max {1e6 * max(xs):.0f} us")
