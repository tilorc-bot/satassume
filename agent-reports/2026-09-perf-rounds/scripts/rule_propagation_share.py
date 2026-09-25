"""Item 2.3: the share of solver propagation work that the rule block causes.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy:tools python agent-reports/2026-09-perf-rounds/scripts/rule_propagation_share.py \
        ~/.cache/satassume/stream.pkl

Read-only wrappers on the replay.  Every problem clause is tagged by the
insertion call the engine used: ``add_pattern(RULE_INTERNAL, ...)`` -> rule
(the unary predicate implication rules, one block per node),
``add_internal`` -> template (compiled structural templates), ``add_clauses``
/ ``add_clause`` -> other (cached facts, the assumption formula, cone
clauses); learnt and theory clauses by their class.  ``_propagate`` is
wrapped: for every call, the literals it processed (the trail slice
between the queue head before and after) give the watch lists it scanned,
counted by clause tag, and the literals it assigned give the reason
clauses, by tag.  Propagation time on rule clauses is estimated as the
``_propagate`` time times the rule share of watch-list visits (the cost of
visiting a clause in a watch list is the same for every tag).  The time of
the ``add_pattern(RULE_INTERNAL)`` calls is the solver-side materialization
of the rule block.
"""
import pickle, sys, time
from collections import Counter

stream = pickle.load(open(sys.argv[1], "rb"))
from satassume.solver import Solver, Clause
from satassume.rules import RULE_INTERNAL
from satassume.sympy_api import ask

depth = [0]
T = Counter()          # times, ms
N = Counter()          # counts
visits = Counter()     # watch-list visits by tag
reasons = Counter()    # assignments by reason tag


def tag_of(s, c):
    if c.__class__ is Clause:
        return "learnt" if c.learnt else "theory"
    return s.__dict__.get("_ctag", {}).get(id(c), "untagged")


def tagging(name, tag):
    orig = getattr(Solver, name)

    def w(self, *a, **k):
        n0 = len(self._clauses)
        depth[0] += 1
        t0 = time.perf_counter()
        try:
            return orig(self, *a, **k)
        finally:
            dt = 1000 * (time.perf_counter() - t0)
            depth[0] -= 1
            if depth[0] == 0:
                t = tag
                if name == "add_pattern" and a and a[0] is RULE_INTERNAL:
                    t = "rule"
                tags = self.__dict__.setdefault("_ctag", {})
                cls = self._clauses
                for i in range(n0, len(cls)):
                    tags[id(cls[i])] = t
                T["insert_" + t] += dt
                N["insert_" + t] += 1
                N["clauses_" + t] += len(cls) - n0
    setattr(Solver, name, w)


tagging("add_pattern", "pattern")
tagging("add_internal", "template")
tagging("add_clauses", "other")
tagging("add_clause", "other")

orig_prop = Solver._propagate


def _propagate(self):
    q0 = self._qhead
    t0 = len(self._trail)
    tt = time.perf_counter()
    r = orig_prop(self)
    T["propagate"] += 1000 * (time.perf_counter() - tt)
    N["propagate"] += 1
    trail = self._trail
    watches = self._watches
    reason = self._reason
    for i in range(q0, self._qhead):
        for c in watches[trail[i] ^ 1]:
            visits[tag_of(self, c)] += 1
    for i in range(t0, len(trail)):
        c = reason[trail[i] >> 1]
        reasons["unit/decision" if c is None else tag_of(self, c)] += 1
    return r


Solver._propagate = _propagate

t_all = time.perf_counter()
bad = 0
for p, a, r in stream:
    try:
        got = ask(p, a)
    except ValueError:
        got = "error"
    if got is not r:
        bad += 1
total = time.perf_counter() - t_all
print(f"instrumented pass {total:.2f} s (heavily instrumented; shares below use inner timings), answers differ: {bad}")
print(f"clauses inserted: " + ", ".join(f"{k[8:]} {v}" for k, v in sorted(N.items()) if k.startswith("clauses_")))
print(f"insertion time (ms): " + ", ".join(f"{k[7:]} {v:.0f}" for k, v in sorted(T.items()) if k.startswith("insert_")))
print(f"_propagate: {N['propagate']} calls, {T['propagate']:.0f} ms inner time")
tv = sum(visits.values()); tr = sum(reasons.values())
print("watch-list visits by tag: " + ", ".join(f"{k} {v} ({100 * v / tv:.1f}%)" for k, v in visits.most_common()))
print("assignments by reason tag: " + ", ".join(f"{k} {v} ({100 * v / tr:.1f}%)" for k, v in reasons.most_common()))
rule_prop = T["propagate"] * visits["rule"] / tv
print(f"\npropagation time attributable to rule clauses: {rule_prop:.0f} ms of {T['propagate']:.0f} ms; "
      f"rule-block insertion (add_pattern(RULE_INTERNAL)): {T['insert_rule']:.0f} ms")
