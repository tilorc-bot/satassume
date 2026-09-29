"""Round 3, item B6: how much a monotone answer memo could answer.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/2026-09-perf-rounds/scripts/memo_subsumption.py \
        stream.pkl log-747fb0e.jsonl

Offline, over the stream in order and the per-query log of ``747fb0e``
(``tools/query_log.py`` format; ``ms``, ``outcome``, ``via``).  The answer
memo keys on ``(proposition, assumptions)`` as SymPy objects.  Here the
assumptions are a set of conjuncts: ``True`` is the empty set, an ``And``
its arguments, anything else a singleton (SymPy's ``And`` is flattened
and argument-sorted, so this is the memo's own equality lifted to sets).

For every query that missed the memo (log ``via`` not ``"memo"``):

* **subsumed**: an earlier query with the same proposition and a
  conjunct set that is a subset of this one's got a definite answer
  (True/False).  Monotonicity says the answer holds here too if these
  assumptions are consistent.  Split by what the engine actually did:
  the same answer, ``None`` (the memo would strengthen it: an answer
  change), the other definite value (would mean a bug), or ``error``
  (inconsistent assumptions: the memo would skip the ValueError).
* **None predicted** (information only, not sound): an earlier query
  with the same proposition and a superset of conjuncts answered None.
"""
import json, pickle, sys
from collections import Counter

stream = pickle.load(open(sys.argv[1], "rb"))
log = [json.loads(l) for l in open(sys.argv[2])]
assert len(log) == len(stream)
from sympy.logic.boolalg import And


def conj(a):
    if a is True:
        return frozenset()
    if isinstance(a, And):
        return frozenset(a.args)
    return frozenset([a])


tot_ms = sum(r["ms"] for r in log)
seen = {}                     # proposition -> list of (conjuncts, outcome)
SAME = []
C = Counter(); M = Counter()
for (p, a, rec), r in zip(stream, log):
    out = r["outcome"]
    S = conj(a)
    prior = seen.setdefault(p, [])
    if r["via"] != "memo":
        C["misses"] += 1; M["misses"] += r["ms"]
        defs = {o for s, o in prior if o in (True, False) and s <= S}
        if defs:
            if len(defs) > 1:
                k = "subsumed: conflicting earlier answers"
                print("conflicting:", p, "|", a, "->", out, [(sorted(map(str, s_)), o) for s_, o in prior if o in (True, False) and s_ <= S])
            elif out == "error":
                k = "subsumed: this query raises (inconsistent)"
            elif out is None:
                k = "subsumed: engine said None (answer would change)"
                why = r.get("session_error") or ("path " + ">".join(r["path"]) if r["path"] else "via " + r["via"])
                C["  None because: " + why] += 1; M["  None because: " + why] += r["ms"]
            elif out in defs:
                k = "subsumed: same answer"
                SAME.append(r)
                pth = ">".join(r["path"]) or ("(empty) via " + r["via"])
                C["  same answer, path " + pth] += 1; M["  same answer, path " + pth] += r["ms"]
            else:
                k = "subsumed: opposite answer (bug)"
            C[k] += 1; M[k] += r["ms"]
            C["subsumed"] += 1; M["subsumed"] += r["ms"]
        nones = any(o is None and s >= S for s, o in prior)
        if nones:
            k = "None predicted: " + ("right" if out is None else "wrong (" + str(out) + ")")
            C[k] += 1; M[k] += r["ms"]
    prior.append((S, out))

print(f"{len(log)} queries, logged {tot_ms:.0f} ms")
for k in sorted(C):
    print(f"  {k:50s} {C[k]:6d}  {M[k]:8.1f} ms  {100 * M[k] / tot_ms:5.2f}%")

# with the consistency check kept, a subsumption hit still pays for the
# contextual session and its propagation (query_literal checks implied(A')
# first): the saving is at most what a query spends beyond a
# propagation-only query on its path's session.  Median ms of the
# propagation-only queries (path exactly "propagation") by session_new:
from statistics import median
prop = {}
for r in log:
    if r["path"] == ["propagation"]:
        prop.setdefault(r["session_new"], []).append(r["ms"])
print("median ms of propagation-only queries by session_new:",
      {k: round(median(v), 3) for k, v in prop.items()})
sn = Counter(r["session_new"] for r in SAME)
check = sum(median(prop.get(r["session_new"], [0.0])) for r in SAME)
same_ms = sum(r["ms"] for r in SAME)
print(f"same-answer hits by session_new: {dict(sn)}")
print(f"with the consistency check kept (proxy: the median propagation-only query of the same "
      f"session kind): check {check:.1f} ms, saving {same_ms - check:.1f} ms = "
      f"{100 * (same_ms - check) / tot_ms:.2f}%")
