"""Bound for item 1.1 (witness reuse): simulate a ring of earlier models on
the refine-stream replay and count the solves a stored model would have
answered.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/2026-09-perf-rounds/scripts/witness_bound.py \
        ~/.cache/satassume/stream.pkl [--ring 1,2,4,8,16] [--no-theory-gate]

The per-query log (0.3) holds the models but not the assumption and target
literals of the entails solves, so the check "would an earlier model have
satisfied A and not-P" is made here, online: ``Solver._solve`` is wrapped;
before each real solve every stored model of that solver (most recent
first) is tested against the literals of the call, the problem clauses
added since the model was found (an index slice of ``_clauses``), the root
literals fixed since (a slice of the trail) and, with theories attached,
dropped if an atom was registered since (the conservative gate of the
plan).  A model that passes would have made the solve unnecessary; the
real solve still runs (answers stay identical) and its wall time is what
the hit saves.  A hit does not add the real solve's model to the ring, so
the ring evolves as it would in the implementation (second-order effects
of skipped solves on learnt clauses and phases are ignored).

Models from other sessions are never comparable (each session has its own
variable table), so "under the same assumption set" across sessions is
not a source of witnesses.

Prints, per ring size: hits by target and by query outcome, the solve
time saved, the check time spent, and the bound as a share of the replay.
"""
import pickle, sys, time
from collections import Counter, defaultdict

argv = sys.argv[1:]
ring_sizes = [1, 2, 4, 8, 16]
if "--ring" in argv:
    k = argv.index("--ring"); ring_sizes = [int(x) for x in argv[k + 1].split(",")]; del argv[k:k + 2]
theory_gate = "--no-theory-gate" not in argv
if not theory_gate: argv.remove("--no-theory-gate")
stream = pickle.load(open(argv[0], "rb"))

from satassume.sympy_api import ask
from satassume.solver import Solver

RING = max(ring_sizes)


class Rec:
    """One stored model: the assignment and the clause-db position it was
    validated against."""
    __slots__ = ("model", "nclauses", "root_len", "natoms")

    def __init__(self, model, nclauses, root_len, natoms):
        self.model = model; self.nclauses = nclauses; self.root_len = root_len; self.natoms = natoms


def root_len(s):
    return s._trail_lim[0] if s._trail_lim else len(s._trail)


def satisfies(rec, s, lits):
    """Would ``rec.model`` still be a model of ``s``'s clauses and of ``lits``?"""
    m = rec.model
    for l in lits:
        b = m.get(l >> 1)
        if b is None or b != (l & 1 == 0):
            return False
    trail = s._trail
    for i in range(rec.root_len, root_len(s)):
        l = trail[i]
        b = m.get(l >> 1)
        if b is None or b != (l & 1 == 0):
            return False
    cls = s._clauses
    for i in range(rec.nclauses, len(cls)):
        for l in cls[i]:
            b = m.get(l >> 1)
            if b is not None and b == (l & 1 == 0):
                break
        else:
            return False
    return True


stats = {k: Counter() for k in ring_sizes}     # per ring size
saved = {k: 0.0 for k in ring_sizes}           # solve seconds a hit would save
check_time = {k: 0.0 for k in ring_sizes}
solve_time = 0.0
n_solves = Counter()
ctx = {"entails": None, "outcome": None}
orig_entails = Solver.entails
orig_solve = Solver._solve
per_session_hits = defaultdict(Counter)        # id(solver) -> Counter for the largest ring


def entails(self, lit, assumptions=()):
    assumptions = list(assumptions)
    v = -lit if lit < 0 else lit
    prev = ctx["entails"]
    ctx["entails"] = (self, 2 * v + 1 if lit < 0 else 2 * v, len(assumptions))
    try:
        return orig_entails(self, lit, assumptions)
    finally:
        ctx["entails"] = prev


def target_of(self, lits):
    e = ctx["entails"]
    if e is not None and e[0] is self:
        _, l, k = e
        if len(lits) == k + 1 and lits[-1] == l ^ 1:
            return "not_p"
        if len(lits) == k + 1 and lits[-1] == l:
            return "p"
        if len(lits) == k:
            return "consistency"
    return "solve"


