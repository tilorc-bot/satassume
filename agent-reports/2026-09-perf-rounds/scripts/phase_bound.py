"""Bound for item 1.3 (phase heuristic): what a better phase choice could
remove from the entails searches of the refine-stream replay.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy:tools python agent-reports/2026-09-perf-rounds/scripts/phase_bound.py \
        ~/.cache/satassume/stream.pkl ~/.cache/satassume/log-d166940.jsonl

Offline, from the log: decisions and conflicts per solve and the time of
the queries whose solves see any conflict.  Online, one instrumented pass
(``tools/query_log.py``'s wrappers underneath ours): per entails solve,
decisions on theory atoms (variables in ``_tmap``) against all decisions,
theory conflicts (``_theory_conflict``) and whether the last decision
before each was on a theory atom, Boolean conflicts, and the wall time of
the solves with any conflict.  A phase heuristic can only remove
conflicts and the decisions leading to them; the solve time of the
conflicting solves is therefore its ceiling.
"""
import json, pickle, sys, time
from collections import Counter

stream = pickle.load(open(sys.argv[1], "rb"))
log = [json.loads(l) for l in open(sys.argv[2])]

# -- offline ---------------------------------------------------------------------
solves = [s for q in log for s in q["solves"]]
dec = sorted(s["decisions"] for s in solves)
con = sorted(s["conflicts"] for s in solves)
q_search = [q for q in log if q["solves"]]
ms_search = sum(q["ms"] for q in q_search)
ms_conf = sum(q["ms"] for q in q_search if any(s["conflicts"] for s in q["solves"]))
n_conf = sum(1 for s in solves if s["conflicts"])
print(f"log: {len(solves)} solves in {len(q_search)} queries ({ms_search:.0f} ms); "
      f"decisions median {dec[len(dec) // 2]}, p90 {dec[int(.9 * len(dec))]}, total {sum(dec)}; "
      f"conflicts total {sum(con)}, solves with any {n_conf}; "
      f"queries with a conflicting solve: {sum(1 for q in q_search if any(s['conflicts'] for s in q['solves']))}, "
      f"{ms_conf:.0f} ms ({100 * ms_conf / ms_search:.1f}% of search-query time)")

# -- online ------------------------------------------------------------------------
import query_log
from satassume.solver import Solver
ctx = query_log.ctx
pristine_solve = Solver._solve
orig_pick = Solver._pick_branch
orig_tconf = Solver._theory_conflict
orig_search = Solver._search
cur = {"on": False, "last_theory": False, "dec": 0, "tdec": 0, "tconf": 0, "tconf_after_tdec": 0, "conf": 0}
rows = []


def _pick_branch(self):
    r = orig_pick(self)
    if cur["on"] and r >= 0:
        cur["dec"] += 1
        t = (r >> 1) in self._tmap
        cur["last_theory"] = t
        if t:
            cur["tdec"] += 1
    return r


def _theory_conflict(self, lits):
    if cur["on"]:
        cur["tconf"] += 1
        if cur["last_theory"]:
            cur["tconf_after_tdec"] += 1
    return orig_tconf(self, lits)


def _solve(self, lits, keep):
    e = ctx.entails
    if not (e is not None and e[0] is self and len(lits) == e[2] + 1):
        return pristine_solve(self, lits, keep)
    for k in ("dec", "tdec", "tconf", "tconf_after_tdec"):
        cur[k] = 0
    cur["on"] = True
    c0 = self._n_conflicts
    t0 = time.perf_counter()
    res = pristine_solve(self, lits, keep)
    dt = 1000 * (time.perf_counter() - t0)
    cur["on"] = False
    rows.append({"ms": dt, "dec": cur["dec"], "tdec": cur["tdec"], "tconf": cur["tconf"],
                 "tconf_after_tdec": cur["tconf_after_tdec"], "conf": self._n_conflicts - c0,
                 "theories": bool(self._theories), "sat": bool(res)})
    return res


Solver._pick_branch = _pick_branch
Solver._theory_conflict = _theory_conflict
Solver._solve = _solve
dt, bad = query_log.run(stream, "/dev/null", False)
print(f"\ninstrumented pass {dt:.2f} s, answers differ: {len(bad)}; entails solves {len(rows)}")
ms = sum(r["ms"] for r in rows)
th = [r for r in rows if r["theories"]]
print(f"solve time {ms:.0f} ms; theory sessions: {len(th)} solves, {sum(r['ms'] for r in th):.0f} ms")
print(f"decisions {sum(r['dec'] for r in rows)}, on theory atoms {sum(r['tdec'] for r in rows)} "
      f"(theory sessions: {sum(r['dec'] for r in th)} decisions, {sum(r['tdec'] for r in th)} on atoms)")
print(f"theory conflicts {sum(r['tconf'] for r in rows)}, of which right after a theory-atom decision "
      f"{sum(r['tconf_after_tdec'] for r in rows)}; all conflicts {sum(r['conf'] for r in rows)}")
cf = [r for r in rows if r["conf"] or r["tconf"]]
print(f"solves with any conflict: {len(cf)}, {sum(r['ms'] for r in cf):.0f} ms "
      f"({100 * sum(r['ms'] for r in cf) / ms:.1f}% of solve time): the ceiling of a phase heuristic")
tc = [r for r in rows if r["tconf"]]
print(f"solves with a theory conflict: {len(tc)}, {sum(r['ms'] for r in tc):.0f} ms")
print("decisions per solve, theory sessions:", dict(sorted(Counter(min(r["dec"], 30) for r in th).items())))
