"""asks.py: outermost SymPy entries inside the boundary by category, base vs ids live, using cat_of from
tools-rust/analyze.py. Reads the mon JSON from WORK (argv 1)."""
import ast
import json
import os
import sys
from collections import Counter
W = sys.argv[1]
src = open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "tools-rust", "analyze.py")).read()
ns = {}
for node in ast.parse(src).body:
    if isinstance(node, ast.FunctionDef) and node.name == "cat_of" or isinstance(node, ast.Assign):
        try:
            exec(compile(ast.Module([node], []), "a", "exec"), ns)
        except Exception:  # noqa: BLE001 - only the tables cat_of needs matter
            pass
for w in ("dev", "fuzz"):
    t = {}
    for m in ("base", "live"):
        d = json.loads(open(f"{W}/mon-{m}-{w}.json").read().strip().splitlines()[-1])
        c = Counter()
        by = d["by"]
        for side, name, n, *_ in by:   # side 1 is inside the boundary
            if side == 1:
                c[ns["cat_of"](name)] += n
        t[m] = c
    print("|", w, "| base | ids live |")
    for k in sorted(set(t["base"]) | set(t["live"]), key=lambda k: -t["base"][k]):
        print(f"| {k} | {t['base'][k]:,} | {t['live'][k]:,} |")
    print(f"| total | {sum(t['base'].values()):,} | {sum(t['live'].values()):,} |")