def _solve(self, lits, keep):
    global solve_time
    rings = self.__dict__.get("_wr")
    if rings is None:
        rings = self._wr = {k: [] for k in ring_sizes}
    tgt = target_of(self, lits)
    n_solves[tgt] += 1
    natoms = len(self._tmap)
    hit = {}
    for k in ring_sizes:
        t0 = time.perf_counter()
        ring = rings[k]
        found = None
        for j in range(len(ring) - 1, -1, -1):
            rec = ring[j]
            if theory_gate and self._theories and rec.natoms != natoms:
                continue
            if satisfies(rec, self, lits):
                found = j
                break
        check_time[k] += time.perf_counter() - t0
        hit[k] = found
    t0 = time.perf_counter()
    res = orig_solve(self, lits, keep)
    dt = time.perf_counter() - t0
    solve_time += dt
    for k in ring_sizes:
        ring = rings[k]
        if hit[k] is not None:
            stats[k]["hit"] += 1
            stats[k]["hit_" + tgt] += 1
            stats[k]["hit_age_%d" % (len(ring) - 1 - hit[k])] += 1
            saved[k] += dt
            if k == RING:
                per_session_hits[id(self)]["hit"] += 1
            if not res:
                stats[k]["HIT_ON_UNSAT"] += 1     # would be a wrong answer: must be 0
            continue
        if res:
            ring.append(Rec(self._model, len(self._clauses), root_len(self), natoms))
            if len(ring) > k:
                del ring[0]
                stats[k]["evicted"] += 1
    if RING in hit and hit[RING] is None:
        per_session_hits[id(self)]["miss"] += 1
    ctx.setdefault("solves_this_query", []).append((tgt, res, {k: hit[k] is not None for k in ring_sizes}))
    return res


Solver.entails = entails
Solver._solve = _solve

outcome_hits = {k: Counter() for k in ring_sizes}
t_all = time.perf_counter()
bad = 0
for i, (p, a, r) in enumerate(stream):
    ctx["solves_this_query"] = []
    try:
        got = ask(p, a)
    except ValueError:
        got = "error"
    if got is not r:
        bad += 1
    sv = ctx["solves_this_query"]
    if sv:
        key = {True: "True", False: "False", None: "None"}.get(got, "error")
        for k in ring_sizes:
            hits = sum(1 for _, _, h in sv if h[k])
            outcome_hits[k][key + "_solves"] += len(sv)
            outcome_hits[k][key + "_hits"] += hits
            if hits == len(sv):
                outcome_hits[k][key + "_queries_all_hit"] += 1
            outcome_hits[k][key + "_queries"] += 1
total = time.perf_counter() - t_all

print(f"replay (instrumented) {total:.2f} s, answers differ: {bad}; solve time {solve_time:.2f} s "
      f"({100 * solve_time / total:.1f}% of the instrumented pass); solves {dict(n_solves)}")
print(f"theory gate {'on' if theory_gate else 'off'}")
for k in ring_sizes:
    st = stats[k]
    n = sum(n_solves.values())
    print(f"\nring {k}: hits {st['hit']} of {n} solves ({100 * st['hit'] / n:.1f}%): "
          + ", ".join(f"{t} {st['hit_' + t]}" for t in ("not_p", "p", "consistency", "solve") if st['hit_' + t]))
    print(f"  hits on an unsat solve (must be 0): {st['HIT_ON_UNSAT']}; evictions {st['evicted']}")
    ages = sorted((int(a.split('_')[-1]), c) for a, c in st.items() if a.startswith("hit_age_"))
    print(f"  hit by age (0 = most recent model): {ages}")
    oh = outcome_hits[k]
    for key in ("None", "False", "True"):
        if oh[key + "_queries"]:
            print(f"  {key}: {oh[key + '_queries']} searching queries, {oh[key + '_solves']} solves, "
                  f"{oh[key + '_hits']} hits, {oh[key + '_queries_all_hit']} queries fully answered by stored models")
    print(f"  solve time saved {saved[k]:.3f} s, check time {check_time[k]:.3f} s; "
          f"net {saved[k] - check_time[k]:.3f} s = {100 * (saved[k] - check_time[k]) / total:.1f}% of the instrumented pass "
          f"(the check time here is Python-level and per ring size; only one ring would run)")
# Do the Nones of a session share one model?  Per solver (session), hits vs
# misses with the largest ring.
hs = [(c["hit"], c["miss"]) for c in per_session_hits.values() if c["hit"] + c["miss"] >= 4]
if hs:
    shares = sorted(h / (h + m) for h, m in hs)
    print(f"\nsessions with 4+ solves: {len(hs)}; hit share per session with ring {RING}: "
          f"median {shares[len(shares) // 2]:.2f}, p25 {shares[len(shares) // 4]:.2f}, "
          f"p75 {shares[3 * len(shares) // 4]:.2f}")
