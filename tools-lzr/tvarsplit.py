import sys, collections, json
from sympy import S as SS
from satassume import relations as R, sympy_api
from evalbench.common import workload, ask_all
C = collections.Counter()
def why(self, e, M, atoms):
    src = []
    for spec in self.specs:
        ad = self.adapters.get(spec.name)
        if ad is None: return "noadapter"
        if spec.guarded:
            src += [(u, R._IL) for a in atoms for u in (ad.terms(R.sympy_atom(a)) or ())]
        elif hasattr(ad, "node_term"):
            src += [(u, R._IE) for u in ad.interned(atoms[2].expr)] + [(e, R._SD), (SS.Zero, R._SD)]
    kinds = set()
    for u, k in src:
        t = self._tv.get(u)
        if t is None or not t[k]: kinds.add("unalloc " + "SD EN MC IE IL".split()[k])
        elif not M.get(t[k]): kinds.add("false " + "SD EN MC IE IL".split()[k])
    return " ".join(sorted(kinds)) or "share"
f0 = R.Relations._tvar_disagree
def w(self, e, M, atoms):
    r = f0(self, e, M, atoms)
    if r:
        C[why(self, e, M, atoms)] += 1
        C["nadapters=%d" % len(self.adapters)] += 1
    return r
R.Relations._tvar_disagree = w
if sys.argv[1] == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(int(sys.argv[2]))
else:
    pairs = workload(sys.argv[1])
ask_all(sympy_api.ask, pairs)
for k, v in C.most_common(): print(v, k)
