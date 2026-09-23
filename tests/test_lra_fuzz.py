"""Differential fuzzing of the LRA theory, direct and through the solver.

Oracles (both independent of the implementation, defined in test_lra.py):

* ``fm_feasible``: Fourier-Motzkin elimination over ``Fraction`` with
  strictness tracking, extended to disequalities.  **Complete and exact**
  for conjunctions of ``<=, <, ==, >=, >, !=`` over the reals; every SAT
  verdict on the convex part is certified by a back-substituted witness.
* ``grid_feasible``: exhaustive search over a rational grid.  **Incomplete**
  (SAT answers are certain, UNSAT only means "no grid point"); used as a
  second, dumb opinion: whenever it finds a point the theory must say SAT.

Direction coverage: every theory verdict is compared with FM in both
directions; a SAT verdict must come with a model satisfying every asserted
literal (exact evaluation); an UNSAT verdict must come with a conflict
clause that is false, infeasible by FM and (outside disequalities) minimal.

End-to-end: random CNF over relation atoms, ``Solver`` + theory versus
enumeration of all Boolean assignments, each checked by FM
(``theory_harness.check_solve`` / ``check_entails`` / ``check_implied``),
with the theory wrapped in ``Recorder`` so the protocol is checked on both
sides.
"""
from __future__ import annotations

import random
import time
from fractions import Fraction as F

import pytest
from hypothesis import HealthCheck, assume, given, settings, strategies as st

from test_lra import (DISEQ_COMPLETE, Driver, fm_feasible, grid_feasible, holds,
                      lits_feasible, consistent_for, needs_lra, new_theory,
                      payload, payload_constraint, run_fresh)
from theory_harness import (Recorder, TheoryCase, check_entails, check_implied,
                            check_protocol, check_solve)

FUZZ = settings(max_examples=150, deadline=None,
                suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])

NAMES = ["x", "y", "z"]

# ----------------------------------------------------------------------
# Strategies
# ----------------------------------------------------------------------

coef = st.integers(-3, 3)
rhs = st.builds(F, st.integers(-4, 4), st.sampled_from([1, 1, 2, 3]))
op = st.sampled_from(["<=", "<", "==", ">=", ">", "!="])


@st.composite
def atom(draw, names=NAMES):
    k = draw(st.integers(1, len(names)))
    vs = draw(st.permutations(names))[:k]
    co = {v: draw(coef) for v in vs}
    if draw(st.integers(0, 9)) == 0:
        co = {v: c for v, c in co.items() if c}          # sometimes empty
    return payload(co, draw(op), draw(rhs))


@st.composite
def system(draw, max_atoms=6, names=None):
    names = names or NAMES[:draw(st.integers(1, 3))]
    n = draw(st.integers(1, max_atoms))
    atoms = {i + 1: draw(atom(names)) for i in range(n)}
    lits = [v * draw(st.sampled_from([1, -1])) for v in atoms]
    lits = draw(st.permutations(lits))
    return atoms, lits


# ----------------------------------------------------------------------
# Direct differential tests
# ----------------------------------------------------------------------

@needs_lra
@FUZZ
@given(system())
def test_fuzz_conjunction_at_root(sys_):
    atoms, lits = sys_
    d = Driver(atoms)
    ok = d.assert_all(lits)
    verdict = d.check() if ok else False
    # d.check / d._conflict compared with FM; add the dumb grid opinion
    cons = [payload_constraint(atoms[abs(l)], l > 0) for l in lits]
    if grid_feasible(cons, NAMES, lo=-2, hi=2, dens=(1, 2)):
        assert verdict is not False


@needs_lra
@FUZZ
@given(system(), st.data())
def test_fuzz_conjunction_split_over_levels(sys_, data):
    atoms, lits = sys_
    d = Driver(atoms)
    for l in lits:
        if data.draw(st.booleans()):
            d.push()
        if not d.assert_(l):
            return
    d.check()


@needs_lra
@FUZZ
@given(system(), st.data())
def test_fuzz_pop_then_flip(sys_, data):
    """Assert a set, check, pop it, assert the flipped set: the second
    verdict must equal a fresh theory's (reference by reconstruction)."""
    atoms, lits = sys_
    d = Driver(atoms)
    keep = data.draw(st.integers(0, len(lits)))
    base, top = lits[:keep], lits[keep:]
    if not d.assert_all(base):
        return
    d.push()
    if d.assert_all(top):
        d.check()
    d.pop()
    flipped = [-l for l in top]
    d.push()
    r = d.check() if d.assert_all(flipped) else False
    assert r == run_fresh(atoms, base + flipped)


