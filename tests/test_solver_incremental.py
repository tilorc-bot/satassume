"""Differential test of the incremental ``Solver`` against fresh solvers.

One long-lived solver is driven through a random sequence of operations
(clause insertion in all its forms, ``implied``, ``entails``, ``solve``
under assumptions, ``propagate``, ``value``/``root_trail``), and every
answer is checked against fresh solvers of the *same* code built from the
same clauses.  The fresh solver is the oracle: it never holds state between
calls, so anything the long-lived solver keeps between public calls (the
propagation cache, held assumption levels, clauses attached while levels
are held, learnt clauses and their deletion, the model witness) cannot
change an answer without being caught here.  This is the test form of
``tools/solver_diff_fuzz.py`` (kept as a tool for cross-version runs).

Operation mix
-------------

Every operation is a function ``fn(h)`` on a :class:`Harness`, registered
with ``@op(weight)`` into ``OPS``.  Adding an operation is adding one such
function; a variant (a theory attached, say) builds its own list
``OPS + [...]`` and passes a ``setup`` hook that is applied to the live
solver and to every oracle solver, then calls :func:`run_seed` with them.
Adding or reweighting operations changes the random stream, so seeds are
not stable across versions of this file; every failure prints its seed
and the operation log, which is the reproduction.

Seed count
----------

``SOLVER_FUZZ_SEEDS`` (default 500) seeds starting at ``SOLVER_FUZZ_SEED0``
(default 0), split into ``CHUNKS`` test items.  For a long run by hand::

    SOLVER_FUZZ_SEEDS=4000 pytest -q tests/test_solver_incremental.py
    python tests/test_solver_incremental.py 0 4000     # same, with counters
    python tests/test_solver_incremental.py 0 2000 block    # rule-block mode
    python tests/test_solver_incremental.py 0 2000 theory   # ... with a theory

(each command under about 110 s; split longer runs by seed range).

Rule-block mode
---------------

The same harness with ``Solver.set_rule_block``: the live solver runs its
blocks as the propagator (``register_block``; even seeds) or mixes them
with ``add_pattern`` clauses (odd seeds), the oracle always gets them as
plain clauses.  The block is the engine's ``RULE_INTERNAL`` or a small
random one; blocks are registered on fresh variables that are sometimes
already constrained or assigned (at root or at a held level), sometimes
while levels are held.  The theory variant attaches a ``ForbidTheory``
whose atoms are variables of the first block.  See ``register_block``.

Per seed, about 30% of instances are "hard" (15 to 40 variables and a
burst of random 3-clauses near the satisfiability threshold) with small
learnt-clause and restart budgets on the live solver, so that conflicts,
learnt-clause deletion and restarts happen at this size; the rest are the
small, under-constrained instances of the original fuzz, where propagation
answers most queries and held levels survive many calls.
"""
from __future__ import annotations

import os
import random
import sys
from collections.abc import Callable

import pytest

from satassume.rules import NPRED, RULE_INTERNAL
from satassume.solver import Solver
from theory_harness import ForbidTheory, Recorder, check_protocol

SEEDS = int(os.environ.get("SOLVER_FUZZ_SEEDS", "500"))
SEED0 = int(os.environ.get("SOLVER_FUZZ_SEED0", "0"))
CHUNKS = 6


class Mismatch(AssertionError):
    """The long-lived solver disagreed with a fresh one (or with itself)."""


# ----------------------------------------------------------------------
# Harness
# ----------------------------------------------------------------------

OPS: list[tuple[str, int, Callable]] = []


def op(weight: int):
    """Register the decorated ``fn(h)`` as an operation with ``weight``."""
    def deco(fn):
        OPS.append((fn.__name__, weight, fn))
        return fn
    return deco


