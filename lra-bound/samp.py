"""Sampling profile of the stream pass: where LRA-session solves spend time.
A thread samples the main thread's stack every ~0.5 ms; one light wrapper on
Solver._solve tags samples with the solve's class (plain / lra idle / active)."""
import pickle, sys, time, gc, collections, threading
from satassume.sat import solver as SV
from satassume.theories.lra import lra as L
from satassume.sympy_api import ask
clock = time.perf_counter
tag = [None]          # current solve class, or None
buf = []              # samples of the current solve
S = collections.Counter(); NS = collections.Counter()   # samples by (class, leaf)
SOLVES = collections.Counter()
f_solve = SV.Solver._solve
def solve(self, lits, keep):
    lra = next((t for t in self._theories if isinstance(t, L.LRATheory)), None)
    if lra is None:
        cls = "plain" if not self._theories else "other"
        tag[0] = cls
        try: return f_solve(self, lits, keep)
        finally:
            tag[0] = None; SOLVES[cls] += 1
            for k in buf: S[(cls, k)] += 1
            buf.clear()
    st0 = (lra.stats["conflicts"], lra.stats["propagations"], lra.stats["branches"])
    tag[0] = "lra"
    try: return f_solve(self, lits, keep)
    finally:
        tag[0] = None
        st1 = (lra.stats["conflicts"], lra.stats["propagations"], lra.stats["branches"])
        cls = "lra-idle" if st0 == st1 else "lra-active"
        if lra.gave_up: cls = "lra-gaveup"
        SOLVES[cls] += 1
        for k in buf: S[(cls, k)] += 1
        buf.clear()
SV.Solver._solve = solve

LEAF = {("LRATheory", n) for n in ("assert_lit", "_simplex", "propagate", "check", "_branch",
        "_concrete", "_model", "push_level", "pop_level", "_int_bounds", "_assert_kind", "_implied")}
SOLV = {"_propagate", "_theory_sync", "_theory_check", "_theory_imply", "_theory_conflict",
        "_backtrack", "_pick_branch", "_learn", "_analyze", "_search", "_solve", "_reduce_db",
        "_ring_hit", "_theory_decide", "_analyze_final"}
def classify(fr):
    # innermost frame that is a known solver/theory function; returns a key path
    keys = []
    while fr is not None:
        co = fr.f_code
        fn = co.co_filename
        if fn.endswith("lra/lra.py"):
            keys.append("lra." + co.co_name)
        elif fn.endswith("sat/solver.py") and co.co_name in SOLV:
            keys.append("s." + co.co_name)
        elif fn.endswith("theories/transfer.py"):
            keys.append("tr." + co.co_name)
        fr = fr.f_back
    if not keys:
        return "?"
    # top two meaningful: outermost-under-search attribution
    # leaf = innermost key; also record the theory-interface frame chain
    return " < ".join(keys[:3])
main = threading.main_thread().ident
stop = [False]
TOT = collections.Counter()
def sampler():
    while not stop[0]:
        time.sleep(0.0005)
        fr = sys._current_frames().get(main)
        if fr is None: continue
        t = tag[0]
        if t is None:
            k = classify(fr)
            TOT["outside-solve"] += 1
            if k != "?": S[("outside", k)] += 1
        else:
            TOT["in-solve"] += 1
            buf.append(classify(fr))
sys.setswitchinterval(0.0002)
st = pickle.load(open(sys.argv[1], "rb"))
gc.collect(); gc.freeze()
th = threading.Thread(target=sampler, daemon=True); th.start()
t = clock()
for p, a, r in st:
    try: ask(p, a)
    except ValueError: pass
tot = clock() - t
stop[0] = True; th.join()
n = TOT["outside-solve"] + TOT["in-solve"]
print("pass", round(tot, 3), "samples", n, dict(TOT), dict(SOLVES))
pickle.dump((dict(S), dict(TOT), dict(SOLVES), tot), open(sys.argv[2], "wb"))
