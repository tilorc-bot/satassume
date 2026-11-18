"""plant320.py OUT (sa-port-320): planted cases for the count build's counters (FALSE ZEROS rule).
Each counter the report gives must be shown nonzero here, on a case where the expected value is known or must be > 0.
Needs SLICE_DIR (with the count build's sa_solver.so) and SA320_COUNT=OUT in the environment. Prints PASS/FAIL rows."""
import os, sys
out = sys.argv[1]
assert os.environ.get("SA320_COUNT") == out, "SA320_COUNT must name OUT"
S = os.environ["SLICE_DIR"]
sys.path.insert(0, S)
import p_install
p_install.install()
from satassume import sympy_api
import sa_solver
import backend
backend.install_euf()
import term_live
term_live.from_env()
import lra_live
lra_live.from_env()
import session_live
session_live.from_env()
import knowledge_live
knowledge_live.from_env()
backend.install()

KIND = ["vis", "reason", "proof"]


def parse(line):
    d = {}
    for kv in line.split()[1:]:
        k, v = kv.split("=", 1)
        if ";" in v:
            d[k] = [[int(x) for x in r.split(",")] for r in v.split(";")]
        elif "," in v:
            d[k] = [int(x) for x in v.split(",")]
        else:
            d[k] = int(v) if v.lstrip("-").isdigit() else v
    return d


def last():
    rows = {}
    if os.path.exists(out):
        for line in open(out):
            if line.startswith("S "):
                d = parse(line)
                rows[d["ser"]] = d
    return rows


fails = 0


def check(name, ok, got):
    global fails
    fails += not ok
    print(("PASS " if ok else "FAIL ") + name + ": " + str(got))


# 1. A solver driven directly, outside build_context (phase 0).
before = set(last())
s = sa_solver.Solver()
for _ in range(7):
    s.new_var()
s.add_clause([-6, -1, 2])    # false at the root in its first literal once the unit is in: the proof rests on the unit
s.add_clause([-1, -2])
s.add_clause([3, 4, 5])        # never touched: nothing assigns 3, 4 or 5 before the conflict
s.add_clause([6])              # a unit
r = s.solve([1])
st = s.stats()
del s
rows = last()
new = [k for k in rows if k not in before]
d = rows[max(new)]
print("direct line:", {k: d[k] for k in ("born", "tag", "nvars", "ncl", "nb", "vb", "ub", "ec")}, "stats", {k: st[k] for k in list(st)[:11]})
check("solve([1]) is unsat", r is False, r)
check("clauses built in phase 0 == 3 (stats clauses %s)" % st.get("clauses"), d["nb"][0] == 3 and d["ncl"] == 3, d["nb"])
check("vars built in phase 0 == 7", d["vb"][0] == 7 and d["nvars"] == 7, d["vb"])
check("units built in phase 0 == 1", d["ub"][0] == 1, d["ub"])
check("clauses visited by propagation, phase 0 == 2 of 3 (the untouched one stays unread)", d["cm"][0][0] == 2, d["cm"][0])
check("clauses used as reason or conflict, phase 0 >= 1", d["cm"][0][3] >= 1, d["cm"][0])
check("clauses in the proof, phase 0 >= 1", d["cm"][0][6] >= 1, d["cm"][0])
check("any-phase columns equal phase 0 here", d["cm"][0][9:12] == [d["cm"][0][0], d["cm"][0][3], d["cm"][0][6]], d["cm"][0])
check("vars visited >= 2, implied >= 1, in proof >= 1", d["vm"][0][0] >= 2 and d["vm"][0][3] >= 1 and d["vm"][0][6] >= 1, d["vm"][0])
check("unit's var visited == 1", d["um"][0][0] == 1, d["um"][0])
check("unit in the proof == 1 (root cone)", d["um"][0][6] == 1, d["um"][0])
check("entry counter: solve_int >= 1", d["ec"][0] >= 1, d["ec"])
check("a Drop line was written", d["tag"] == "D", d["tag"])

# 1b. An entailment read off the trail: no conflict analysis, the cone walk must mark the proof.
before = set(last())
s = sa_solver.Solver()
for _ in range(6):
    s.new_var()
s.add_clause([-1, 2])
s.add_clause([-2, 3])
s.add_clause([4, 5, 6])
e = s.entails(3, [1])
del s
rows = last()
d = rows[max(k for k in rows if k not in before)]
check("entails(3, [1]) is True", e is True, e)
check("entails by a live trail counted", d["ec"][3] >= 1, d["ec"])
check("cone: 2 clauses in the proof, 1 not", d["cm"][0][6] == 2 and d["nb"][0] == 3, d["cm"][0])
check("cone: 3 vars in the proof", d["vm"][0][6] == 3, d["vm"][0])

# 1c. A conflict at the root: no analysis runs; the conflict clause and the cones of its literals are the proof.
before = set(last())
s = sa_solver.Solver()
for _ in range(6):
    s.new_var()
s.add_clause([-1, 2])
s.add_clause([-1, -2])
s.add_clause([4, 5, 6])
ok = s.add_clause([1])
r = s.solve([])
del s
rows = last()
d = rows[max(k for k in rows if k not in before)]
check("root conflict: unsat", (ok, r) == (False, False), (ok, r))
check("root conflict counted", d["ec"][5] >= 1, d["ec"])
check("root conflict: 2 clauses and the unit in the proof, 1 clause not", d["cm"][0][6] == 2 and d["um"][0][6] == 1, (d["cm"][0], d["um"][0]))

