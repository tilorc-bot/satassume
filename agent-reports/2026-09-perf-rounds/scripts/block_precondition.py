"""Round 3, item A2: how often is a rule block instantiated over variables
that are already assigned (the case where the propagator's
``register_block`` precondition, "every variable of the block is
unassigned", fails and the engine must fall back to ``add_pattern``)?

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/2026-09-perf-rounds/scripts/block_precondition.py stream.pkl

Wraps ``Solver.add_pattern`` for ``RULE_INTERNAL`` calls on the cold pass
(answers checked) and classifies each call: all block variables unassigned,
some assigned at root (level 0 with no held levels, or below the first
held level), some assigned only at a held level.  Also counts the
``ensure_vars`` branch of ``Session.node`` (complete constants: no block).
"""
import pickle, sys, time
from collections import Counter

stream = pickle.load(open(sys.argv[1], "rb"))
import satassume.sympy_api as api
from satassume.solver import Solver
from satassume.rules import RULE_INTERNAL, NPRED

C = Counter()
assigned_n = Counter()
orig = Solver.add_pattern


def add_pattern(self, pattern, base, nvars):
    if pattern is RULE_INTERNAL:
        top = base + nvars - 1
        if top > self._nvars:
            C["free"] += 1                    # variables not even allocated yet
        else:
            lo = 2 * base
            sl = self._val[lo:lo + 2 * nvars]
            k = (2 * nvars - sl.count(None)) // 2
            if k == 0:
                C["free"] += 1
            else:
                lv = [self._level[base + i] for i in range(nvars) if self._val[2 * (base + i)] is not None]
                if all(l == 0 for l in lv):
                    C["assigned_root"] += 1
                else:
                    C["assigned_held"] += 1
                assigned_n[k] += 1
    return orig(self, pattern, base, nvars)


Solver.add_pattern = add_pattern
orig_ev = Solver.ensure_vars
t0 = time.perf_counter()
bad = 0
for p, a, r in stream:
    try:
        got = api.ask(p, a)
    except ValueError:
        got = "err"
    if got is not r and got != "err":
        bad += 1
dt = time.perf_counter() - t0
tot = sum(C.values())
print(f"pass {dt:.2f}s, mismatches {bad}; rule blocks instantiated {tot}")
for k in ("free", "assigned_root", "assigned_held"):
    print(f"  {k:14s} {C[k]:7d}  {100 * C[k] / tot:5.1f}%")
print("  assigned variables per non-free block (count: blocks):",
      dict(sorted(assigned_n.items())[:15]))
