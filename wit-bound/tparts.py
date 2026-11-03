import pickle, sys, time, gc, collections
from satassume.sat import solver as SV
from satassume.theories.lra import lra as L
from satassume.theories import transfer as TR
from satassume import engine as E
from satassume.sympy_api import ask
clock = time.perf_counter
acc = collections.Counter(); depth = [0]
def wrap(cls, name, key):
    f = getattr(cls, name)
    def g(*a, **k):
        if depth[0]: return f(*a, **k)
        depth[0] += 1; t = clock()
        try: return f(*a, **k)
        finally: acc[key] += clock() - t; depth[0] -= 1
    setattr(cls, name, g)
wrap(SV.Solver, "_solve", "solve")
st = pickle.load(open(sys.argv[1], "rb"))
inner = collections.Counter()
def wrap2(cls, name, key):
    f = getattr(cls, name)
    def g(*a, **k):
        t = clock()
        try: return f(*a, **k)
        finally: inner[key] += clock() - t
    setattr(cls, name, g)
wrap2(L.LRATheory, "check", "lra.check"); wrap2(L.LRATheory, "_branch", "lra._branch"); wrap2(L.LRATheory, "_concrete", "lra._concrete")
wrap2(L.LRATheory, "assert_lit", "lra.assert"); wrap2(L.LRATheory, "propagate", "lra.propagate")
wrap2(TR.TransferTheory, "propagate", "tr.propagate")
wrap2(SV.Solver, "_tpropagate", "tpropagate")
gc.collect(); gc.freeze()
t = clock()
for p, a, r in st:
    try: ask(p, a)
    except ValueError: pass
tot = clock() - t
print("pass", round(tot, 3), {k: f"{v:.3f} ({100*v/tot:.1f}%)" for k, v in acc.items()})
print({k: f"{v:.3f} ({100*v/tot:.1f}%)" for k, v in inner.items()})
