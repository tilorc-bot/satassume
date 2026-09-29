"""Bound for item 1.2 (component-restricted search): per entails search on
the refine-stream replay, the connected component of the query variable in
the clause graph under the root and assumption assignment, against the
session's unassigned variables, and the share of the real search's
decisions that fall outside that component.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy:tools python agent-reports/2026-09-perf-rounds/scripts/component_bound.py \
        ~/.cache/satassume/stream.pkl

Component: breadth-first from the query variable over an occurrence index
of the problem clauses (``_clauses``; unit clauses live on the trail and
learnt clauses are consequences), skipping clauses with a literal true
under the assignment and stepping only through unassigned variables.  The
assignment is the solver's own when the assumptions are held (``_held``,
which ``entails`` has just established); otherwise (theories attached) a
plain offline unit propagation of the assumptions over the clauses, which
under-propagates (no theory propagation) and so over-estimates the
component.  The real search runs unchanged; ``_pick_branch`` is wrapped to
attribute each decision to inside or outside the component.

Path split via ``tools/query_log.py``'s stage tracking ("cone" in the
query's path: the search ran in a cone rebuild).
"""
import pickle, sys, time
from collections import Counter, defaultdict

stream = pickle.load(open(sys.argv[1], "rb"))
import query_log
from satassume.solver import Solver

_pristine_solve = Solver._solve            # query_log.run() installs its wrappers on top of ours
ctx = query_log.ctx

orig_solve = Solver._solve
orig_pick = Solver._pick_branch
cur = {"comp": None, "inside": 0, "outside": 0, "restricted": False, "comp_sorted": (), "pos": 0, "popped": []}
rows = []                                    # one per entails solve


def occ_index(s):
    """var -> list of problem clauses, extended incrementally."""
    idx = s.__dict__.get("_occ")
    if idx is None:
        idx = s._occ = (defaultdict(list), [0])
    occ, done = idx
    cls = s._clauses
    for i in range(done[0], len(cls)):
        c = cls[i]
        for l in c:
            occ[l >> 1].append(c)
    done[0] = len(cls)
    return occ


def offline_assignment(s, lits):
    """``_val`` copy with ``lits`` assumed and unit-propagated over the
    problem and learnt clauses (no theory propagation)."""
    val = list(s._val)
    for l in lits:
        if val[l] is False:
            return val
        val[l] = True; val[l ^ 1] = False
    cls = s._clauses + s._learnts
    changed = True
    while changed:
        changed = False
        for c in cls:
            unassigned = None; n = 0; sat = False
            for l in c:
                v = val[l]
                if v is True:
                    sat = True; break
                if v is None:
                    n += 1; unassigned = l
            if sat or n != 1:
                continue
            val[unassigned] = True; val[unassigned ^ 1] = False
            changed = True
    return val


def component(s, val, var):
    occ = occ_index(s)
    seen = {var}
    todo = [var]
    while todo:
        u = todo.pop()
        for c in occ.get(u, ()):
            for l in c:
                if val[l] is True:
                    break
            else:
                for l in c:
                    w = l >> 1
                    if val[2 * w] is None and w not in seen:
                        seen.add(w); todo.append(w)
    return seen


def _solve(self, lits, keep):
    e = ctx.entails
    is_entails = e is not None and e[0] is self and len(lits) == e[2] + 1
    if not is_entails:
        return orig_solve(self, lits, keep)
    A = lits[:-1]
    target = lits[-1] >> 1
    held = self._held is not None and self._held == A
    t0 = time.perf_counter()
    val = self._val if held else offline_assignment(self, A)
    unassigned = sum(1 for v in range(1, self._nvars + 1) if val[2 * v] is None)
    comp = component(self, val, target) if val[2 * target] is None else set()
    t_walk = time.perf_counter() - t0
    # Prototype of the restricted search, timed, before the real solve:
    # decisions only inside the component; stop when it is assigned.
    # State it must not leave behind: the partial model as witness, and
    # heap entries popped for non-component variables.
    key = (id(self), tuple(A), self._stamp, len(self._trail) if not self._trail_lim else self._trail_lim[0])
    same_walk = key == cur.get("last_key")
    cur["last_key"] = key
    t_restricted = None
    if comp and not self._theories:
        w, m = self._witness, self._model
        cur["comp"] = comp; cur["comp_sorted"] = sorted(comp); cur["pos"] = 0
        cur["popped"] = []; cur["restricted"] = True
        t0 = time.perf_counter()
        rres = Solver._solve_orig(self, lits, keep)
        t_restricted = 1000 * (time.perf_counter() - t0)
        cur["restricted"] = False; cur["comp"] = None
        for v in cur["popped"]:
            if self._val[2 * v] is None:
                self._heap_insert(v)
        self._witness, self._model = w, m
    else:
        rres = None
    cur["comp"] = comp; cur["inside"] = 0; cur["outside"] = 0
    t0 = time.perf_counter()
    res = orig_solve(self, lits, keep)
    dt = time.perf_counter() - t0
    if rres is not None and rres != res:
        cur["disagree"] = cur.get("disagree", 0) + 1
    rows.append({"i": ctx.i, "cone": "cone" in ctx.path, "session_new": ctx.session_new,
                 "held": held, "comp": len(comp), "unassigned": unassigned,
                 "nvars": self._nvars, "inside": cur["inside"], "outside": cur["outside"],
                 "sat": bool(res), "ms": 1000 * dt, "walk_ms": 1000 * t_walk,
                 "theories": bool(self._theories), "A": tuple(A), "solver": id(self),
                 "restricted_ms": t_restricted, "same_walk": same_walk})
    cur["comp"] = None
    return res


