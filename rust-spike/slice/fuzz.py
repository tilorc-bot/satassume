"""S step 2: the compare tool. A direct API fuzzer with a scripted stub theory, run on both solvers in one process.

Each session is a script of API calls made in advance from a seed, independent of any result. After every call the
two solvers must agree on, by level:
  answers  the result or exception (type and message), and conflict()
  state    the above, every theory call since the last entry with its arguments, and the full state dump (`state.py`)
`model()` runs only where the script says, since it completes stored models (step 1's check called it after every
call, which hid the ring's None and `_fill` paths).

  fuzz.py [--sessions N] [--seed S] [--corpus fuzz|step1] [--level answers|state] [--so DIR] [--reach] [--one SEED]
          [--label L] [--progress FILE] [--shrink-seconds T] [--no-shrink] [--no-fixed] [--json] [--known]

--corpus step1 runs step 1's hand and random scripts instead of fuzz sessions. --so loads sa_solver from DIR (a mutant).
--reach adds the reentry table and the lines of solver.py never run. A mismatch prints the first differing field, then
the smallest script that still shows it, and exits 1. Shrinking stops at --shrink-seconds and says so: it re-runs the
script for every candidate, with a state dump per call, so a long script can take far longer than the fuzzing did.
--label runs one session by its label ("fixed 2", a seed, or a step 1 index). --progress names a file holding the label
of the session now running, so a run that gets killed says where. --known runs each listed known difference and the
self-test of its exemption, and prints what each solver does.
--no-fixed leaves out the hand-written sessions, to see whether the random ones reach a path by themselves.
"""
import argparse
import collections
import gc
import hashlib
import itertools
import json
import linecache
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
_a = argparse.ArgumentParser()
_a.add_argument("--sessions", type=int, default=2000)
_a.add_argument("--seed", type=int, default=1)
_a.add_argument("--corpus", default="fuzz")
_a.add_argument("--level", default="state")
_a.add_argument("--so")
_a.add_argument("--reach", action="store_true")
_a.add_argument("--one", type=int)
_a.add_argument("--no-shrink", action="store_true")
_a.add_argument("--json", action="store_true")
_a.add_argument("--label")
_a.add_argument("--progress")
_a.add_argument("--shrink-seconds", type=float, default=60)
_a.add_argument("--known", action="store_true")
_a.add_argument("--no-fixed", action="store_true")
ARGS = _a.parse_args() if __name__ == "__main__" else _a.parse_args([])
sys.path.insert(0, HERE)
if ARGS.so:
    sys.path.insert(0, ARGS.so)       # ahead of HERE, which holds the unmutated build
import sa_solver  # noqa: E402
if ARGS.so and os.path.dirname(os.path.abspath(sa_solver.__file__)) != os.path.abspath(ARGS.so):
    sys.exit(f"--so {ARGS.so}: loaded {sa_solver.__file__} instead")
import state  # noqa: E402
from satassume.sat import solver as pysolver  # noqa: E402

RustSolver = sa_solver.Solver
REACH = collections.Counter()


class Probe(pysolver.Solver):
    """The Python solver, counting the paths this fuzzer has to reach. Overrides call through and change nothing."""
    _in_final = False
    _nment = 0

    def _fill(self, mv, v):
        before = len(mv)
        r = super()._fill(mv, v)
        REACH["fill"] += 1
        REACH["fill past the model's end"] += len(mv) > before
        REACH["fill leaves None"] += r is None
        return r

    def _ring_hit(self, lits):
        none = any(None in rec[0] for rec in self._ring)
        r = super()._ring_hit(lits)
        REACH["ring read with a None stored"] += none
        REACH["ring hit on a model with None"] += r is not None and None in r[0]
        return r

    def _analyze_final(self, p):
        REACH["analyze_final"] += 1
        self._in_final = bool(self._rb_bases)
        REACH["analyze_final with blocks"] += self._in_final
        try:
            return super()._analyze_final(p)
        finally:
            self._in_final = False

    def _rb_reason(self, v, r):
        if self._in_final:
            REACH["analyze_final on a block reason"] += 1
        else:
            REACH["block reason elsewhere"] += 1
        return super()._rb_reason(v, r)

    def _reduce_db(self):
        REACH["reduce_db"] += 1
        REACH["reduce_db with blocks"] += bool(self._rb_bases)
        REACH["reduce_db with theories"] += bool(self._theories)
        return super()._reduce_db()

    def _search(self, budget):
        r = super()._search(budget)
        REACH["search budget ran out (a restart)"] += r is None
        return r

    def _bump_clause(self, c):
        before = self._cla_inc
        super()._bump_clause(c)
        REACH["clause rescale"] += self._cla_inc != before

    def _mention(self, lits):
        self._nment = 0
        super()._mention(lits)
        REACH["mention with 2+ blocks pending"] += self._nment >= 2

    def _rb_mentioned(self, base, new, mm):
        self._nment += 1
        REACH["rb_mentioned"] += 1
        return super()._rb_mentioned(base, new, mm)

    def _theory_imply(self, x, lits):
        before = len(self._trail)
        r = super()._theory_imply(x, lits)
        if len(self._trail) > before and self._trail_lim and self._reason[abs(x)].__class__ is pysolver.Clause:
            REACH["theory unit reason above root" if len(self._reason[abs(x)]) == 1 else "theory reason above root"] += 1
        return r

    def _theory_conflict(self, lits):
        REACH["theory conflict"] += 1
        return super()._theory_conflict(lits)