class Harness:
    """State of one seed: the live solver, the clauses it was given (in
    external literals, as the oracle replays them), the current assumption
    set ``A``, the operation log and coverage counters."""

    def __init__(self, seed: int, ops=None, setup: Callable | None = None,
                 hard: bool | None = None, nv: int | None = None,
                 block: str | None = None):
        self.seed = seed
        self.rng = rng = random.Random(seed)
        self.ops = list(ops if ops is not None else OPS)
        self.setup = setup
        self.hard = (rng.random() < 0.3) if hard is None else hard
        if nv is None:
            nv = rng.randint(20, 80) if self.hard else rng.randint(3, 20)
        # Rule-block mode (see register_block below): None, "prop" (every
        # block of the live solver is a propagator) or "mixed" (some are
        # add_pattern clauses).  The oracle always gets the clauses.
        self.block_mode = block
        self.pos = 0.5              # probability of a positive literal in rclause
        if block:
            if rng.random() < 0.5:
                self.block, self.bk = RULE_INTERNAL, NPRED
                # Most rules exclude predicates pairwise: random positive
                # literals over them make nearly every problem UNSAT.
                self.pos = 0.3
            else:
                self.block, self.bk = random_block(rng)
            nv = max(nv, self.bk)
        self.nv = nv
        self.clauses: list[list[int]] = []
        self.regs: list[tuple[int, int]] = []   # (theory index, var) registered by ops
        self.A: list[int] | None = None
        self.A_bad = False          # A was found inconsistent
        self.last_trail: list[int] | None = None   # last implied() result
        self.log: list[tuple] = []
        self.step = -1
        self.after_prop = True      # root propagation is complete
        self.verified: set[int] = set()   # root literals proven entailed
        self.counts: dict[str, int] = {}
        self.solver = s = BlockSolver() if block else Solver()
        if self.hard:
            # Small budgets so that learnt-clause deletion and restarts
            # happen on instances this small (both are tunables of Solver).
            s._learnt_size_min = rng.choice([1, 2, 4, 8])
            s._restart_first = rng.choice([1, 2, 4, 100])
        if setup is not None:
            setup(s)
        if block:
            s.set_rule_block(self.block, self.bk)
        s.ensure_vars(self.nv)
        if block:
            self.add_block(1, True)     # variables 1..bk (theory atoms live there)
        if self.hard:
            # (a lower ratio with blocks: they constrain the problem too)
            ratio = (rng.uniform(4.0, 4.5) if not block else rng.uniform(3.4, 4.2)
                     if self.pos == 0.5 else rng.uniform(1.0, 2.0))
            burst = [self.rclause(3) for _ in range(int(ratio * self.nv))]
            self.record("add_clauses", burst)
            self.clauses.extend(burst)
            r = s.add_clauses(burst)
            self.check(r or not self.sat([]), "add_clauses False but SAT")
            self.after_prop = False

    # -- oracle ---------------------------------------------------------

    def fresh(self) -> Solver:
        """A fresh solver over the same clauses, propagated at root."""
        o = Solver()
        if self.setup is not None:
            self.setup(o)
        o.ensure_vars(self.nv)
        for ti, v in self.regs:
            o.register_atom(o.fuzz_theories[ti], v, None)
        for c in self.clauses:
            o.add_clause(c)
        o.propagate()
        return o

    def sat(self, assumptions) -> bool:
        return self.fresh().solve(list(assumptions))

    def entailed(self, assumptions, x: int) -> bool:
        return not self.fresh().solve(list(assumptions) + [-x])

    # -- bookkeeping ----------------------------------------------------

    def count(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    def record(self, *event) -> None:
        self.log.append(event)

    def rclause(self, k: int) -> list[int]:
        rng = self.rng
        vs = rng.sample(range(1, self.nv + 1), min(k, self.nv))
        return [v if rng.random() < self.pos else -v for v in vs]

    def rlit(self) -> int:
        return self.rng.choice([1, -1]) * self.rng.randint(1, self.nv)

    def check(self, cond, what: str, *detail) -> None:
        if cond:
            return
        lines = [f"seed {self.seed}, step {self.step}: {what}"
                 + (f" {detail}" if detail else ""),
                 f"reproduce: SOLVER_FUZZ_SEED0={self.seed} SOLVER_FUZZ_SEEDS=1 "
                 f"pytest -q {os.path.relpath(__file__)}",
                 f"nvars {self.nv}, hard {self.hard}, operations:"]
        lines += [f"  {e}" for e in self.log]
        raise Mismatch("\n".join(lines))

    # -- driving --------------------------------------------------------

    def run(self, steps: int | None = None) -> None:
        rng = self.rng
        if steps is None:
            steps = rng.randint(30, 120) if self.hard else rng.randint(5, min(80, 8 * self.nv))
        names = [o[0] for o in self.ops]
        weights = [o[1] for o in self.ops]
        fns = [o[2] for o in self.ops]
        dead = 0
        for self.step in range(steps):
            i = rng.choices(range(len(fns)), weights)[0]
            self.count(names[i])
            fns[i](self)
            self.check_root_values()
            if not self.solver._ok:
                # Root-UNSAT: a few more steps check the dead solver, then
                # the seed ends (every answer is trivial from here on).
                self.count("steps_dead")
                dead += 1
                if dead > 3:
                    break
        if not self.solver._ok:
            self.count("seeds_ending_unsat")

    def check_root_values(self) -> None:
        """``value``: sound always; complete with respect to root
        propagation right after ``propagate()``.  Root assignments only
        grow, so each fixed literal is verified once."""
        s = self.solver
        if not s._ok:
            return
        ref = self.fresh() if self.after_prop else None
        if ref is None:
            self.count("value_completeness_unchecked")
        for v in range(1, self.nv + 1):
            x = s.value(v)
            if x is not None:
                lit = v if x else -v
                if lit not in self.verified:
                    self.check(self.entailed([], lit), "value unsound", lit)
                    self.verified.add(lit)
            if ref is not None and ref._ok and ref.value(v) is not None:
                self.check(x == ref.value(v), "value incomplete", v, x, ref.value(v))

    def add_block(self, base: int, prop: bool) -> bool:
        """The rule block on ``base..``: registered as a propagator
        (``prop``) or added as ``add_pattern`` clauses on the live solver,
        always as clauses for the oracle."""
        lo = 2 * base
        self.clauses.extend([Solver._to_ext(l + lo) for l in c] for c in self.block)
        s = self.solver
        if prop:
            self.record("register_block", base)
            r = s.register_block(base)
            self.count("blocks_registered")
        else:
            self.record("add_pattern_block", base)
            r = s.add_pattern(self.block, base, self.bk)
            self.after_prop = False
        self.check(r or not self.sat([]), "block False but SAT", base, prop)
        return r

    def held_now(self, lits) -> bool:
        """Will the next call with ``lits`` be answered from held levels?"""
        h = self.solver._held
        return h is not None and h == [Solver._to_int(x) for x in lits]


def run_seed(seed: int, ops=None, setup=None, steps=None, **kw) -> dict[str, int]:
    """Drive one seed; raise :class:`Mismatch` on the first disagreement.
    Returns the coverage counters."""
    h = Harness(seed, ops, setup, **kw)
    h.run(steps)
    st = h.solver.stats()
    rec = getattr(h.solver, "recorder", None)
    if rec is not None:
        try:
            check_protocol(rec)
        except AssertionError as e:
            h.check(False, f"theory protocol: {e}")
    if h.block_mode:
        h.count("block_seeds")
        h.count("block_conflicts", st["conflicts"])
        h.count("block_hard_conflicts", st["conflicts"] if h.hard else 0)
        h.count("rb_reasons_read", h.solver.n_rb_reasons)
    h.count("seeds")
    h.count("witness_hits", st["witness_hits"])
    h.count("conflicts", st["conflicts"])
    h.count("restarts", st["restarts"])
    h.count("reductions", h.solver._n_reductions)
    h.count("hard_seeds", int(h.hard))
    return h.counts


def _merge(total: dict[str, int], counts: dict[str, int]) -> dict[str, int]:
    for k, v in counts.items():
        total[k] = total.get(k, 0) + v
    return total


def run_seeds(seed0: int, n: int, total=None, **kw) -> dict[str, int]:
    total = {} if total is None else total
    for seed in range(seed0, seed0 + n):
        _merge(total, run_seed(seed, **kw))
    return total


# ----------------------------------------------------------------------
# Operations: clause insertion (while levels may be held)
# ----------------------------------------------------------------------

def _note_add(h: Harness) -> None:
    if h.solver._trail_lim:
        h.count("adds_while_held")


@op(26)
def add_clause(h: Harness) -> None:
    c = h.rclause(h.rng.choice([1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4]))
    h.record("add_clause", c)
    _note_add(h)
    h.clauses.append(c)
    r = h.solver.add_clause(c)
    h.check(r or not h.sat([]), "add_clause False but SAT")
    # A clause unit at root is propagated at once, but without the theories
    # (they hear of it at the next propagate or search).
    h.after_prop = len(c) != 1 and h.after_prop and not h.solver._theories


@op(8)
def add_clauses(h: Harness) -> None:
    cs = [h.rclause(h.rng.choice([1, 2, 3, 3, 3, 4, 4])) for _ in range(h.rng.randint(1, 4))]
    h.record("add_clauses", cs)
    _note_add(h)
    h.clauses.extend(cs)
    r = h.solver.add_clauses(cs)
    h.check(r or not h.sat([]), "add_clauses False but SAT")
    h.after_prop = False


@op(8)
def add_internal(h: Harness) -> None:
    ext = [h.rclause(h.rng.choice([1, 2, 3, 3, 3, 4, 4])) for _ in range(h.rng.randint(1, 4))]
    cs = [[Solver._to_int(x) for x in c] for c in ext]
    h.record("add_internal", ext)
    _note_add(h)
    h.clauses.extend(ext)
    r = h.solver.add_internal(cs)
    h.check(r or not h.sat([]), "add_internal False but SAT")
    h.after_prop = False


@op(5)
def add_pattern(h: Harness) -> None:
    """A 3-variable template (three binary clauses, internal encoding
    relative to variable 0) instantiated on fresh variables, then linked
    to the old ones by one clause."""
    rng = h.rng
    k = 3
    base = h.nv + 1
    h.nv += k
    pat = []
    for _ in range(3):
        u, w = rng.sample(range(k), 2)
        pat.append((2 * u + rng.randint(0, 1), 2 * w + rng.randint(0, 1)))
    pat = tuple(pat)
    h.record("add_pattern", pat, base, k)
    _note_add(h)
    h.solver.ensure_vars(h.nv)
    for c in pat:
        h.clauses.append([Solver._to_ext(l + 2 * base) for l in c])
    r = h.solver.add_pattern(pat, base, k)
    link = [rng.randint(base, h.nv), -rng.randint(1, base - 1)]
    h.record("add_clause", link)
    h.clauses.append(link)
    r = h.solver.add_clause(link) and r
    h.check(r or not h.sat([]), "add_pattern False but SAT")
    h.after_prop = False


@op(2)
def grow(h: Harness) -> None:
    """New variables (unconstrained) while levels may be held."""
    h.record("grow")
    if h.rng.random() < 0.5:
        v = h.solver.new_var()
        h.check(v == h.nv + 1, "new_var id", v)
        h.nv = v
    else:
        h.nv += h.rng.randint(1, 3)
        h.solver.ensure_vars(h.nv)
    h.check(h.solver.nvars() == h.nv, "nvars after grow")


# ----------------------------------------------------------------------
# Operations: queries
# ----------------------------------------------------------------------

def _assumptions(h: Harness, sizes=(1, 1, 1, 2, 3)) -> list[int]:
    """The current assumption set, changed now and then.  A new set is
    usually read off a model of the current formula (consistent, like the
    engine's assumption sets nearly always are), sometimes random."""
    rng = h.rng
    if h.A is None or rng.random() < (0.8 if h.A_bad else 0.3):
        h.A_bad = False
        A = h.rclause(rng.choice(sizes))
        if rng.random() < 0.7:
            o = h.fresh()
            if o.solve():
                m = o.model()
                A = [v if m[v] else -v for v in map(abs, A)]
        h.A = A
    return h.A


@op(19)
def implied(h: Harness) -> None:
    A = _assumptions(h)
    h.record("implied", A)
    if h.held_now(A):
        h.count("implied_from_held")
    got = h.solver.implied(A)
    ref = h.fresh().implied(A)
    if got is None:
        h.count("implied_none")
        h.check(not h.sat(A), "implied None but consistent")
        h.last_trail = None
        h.A_bad = True
        return
    h.check(ref is not None, "implied misses a propagation conflict", ref)
    h.check(set(ref) <= set(got), "implied misses", sorted(set(ref) - set(got)))
    h.check(len(set(got)) == len(got), "implied has duplicates")
    h.check(not any(-x in got for x in got), "implied contradicts itself")
    for x in set(got) - set(ref):
        h.check(h.entailed(A, x), "implied unsound", x)
    h.last_trail = got


@op(13)
def entails(h: Harness) -> None:
    A = _assumptions(h)
    # Half the time a literal already settled by propagation: the answer
    # is then read off the trail and only the consistency of the
    # assumptions is established (by the witness or one search).
    if h.last_trail and h.rng.random() < 0.5:
        lit = h.rng.choice(h.last_trail)
        if h.rng.random() < 0.5:
            lit = -lit
    else:
        lit = h.rlit()
    h.record("entails", lit, A)
    try:
        got = h.solver.entails(lit, A)
    except ValueError:
        got = "inconsistent"
    try:
        ref = h.fresh().entails(lit, A)
    except ValueError:
        ref = "inconsistent"
    h.count(f"entails_{got}")
    h.check(got == ref, "entails", lit, A, got, ref)
    if got == "inconsistent":
        h.A_bad = True


@op(7)
def solve(h: Harness) -> None:
    """``solve`` on the current assumptions, an extension of them (the
    held levels are a prefix), a prefix, or a fresh set; the model or the
    conflict core is checked against the oracle."""
    A = _assumptions(h)
    rng = h.rng
    which = rng.random()
    if which < 0.35:
        AA = A + [h.rlit()]
    elif which < 0.55:
        AA = list(A)
    elif which < 0.7:
        AA = A[:-1]
    else:
        AA = h.rclause(rng.choice([0, 1, 2, 3]))
    _check_solve(h, AA)


def _check_solve(h: Harness, AA: list[int]) -> None:
    A = h.A
    h.record("solve", AA)
    held = h.solver._held
    if held is not None and h.held_now(AA[:len(held)]):
        h.count("solve_from_held")
    hits = h.solver._n_ring_hits
    got = h.solver.solve(AA)
    if h.solver._n_ring_hits > hits:
        h.count("solve_by_stored_model")
    h.check(got == h.sat(AA), "solve", AA, got)
    if got:
        m = h.solver.model()
        h.check(m is not None, "model missing after SAT")
        h.check(all(m[abs(x)] == (x > 0) for x in AA), "model violates assumptions")
        h.check(all(any(m[abs(x)] == (x > 0) for x in c) for c in h.clauses),
                "model violates a clause")
    else:
        h.count("solve_unsat")
        if A is not None and AA[:len(A)] == A:
            h.A_bad = True
        core = h.solver.conflict()
        h.check(h.solver.model() is None, "model after UNSAT")
        h.check(set(core) <= set(AA), "conflict core not a subset", core, AA)
        h.check(not h.sat(core), "conflict core is consistent", core)


@op(4)
def solve_witness(h: Harness) -> None:
    """``solve`` on assumptions true in one of the live solver's stored
    models (``Solver._ring``): answered by that model unless something
    added since falsifies it; the model is then checked like any other."""
    ring = h.solver._ring
    if not ring:
        return
    mv = h.rng.choice(ring)[0]
    vs = h.rng.sample(range(1, len(mv) + 1), min(len(mv), h.rng.randint(1, 3)))
    AA = [v if mv[v - 1] else -v for v in vs]
    if h.rng.random() < 0.3:
        AA.append(h.rlit())
    _check_solve(h, AA)


@op(5)
def propagate(h: Harness) -> None:
    h.record("propagate")
    r = h.solver.propagate()
    h.check(r or not h.sat([]), "propagate False but SAT")
    h.after_prop = True


@op(4)
def root(h: Harness) -> None:
    h.record("root_trail")
    rt = h.solver.root_trail()
    h.check(len(set(rt)) == len(rt), "root_trail has duplicates")
    for x in rt:
        h.check(x in h.verified or h.entailed([], x), "root_trail unsound", x)
        h.verified.add(x)
        h.check(h.solver.value(x) is True, "value disagrees with root_trail", x)


# ----------------------------------------------------------------------
# Rule block: the same problems with the block as a propagator
# ----------------------------------------------------------------------
#
# In block mode the live solver has ``set_rule_block`` and a block on
# variables 1..bk from the start; the operation ``register_block`` adds a
# block on fresh variables (sometimes already constrained or assigned,
# sometimes while levels are held) and links it to the rest.  The oracle
# gets every block as plain clauses, so each check of the harness compares
# the propagator with clause propagation.  The block is the engine's
# ``RULE_INTERNAL`` or a small random one (more conflicts per variable).

class BlockSolver(Solver):
    """Counts the rule-block reasons conflict analysis reads."""
    n_rb_reasons = 0

    def _rb_reason(self, v, r):
        self.n_rb_reasons += 1
        return super()._rb_reason(v, r)


def random_block(rng: random.Random) -> tuple[tuple, int]:
    """A random clean pattern: k variables, binary to 4-ary clauses."""
    k = rng.randint(3, 8)
    out = []
    for _ in range(rng.randint(k, 2 * k)):
        vs = rng.sample(range(k), min(k, rng.choice([2, 2, 2, 3, 3, 4])))
        out.append(tuple(2 * v + rng.randint(0, 1) for v in vs))
    return tuple(out), k


def _old_lit(h: Harness, below: int) -> int:
    return h.rng.choice([1, -1]) * h.rng.randint(1, below)


def register_block(h: Harness) -> None:
    """A block on fresh variables: sometimes constrained first (a unit, or
    a link from an old variable, possibly propagated at a held level), then
    registered (in mixed mode sometimes added as clauses instead), then
    linked to the old variables (in hard seeds by a burst of 3-clauses)."""
    rng = h.rng
    s = h.solver
    k = h.bk
    base = h.nv + 1
    h.nv += k
    s.ensure_vars(h.nv)
    if rng.random() < 0.4:
        for _ in range(rng.randint(1, 3)):
            v = rng.randint(base, h.nv)
            x = v if rng.random() < 0.5 else -v
            r = rng.random()
            top = s._trail[s._trail_lim[-1]:] if s._trail_lim else ()
            if top and r < 0.5:
                # implied by a literal of the top held level: x is assigned
                # at that level (``_attach_held``) and the levels stay held
                t = rng.choice(top)
                c = [x, -Solver._to_ext(t)]
            elif r < 0.7:
                c = [x]                 # a root value (drops held levels)
            else:
                c = [x, _old_lit(h, base - 1)]
            h.record("add_clause", c)
            h.clauses.append(c)
            if not s.add_clause(c):
                h.check(not h.sat([]), "add_clause False but SAT")
                return
        if not s._trail_lim and rng.random() < 0.5:
            implied(h)                  # hold levels over the root values
    held = bool(s._trail_lim)
    if held:
        h.count("blocks_while_held")
    val = s._val
    lv = [s._level[v] for v in range(base, h.nv + 1) if val[2 * v] is not None]
    if lv:
        h.count("blocks_over_assigned")
        if max(lv):
            h.count("blocks_over_held_assigned")
        elif held:
            h.count("blocks_over_root_assigned_while_held")
    prop = h.block_mode == "prop" or rng.random() < 0.7
    if not h.add_block(base, prop):
        return
    if h.hard:
        links = []
        for _ in range(int(rng.uniform(0.3, 1.0) * k)):
            c = [rng.randint(base, h.nv) * rng.choice([1, -1])]
            c += [h.rlit() for _ in range(2)]
            if len({abs(x) for x in c}) == 3:
                links.append(c)
    else:
        links = [[rng.randint(base, h.nv) * rng.choice([1, -1]), _old_lit(h, base - 1)]
                 for _ in range(rng.randint(1, 3))]
    h.record("add_clauses", links)
    h.clauses.extend(links)
    r = s.add_clauses(links)
    h.check(r or not h.sat([]), "add_clauses False but SAT")
    h.after_prop = False


BLOCK_OPS = OPS + [("register_block", 6, register_block)]


def theory_setup(seed: int) -> Callable:
    """A ForbidTheory (random mode, two or three forbidden sets) over atoms
    1..3, which in block mode are variables of the first block; the live
    solver's copy is wrapped in a Recorder for check_protocol."""
    rng = random.Random(10007 * seed + 1)
    mode = rng.choice(["eager", "lazy", "propagate"])
    atoms = [1, 2, 3]
    forbidden = [[v * rng.choice([1, -1]) for v in rng.sample(atoms, rng.randint(2, 3))]
                 for _ in range(rng.randint(2, 3))]
    # A second theory with no atoms at the start: register_second gives it
    # variables the first one already has (a new constraint on a variable
    # that is already a theory atom).
    mode2 = rng.choice(["eager", "lazy", "propagate"])
    forbidden2 = [[v * rng.choice([1, -1]) for v in rng.sample(atoms, rng.randint(1, 2))]
                  for _ in range(rng.randint(1, 2))]

    def setup(s: Solver) -> None:
        t = ForbidTheory(forbidden, mode)
        if isinstance(s, BlockSolver):
            t = s.recorder = Recorder(t, s)
        s.attach_theory(t)
        t2 = ForbidTheory(forbidden2, mode2)
        s.attach_theory(t2)
        s.fuzz_theories = [t, t2]
        for v in atoms:
            s.register_atom(t, v, None)
    return setup


def register_second(h: Harness) -> None:
    """Register a variable of the first theory with the second one (theory
    mode only): the formula changes while the number of theory variables
    does not."""
    s = h.solver
    ts = getattr(s, "fuzz_theories", None)
    if ts is None:
        return
    free = [v for v in (1, 2, 3) if (1, v) not in h.regs]
    if not free:
        return
    v = h.rng.choice(free)
    h.record("register_second", v)
    h.regs.append((1, v))
    r = s.register_atom(ts[1], v, None)
    h.check(r or not h.sat([]), "register_atom False but SAT")
    h.after_prop = False


def run_block_seed(seed: int, theory: bool = False) -> dict[str, int]:
    mode = "prop" if seed % 2 == 0 else "mixed"
    setup = theory_setup(seed) if theory else None
    ops = BLOCK_OPS + [("register_second", 3, register_second)] if theory else BLOCK_OPS
    return run_seed(seed, ops=ops, setup=setup, block=mode)


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------

def _chunk(i: int) -> range:
    lo = SEED0 + i * SEEDS // CHUNKS
    hi = SEED0 + (i + 1) * SEEDS // CHUNKS
    return range(lo, hi)


COVERAGE: dict[str, int] = {}       # counters accumulated by the chunk tests


@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_incremental_matches_fresh(chunk):
    for seed in _chunk(chunk):
        _merge(COVERAGE, run_seed(seed))


def test_mix_covers_the_incremental_paths():
    """The counters that justify this test: held levels reused across
    calls, clauses attached while held, conflicts, learnt-clause deletion,
    restarts and every kind of answer all happen.  Reads the counters of
    the chunk tests above (runs 300 seeds itself if they did not run)."""
    c = COVERAGE if COVERAGE.get("seeds", 0) >= 300 else run_seeds(0, 300)
    for key in ("implied_from_held", "solve_from_held", "adds_while_held",
                "conflicts", "reductions", "restarts", "solve_unsat", "witness_hits",
                "entails_None", "entails_True", "entails_False",
                "entails_inconsistent", "implied_none"):
        assert c.get(key, 0) > 0, (key, c)


def test_harness_catches_a_dropped_clause(monkeypatch):
    """A checker must be shown to check: a solver that silently drops a
    clause added while assumption levels are held is caught within a few
    seeds."""
    real = Solver.add_clause

    def dropping(self, lits):
        if self._trail_lim:
            return True
        return real(self, lits)

    monkeypatch.setattr(Solver, "add_clause", dropping)
    with pytest.raises(Mismatch):
        run_seeds(0, 40)


BLOCK_COVERAGE: dict[str, int] = {}


@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_block_propagator_matches_clauses(chunk):
    for seed in _chunk(chunk):
        _merge(BLOCK_COVERAGE, run_block_seed(seed))


@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_block_propagator_with_theory_matches_clauses(chunk):
    for seed in _chunk(chunk):
        _merge(BLOCK_COVERAGE, run_block_seed(seed, theory=True))


def test_block_mix_covers_the_propagator_paths():
    """Conflicts whose analysis reads a propagator reason, blocks
    registered while levels are held and over assigned variables, and
    every kind of answer, happen in block mode."""
    c = BLOCK_COVERAGE
    if c.get("block_seeds", 0) < 300:
        c = {}
        for seed in range(150):
            _merge(c, run_block_seed(seed))
            _merge(c, run_block_seed(seed, theory=True))
    for key in ("rb_reasons_read", "block_hard_conflicts", "blocks_while_held",
                "blocks_over_assigned", "blocks_over_held_assigned",
                "blocks_over_root_assigned_while_held", "blocks_registered", "implied_from_held",
                "solve_from_held", "reductions", "solve_unsat", "witness_hits", "entails_None",
                "entails_True", "entails_False", "entails_inconsistent"):
        assert c.get(key, 0) > 0, (key, c)


def test_harness_catches_a_weak_propagator(monkeypatch):
    """The block fuzz checks the propagator: one that forgets a clause of
    the block is caught within a few seeds."""
    real = Solver.set_rule_block

    def forgetting(self, block, nvars=None):
        return real(self, tuple(block)[:-1], nvars)

    monkeypatch.setattr(Solver, "set_rule_block", forgetting)
    with pytest.raises(Mismatch):
        for seed in range(40):
            run_block_seed(seed)


def test_harness_catches_a_stale_witness(monkeypatch):
    """A solver that answers from a stored model without checking what was
    added since (clauses, root literals, blocks) is caught."""
    def stale(self, lits):
        for rec in reversed(self._ring):
            mv = rec[0]
            if all((l >> 1) <= len(mv) and mv[(l >> 1) - 1] is (not l & 1) for l in lits):
                return rec
        return None

    monkeypatch.setattr(Solver, "_ring_hit", stale)
    with pytest.raises(Mismatch):
        run_seeds(0, 60)


if __name__ == "__main__":
    seed0 = int(sys.argv[1]) if len(sys.argv) > 1 else SEED0
    n = int(sys.argv[2]) if len(sys.argv) > 2 else SEEDS
    mode = sys.argv[3] if len(sys.argv) > 3 else "plain"
    if mode == "plain":
        counts = run_seeds(seed0, n)
    else:
        counts = {}
        for seed in range(seed0, seed0 + n):
            _merge(counts, run_block_seed(seed, theory=(mode == "theory")))
    print("ok", n, "seeds from", seed0)
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")
