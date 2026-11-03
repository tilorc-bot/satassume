"""Bound: where LRA-session searches spend time; idle-LRA solves."""
import pickle, sys, time, gc, collections
from satassume.sat import solver as SV
from satassume.theories.lra import lra as L
from satassume.theories import transfer as TR
from satassume.sympy_api import ask
clock = time.perf_counter
T = collections.Counter()      # time by (cls, key)
N = collections.Counter()
cur = [None]                    # current solve record
act = collections.Counter()     # per-solve activity of LRA

def timed(cls, name, key, after=None):
    f = getattr(cls, name)
    def g(*a, **k):
        t = clock()
        r = f(*a, **k)
        dt = clock() - t
        c = cur[0] or "outside"
        T[(c, key)] += dt; N[(c, key)] += 1
        if after is not None and cur[0] is not None:
            after(a[0], r)
        return r
    setattr(cls, name, g)

def a_assert(th, r):
    if r is not None and r[0] is False: act["c"] += 1
def a_prop(th, r):
    if r: act["p"] += len(r)
def a_check(th, r):
    if r is not None and r[0] is False: act["c"] += 1
br0 = {}
timed(L.LRATheory, "assert_lit", "lra.assert", a_assert)
timed(L.LRATheory, "_simplex", "lra._simplex")
timed(L.LRATheory, "propagate", "lra.propagate", a_prop)
timed(L.LRATheory, "check", "lra.check", a_check)
timed(L.LRATheory, "_branch", "lra._branch")
timed(L.LRATheory, "_concrete", "lra._concrete")
timed(L.LRATheory, "push_level", "lra.push")
timed(L.LRATheory, "pop_level", "lra.pop")
for nm in ("assert_lit", "propagate", "check", "push_level", "pop_level"):
    if hasattr(TR.TransferTheory, nm):
        timed(TR.TransferTheory, nm, "tr." + nm,
              a_prop if nm == "propagate" else None)
timed(SV.Solver, "_propagate", "s._propagate")
timed(SV.Solver, "_theory_sync", "s._theory_sync")
timed(SV.Solver, "_theory_check", "s._theory_check")
timed(SV.Solver, "_backtrack", "s._backtrack")

S = collections.Counter()   # per class: solves, time, decisions, conflicts
f_solve = SV.Solver._solve
def solve(self, lits, keep):
    ths = self._theories
    has_l = any(isinstance(t, L.LRATheory) for t in ths)
    has_t = any(isinstance(t, TR.TransferTheory) for t in ths)
    cls = "lra" if has_l else ("tr" if has_t else ("oth" if ths else "plain"))
    lra = next((t for t in ths if isinstance(t, L.LRATheory)), None)
    b0 = lra.stats["branches"] if lra else 0
    d0, c0 = self._n_decisions, self._n_conflicts
    act.clear()
    prev = cur[0]; cur[0] = cls
    t = clock()
    r = f_solve(self, lits, keep)
    dt = clock() - t
    cur[0] = prev
    br = (lra.stats["branches"] - b0) if lra else 0
    sub = cls
    if cls == "lra":
        sub = "lra-idle" if not act and not br else "lra-active"
        if lra.gave_up: sub = "lra-gaveup"
    for k in (cls, sub) if sub != cls else (cls,):
        S[(k, "n")] += 1; S[(k, "t")] += dt
        S[(k, "dec")] += self._n_decisions - d0; S[(k, "confl")] += self._n_conflicts - c0
        S[(k, "br")] += br; S[(k, "atoms")] += len(lra._atoms) if lra else 0
        S[(k, "rows")] += len(lra._rows) if lra else 0
        S[(k, "lits")] += len(lits)
    if cls == "lra":
        # idle-solve time inside the theory: cumulative counter
        pass
    return r
SV.Solver._solve = solve

st = pickle.load(open(sys.argv[1], "rb"))
gc.collect(); gc.freeze()
t = clock()
for p, a, r in st:
    try: ask(p, a)
    except ValueError: pass
tot = clock() - t
print("pass", round(tot, 3))
for k in ("plain", "oth", "tr", "lra", "lra-idle", "lra-active", "lra-gaveup"):
    n = S[(k, "n")]
    if not n: continue
    print(f"{k:11s} solves {n:6d} t {S[(k,'t')]:.3f}s ({100*S[(k,'t')]/tot:.1f}%) "
          f"ms/solve {1000*S[(k,'t')]/n:.3f} dec/solve {S[(k,'dec')]/n:.2f} "
          f"confl/solve {S[(k,'confl')]/n:.2f} br {S[(k,'br')]} atoms/s {S[(k,'atoms')]/n:.1f} "
          f"rows/s {S[(k,'rows')]/n:.1f} lits/s {S[(k,'lits')]/n:.1f}")
for c in ("plain", "tr", "lra", "outside"):
    for (cc, key), v in sorted(T.items(), key=lambda x: -x[1]):
        if cc == c:
            print(f"  {c:8s} {key:18s} {v:.3f}s ({100*v/tot:.1f}%) calls {N[(cc,key)]}")
pickle.dump((dict(S), dict(T), dict(N), tot), open(sys.argv[2], "wb"))