@needs_lra
@FUZZ
@given(system(max_atoms=5, names=["x", "y"]))
def test_fuzz_every_subset_via_levels(sys_):
    """All prefixes of the literal list at increasing levels, checking at
    every level, then unwinding and re-checking at each level."""
    atoms, lits = sys_
    d = Driver(atoms)
    verdicts = []
    for l in lits:
        d.push()
        if not d.assert_(l):
            break
        verdicts.append(d.check())
        if verdicts[-1] is False:
            break
    while d.level:
        d.pop()
        if not d.blocked:
            d.check()


@needs_lra
@FUZZ
@given(system(max_atoms=6))
def test_fuzz_propagation_reasons(sys_):
    atoms, lits = sys_
    d = Driver(atoms)
    for l in lits:
        if abs(l) in {abs(m) for m in d.asserted}:
            continue
        d.push()
        if not d.assert_(l):
            return
        for p in d.propagate():
            if -p in d.asserted:
                return                   # the solver would treat it as a conflict
            if p not in d.asserted:
                d.push()
                if not d.assert_(p):
                    return


# ----------------------------------------------------------------------
# End to end through the CDCL solver
# ----------------------------------------------------------------------

@st.composite
def cnf_case(draw):
    names = NAMES[:draw(st.integers(1, 3))]
    n = draw(st.integers(2, 8))
    atoms = {i + 1: draw(atom(names)) for i in range(n)}
    extra = draw(st.integers(0, 2))                # a few pure Boolean vars
    nv = n + extra
    lit = st.integers(1, nv).flatmap(lambda v: st.sampled_from([v, -v]))
    clauses = draw(st.lists(st.lists(lit, min_size=1, max_size=3), max_size=10))
    return atoms, clauses, nv


def _check_theory_models(case, atoms):
    models = case.solver.theory_models()
    m = case.solver.model()
    assert models is not None and m is not None
    tm = models[0]
    if tm is None:
        return
    vals = dict(tm)
    for v, p in atoms.items():
        assert holds(payload_constraint(p, m[v]), vals), (v, m[v], p, vals)


@needs_lra
@FUZZ
@given(cnf_case())
def test_fuzz_solve_against_enumeration(c):
    atoms, clauses, nv = c
    rec = Recorder(new_theory())
    case = TheoryCase(rec, atoms, clauses, nvars=nv)
    if check_solve(case, consistent_for(atoms)):
        _check_theory_models(case, atoms)
    check_protocol(rec)


@needs_lra
@FUZZ
@given(cnf_case(), st.data())
def test_fuzz_entails_and_implied(c, data):
    atoms, clauses, nv = c
    rec = Recorder(new_theory())
    case = TheoryCase(rec, atoms, clauses, nvars=nv)
    cons = consistent_for(atoms)
    lit_st = st.integers(1, nv).flatmap(lambda v: st.sampled_from([v, -v]))
    for _ in range(3):
        assumptions = data.draw(st.lists(lit_st, max_size=3, unique_by=abs))
        check_entails(case, cons, data.draw(lit_st), assumptions)
        check_implied(case, cons, assumptions)
        check_solve(case, cons, assumptions)
    check_protocol(rec)


@needs_lra
@pytest.mark.parametrize("seed", range(40))
def test_random_cnf_repeated_queries(seed):
    """One solver, many solve/entails calls: learnt theory clauses and
    theory state must stay correct across queries."""
    rng = random.Random(seed)
    names = NAMES[:rng.randint(1, 3)]
    atoms = {}
    for i in range(rng.randint(3, 9)):
        co = {v: rng.randint(-2, 2) for v in rng.sample(names, rng.randint(1, len(names)))}
        atoms[i + 1] = payload(co, rng.choice(["<=", "<", "==", ">=", ">"]), rng.randint(-2, 2))
    n = len(atoms)
    clauses = [[rng.choice([1, -1]) * rng.randint(1, n) for _ in range(rng.randint(1, 3))]
               for _ in range(rng.randint(0, 8))]
    rec = Recorder(new_theory())
    case = TheoryCase(rec, atoms, clauses)
    cons = consistent_for(atoms)
    for _ in range(8):
        a = [rng.choice([1, -1]) * v for v in rng.sample(range(1, n + 1), rng.randint(0, min(3, n)))]
        if check_solve(case, cons, a):
            _check_theory_models(case, atoms)
        check_entails(case, cons, rng.choice([1, -1]) * rng.randint(1, n), a)
    check_protocol(rec)


@needs_lra
def test_solver_finds_the_only_consistent_assignment():
    """x < y, y < z, z < x as three atoms plus their negations' only
    consistent combination: exactly one atom false."""
    atoms = {1: payload({"x": 1, "y": -1}, "<", 0), 2: payload({"y": 1, "z": -1}, "<", 0),
             3: payload({"z": 1, "x": -1}, "<", 0), 4: payload({"x": 1, "z": -1}, "==", 0)}
    rec = Recorder(new_theory())
    case = TheoryCase(rec, atoms, [[1], [2], [3, 4]])
    cons = consistent_for(atoms)
    assert check_solve(case, cons) is False
    rec = Recorder(new_theory())
    case = TheoryCase(rec, atoms, [[1], [2]])
    assert check_entails(case, cons, -3) is True
    assert check_entails(case, cons, -4) is True
    check_protocol(rec)