# 2. The engine: phases 1 and 2 (build_context and its complete check) and relation rows.
from sympy import Q, symbols
x, y, z = symbols("x y z", real=True)
before = set(last())
answers = [sympy_api.ask(Q.gt(x, 0), Q.gt(x, y) & Q.gt(y, 1)),
           sympy_api.ask(Q.positive(x), Q.eq(x, y) & Q.positive(y)),
           sympy_api.ask(Q.gt(x + z, 2), Q.gt(x, 1) & Q.gt(z, 1) & Q.eq(y, x + z))]
try:        # inconsistent assumptions: the complete check must refute them, so its proof marks fire
    answers.append(sympy_api.ask(Q.gt(x, 5), Q.gt(x, 1) & Q.lt(x, 0) & Q.gt(y, x)))
except ValueError as e:
    answers.append("ValueError: " + str(e)[:24])
import gc
gc.collect()
rows = last()
new = [rows[k] for k in rows if k not in before]
print("engine answers:", answers, "solvers:", len(new), "born:", sorted(set(n["born"] for n in new)))
tot = lambda key, i, j=None: sum((n[key][i] if j is None else n[key][i][j]) for n in new)
check("solvers born inside build_context", any(n["born"] == 1 for n in new), [n["born"] for n in new])
check("clauses built in phase 1 > 0", tot("nb", 1) > 0, [tot("nb", i) for i in range(5)])
check("vars built in phase 1 > 0", tot("vb", 1) > 0, [tot("vb", i) for i in range(3)])
for k in range(3):
    if k < 2:
        check("phase-1 clauses %s in the complete check (phase 2) > 0" % KIND[k], tot("cm", 1, k * 3 + 2) > 0, tot("cm", 1, k * 3 + 2))
    check("phase-1 clauses %s by the query (phase 0) > 0" % KIND[k], tot("cm", 1, k * 3) > 0, tot("cm", 1, k * 3))
# sa-port-321: the fourth ask is refuted inside implied() (assume, at an assumption level): no analysis runs there and
# the patch walks no cone, so the check's proof column stays 0 on it. That 0 is an unmarked site, not "nothing read".
check("check refuted in assume (no solve_int in that solver, no root conflict): proof column 0 there is UNMARKED",
      any(n["ec"][0] == 0 and n["ec"][1] >= 1 and n["ec"][5] == 0 and n["cm"][1][5] > 0 and n["cm"][1][8] == 0 for n in new),
      [(n["ec"][:6], n["cm"][1][5], n["cm"][1][8]) for n in new if n["ec"][0] == 0])
rk = max(new, key=lambda n: sum(n["rk"]))["rk"]
check("relation rows made, by kind (user eq, queued atom, top entry, pending link)", sum(rk) > 0, rk)
check("relation rows that emitted a clause, variable or unit", sum(tot("re", i) for i in range(4)) > 0, [tot("re", i) for i in range(4)])
check("relation rows read (any kind, any phase)", sum(tot("rm", i, 9) for i in range(4)) > 0, [[tot("rm", i, j) for j in (9, 10, 11)] for i in range(4)])
check("rule blocks built", sum(tot("bb", i) for i in range(3)) > 0, [tot("bb", i) for i in range(3)])
check("rule blocks visited, reason (any phase)", tot("bm", 9) > 0 and tot("bm", 10) > 0, [tot("bm", j) for j in (9, 10, 11)])
check("units of phase 1 visited (any phase)", tot("um", 1, 9) > 0, [tot("um", 1, j) for j in (9, 10, 11)])
print("blocks marks any-phase:", [tot("bm", j) for j in (9, 10, 11)], "units built:", [tot("ub", i) for i in range(3)],
      "units marks:", [[tot("um", i, j) for j in (9, 10, 11)] for i in range(3)])

# 3. (sa-port-321) The check's proof column: assumptions that unit propagation cannot refute, so the complete check
# reaches solve(), decides, and analyses a conflict. All four assumption clauses are in that refutation.
P = Q.positive
before = set(last())
try:
    a5 = sympy_api.ask(P(x), (P(x) | P(y)) & (P(x) | ~P(y)) & (~P(x) | P(y)) & (~P(x) | ~P(y)))
except ValueError as e:
    a5 = "ValueError: " + str(e)[:24]
gc.collect()
rows = last()
new = [rows[k] for k in rows if k not in before]
check("propositional refutation raises", str(a5).startswith("ValueError"), a5)
check("the check reached solve_int", tot("ec", 0) >= 1, [tot("ec", i) for i in range(6)])
check("phase-1 clauses proof in the complete check (phase 2) == 4 of 4", (tot("cm", 1, 8), tot("nb", 1)) == (4, 4), (tot("cm", 1, 8), tot("nb", 1)))
check("learnt clause proof in the complete check (phase 2) > 0", tot("cm", 3, 8) > 0, tot("cm", 3, 8))
print("FAILS", fails)
sys.exit(1 if fails else 0)
