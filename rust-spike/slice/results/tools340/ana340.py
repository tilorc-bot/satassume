"""ana340.py CNT340 CNT329 RUN325 COUNT322 TOOLS322 (sa-port-340, issue 323; offline): cnt340.py's rows joined by query
with 329's reasons rows (CNT329/WL-new-reasons.json, the rows ana329.py's table was made from) and 325's class (i) Nones
with both witnesses (ana329.py's set: 368 dev, 2157 fuzz). Prints, per workload, on that set and on every None answer:
(2a) the pi-blocked queries by what else stands in them, (2b) pi in the no-rational-pair rows, (3) certified within
32 points under each pool order (h head, r roots, c constants, t tail; hrct is witness._pools's order)."""
import json, os, sys
from collections import Counter
c340, c329, run325, c322, t322 = sys.argv[1:6]
sys.path.insert(0, t322)
import sum322
for wl in ("dev", "fuzz"):
    d, o = json.load(open(f"{c340}/{wl}.json")), json.load(open(f"{c329}/{wl}-new-reasons.json"))
    n = d["n"]
    assert n == o["n"] and [r["i"] for r in d["rows"]] == [w[0] for w in o["why"]], "not the same calls"
    same = sum((a is None) == (b is None) for a, b in zip(d["ans"], o["ans"]))
    row = {r["i"]: r for r in d["rows"]}          # one call a query at most on both workloads (asserted)
    assert len(row) == len(d["rows"])
    why = {w[0]: w[1] for w in o["why"]}
    rows322 = sum322.load(os.path.join(c322, wl + ".jsonl"))[1]
    r325 = [json.loads(l) for l in open(os.path.join(run325, wl + ".jsonl"))]
    ci = [i for i in range(n) if rows322[i]["ans"] is None and sum322.klass(rows322[i]) == "i"]
    sb = [i for i in ci if (r325[i].get("search") or {}).get("T") is not None and (r325[i].get("search") or {}).get("F") is not None]
    nones = [i for i in range(n) if d["ans"][i] is None]
    print(f"== {wl}: {n} queries, digest {d['digest']} (329's {o['digest']}; None in the same places {same}/{n}), witness.py "
          f"{d['witness_sha']}; calls {len(row)}; certified uncapped {sum(r['cert'] for r in row.values())} (329: {o['certified']})")
    for name, ids in (("325's class (i) Nones with both witnesses", sb), ("all None answers", nones)):
        print(f" -- {name}: {len(ids)}")
        pis = [i for i in ids if why.get(i) == "atom: constant pi"]
        c = Counter()
        for i in pis:
            r = row[i]
            ctx = set(r["pi"])
            oth = sorted(set(k for k, _ in r["other"]))
            if not r["pi"]:
                c["no pi leaf outside a function (329's kind was the first undecided leaf met)"] += 1
            elif oth:
                c["pi outside a function, and also undecided: " + ", ".join(k.split()[0] for k in oth)] += 1
            elif ctx <= {"plain", "base:N"}:
                c["RECOVERABLE AT MOST: pi only under Add, Mul and non-negative integer literal powers; nothing else undecided"] += 1
            else:
                c["pi only outside functions, but under another power: " + ", ".join(sorted(ctx - {"plain", "base:N"}))] += 1
        print(f"   (2a) pi-blocked (329's reason 'a constant pi'): {len(pis)}")
        for k, v in c.most_common():
            print(f"        {v:5d} ({100 * v / max(len(pis), 1):5.1f}%)  {k}")
        allpi = [i for i in ids if i in row and (row[i]["pi"] or any(p for _, p in row[i]["other"]))]
        print(f"        queries with a pi anywhere (any reason): {len(allpi)}; by 329's reason: "
              f"{dict(Counter(why[i].split(': ')[0] + ': ' + why[i].split(': ')[1].split()[0] for i in allpi))}")
        nop = [i for i in ids if why.get(i, "").startswith("no pair") and row[i]["sim"] is not None]
        print(f"   (2b) no-rational-pair rows (search ended with no pair, uncapped): {len(nop)}; with a pi leaf: "
              f"{sum(1 for i in nop if row[i]['pi'])}; with a pi inside a function: {sum(1 for i in nop if any(p for _, p in row[i]['other']))}")
        print("   (3) certified within 32 points, by pool order (uncapped in brackets):")
        base = {i for i in ids if i in row and row[i]["sim"] and row[i]["sim"]["hrct"] is not None and row[i]["sim"]["hrct"] <= 32}
        late = {i for i in ids if i in row and row[i]["sim"] and row[i]["sim"]["hrct"] is not None and row[i]["sim"]["hrct"] > 32}
        for k in d["orders"]:
            t = {i: row[i]["sim"][k] for i in ids if i in row and row[i]["sim"]}
            in32 = {i for i, v in t.items() if v is not None and v <= 32}
            unc = sum(1 for v in t.values() if v is not None)
            print(f"        {k}: {len(in32):5d} [{unc}]  gained {len(in32 - base):4d} (of the {len(late)} found after point 32: "
                  f"{len(in32 & late)}), lost {len(base - in32):4d}; net {len(in32) - len(base):+d} = {100 * (len(in32) - len(base)) / len(ids):+.1f}% of the class")
        ns = Counter(row[i]["nsyms"] for i in late)
        print(f"        the {len(late)} found after point 32, by number of symbols: {dict(sorted(ns.items()))}")
