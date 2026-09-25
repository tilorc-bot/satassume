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

``SOLVER_FUZZ_SEEDS`` (default 300) seeds starting at ``SOLVER_FUZZ_SEED0``
(default 0), split into ``CHUNKS`` test items.  For a long run by hand::

    SOLVER_FUZZ_SEEDS=4000 pytest -q tests/test_solver_incremental.py
    python tests/test_solver_incremental.py 0 4000     # same, with counters

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

from satassume.solver import Solver

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
                 hard: bool | None = None, nv: int | None = None):
        self.seed = seed
        self.rng = rng = random.Random(seed)
        self.ops = list(ops if ops is not None else OPS)
        self.setup = setup
        self.hard = (rng.random() < 0.3) if hard is None else hard
        if nv is None:
            nv = rng.randint(20, 80) if self.hard else rng.randint(3, 20)
        self.nv = nv
        self.clauses: list[list[int]] = []
        self.A: list[int] | None = None
        self.A_bad = False          # A was found inconsistent
        self.last_trail: list[int] | None = None   # last implied() result
        self.log: list[tuple] = []
        self.step = -1
        self.after_prop = True      # root propagation is complete
        self.verified: set[int] = set()   # root literals proven entailed
        self.counts: dict[str, int] = {}
        self.solver = s = Solver()
        if self.hard:
            # Small budgets so that learnt-clause deletion and restarts
            # happen on instances this small (both are tunables of Solver).
            s._learnt_size_min = rng.choice([1, 2, 4, 8])
            s._restart_first = rng.choice([1, 2, 4, 100])
        if setup is not None:
            setup(s)
        s.ensure_vars(self.nv)
        if self.hard:
            burst = [self.rclause(3) for _ in range(int(rng.uniform(4.0, 4.5) * self.nv))]
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
        return [v if rng.random() < 0.5 else -v for v in vs]

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
    h.count("seeds")
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
    h.after_prop = len(c) != 1 and h.after_prop


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
    h.record("solve", AA)
    held = h.solver._held
    if held is not None and h.held_now(AA[:len(held)]):
        h.count("solve_from_held")
    got = h.solver.solve(AA)
    h.check(got == h.sat(AA), "solve", AA, got)
    if got:
        m = h.solver.model()
        h.check(m is not None, "model missing after SAT")
        h.check(all(m[abs(x)] == (x > 0) for x in AA), "model violates assumptions")
        h.check(all(any(m[abs(x)] == (x > 0) for x in c) for c in h.clauses),
                "model violates a clause")
    else:
        h.count("solve_unsat")
        if AA[:len(A)] == A:
            h.A_bad = True
        core = h.solver.conflict()
        h.check(h.solver.model() is None, "model after UNSAT")
        h.check(set(core) <= set(AA), "conflict core not a subset", core, AA)
        h.check(not h.sat(core), "conflict core is consistent", core)


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
                "conflicts", "reductions", "restarts", "solve_unsat",
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


if __name__ == "__main__":
    seed0 = int(sys.argv[1]) if len(sys.argv) > 1 else SEED0
    n = int(sys.argv[2]) if len(sys.argv) > 2 else SEEDS
    counts = run_seeds(seed0, n)
    print("ok", n, "seeds from", seed0)
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")
