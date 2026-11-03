"""Shared-session hits on the switch-ON tree, with and without a static guard.

    python guard_child.py SPEC GUARD OUT     GUARD: none | noint
noint: a theory session is shared only if every LRA theory in it has no
integrality atom registered and (no constants or certified)."""
import json, sys
sys.setrecursionlimit(10000)
spec, guard, out = sys.argv[1:4]
from evalbench.common import workload, ask_all
if spec.startswith("fuzz:"):
    from evalbench.fuzz import queries
    pairs = queries(int(spec.split(":")[1]))
else:
    pairs = workload(spec)
import satassume.engine as E
from satassume import sympy_api
from satassume.theories.lra.lra import LRATheory
E.SHARE_THEORY = True
C = {"hits_free": 0, "hits_theory": 0, "unshared": 0, "blocked_int": 0, "blocked_const": 0}
o_shareable = E._shareable

def static_ok(s):
    for t in s.solver.theories():
        if isinstance(t, LRATheory):
            if t._ints:
                C["blocked_int"] += 1; return False
            if t._fields and not t.certified:
                C["blocked_const"] += 1; return False
    return True

if guard == "noint":
    E._shareable = lambda s: o_shareable(s) and (E._theory_free(s) or static_ok(s))
orig = E.Engine._ask_shared
def ask_shared(self, s, p):
    r = orig(self, s, p)
    if r is E._UNSHARED: C["unshared"] += 1
    elif E._theory_free(s): C["hits_free"] += 1
    else: C["hits_theory"] += 1
    return r
E.Engine._ask_shared = ask_shared
ans = ask_all(sympy_api.ask, pairs)
with open(out + ".answers", "w") as f:
    for (p, a), r in zip(pairs, ans):
        f.write(json.dumps([str(p), str(a), r]) + "\n")
print(spec, guard, json.dumps(C))