class Stub:
    """A scripted theory. Everything it does is a function of its spec and the calls it has had:
    conflicts: sets of literals it refuses, on `assert_lit`
    finals:    sets it refuses at `check`
    implies:   (premises, literal, unit): once the premises are true, `propagate` implies the literal, with reason
               clause [literal, -premises...], or [literal] alone if `unit`
    decide:    variables it wants decided, in order; not offered when assigned as far as it knows
    model:     whether `check` returns a model or None
    gen:       `propagate` as a generator, or a list
    raise_at:  {hook: n}: its n-th call raises KeyError, once
    bad_at:    n: the n-th `assert_lit` returns a clause that isn't false, once
    """

    def __init__(self, spec, log, name):
        self.spec, self.log, self.name = spec, log, name
        self.true, self.levels, self.calls = set(), [], collections.Counter()
        self.nasserts = 0
        self.pop_raised = False

    def _hit(self, hook, *args):
        self.log.append((self.name, hook) + args)
        self.calls[hook] += 1
        if self.spec.get("raise_at", {}).get(hook) == self.calls[hook]:
            raise KeyError(f"{self.name} {hook} {self.calls[hook]}")

    def register_atom(self, v, payload):
        self._hit("reg", v, payload)

    def assert_lit(self, x):
        self._hit("assert", x)
        self.nasserts += 1
        if self.spec.get("bad_at") == self.nasserts:
            return (False, [x])
        self.true.add(x)
        if self.levels:
            self.levels[-1].append(x)
        for c in self.spec.get("conflicts", ()):
            if x in c and set(c) <= self.true:
                r = (False, [-q for q in c])
                self.log.append((self.name, "says", r))
                return r
        return None

    def _props(self):
        for prem, x, unit in self.spec.get("implies", ()):
            if x not in self.true and set(prem) <= self.true:
                yield (x, [x] if unit else [x] + [-q for q in prem])

    def check(self):
        self._hit("check")
        for c in self.spec.get("finals", ()):
            if set(c) <= self.true:
                return (False, [-q for q in c])
        return (True, sorted(self.true)) if self.spec.get("model") else None

    def push_level(self):
        self.levels.append([])     # first: if this call raises, the solver has counted the level too
        self._hit("push")

    def pop_level(self):
        try:
            self._hit("pop")
            self.true.difference_update(self.levels.pop())   # an empty list if an earlier `push_level` raised
        except Exception:
            self.pop_raised = True
            raise


class StubProp(Stub):
    def propagate(self):
        self._hit("prop")
        return self._props() if self.spec.get("gen") else list(self._props())


class StubDecide(Stub):
    def decide(self):
        self._hit("decide")
        for v in self.spec.get("decide", ()):
            if v not in self.true and -v not in self.true:
                return v
        return None


class StubBoth(StubProp, StubDecide):
    pass


def new_stub(spec, log, name):
    cls = {(0, 0): Stub, (1, 0): StubProp, (0, 1): StubDecide, (1, 1): StubBoth}[
        ("implies" in spec or "prop" in spec), ("decide" in spec)]
    return cls(spec, log, name)


class Side:
    def __init__(self, cls, specs):
        self.s, self.log, self.exc = cls(), [], None
        self.ths = [new_stub(sp, self.log, f"T{i}") for i, sp in enumerate(specs)]

    def apply(self, op):
        name, args = op
        self.exc = None
        try:
            if name == "_set":
                setattr(self.s, args[0], args[1])
                return ("ok", None)
            args = [self.ths[int(a[1:])] if a in ("T0", "T1") else a for a in args] if name in THEORY_OPS else args
            return ("ok", getattr(self.s, name)(*args))
        except Exception as e:
            self.exc = e
            return ("raise", type(e).__name__, str(e))
        except BaseException as e:           # a Rust panic: nothing Python does corresponds to this
            return ("PANIC", type(e).__name__, str(e))


THEORY_OPS = ("attach_theory", "register_atom")


def after_pop_raised(a, b, f):
    """`pop_level` raised inside a backtrack, on both solvers, after `_rb_ulim` was cut and before `_trail_lim` was."""
    return (any(t.pop_raised for t in a.ths) and any(t.pop_raised for t in b.ths)
            and len(a.s._trail_lim) > len(a.s._rb_ulim))


def no_such_var(name):
    """The docstrings say variables must exist. This call gave one that doesn't."""
    return lambda a, b, f: f.f_locals[name] > a.s.nvars()


