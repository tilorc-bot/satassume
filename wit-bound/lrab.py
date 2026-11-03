import pickle, sys, time, gc, collections
from satassume.theories.lra import lra as L
from satassume.sympy_api import ask
clock = time.perf_counter
C = collections.Counter(); T = collections.Counter()
f = L.LRATheory._check
def g(self):
    b0 = self.stats["branches"]; e0 = self.stats["exhausted"]
    neg = sum(1 for v, m, k, lit in self._int_lits if lit < 0); pos = len(self._int_lits) - neg
    t = clock(); r = f(self); dt = clock() - t
    k = ("branched" if self.stats["branches"] > b0 else "nobranch", "pos" if pos else "neg-only" if neg else "noint",
         "conflict" if r[0] is False else "sat")
    C[k] += 1; T[k] += dt; C[k + ("br",)] += self.stats["branches"] - b0
    return r
L.LRATheory._check = g
st = pickle.load(open(sys.argv[1], "rb"))
gc.collect(); gc.freeze()
t = clock()
for p, a, r in st:
    try: ask(p, a)
    except ValueError: pass
tot = clock() - t
print("pass", round(tot, 3))
for k in sorted(T): print(k, C[k], f"{T[k]:.3f}s ({100*T[k]/tot:.1f}%)", "branches", C[k + ("br",)])
