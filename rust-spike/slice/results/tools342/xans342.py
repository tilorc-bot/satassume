"""xans342.py NEWDIR BASEDIR (sa-port-342): gate330.sh's rows of two trees, cell by cell (workload, mode, switch): the
answers and messages of NEW against BASE."""
import glob, json, os, sys
new, base = sys.argv[1:3]
bad = cells = 0
for fa in sorted(glob.glob(f"{new}/*.jsonl")):
    name = os.path.basename(fa)
    fb = f"{base}/{name}"
    if name.count("-") < 2 or not os.path.exists(fb):
        print(name, "NO BASE ROWS")
        bad += 1
        continue
    a = [json.loads(l) for l in open(fa) if l.startswith('{"q"')]
    b = [json.loads(l) for l in open(fb) if l.startswith('{"q"')]
    ad = [(x["q"], x["ans"], y["ans"]) for x, y in zip(a, b) if x["ans"] != y["ans"]]
    md = sum(x.get("msg") != y.get("msg") for x, y in zip(a, b))
    ok = len(a) == len(b) and len(a) > 0 and not ad and not md
    cells += 1
    bad += not ok
    if not ok:
        print(name, f"{len(a)}/{len(b)}", "answers", len(ad), "messages", md, repr(ad[:5]))
print("XANS", cells, "cells;", "answers and messages equal" if not bad else f"{bad} cells differ")
