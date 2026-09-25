"""Item A1: what the rule-block propagator does on the replay, with the
engine's block redirected to it (A2 simulated, no engine change).

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/2026-09-perf-rounds/scripts/propagator_census.py \
        ~/.cache/satassume/stream.pkl [off|on]

``on`` (default): every ``add_pattern(RULE_INTERNAL, b, NPRED)`` the engine
makes becomes ``set_rule_block`` (first time per solver) plus
``register_block(b)``, which is exactly what A2 changes in
``Session.__init__`` / ``Session.node``.  ``off``: the engine as it is.
Read-only wrappers: timing of the block's insertion (``add_pattern`` or
``register_block``, and within it ``_rb_settle``), of ``_propagate``, and,
in ``on`` mode, a census of the hook's work per processed literal (block
literals, binary implications visited, longer clauses evaluated) against
the watch-list visits that remain.  Answers are compared with the
recording.
"""
import pickle
import sys
import time
from collections import Counter

stream = pickle.load(open(sys.argv[1], "rb"))
mode = sys.argv[2] if len(sys.argv) > 2 else "on"
from satassume.rules import NPRED, RULE_INTERNAL  # noqa: E402
from satassume.solver import Solver  # noqa: E402

T = Counter()
N = Counter()
orig_ap = Solver.add_pattern


def ap(self, pattern, base, nvars):
    if pattern is not RULE_INTERNAL:
        return orig_ap(self, pattern, base, nvars)
    t = time.perf_counter()
    try:
        if mode == "off":
            return orig_ap(self, pattern, base, nvars)
        if self._rb_clauses is None:
            self.set_rule_block(RULE_INTERNAL, NPRED)
        lo = 2 * base
        if base + nvars - 1 <= self._nvars and self._val[lo:lo + 2 * nvars].count(None) != 2 * nvars:
            N["blocks over assigned variables"] += 1
            if self._trail_lim:
                N["... while levels are held"] += 1
        return self.register_block(base)
    finally:
        T["block insertion"] += time.perf_counter() - t
        N["block insertion"] += 1


Solver.add_pattern = ap
orig_settle = Solver._rb_settle


def settle(self, base):
    t = time.perf_counter()
    try:
        return orig_settle(self, base)
    finally:
        T["  of which _rb_settle"] += time.perf_counter() - t
        N["  of which _rb_settle"] += 1


Solver._rb_settle = settle
orig_prop = Solver._propagate


def prop(self):
    q0 = self._qhead
    t = time.perf_counter()
    r = orig_prop(self)
    T["_propagate"] += time.perf_counter() - t
    N["_propagate"] += 1
    if mode == "on" and self._rb_clauses is not None:
        imp, occ3, occn, _, _, _ = self._rb
        trail, rb, W = self._trail, self._rb_base, self._watches
        for i in range(q0, self._qhead):
            p = trail[i]
            N["processed literals"] += 1
            N["watch-list visits"] += len(W[p ^ 1])
            b = rb[p >> 1]
            if b:
                rel = p - 2 * b
                N["block literals"] += 1
                N["binary implications visited"] += len(imp[rel])
                N["longer clauses evaluated"] += len(occ3[rel]) + len(occn[rel])
    return r


Solver._propagate = prop
from satassume.sympy_api import ask  # noqa: E402

bad = 0
t0 = time.perf_counter()
for p, a, r in stream:
    try:
        got = ask(p, a)
    except ValueError:
        got = "error"
    if got is not r:
        bad += 1
print(f"mode {mode}: instrumented pass {time.perf_counter() - t0:.2f} s, answers differ: {bad}")
for k in ("block insertion", "  of which _rb_settle", "_propagate"):
    if N[k]:
        print(f"  {k:28s} {1000 * T[k]:7.0f} ms  ({N[k]} calls)")
for k, v in N.items():
    if k not in T:
        print(f"  {k:28s} {v}")
