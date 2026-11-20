"""cmp359.py PY.jsonl RUST.jsonl (sa-port-359): diff359.py's rows, Python's walker against SLICE_CONVERT=rust, per query:
the answer, Engine.stats, last_budget_limited, and per conversion kept/converted, counts (the same keys in the same
order with the same numbers), raised (the same entries in the same order) and the number of terms. One line."""
import json, sys
a, b = ([json.loads(l) for l in open(f)] for f in sys.argv[1:3])
ta, tb = a.pop(), b.pop()
assert ta.get("total") and tb.get("total"), "a pass did not end"
n = dict(answer=0, stats=0, bl=0, cv_calls=0, kept=0, counts=0, raised=0, terms=0)
first = None
convs = kept = raised = reads = 0
for x, y in zip(a, b):
    d = [k for k, kk in (("answer", "a"), ("stats", "stats"), ("bl", "bl")) if x[kk] != y[kk]]
    if len(x["cv"]) != len(y["cv"]):
        d.append("cv_calls")
    for cx, cy in zip(x["cv"], y["cv"]):
        convs += 1
        if cx[0] == "kept" or cy[0] == "kept":
            kept += cx[0] == "kept"
            if cx != cy:
                d.append("kept")
            continue
        raised += len(cx[2])
        reads += sum(v for k, v in cx[1] if k.startswith("read:"))
        d += [k for k, i in (("counts", 1), ("raised", 2), ("terms", 3)) if cx[i] != cy[i]]
    for k in set(d):
        n[k] += 1
    if d and first is None:
        first = (x["q"], sorted(set(d)))
ok = len(a) == len(b) and len(a) == ta["n"] == tb["n"] and not any(n.values()) and ta["walk"] == "py" and tb["walk"] != "py"
print(f"{ta['wl']} queries {len(a)}/{len(b)} conversions {convs} kept {kept} reads {reads} raised {raised} differ {n} first {first} "
      f"digest {ta['digest']} {tb['digest']} walk {ta['walk']}|{tb['walk']} so {tb['so']} cv {tb['cv']} cv_py {ta['cv']} "
      f"term_raised {len(ta['term_raised'])}/{len(tb['term_raised'])} life_py {ta['life']} life_rust {tb['life']} {'EQUAL' if ok and ta['term'] == tb['term'] and ta['term_raised'] == tb['term_raised'] else 'DIFFER'}")
