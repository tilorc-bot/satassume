"""Item 3.1: where the ``implied`` misses come from.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy:tools python agent-reports/2026-09-perf-rounds/scripts/assume_misses.py \
        ~/.cache/satassume/stream.pkl

One instrumented pass (``tools/query_log.py``'s wrappers underneath).
``Solver._assume`` (the engine of ``implied`` and of the propagation stage
of ``entails``) is wrapped; a call is a *hit* if it is answered from the
held levels or the propagation cache, a *miss* if ``_assume_propagate``
ran.  Every miss is classified from the solver's state before the call:

    theory        a theory is attached (levels are never held there)
    first         no earlier call on this solver
    changed       held levels exist but for another assumption set
    root_grew     levels were dropped because the root trail grew since
                  the last call (a unit clause: the fact write-back)
    search        a _solve ran since the last call and did not keep the levels
    attach        levels dropped by a clause insertion (_attach_held fallback)
    other         anything else (e.g. the last call itself conflicted)

For ``root_grew`` misses the recomputed trail is compared with the
previous held trail plus the new root literals: equal means the unit
implied nothing new at the held levels, which is when the solver-side
alternative of the plan (keep the levels, insert the unit at root) is
valid.  For ``theory`` misses, "same assumptions as the previous call and
nothing changed since" (no root growth, no search, no atom registered) is
what holding levels with a theory attached would recover.
"""
import pickle, sys, time
from collections import Counter, defaultdict

stream = pickle.load(open(sys.argv[1], "rb"))
import query_log
from satassume.solver import Solver

ctx = query_log.ctx
orig_assume = Solver._assume
orig_ap = Solver._assume_propagate
orig_solve = Solver._solve
cur = {"ap": False}
state = {}          # id(solver) -> dict(last_lits, last_held, trail, root_len, solved, natoms, ok)
count = Counter()
ms = Counter()
n_calls = 0


def root_len(s):
    return s._trail_lim[0] if s._trail_lim else len(s._trail)


def _assume_propagate(self, lits):
    cur["ap"] = True
    return orig_ap(self, lits)


t_A = Counter()        # theory sessions: ms of propagating the assumptions from root, per entails solve
n_A = Counter()


def _solve(self, lits, keep):
    st = state.get(id(self))
    if st is not None:
        st["solved"] = True
    e = ctx.entails
    if self._theories and e is not None and e[0] is self and len(lits) == e[2] + 1 and not self._trail_lim:
        # What a held level would save in a theory session: the search is
        # about to decide and propagate A from root (theory asserts, simplex).
        # Measure that work once here and undo it; a learnt reason clause a
        # theory propagation adds is one the search would add anyway.
        A = lits[:-1]
        t0 = time.perf_counter()
        ok = self._assume_propagate(A)
        dt = 1000 * (time.perf_counter() - t0)
        self._backtrack(0)
        key = "consistent" if ok else "conflict"
        t_A[key] += dt; n_A[key] += 1
        t0 = time.perf_counter()
        r = orig_solve(self, lits, keep)
        t_A["solve"] += 1000 * (time.perf_counter() - t0); n_A["solve"] += 1
        return r
    return orig_solve(self, lits, keep)


def _assume(self, assumptions):
    global n_calls
    lits = self._internal_lits(list(assumptions))
    st = state.get(id(self))
    held = self._held
    natoms = len(self._tmap)
    where = "entails" if ctx.entails is not None and ctx.entails[0] is self else "implied"
    cur["ap"] = False
    t0 = time.perf_counter()
    r = orig_assume(self, assumptions)
    dt = 1000 * (time.perf_counter() - t0)
    n_calls += 1
    if not cur["ap"]:
        kind = "hit_held" if held is not None and held == lits else "hit_cache"
        sub = ""
    else:
        if self._theories:
            kind = "theory"
            if st is None:
                sub = "first"
            elif st["last_lits"] != lits:
                sub = "changed"
            elif st["natoms"] != natoms:
                sub = "atoms_registered"
            elif st["root_len"] != root_len(self):
                sub = "root_grew"
            elif st["solved"]:
                sub = "search"
            else:
                sub = "same_nothing_changed"
        elif st is None:
            kind, sub = "first", ""
        elif held is not None:
            kind, sub = "changed", ""
        elif st["last_held"] is None:
            kind, sub = "other", ("prev_conflict" if not st["ok"] else "prev_unheld")
        elif st["solved"]:
            kind, sub = "search", ""
        elif st["root_len"] != root_len(self):
            kind = "root_grew"
            if st["last_lits"] == lits and r is not None:
                new_root = set(self._trail[st["root_len"]:root_len(self)])
                old = set(st["trail"])
                sub = "unit_implied_nothing_new" if set(r) == old | new_root else "unit_implied_more"
            else:
                sub = "changed_set"
        else:
            kind, sub = "attach", ""
    key = (where, kind, sub)
    count[key] += 1
    ms[key] += dt
    state[id(self)] = {"last_lits": lits, "last_held": self._held, "trail": list(self._trail) if self._held is not None else [],
                       "root_len": root_len(self), "solved": False, "natoms": natoms, "ok": r is not None}
    return r


Solver._assume_propagate = _assume_propagate
Solver._solve = _solve
Solver._assume = _assume
dt, bad = query_log.run(stream, "/dev/null", False)
print(f"instrumented pass {dt:.2f} s, answers differ: {len(bad)}; _assume calls {n_calls}, "
      f"time in _assume {sum(ms.values()):.0f} ms")
tot_miss = sum(c for k, c in count.items() if not k[1].startswith("hit"))
print(f"hits {sum(c for k, c in count.items() if k[1].startswith('hit'))}, misses {tot_miss}, "
      f"miss time {sum(m for k, m in ms.items() if not k[1].startswith('hit')):.0f} ms")
print(f"\n{'where':8} {'kind':10} {'sub':26} {'n':>6} {'ms':>8} {'ms/call':>8}")
for key in sorted(count, key=lambda k: -ms[k]):
    print(f"{key[0]:8} {key[1]:10} {key[2]:26} {count[key]:6} {ms[key]:8.1f} {ms[key] / count[key]:8.3f}")
by_kind = Counter()
ms_kind = Counter()
for k, c in count.items():
    by_kind[k[1]] += c; ms_kind[k[1]] += ms[k]
print("\nby kind:", {k: (by_kind[k], round(ms_kind[k])) for k in sorted(by_kind, key=lambda k: -ms_kind[k])})

print(f"\ntheory-session entails solves: {n_A['solve']} solves, {t_A['solve']:.0f} ms; "
      f"propagating A from root per solve: {n_A['consistent']} measured, {t_A['consistent']:.1f} ms "
      f"({t_A['consistent'] / max(1, n_A['consistent']):.3f} ms each), conflicts {n_A['conflict']}")
