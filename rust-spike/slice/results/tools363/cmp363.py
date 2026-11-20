"""cmp363.py BASE.jsonl NEW.jsonl (sa-port-363): diff359.py's rows of one workload under one walker, on 966268c and on
the removal, per query: the answer, Engine.stats, last_budget_limited, and per conversion kept (reason and detail, the
refusals) or converted with its counts (the same keys in the same order with the same numbers), raised (the same
entries in the same order) and the number of terms. Then the pass: the walker, sa_solver.walk_counts() (740-746),
term_live.counts() and RAISED, the walkers' lifetime. One line; `kept` tallies NEW's refusals by reason, and `power`
is NEW's `read:power` (conversions that asked for one, reads), which is what a power row (plant 769's site) is for."""
import json, sys
from collections import Counter
a, b = ([json.loads(l) for l in open(f)] for f in sys.argv[1:3])
ta, tb = a.pop(), b.pop()
assert ta.get("total") and tb.get("total"), "a pass did not end"
n = dict(answer=0, stats=0, bl=0, cv_calls=0, kept=0, counts=0, raised=0, terms=0)
first = None
convs = raised = reads = 0
kept = Counter()
power = [0, 0]
for x, y in zip(a, b):
    d = [k for k, kk in (("answer", "a"), ("stats", "stats"), ("bl", "bl")) if x[kk] != y[kk]]
    if len(x["cv"]) != len(y["cv"]):
        d.append("cv_calls")
    for cx, cy in zip(x["cv"], y["cv"]):
        convs += 1
        if cx[0] == "kept" or cy[0] == "kept":
            if cy[0] == "kept":
                kept[cy[1]] += 1
            if cx != cy:
                d.append("kept")
            continue
        raised += len(cy[2])
        reads += sum(v for k, v in cy[1] if k.startswith("read:"))
        p = dict(cy[1]).get("read:power", 0)
        power[0] += p > 0
        power[1] += p
        d += [k for k, i in (("counts", 1), ("raised", 2), ("terms", 3)) if cx[i] != cy[i]]
    for k in set(d):
        n[k] += 1
    if d and first is None:
        first = (x["q"], sorted(set(d)))
tot = [k for k in ("wl", "n", "walk", "cv", "term", "term_raised", "life", "digest", "env") if ta[k] != tb[k]]
ok = len(a) == len(b) and len(a) == ta["n"] == tb["n"] and not any(n.values()) and not tot
print(f"{ta['wl']} walk {tb['walk'] if tb['walk'] == 'py' else 'rust'} queries {len(a)}/{len(b)} conversions {convs} kept {dict(sorted(kept.items()))} "
      f"reads {reads} power {power} raised {raised} differ {n} first {first} pass-differs {tot} digest {ta['digest']} {tb['digest']} "
      f"so {ta['so']} {tb['so']} cv {tb['cv']} term_raised {len(tb['term_raised'])} life {tb['life']} {'EQUAL' if ok else 'DIFFER'}")