# ----------------------------------------------------------------------
# Performance guard rails (cores 8,9; generous but loud limits)
# ----------------------------------------------------------------------

def _timed(f):
    t0 = time.process_time()
    r = f()
    return r, time.process_time() - t0


LIMIT = 1.0   # seconds of CPU; the brief asks for "well under a second"


@needs_lra
def test_perf_long_strict_chain_unsat():
    """x0 < x1 < ... < x149 < x0: 150 two-term rows, UNSAT at check."""
    n = 150
    atoms = {i + 1: payload({f"x{i}": 1, f"x{(i + 1) % n}": -1}, "<", 0) for i in range(n)}

    def run():
        t = new_theory()
        for v, p in atoms.items():
            t.register_atom(v, p)
        for v in atoms:
            r = t.assert_lit(v)
            if r is not None and r[0] is False:
                return r
        return t.check()
    r, dt = _timed(run)
    assert r is not None and r[0] is False
    assert sorted(-l for l in r[1]) == sorted(atoms)
    assert dt < LIMIT, f"150-row cycle took {dt:.2f}s"


@needs_lra
def test_perf_random_feasible_box_200():
    """200 random constraints over 10 variables around a known point."""
    rng = random.Random(42)
    names = [f"v{i}" for i in range(10)]
    point = {v: F(rng.randint(-5, 5)) for v in names}
    atoms = {}
    for i in range(200):
        co = {v: rng.randint(-3, 3) for v in rng.sample(names, rng.randint(1, 4))}
        val = sum(c * point[v] for v, c in co.items())
        atoms[i + 1] = payload(co, rng.choice(["<=", "<"]), val + rng.randint(1, 3))

    def run():
        t = new_theory()
        for v, p in atoms.items():
            t.register_atom(v, p)
        for v in atoms:
            r = t.assert_lit(v)
            assert r is None or r[0] is not False
        return t.check()
    r, dt = _timed(run)
    assert r is not None and r[0] is True
    vals = dict(r[1])
    for v, p in atoms.items():
        assert holds(payload_constraint(p), vals)
    assert dt < LIMIT, f"200 feasible constraints took {dt:.2f}s"


@needs_lra
def test_perf_push_pop_cycles():
    """100 levels of bounds, each checked, then popped and redone: the
    per-level cost must not grow with the history."""
    n = 50
    atoms = {}
    for i in range(n):
        atoms[2 * i + 1] = payload({f"x{i}": 1, f"x{(i + 1) % n}": -1}, "<=", 1)
        atoms[2 * i + 2] = payload({f"x{i}": 1}, ">=", -i)

    def run():
        t = new_theory()
        for v, p in atoms.items():
            t.register_atom(v, p)
        for _ in range(2):
            for v in sorted(atoms):
                t.push_level()
                r = t.assert_lit(v)
                assert r is None or r[0] is not False
            r = t.check()
            assert r is not None and r[0] is True
            for _ in atoms:
                t.pop_level()
        return True
    _, dt = _timed(run)
    assert dt < LIMIT, f"push/pop cycles took {dt:.2f}s"


@needs_lra
@pytest.mark.parametrize("unsat", [False, True])
def test_perf_through_solver_60_atoms(unsat):
    """62 atoms, 30 binary clauses ``x >= i or x + y <= i`` with ``y >= 0``
    and ``x < 0``: SAT (x + y <= 0).  With the unit ``x + y > 0`` added
    every clause loses both options at i = 0: UNSAT."""
    atoms = {}
    clauses = []
    for i in range(30):
        atoms[2 * i + 1] = payload({"x": 1}, ">=", i)
        atoms[2 * i + 2] = payload({"x": 1, "y": 1}, "<=", i)
        clauses.append([2 * i + 1, 2 * i + 2])
    atoms[61] = payload({"y": 1}, ">=", 0)
    atoms[62] = payload({"x": 1}, "<", 0)
    atoms[63] = payload({"x": 1, "y": 1}, ">", 0)
    clauses += [[61], [62]] + ([[63]] if unsat else [])

    def run():
        case = TheoryCase(new_theory(), atoms, clauses)
        return case, case.solve()
    (case, r), dt = _timed(run)
    assert r is (not unsat)
    if r:
        _check_theory_models(case, atoms)
    assert dt < LIMIT, f"solver with 63 atoms took {dt:.2f}s"
