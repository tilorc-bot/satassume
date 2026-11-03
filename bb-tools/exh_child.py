"""Record every B&B exhaustion of one workload pass (cold process).

    python exh_child.py SPEC OUT_JSONL
On each LRATheory.check that exhausts: dump the asserted problem, probe LP
boundedness of every integrality variable, and re-run B&B on a deep copy
with a large budget (nodes to decide, outcome).
"""
import copy
import json
import sys
import time
from fractions import Fraction

sys.setrecursionlimit(100000)
spec, out = sys.argv[1:3]
from evalbench.common import workload, ask_all  # noqa: E402

if spec.startswith("fuzz:"):
    from evalbench.fuzz import queries
    pairs = queries(int(spec.split(":")[1]))
else:
    pairs = workload(spec)

from satassume import sympy_api  # noqa: E402
from satassume.theories.lra import lra  # noqa: E402

BIG = Fraction(10) ** 40
RERUN = [200, 2000, 20000]
recs = []
cur = {"i": -1}


def s(x):
    return str(x)


def dump(t):
    form_of = {v: f for f, v in t._slack_of.items()}
    bounds = []
    for v in range(len(t._lo)):
        lo, up = t._lo[v], t._up[v]
        if lo is None and up is None:
            continue
        f = form_of.get(v)
        bounds.append({"v": v, "key": None if t._key[v] is None else s(t._key[v]),
                       "form": None if f is None else [[a, s(c)] for a, c in f],
                       "lo": None if lo is None else [s(lo[0]), s(lo[1])],
                       "up": None if up is None else [s(up[0]), s(up[1])]})
    ints = [[v, s(m), s(k), lit, None if form_of.get(v) is None else
             [[a, s(c)] for a, c in form_of[v]]] for v, m, k, lit in t._int_lits]
    dis = [[v, s(c), None if form_of.get(v) is None else
            [[a, s(c2)] for a, c2 in form_of[v]]] for v, c, lit in t._diseqs]
    return bounds, ints, dis


def probe(t, v, kind, c):
    t.push_level()
    try:
        r = t._assert_kind(v, kind, c, 0)
        if r is None:
            r = t._simplex()
        return r is None                   # feasible at |v| >= 1e40: unbounded
    except Exception as e:                 # constants: say so
        return "err:" + type(e).__name__
    finally:
        t.pop_level()


def analyse(t):
    rec = {"q": cur["i"], "fields": t._fields, "nvars": len(t._lo),
           "nrows": len(t._rows)}
    rec["bounds"], rec["ints"], rec["dis"] = dump(t)
    rec["nbounded_vars"] = len(rec["bounds"])
    rec["terms"] = sorted({a for b in rec["bounds"] if b["form"] for a, _ in b["form"]}
                          | {b["v"] for b in rec["bounds"] if b["form"] is None}
                          | {a for i in rec["ints"] if i[4] for a, _ in i[4]}
                          | {i[0] for i in rec["ints"] if i[4] is None})
    try:
        c = copy.deepcopy(t)
    except Exception as e:
        rec["copy_err"] = repr(e)
        return rec
    ub = {}
    for v, m, k, lit in c._int_lits:
        if v not in ub:
            ub[v] = [probe(c, v, ">=", BIG), probe(c, v, "<=", -BIG)]
    rec["unbounded"] = {str(v): x for v, x in ub.items()}
    for n in RERUN:
        c2 = copy.deepcopy(t)
        c2.exhausted = False
        b0 = c2.stats["branches"]
        t0 = time.perf_counter()
        try:
            r = c2._simplex()
            if r is None:
                r = c2._branch([n])
            res = "conflict" if r is not None else ("exhausted" if c2.exhausted else "intpoint")
        except Exception as e:
            res = "err:" + type(e).__name__
        rec[f"rerun{n}"] = [res, c2.stats["branches"] - b0, round(time.perf_counter() - t0, 3)]
        if not res.startswith("exhausted"):
            break
    return rec


ocheck = lra.LRATheory._check


def check(self):
    e0 = self.stats["exhausted"]
    b0 = self.stats["branches"]
    r = ocheck(self)
    if self.stats["exhausted"] != e0:
        rec = analyse(self)
        rec["branches_in_check"] = self.stats["branches"] - b0
        rec["check_result"] = bool(r[0])
        recs.append(rec)
    return r


lra.LRATheory._check = check
ans = []
for i, pa in enumerate(pairs):
    cur["i"] = i
    ans.extend(ask_all(sympy_api.ask, [pa]))
with open(out, "w") as f:
    for r in recs:
        f.write(json.dumps(r) + "\n")
with open(out + ".answers", "w") as f:
    for (p, a), r in zip(pairs, ans):
        f.write(json.dumps([str(p), str(a), r]) + "\n")
print(spec, "queries", len(pairs), "exhaustions", len(recs))
