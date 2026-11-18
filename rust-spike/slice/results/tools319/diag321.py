"""diag321.py OUT: where does the complete check's refutation happen? One ask per case, per-case sums."""
import os, sys, gc
out = sys.argv[1]
S = os.environ["SLICE_DIR"]
sys.path.insert(0, S)
import p_install
p_install.install()
from satassume import sympy_api
import sa_solver, backend
backend.install_euf()
import term_live; term_live.from_env()
import lra_live; lra_live.from_env()
import session_live; session_live.from_env()
import knowledge_live; knowledge_live.from_env()
backend.install()
def parse(line):
    d = {}
    for kv in line.split()[1:]:
        k, v = kv.split("=", 1)
        if ";" in v: d[k] = [[int(x) for x in r.split(",")] for r in v.split(";")]
        elif "," in v: d[k] = [int(x) for x in v.split(",")]
        else: d[k] = int(v) if v.lstrip("-").isdigit() else v
    return d
def last():
    rows = {}
    if os.path.exists(out):
        for line in open(out):
            if line.startswith("S "):
                d = parse(line); rows[d["ser"]] = d
    return rows
from sympy import Q, symbols
x, y, z = symbols("x y z", real=True)
P, N, Z = Q.positive, Q.negative, Q.zero
cases = {
 "A inconsistent bounds (320's)": (Q.gt(x, 5), Q.gt(x, 1) & Q.lt(x, 0) & Q.gt(y, x)),
 "B propositional, needs a decision": (P(x), (P(x) | P(y)) & (P(x) | ~P(y)) & (~P(x) | P(y)) & (~P(x) | ~P(y))),
 "C consistent with disjunctions": (Q.gt(x + y, 0), (Q.gt(x, 1) | Q.gt(y, 1)) & (Q.lt(x, 3) | Q.lt(y, 3)) & Q.gt(x, y)),
 "D lra cycle": (Q.gt(x, 0), Q.gt(x, y) & Q.gt(y, z) & Q.gt(z, x)),
 "E disjunctive lra unsat": (Q.gt(x, 0), (Q.gt(x, 2) | Q.gt(y, 2)) & Q.lt(x, 1) & Q.lt(y, 1)),
 "F disjunctive, two-sided unsat": (Q.gt(x, 0), (Q.gt(x, 2) | Q.lt(x, -2)) & (Q.gt(y, 2) | Q.lt(y, -2)) & Q.eq(x + y, 1) & Q.lt(x - y, 1) & Q.gt(x - y, -1)),
 "G consistent, split needed": (Q.gt(x, 0), (Q.gt(x, 2) | Q.lt(x, -2)) & (Q.gt(y, 2) | Q.lt(y, -2)) & Q.gt(x + y, 3)),
}
for name, (q, a) in cases.items():
    before = set(last())
    try: ans = sympy_api.ask(q, a)
    except ValueError as e: ans = "ValueError: " + str(e)[:24]
    gc.collect()
    rows = last(); new = [rows[k] for k in rows if k not in before]
    tot = lambda key, i, j=None: sum((n[key][i] if j is None else n[key][i][j]) for n in new)
    print(name, "->", ans, "| solvers", len(new), "born", [n["born"] for n in new])
    print("   ec", [tot("ec", i) for i in range(8)], "nb", [tot("nb", i) for i in range(5)])
    print("   cm[1] vis p0,1,2 / reason / proof:", [tot("cm", 1, j) for j in range(9)])
    print("   cm[2] (check-made clauses):", [tot("cm", 2, j) for j in range(9)], "cm[3] learnt:", [tot("cm", 3, j) for j in range(9)])
