"""Round 3, item B5: bound for precompiled template clause emission.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/2026-09-perf-rounds/scripts/emit_bound.py stream.pkl [PLAIN_SECONDS]

Records, over the cold pass, every demand filter the engine applies to a
pattern's clauses (``_compile_patterns``: ``c[1] & want`` over
``pat.clauses``; ``_compile_pending``: the same over a parked list) and
every shift (``_emit_pattern``: ``[[bases[k] + off for k, off in li] ...]``).
Then re-times both on the recorded calls, as the engine does them today,
against a prototype of the precompiled form:

* filter: one dict lookup keyed by (clause list identity, want) returning
  the (now, later) pair computed once;
* shift: a generated function per clause list (``lambda B: [[B[0] + 3,
  B[1] + 8], ...]``), built once, called with the bases.

The difference is the saving the precompiled form could make (the
solver's ``add_internal`` is not touched and not timed).
"""
import pickle, sys, time
from collections import Counter

stream = pickle.load(open(sys.argv[1], "rb"))
plain = float(sys.argv[2]) if len(sys.argv) > 2 else None
import satassume.sympy_api as api
from satassume.engine import Session, want_of

pc = time.perf_counter
filters = []     # (clauses, want)
shifts = []      # (clauses, bases)

orig_emit = Session._emit_pattern


def emit(self, clauses, bases):
    shifts.append((clauses, list(bases)))
    return orig_emit(self, clauses, bases)


orig_cp = Session._compile_patterns


def cp(self, node, compiled, demanded):
    if demanded is not None:
        w = want_of(demanded)
        for comp in compiled:
            filters.append((comp.pattern.clauses, w))
    return orig_cp(self, node, compiled, demanded)


orig_pend = Session._compile_pending


def pend(self, node, demanded):
    pc_ = self.pending_c.get(node)
    if pc_:
        w = want_of(demanded)
        for clauses, bases in pc_:
            filters.append((clauses, w))
    return orig_pend(self, node, demanded)


Session._emit_pattern = emit
Session._compile_patterns = cp
Session._compile_pending = pend
t0 = pc()
for p, a, r in stream:
    try:
        api.ask(p, a)
    except ValueError:
        pass
dt = pc() - t0
D = plain or dt
print(f"recorded pass {dt:.3f}s; {len(filters)} filters, {len(shifts)} shifts "
      f"({sum(len(c) for c, _ in shifts)} clauses); shares of {D:.3f}s")


def best(f, reps=5):
    b = 1e9
    for _ in range(reps):
        t = pc(); f(); b = min(b, pc() - t)
    return b


# today
def filt_today():
    for clauses, want in filters:
        now = [c for c in clauses if c[1] & want]
        if len(now) < len(clauses):
            later = [c for c in clauses if not (c[1] & want)]


def shift_today():
    for clauses, bases in shifts:
        [[bases[k] + off for k, off in li] for _, _, li in clauses]


# precompiled
fmemo = {}
for clauses, want in filters:
    key = (id(clauses), want)
    if key not in fmemo:
        now = tuple(c for c in clauses if c[1] & want)
        fmemo[key] = (now, tuple(c for c in clauses if not (c[1] & want)))
fkeys = [(id(c), w) for c, w in filters]


def filt_pre():
    g = fmemo.get
    for k in fkeys:
        g(k)


gen = {}


def make(clauses):
    body = ", ".join("[" + ", ".join(f"B[{k}] + {off}" for k, off in li) + "]" for _, _, li in clauses)
    return eval(f"lambda B: [{body}]")


calls = []
for clauses, bases in shifts:
    f = gen.get(id(clauses))
    if f is None:
        f = gen[id(clauses)] = make(clauses)
    calls.append((id(clauses), bases))


def shift_pre():
    g = gen.get
    for k, bases in calls:
        g(k)(bases)


# check equal output
for (clauses, bases), (k, _) in zip(shifts[:2000], calls[:2000]):
    assert gen[k](bases) == [[bases[kk] + off for kk, off in li] for _, _, li in clauses]

ft, fp, st, sp = best(filt_today), best(filt_pre), best(shift_today), best(shift_pre)
print(f"filter: today {1000 * ft:.1f} ms ({100 * ft / D:.2f}%), precompiled {1000 * fp:.1f} ms "
      f"({100 * fp / D:.2f}%); distinct (clauses, want) {len(fmemo)}")
print(f"shift:  today {1000 * st:.1f} ms ({100 * st / D:.2f}%), generated {1000 * sp:.1f} ms "
      f"({100 * sp / D:.2f}%); distinct clause lists {len(gen)}")
print(f"saving bound (both): {1000 * (ft - fp + st - sp):.1f} ms = {100 * (ft - fp + st - sp) / D:.2f}%")
