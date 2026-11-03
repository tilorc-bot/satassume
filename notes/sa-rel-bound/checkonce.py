"""Bound for 'check once per set': a query's context session is the set
assumed (no complete check); the set's verdict comes from the verdict memo,
computed on a miss by the unchanged build (proposition None).  Mode
base|once.  Prints time, engine stats, writes answers."""
import sys, collections, pickle, time, json
from satassume import engine as E
from satassume.sympy_api import ask
clock = time.perf_counter
MODE = sys.argv[1]
fb = E.Engine._build_context
acc = collections.Counter()
def build(self, assumptions, proposition=None):
    if proposition is None:
        t = clock()
        try: return fb(self, assumptions, None)
        finally: acc["verdict_builds"] += 1; acc["verdict_time"] += clock() - t
    t0 = clock()
    v = self._verdict.get(assumptions)
    if v is None:
        acc["verdict_miss"] += 1
        v = self.verdict(assumptions)
    t = clock()
    self.stats["set_checks"] += 1
    s = self._fresh_session(E.theory_scope(assumptions, proposition, self._extensions))
    lits = s.assume_formula(assumptions)
    s.verdict = v
    if v is not E.INCONSISTENT:
        s.link_set()
    acc["query_builds"] += 1; acc["query_build_time"] += clock() - t
    return s, lits
def build_timed(self, assumptions, proposition=None):
    t = clock()
    try: return fb(self, assumptions, proposition)
    finally: acc["builds"] += 1; acc["build_time"] += clock() - t
E.Engine._build_context = build if MODE == "once" else build_timed
fa = E.Engine._ask
def _ask(self, *a):
    t = clock()
    try: return fa(self, *a)
    finally: acc["_ask_time"] += clock() - t
E.Engine._ask = _ask
stream = pickle.load(open("/home/tilo/provable/data/stream.pkl", "rb"))
seen, uniq = set(), []
for p, a, r in stream:
    if (p, a) not in seen: seen.add((p, a)); uniq.append((p, a))
from satassume import sympy_api
out = []
t0 = clock()
for p, a in uniq:
    try: out.append(repr(ask(p, a)))
    except ValueError: out.append("error")
T = clock() - t0
eng = sympy_api.default_engine()
print(MODE, f"total {T:.3f}s", {k: round(v, 3) for k, v in acc.items()})
if eng is not None: print("  stats", {k: v for k, v in eng.stats.items() if k in ("searches", "escalations", "theory_gave_up", "set_checks", "queries")})
json.dump(out, open(__file__.rsplit("/", 1)[0] + f"/ans-c{MODE}.json", "w"))