# The exempted differences: Python raises IndexError, Rust panics (a BaseException) at the matching index. Keyed by
# (function, source line) in solver.py; then the list Python indexed, the local holding the index, and the cause.
KNOWN_SITES = {
    ("_backtrack", "k = self._rb_ulim[lvl]"): ("_rb_ulim", "lvl", after_pop_raised, "backtrack after pop_level raised"),
    ("mention_blocks", "b0 = rb_base[base]"): ("_rb_base", "base", no_such_var("base"), "mention_blocks past the last variable"),
    ("_mention", "if not ment[v]:"): ("_ment", "v", no_such_var("v"), "a mention_blocks range past the last variable"),
}


def known_difference(a, b, ra, rb):
    """Which exempted difference this is, or None. All must hold, so nothing else can pass as one: the exact line in
    Python, the same list length and index in Rust's message, and that site's cause. The caller goes on to compare the
    conflict, the theory calls, the state and the rest of the session. Counted, never silent. See --known."""
    if not (ra[:2] == ("raise", "IndexError") and rb[:2] == ("PANIC", "PanicException") and a.exc is not None):
        return None
    tb = a.exc.__traceback__
    while tb.tb_next:
        tb = tb.tb_next
    f = tb.tb_frame
    if f.f_code.co_filename != pysolver.__file__:
        return None
    site = KNOWN_SITES.get((f.f_code.co_name, linecache.getline(f.f_code.co_filename, tb.tb_lineno).strip()))
    if site is None:
        return None
    lst, idx, cause, name = site
    if rb[2] != f"index out of bounds: the len is {len(getattr(a.s, lst))} but the index is {f.f_locals[idx]}":
        return None
    return name if cause(a, b, f) else None


def run_session(script, specs, level, reach=False):
    """None, or the first difference: a dict with op, what, py, rs."""
    a, b = Side(Probe, specs), Side(RustSolver, specs)
    deep = level == "state"
    for i, op in enumerate(script):
        ra, rb = a.apply(op), b.apply(op)
        known = known_difference(a, b, ra, rb)
        if known:
            REACH["known difference: " + known] += 1
        elif ra != rb:
            return dict(op=i, what="result", py=repr(ra), rs=repr(rb))
        ca, cb = a.s.conflict(), b.s.conflict()
        if ca != cb:
            return dict(op=i, what="conflict", py=repr(ca), rs=repr(cb))
        if deep:
            if a.log != b.log:
                k = next((j for j, (x, y) in enumerate(zip(a.log, b.log)) if x != y), min(len(a.log), len(b.log)))
                return dict(op=i, what="theory calls", py=repr(a.log[k:k + 3]), rs=repr(b.log[k:k + 3]))
            d = state.diff(state.dump_py(a.s), b.s.dump())
            if d:
                return dict(op=i, what="state " + d[0], py=d[2], rs=d[3])
        a.log.clear()
        b.log.clear()
        REACH["calls"] += 1
        REACH["raises"] += ra[0] == "raise"
    s = a.s
    REACH["sessions"] += 1
    for k, x in (("conflicts", s._n_conflicts), ("decisions", s._n_decisions), ("restarts", s._n_restarts),
                 ("reductions", s._n_reductions), ("ring hits", s._n_ring_hits), ("theory decisions", s._n_tdecisions),
                 ("late mentions", s._n_late), ("late written", s._n_late_written)):
        REACH[k] += x
    return None


def same_kind(d, e):
    """A shrink step has to keep the difference of the same kind, so it doesn't slide to an unrelated one."""
    return e is not None and e["what"] == d["what"]