def _pick_branch(self):
    if cur["restricted"]:
        val = self._val
        if self._scan:
            cl = cur["comp_sorted"]; pos = cur["pos"]
            while pos < len(cl) and val[2 * cl[pos]] is not None:
                pos += 1
            cur["pos"] = pos
            if pos == len(cl):
                return -1
            v = cl[pos]
            return 2 * v + self._polarity[v]
        comp = cur["comp"]; heap = self._heap
        while heap:
            v = self._heap_pop()
            if val[2 * v] is not None:
                continue
            if v in comp:
                return 2 * v + self._polarity[v]
            cur["popped"].append(v)
        return -1
    r = orig_pick(self)
    comp = cur["comp"]
    if comp is not None and r >= 0:
        if (r >> 1) in comp:
            cur["inside"] += 1
        else:
            cur["outside"] += 1
    return r


Solver._solve_orig = _pristine_solve
Solver._solve = _solve
Solver._pick_branch = _pick_branch

t_all = time.perf_counter()
dt, bad = query_log.run(stream, "/dev/null", False)
print(f"instrumented pass {dt:.2f} s, answers differ: {len(bad)}; entails solves {len(rows)}; "
      f"restricted prototype disagreed with the real solve {cur.get('disagree', 0)} times")


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else 0


def report(name, rs):
    if not rs:
        return
    n = len(rs)
    comp = [r["comp"] for r in rs]
    un = [r["unassigned"] for r in rs]
    ratio = [r["comp"] / r["unassigned"] if r["unassigned"] else 1.0 for r in rs]
    dec_in = sum(r["inside"] for r in rs); dec_out = sum(r["outside"] for r in rs)
    ms = sum(r["ms"] for r in rs); walk = sum(r["walk_ms"] for r in rs)
    print(f"\n{name}: {n} solves, {ms:.0f} ms in _solve, walk {walk:.0f} ms")
    print(f"  component size: median {pct(comp, .5)}, p90 {pct(comp, .9)}, max {max(comp)}; "
          f"unassigned: median {pct(un, .5)}, p90 {pct(un, .9)}; "
          f"component/unassigned: median {pct(ratio, .5):.2f}, p90 {pct(ratio, .9):.2f}")
    small = Counter(min(c, 5) for c in comp)
    print(f"  solves with component size 1/2/3/4/5+: {[small[k] for k in (1, 2, 3, 4, 5)]}")
    print(f"  decisions inside {dec_in}, outside {dec_out} "
          f"({100 * dec_out / max(1, dec_in + dec_out):.1f}% outside)")
    # time-weighted: ms of each solve split by its own outside share
    ms_out = sum(r["ms"] * r["outside"] / (r["inside"] + r["outside"]) for r in rs if r["inside"] + r["outside"])
    print(f"  ms attributable to outside decisions (per-solve share): {ms_out:.0f} of {ms:.0f} ({100 * ms_out / ms:.1f}%)")
    pr = [r for r in rs if r["restricted_ms"] is not None]
    if pr:
        full = sum(r["ms"] for r in pr); rest = sum(r["restricted_ms"] for r in pr)
        print(f"  restricted prototype on {len(pr)} solves: {rest:.0f} ms against {full:.0f} ms for the real solve "
              f"({100 * (full - rest) / full:.1f}% less; the prototype ran first, cold)")
    print(f"  consecutive solves sharing (solver, A, stamp, root): {sum(1 for r in rs if r['same_walk'])} of {len(rs)}")


report("all entails solves", rows)
report("  in a reused/first/evicted session (no cone)", [r for r in rows if not r["cone"]])
report("  in a cone rebuild", [r for r in rows if r["cone"]])
report("  with theories attached (offline assignment)", [r for r in rows if r["theories"]])
report("  unsat solves", [r for r in rows if not r["sat"]])
sets = {(r["solver"], r["A"]) for r in rows}
print(f"\ndistinct (solver, assumption set) pairs among the searches: {len(sets)} "
      f"(the once-per-assumption-set full check would add that many solves)")
print(f"held assignment used: {sum(1 for r in rows if r['held'])} of {len(rows)} solves")
print("session_new at solve time:", dict(Counter(r["session_new"] for r in rows)))
