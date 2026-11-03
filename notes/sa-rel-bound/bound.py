import pickle, sys, gc, time, collections
from satassume import engine as E, relations as R
from satassume.sympy_api import ask
clock = time.perf_counter
acc = collections.Counter(); depth = collections.Counter()
def wrap(cls, name, key):
    f = getattr(cls, name)
    def g(*a, **k):
        depth[key] += 1
        t = clock()
        try: return f(*a, **k)
        finally:
            depth[key] -= 1
            if depth[key] == 0: acc[key] += clock() - t
    setattr(cls, name, g)
# process split by caller phase
inbuild = [0]
fb = E.Engine._build_context
keys = collections.Counter(); first_t = [0.0]; rep_t = [0.0]
sizes = []
def build(self, assumptions, proposition=None):
    scope = E.theory_scope(assumptions, proposition, self._extensions) if hasattr(E, "theory_scope") else None
    key = (assumptions, scope)
    inbuild[0] += 1
    t = clock()
    try:
        r = fb(self, assumptions, proposition)
    finally:
        inbuild[0] -= 1
        dt = clock() - t
        acc["build"] += dt
        if keys[key]: rep_t[0] += dt
        else: first_t[0] += dt
        keys[key] += 1
    s = r[0]
    sol = s.solver
    sizes.append((sol.nvars(), len(getattr(sol, "_clauses", []) or []), len(getattr(sol, "_learnts", []) or [])))
    return r
E.Engine._build_context = build
fp = R.Relations.process
def process(self, *a, **k):
    t = clock()
    try: return fp(self, *a, **k)
    finally: acc["process_build" if inbuild[0] else "process_query"] += clock() - t
R.Relations.process = process
fc = E.Engine._complete_check
def cc(s, lits):
    t = clock()
    try: return fc(s, lits)
    finally: acc["complete_check"] += clock() - t
E.Engine._complete_check = staticmethod(cc)
wrap(E.Engine, "_fresh_session", "fresh_session")
wrap(E.Session, "assume_formula", "assume_formula")
wrap(E.Session, "link_set", "link_set")
stream = pickle.load(open("/home/tilo/provable/data/stream.pkl", "rb"))
seen, uniq = set(), []
for p, a, r in stream:
    if (p, a) not in seen: seen.add((p, a)); uniq.append((p, a))
t0 = clock()
for p, a in uniq:
    try: ask(p, a)
    except ValueError: pass
T = clock() - t0
print(f"total {T:.3f}s")
for k, v in sorted(acc.items(), key=lambda kv: -kv[1]): print(f"  {k:16s} {v:7.3f}s {v/T:6.1%}")
n = sum(keys.values())
print(f"builds {n}, distinct (set,scope) {len(keys)}; first-build time {first_t[0]:.3f}s repeat-build time {rep_t[0]:.3f}s ({rep_t[0]/T:.1%} of total)")
import statistics
if sizes and sizes[0][0]:
    print("median vars/clauses/learnts", [statistics.median(x[i] for x in sizes) for i in range(3)])