def shrink(script, specs, level, d):
    """(script, finished): the smallest found by --shrink-seconds."""
    keep = list(script[:d["op"] + 1])
    chunk = max(1, len(keep) // 2)
    end = time.time() + ARGS.shrink_seconds
    while True:
        i = 0
        while i < len(keep):
            if time.time() > end:
                return keep, False
            cand = keep[:i] + keep[i + chunk:]
            if cand and same_kind(d, run_session(cand, specs, level)):
                keep = cand
            else:
                i += chunk
        if chunk == 1:
            return keep, True
        chunk //= 2


# ---- Script generation.

BLOCK = ((1, 2), (0, 3), (1, 4, 6), (2, 5))
CHAIN4 = ((1, 2), (3, 4), (5, 6))                   # v0 -> v1 -> v2 -> v3: implications for block reasons
CHAIN3 = ((1, 2), (3, 4))
EQ2 = ((1, 2), (0, 3))
OR2 = ((0, 2),)
XOR3 = ((0, 2, 4), (0, 3, 5), (1, 2, 5), (1, 3, 4))
WIDE = ((0, 2, 4, 6, 8, 10, 12, 14, 16, 18),)
BLOCKS = [(BLOCK, 4), (CHAIN4, 4), (CHAIN4, 4), (CHAIN3, 3), (EQ2, 2), (OR2, 2), (XOR3, 3), (WIDE, 10)]


def php(p, h, at):
    v = lambda i, j: at + i * h + j + 1
    cl = [[v(i, j) for j in range(h)] for i in range(p)]
    cl += [[-v(i, j), -v(k, j)] for j in range(h) for i, k in itertools.combinations(range(p), 2)]
    return cl


def theory_spec(r, atoms):
    if not atoms:
        return {}
    lit = lambda: r.choice((1, -1)) * r.choice(atoms)
    lits = lambda lo, hi: list({lit() for _ in range(r.randint(lo, hi))})
    sp = {"model": r.random() < .7}
    if r.random() < .8:
        sp["conflicts"] = [tuple(lits(1, 3)) for _ in range(r.randint(1, 4 + len(atoms) // 3))]
    if r.random() < .6:
        sp["finals"] = [tuple(lits(1, 3)) for _ in range(r.randint(1, 4))]
    if r.random() < .75:
        sp["implies"] = []
        for _ in range(r.randint(1, 3 + len(atoms) // 3)):
            prem, x = tuple(lits(1, 3)), lit()
            if x in prem or -x in prem:
                continue
            sp["implies"].append((prem, x, r.random() < .3))
        sp["gen"] = r.random() < .5
    if r.random() < .4:
        sp["decide"] = [r.choice(atoms) for _ in range(r.randint(1, 5))]
    k = r.random()
    if k < .10:
        hook = r.choice(("assert_lit", "check", "push", "pop", "prop", "decide", "reg"))
        sp["raise_at"] = {{"assert_lit": "assert"}.get(hook, hook): r.randint(1, 40)}
    elif k < .13:
        sp["bad_at"] = r.randint(1, 30)
    return sp


def gen_session(seed):
    """(script, theory specs) for one session. Mixes a formula hard enough to restart and reduce with random calls and
    the recipes for each path the replays and step 1 didn't reach."""
    r = random.Random(seed)
    ops = []
    add = lambda name, *args: ops.append((name, args))
    size = r.random()
    n = r.randint(3, 12) if size < .35 else r.randint(12, 45)
    use_blocks = r.random() < .6
    nth = r.choice((0, 0, 1, 1, 1, 2))
    # Tunables, so that small scripts restart, reduce and rescale; some sessions keep the defaults.
    if r.random() < .75:
        add("_set", "_restart_first", r.choice((1, 2, 3, 5, 10)))
        add("_set", "_learnt_size_min", r.choice((1, 2, 3, 5, 10, 30)))
    if r.random() < .15:
        add("_set", "_cla_inc", r.choice((1e19, 9.99e19, 1e20, 1.5e20)))
    if r.random() < .10:
        add("_set", "_var_inc", r.choice((1e99, 9.9e99, 1e100, 1.5e100)))
    blocks, bsize = [], 0
    if use_blocks:
        block, bsize = r.choice(BLOCKS)
        add("set_rule_block", block, bsize)
        nb = r.randint(1, max(1, min(6, n // (bsize + 1))))
        at = r.randint(1, 2)
        for _ in range(nb):
            blocks.append(at)
            at += bsize + r.randint(0, 2)
        n = max(n, at)
        for b in blocks:
            if r.random() < .8:
                add("register_block", b, r.choice((0, 0, 3, 12, (1 << (2 * bsize)) - 1)))
    lit = lambda: r.choice((1, -1)) * r.randint(1, n)
    def blit():
        if blocks and r.random() < .5:
            return r.choice((1, -1)) * (r.choice(blocks) + r.randrange(bsize))
        return lit()
    lits = lambda lo, hi: [blit() for _ in range(r.randint(lo, hi))]
    # Theories.
    specs = []
    atoms_of = []
    for _ in range(nth):
        pool = list(range(1, n + 1))
        atoms = sorted(r.sample(pool, r.randint(1, max(1, min(len(pool), 12)))))
        atoms_of.append(atoms)
        specs.append(theory_spec(r, atoms))
    held = lambda: r.choice((None, None, 0, 1, 2))

    def attach(i):
        add("attach_theory", f"T{i}")
        for v in atoms_of[i]:
            add("register_atom", f"T{i}", v, f"a{v}", r.random() > .25)
    # `decide` is only asked once nothing else is left to decide: make some of its variables inert, so it has work.
    for sp in specs:
        if r.random() < .6:
            for v in sp.get("decide", ()):
                if not any(b <= v < b + bsize for b in blocks):
                    add("set_inert", v)
    early = [i for i in range(nth) if r.random() < .7]
    for i in early:
        attach(i)
    # The formula: nothing, random 3-SAT near the threshold, or pigeonholes (with blocks and theories on top of them).
    k = r.random()
    if k < .35:
        ratio = r.uniform(3.6, 5.2)
        n3 = max(n, r.randint(20, 60)) if size > .35 else n
        n = n3
        formula = [[r.choice((1, -1)) * v for v in r.sample(range(1, n + 1), min(3, n))] for _ in range(int(n * ratio))]
    elif k < .55:
        p = r.randint(3, 6)
        formula = php(p, p - r.randint(0, 1), r.randint(0, 3))
        n = max(n, max(abs(x) for c in formula for x in c))
    else:
        formula = [lits(1 if r.random() < .1 else 2, 4) for _ in range(int(n * r.uniform(1.5, 5.5)))]
        formula = [c for c in formula if c]
    fuzz_ops(r, ops, formula, lambda: n, blit, lits, held)
    for i in range(nth):
        if i not in early:
            attach(i)
            if r.random() < .5:
                add("solve", lits(0, 2))
    recipes = [rc_ring_none, rc_final, rc_fill_past_end, rc_two_pending, rc_after_raise, rc_settle]
    for rc in r.sample(recipes, r.randint(0, 3)):
        n = rc(r, ops, n, blocks, bsize, lits, held, nth)
    add("solve")
    add("solve", lits(1, 3))
    if r.random() < .5:
        add("model")
    if nth and r.random() < .5:
        add("theory_models")
    add("stats")
    return ops, specs


def fuzz_ops(r, ops, formula, nf, blit, lits, held):
    """The formula, with random calls in between. `model` is rare, since it completes stored models."""
    add = lambda name, *args: ops.append((name, args))
    rate = r.choice((.03, .1, .25))
    for c in formula:
        add("add_clause", c)
        if r.random() > rate:
            continue
        k = r.randrange(20)
        if k <= 2:
            add("solve", lits(0, 3))
        elif k == 3:
            add("implied", lits(0, 3), held())
        elif k == 4:
            add("entails", blit(), lits(0, 3), held())
        elif k == 5:
            add("consistent", lits(0, 3), held())
        elif k == 6:
            add("entails_all", lits(1, 3), lits(0, 2), held())
        elif k == 7:
            add("release", r.randint(0, 2))
        elif k == 8:
            add("mention", lits(1, 3))
        elif k == 9:
            add("propagate")
        elif k == 10:
            add("set_inert", r.randint(1, nf()))
        elif k == 11:
            add("value", blit())
        elif k == 12:
            add("ensure_vars", nf() + r.randint(0, 3))
        elif k == 13:
            add("add_clauses", [lits(2, 3), lits(1, 2)])
        elif k == 14:
            add("root_trail")
        elif k == 15 and r.random() < .3:
            add("model")
        elif k == 16:
            add("new_var")
        elif k == 17:
            add("add_pattern", r.choice(([[0, 2], [1, 3]], [[0, 3], [1, 2]], [[1, 3], [0, 2]])), r.randint(1, nf()), 2)
        elif k == 18:
            add("ensure_vars", nf())
            add("add_internal", [[2 * abs(x) + (x < 0) for x in lits(1, 3)] for _ in range(r.randint(1, 3))])
        elif k == 19:
            add("mention_blocks", [(abs(blit()), r.choice((3, 12, 15, 0xff))) for _ in range(r.randint(1, 3))])


def rc_ring_none(r, ops, n, blocks, bsize, lits, held, nth):
    """A model stored with an inert or lazy variable unset, then a clause on it, so the ring has to read the None."""
    add = lambda name, *args: ops.append((name, args))
    v = r.randint(1, n)
    add("set_inert", v)
    add("solve", lits(0, 2))
    add("add_clause", [r.choice((1, -1)) * v, r.choice((1, -1)) * r.randint(1, n)])
    add("solve", lits(0, 1))
    if blocks:
        b = r.choice(blocks) + r.randrange(bsize)
        add("solve", lits(0, 1))
        add("add_clause", [r.choice((1, -1)) * b] + lits(0, 1))
        add("mention", [b])
        add("solve", lits(0, 1))
    return n


def rc_final(r, ops, n, blocks, bsize, lits, held, nth):
    """Assumptions whose later literal is false under the earlier ones through a block implication."""
    if not blocks:
        return n
    add = lambda name, *args: ops.append((name, args))
    b = r.choice(blocks)
    k = r.randrange(bsize)
    j = r.randrange(bsize)
    mid = lits(0, 2)
    add("solve", [b + k] + mid + [-(b + j)])
    add("solve", [-(b + j)] + mid + [b + k])
    add("solve", [r.choice((1, -1)) * (b + k), r.choice((1, -1)) * (b + j)] + mid)
    if r.random() < .5:
        add("implied", [b + k], 1)
        add("solve", [b + k, -(b + j)])
    return n


def rc_fill_past_end(r, ops, n, blocks, bsize, lits, held, nth):
    """A stored model ends at an inert variable; a block then starts there, past the model's end: `_fill` has to grow
    the stored list. Needs the rule table set and room at the top."""
    if not blocks or bsize < 2:
        return n
    add = lambda name, *args: ops.append((name, args))
    top = n + r.randint(1, 3)
    add("ensure_vars", top)
    add("set_inert", top)
    add("solve", lits(0, 1))
    add("register_block", top, r.choice((0, 0, 3)))
    add("add_clause", [r.choice((1, -1)) * top, r.choice((1, -1)) * r.randint(1, n)])
    add("solve", [r.choice((1, -1)) * top] if r.random() < .5 else lits(0, 1))
    add("solve", lits(0, 1))
    if r.random() < .4:
        add("model")
    return top + bsize - 1


def rc_two_pending(r, ops, n, blocks, bsize, lits, held, nth):
    """Levels held, then one `mention` of variables in two or more blocks: the order `_rb_mentioned` runs them in."""
    if len(blocks) < 2:
        return n
    add = lambda name, *args: ops.append((name, args))
    bs = r.sample(blocks, min(len(blocks), r.randint(2, 3)))
    add("implied", [b for b in bs], r.choice((None, len(bs))))
    add("mention", [b + r.randrange(bsize) for b in reversed(bs)])
    add("implied", [b for b in bs], None)
    add("mention", [r.choice((1, -1)) * (b + r.randrange(bsize)) for b in bs])
    add("solve", lits(0, 2))
    return n


def rc_after_raise(r, ops, n, blocks, bsize, lits, held, nth):
    """A theory that raised mid-search leaves the solver where it stood; keep using it, with new clauses and solves."""
    if not nth:
        return n
    add = lambda name, *args: ops.append((name, args))
    for _ in range(r.randint(2, 5)):
        add("solve", lits(0, 2))
        add("add_clause", lits(1, 3))
    return n


def rc_settle(r, ops, n, blocks, bsize, lits, held, nth):
    """A block registered over variables that already have values, at root or at held levels: `_rb_settle`."""
    if not blocks or bsize < 2:
        return n
    add = lambda name, *args: ops.append((name, args))
    top = n + r.randint(1, 3)
    x = r.choice((1, -1)) * (top + r.randrange(bsize))
    if r.random() < .5:
        add("add_clause", [x])
    else:
        add("implied", [x], 1)
    add("register_block", top, r.choice((0, 3)))
    add("implied", [r.choice((1, -1)) * (top + r.randrange(bsize))], r.choice((None, 1)))
    add("solve", lits(0, 2))
    return top + bsize - 1


def fixed_sessions():
    """Scripts for the paths that random mixes reach too rarely, at the real tunables where the path needs them."""
    out = []
    # Real tunables: restarts and reductions the way the engine sees them.
    for seed, (n, ratio) in enumerate(((180, 4.26), (220, 4.2))):
        r = random.Random(seed + 7)
        cl = [[r.choice((1, -1)) * v for v in r.sample(range(1, n + 1), 3)] for _ in range(int(n * ratio))]
        out.append(([("add_clause", (c,)) for c in cl] + [("solve", ()), ("stats", ())], []))
    out.append(([("add_clause", (c,)) for c in php(8, 7, 0)] + [("solve", ()), ("stats", ())], []))
    # A theory conflict in every branch of a pigeonhole, at real tunables, with an implied and a unit-reason literal.
    atoms = list(range(1, 21))
    sp = {"model": True, "conflicts": [(1, 7), (2, 8), (3, 9)], "implies": [((6,), 12, True), ((5,), 11, False)],
          "gen": True, "decide": [19, 18]}
    out.append(([("attach_theory", ("T0",))] + [("register_atom", ("T0", v, f"a{v}")) for v in atoms]
                + [("add_clause", (c,)) for c in php(5, 4, 0)] + [("solve", ([6],)), ("solve", ()), ("stats", ())], [sp]))
    # A chain block: analyze_final on a block reason, by hand, and the `_cla_inc` rescale at a new learnt clause.
    final = [("set_rule_block", (CHAIN4, 4)), ("register_block", (1,)), ("solve", ([1, -4],)), ("solve", ([1, 9, -4],)),
             ("conflict", ()), ("add_clause", ([9, 10],)), ("solve", ([-9, 1, -3],))]
    out.append((final, []))
    # A None that `_fill` can't complete. `push_level` raises right after `_pick_branch` popped variable 7, so 7 is off
    # the heap for good. The next solve has a conflict before the index scan reaches 7, so VSIDS never offers it, and
    # the model holds None for a variable that is neither lazy nor in a block. The clause [7, 6] is then "satisfied" in
    # the ring only by that None: the ring-None mutant's one path. Only a caller who keeps a solver after a hook raised.
    none = [("attach_theory", ("T0",)), ("register_atom", ("T0", 8, "a8")), ("add_clause", ([3, 4],)),
            ("add_clause", ([3, -4],)), ("ensure_vars", (8,)), ("solve", ()), ("add_clause", ([1, 2],)),
            ("add_clause", ([1, -2],)), ("solve", ()), ("add_clause", ([7, 6],)), ("solve", ()), ("model", ()),
            ("stats", ())]
    out.append((none, [{"model": True, "raise_at": {"push": 5}}]))
    return out


def step1_sessions():
    import check_step1
    out = [(s, []) for s in check_step1.HAND.values()]
    rng = random.Random(20261107)
    return out + [(check_step1.random_script(rng), []) for _ in range(ARGS.sessions)]


# ---- Reentry: a hook that calls back into its solver.

REENTRY_CALLS = {"value": (1,), "nvars": (), "stats": (), "new_var": (), "add_clause": ([1, 2],), "propagate": ()}
REENTRY_HOOKS = ("assert_lit", "check", "push_level", "pop_level", "propagate", "decide", "register_atom")


def reentry():
    """Each hook calls each solver method once, catching what it raises. Lists where the backends part."""
    def session(cls, hook, call):
        got = []

        class T(StubBoth):
            done = False

            def __init__(self):
                super().__init__({"decide": [], "implies": [], "model": True}, [], "T0")

            def _hit(self, h, *a):
                if {"assert": "assert_lit", "prop": "propagate", "reg": "register_atom", "push": "push_level",
                    "pop": "pop_level"}.get(h, h) == hook and not self.done:
                    self.done = True
                    try:
                        got.append(("ok", getattr(self.solver, call)(*REENTRY_CALLS[call])))
                    except Exception as e:
                        got.append(("raise", type(e).__name__, str(e)))
        s = cls()
        t = T()
        t.solver = s
        s.attach_theory(t)
        s.register_atom(t, 1, "a1")
        s.register_atom(t, 2, "a2")
        s.add_clause([1, 2, 3])
        res = []
        for a in ([], [1], [-1, -2, -3]):
            try:
                res.append(s.solve(a))
            except Exception as e:
                res.append(("raise", type(e).__name__, str(e)))
        t.solver = None
        return got, res, s.stats()
    same, differ = 0, []
    for hook in REENTRY_HOOKS:
        for call in REENTRY_CALLS:
            a, b = session(pysolver.Solver, hook, call), session(RustSolver, hook, call)
            if a == b:
                same += 1
            else:
                differ.append((hook, call, a[0][:1], b[0][:1]))
    return same, differ


# ---- Line coverage of solver.py, by sys.monitoring.

def coverage_start():
    seen = set()
    mon = sys.monitoring
    tool = mon.COVERAGE_ID
    mon.use_tool_id(tool, "fuzz")
    path = pysolver.__file__

    def line(code, ln):
        if code.co_filename == path:
            seen.add(ln)
        return mon.DISABLE
    mon.register_callback(tool, mon.events.LINE, line)
    mon.set_events(tool, mon.events.LINE)
    return seen


def executable_lines():
    src = open(pysolver.__file__).read()
    out = set()

    def walk(code):
        for _, _, ln in code.co_lines():
            if ln:
                out.add(ln)
        for c in code.co_consts:
            if hasattr(c, "co_lines"):
                walk(c)
    walk(compile(src, pysolver.__file__, "exec"))
    return out


def ranges(xs):
    xs = sorted(xs)
    out = []
    for x in xs:
        if out and out[-1][1] == x - 1:
            out[-1][1] = x
        else:
            out.append([x, x])
    return ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in out)


# ---- Known differences: each listed one, run on both solvers.

def known_scripts():
    """name, script, theory specs: each smallest found. The first three are exempted in `known_difference`. The fourth
    isn't, so it stays a mismatch: the generator makes no unit patterns, which breaks `add_pattern`'s contract."""
    pop = {"raise_at": {"pop": 29}, "decide": [31], "conflicts": [(-31,), (-31, 31)], "finals": [(-31, 31)], "model": True}
    return [
        ("pop_level raised in a backtrack, then a backtrack to that level",
         [("attach_theory", ("T0",)), ("register_atom", ("T0", 31, "a31", False)), ("entails", (24, [], 0)),
          ("add_clause", ([-13, -18],))], [pop]),
        ("mention_blocks with a base past the last variable",
         [("set_rule_block", (WIDE, 10)), ("mention_blocks", ([(44, 3)],))], []),
        ("mention_blocks with a range past the last variable",
         [("ensure_vars", (12,)), ("set_rule_block", (BLOCK, 4)), ("mention_blocks", ([(11, 255)],))], []),
        ("add_pattern with a one-literal clause",
         [("add_pattern", ([[1], [0, 2]], 29, 2))], []),
    ]


def selftest_known():
    """The exemption refuses each near miss: another line, another list length, a cause that doesn't hold."""
    class T:
        pop_raised = True

    class Fresh:
        pop_raised = False

    class S:
        _rb_ulim, _trail_lim = [], [0]

        @staticmethod
        def nvars():
            return 5

    class Fake:
        s, ths = S, [T]

        def __init__(self, exc=None):
            self.exc = exc

    class NoPop(Fake):
        ths = [Fresh]

    def at_line(fn, arg, line):
        """An IndexError whose innermost frame looks like `fn` at the given line of solver.py."""
        src = "\n" * (line - 2) + f"def {fn}({arg}):\n    [][{arg}]\n"
        ns = {}
        exec(compile(src, pysolver.__file__, "exec"), ns)
        try:
            ns[fn](0)
        except IndexError as e:
            return e
    lines = open(pysolver.__file__).read().splitlines()
    site = lines.index("        k = self._rb_ulim[lvl]") + 1
    ra = ("raise", "IndexError", "list index out of range")
    panic = ("PANIC", "PanicException", "index out of bounds: the len is 0 but the index is 0")
    good = lambda: Fake(at_line("_backtrack", "lvl", site))
    return {
        "the site itself is exempted": known_difference(good(), Fake(), ra, panic) is not None,
        "another line of solver.py": known_difference(Fake(at_line("_backtrack", "lvl", site + 1)), Fake(), ra, panic) is None,
        "another list length": known_difference(good(), Fake(), ra, ("PANIC", "PanicException", "index out of bounds: the len is 3 but the index is 0")) is None,
        "another index": known_difference(good(), Fake(), ra, ("PANIC", "PanicException", "index out of bounds: the len is 0 but the index is 1")) is None,
        "no pop_level raise on Rust's stub": known_difference(good(), NoPop(), ra, panic) is None,
        "no pop_level raise on Python's stub": known_difference(NoPop(good().exc), Fake(), ra, panic) is None,
    }


def known():
    """Prints each known difference as it stands, and exits 1 if a self-test fails."""
    bad = 0
    for name, ok in selftest_known().items():
        print(f"exemption self-test: {name}: {'ok' if ok else 'FAILED'}")
        bad += not ok
    for name, script, specs in known_scripts():
        a, b = Side(Probe, specs), Side(RustSolver, specs)
        print(f"{name}\n  theories {specs}\n  script {script}")
        for op in script:
            ra, rb = a.apply(op), b.apply(op)
            k = known_difference(a, b, ra, rb)
            mark = f"exempted ({k})" if k else ("same" if ra == rb else "DIFFERS")
            print(f"  {op[0]}: {mark}: py {ra}, rs {rb}")
        d = state.diff(state.dump_py(a.s), b.s.dump())
        print(f"  state after: {'same' if not d else 'differs at ' + d[0]}")
    same, differ = reentry()
    print(f"solver call inside a hook (hook x method): {same} same, {len(differ)} differ. Smallest: a theory whose "
          "assert_lit calls solver.nvars(), then solve([1]) on a registered atom")
    for x in differ[:2]:
        print("  ", x)
    return 1 if bad else 0


def loaded():
    """The solver actually in this process: `mutate_slice.py` checks it, as the first table was void without this."""
    return dict(so=sa_solver.__file__, so_sha=hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest())


def main():
    if ARGS.known:
        return known()
    seen = coverage_start() if ARGS.reach else None
    t0 = time.time()
    if ARGS.one is not None:
        sessions = [(ARGS.one, gen_session(ARGS.one))]
    elif ARGS.corpus == "step1":
        sessions = list(enumerate(step1_sessions()))
    else:
        sessions = [(f"fixed {i}", x) for i, x in enumerate(fixed_sessions())] if not ARGS.no_fixed else []
        sessions = itertools.chain(sessions, ((ARGS.seed + i, gen_session(ARGS.seed + i)) for i in range(ARGS.sessions)))
    if ARGS.label is not None:
        sessions = itertools.islice((x for x in sessions if str(x[0]) == ARGS.label), 1)
    for label, (script, specs) in sessions:
        if ARGS.progress:
            with open(ARGS.progress, "w") as f:
                f.write(str(label))
        d = run_session(script, specs, ARGS.level)
        if d:
            small, finished = script[:d["op"] + 1], False
            if ARGS.json:            # first, so a run killed while shrinking still counts as found
                print(json.dumps(dict(caught=True, session=str(label), script_len=len(small), shrunk=False, **loaded(), **d)),
                      flush=True)
            if not ARGS.no_shrink:
                small, finished = shrink(script, specs, ARGS.level, d)
            if ARGS.json:
                print(json.dumps(dict(caught=True, session=str(label), specs=repr(specs), script_len=len(small),
                                      shrunk=finished, script=repr(small), **loaded(), **d)), flush=True)
            else:
                print(f"MISMATCH session {label} op {d['op']}: {d['what']}\n  py {d['py']}\n  rs {d['rs']}")
                print(f"smallest script ({len(small)} calls), theories {specs}:\n  {small}")
            return 1
        if REACH["sessions"] % 200 == 0:
            gc.collect()
    dt = time.time() - t0
    reach = dict(sorted(REACH.items()))
    if ARGS.json:
        print(json.dumps(dict(caught=False, seconds=round(dt, 1), reach=reach, **loaded())), flush=True)
    else:
        print(f"clean: {ARGS.corpus} {ARGS.level}, {REACH['sessions']} sessions, {REACH['calls']} calls, {dt:.0f} s")
        for k, v in reach.items():
            print(f"  {k}: {v}")
    if ARGS.reach:
        sys.monitoring.set_events(sys.monitoring.COVERAGE_ID, 0)
        missing = executable_lines() - seen
        total = len(executable_lines())
        print(f"solver.py lines run: {total - len(missing)} of {total}; never run:\n  {ranges(missing)}")
        same, differ = reentry()
        print(f"reentry (hook x method): {same} same, {len(differ)} differ")
        for x in differ:
            print("  ", x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
