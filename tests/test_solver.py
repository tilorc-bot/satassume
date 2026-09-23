"""Tests for satassume.solver (pure stdlib + pytest)."""
import itertools
import random
import time

import pytest

from satassume.solver import Solver

# ----------------------------------------------------------------------
# Brute-force reference
# ----------------------------------------------------------------------

def _models(clauses, nvars, assumptions=()):
    """All satisfying assignments (as tuples of truth values, index v-1)."""
    out = []
    for bits in itertools.product((False, True), repeat=nvars):
        ok = all(any((bits[abs(l) - 1] if l > 0 else not bits[abs(l) - 1])
                     for l in c) for c in clauses)
        if ok and all((bits[abs(a) - 1] if a > 0 else not bits[abs(a) - 1])
                      for a in assumptions):
            out.append(bits)
    return out


def _entailed(models, nvars):
    """Set of literals true in every model (all literals if no model)."""
    if not models:
        return {l for v in range(1, nvars + 1) for l in (v, -v)}
    out = set()
    for v in range(1, nvars + 1):
        if all(m[v - 1] for m in models):
            out.add(v)
        elif all(not m[v - 1] for m in models):
            out.add(-v)
    return out


def _random_3sat(rng, nvars, nclauses, k=3):
    clauses = []
    for _ in range(nclauses):
        vs = rng.sample(range(1, nvars + 1), min(k, nvars))
        clauses.append([v if rng.random() < 0.5 else -v for v in vs])
    return clauses


def _check_model(model, clauses):
    for c in clauses:
        assert any(model[abs(l)] == (l > 0) for l in c), (c, model)


def _load(clauses):
    s = Solver()
    ok = True
    for c in clauses:
        ok = s.add_clause(c) and ok
    return s, ok


# ----------------------------------------------------------------------
# Basics
# ----------------------------------------------------------------------

def test_unit_propagation_chain():
    s = Solver()
    for i in range(1, 6):
        assert s.add_clause([-i, i + 1])
    assert s.root_trail() == []
    assert s.add_clause([1])
    assert s.root_trail() == [1, 2, 3, 4, 5, 6]
    assert s.value(6) is True
    assert s.value(-6) is False
    assert s.value(7) is None
    assert s.nvars() == 6
    assert s.propagate()
    assert s.solve()
    assert s.model()[6] is True


def test_propagation_conflict_at_root():
    s = Solver()
    assert s.add_clause([-1, 2])
    assert s.add_clause([-1, -2])
    assert s.add_clause([1]) is False
    assert s.propagate() is False
    assert s.solve() is False
    assert s.model() is None


def test_empty_clause():
    s = Solver()
    assert s.add_clause([1, 2])
    assert s.add_clause([]) is False
    assert s.solve() is False
    assert s.add_clause([3]) is False


def test_tautology_and_duplicates():
    s = Solver()
    assert s.add_clause([1, -1])
    assert s.root_trail() == []
    assert s.add_clause([2, 2, 2])
    assert s.value(2) is True
    assert s.add_clause([3, -3, 4])
    assert s.value(4) is None
    assert s.add_clause([-2, 5, 5, -2])
    assert s.value(5) is True
    assert s.solve()


def test_zero_literal_rejected():
    s = Solver()
    with pytest.raises(ValueError):
        s.add_clause([0, 1])


def test_root_simplification_when_adding():
    s = Solver()
    assert s.add_clause([1])
    # satisfied clause is dropped, false literal is removed
    assert s.add_clause([1, 2, 3])
    assert s.value(2) is None
    assert s.add_clause([-1, 4])
    assert s.value(4) is True
    assert s.add_clause([-1, -4, 5, 6])
    n = len(s.root_trail())
    assert s.add_clause([-5])
    assert s.root_trail()[n:] == [-5, 6]


def test_new_var_and_implicit_growth():
    s = Solver()
    assert s.new_var() == 1
    assert s.new_var() == 2
    assert s.add_clause([7, -3])
    assert s.nvars() == 7
    assert s.new_var() == 8


def test_stats_keys():
    s = Solver()
    s.add_clause([1, 2])
    s.add_clause([-1, 2])
    s.solve()
    st = s.stats()
    for k in ("propagations", "conflicts", "decisions", "learned"):
        assert k in st and isinstance(st[k], int)


# ----------------------------------------------------------------------
# Random cross-check against brute force
# ----------------------------------------------------------------------

def _instances(seed, count, nmin=3, nmax=10):
    rng = random.Random(seed)
    for _ in range(count):
        n = rng.randint(nmin, nmax)
        m = rng.randint(1, int(4.6 * n))
        yield rng, n, _random_3sat(rng, n, m)


def test_random_solve_vs_bruteforce():
    for rng, n, clauses in _instances(1, 200):
        s, ok = _load(clauses)
        models = _models(clauses, n)
        res = s.solve()
        assert res == bool(models), clauses
        assert ok or not models
        if res:
            _check_model(s.model(), clauses)
        else:
            assert s.model() is None
            assert s.conflict() == []
        # Root facts must be entailed by the formula.
        ent = _entailed(models, n)
        for l in s.root_trail():
            assert l in ent


def test_random_solve_under_assumptions():
    for rng, n, clauses in _instances(2, 200):
        s, _ = _load(clauses)
        for _ in range(3):
            k = rng.randint(0, min(3, n))
            assumptions = [v if rng.random() < 0.5 else -v
                           for v in rng.sample(range(1, n + 1), k)]
            models = _models(clauses, n, assumptions)
            res = s.solve(assumptions)
            assert res == bool(models), (clauses, assumptions)
            if res:
                m = s.model()
                _check_model(m, clauses)
                for a in assumptions:
                    assert m[abs(a)] == (a > 0)
            else:
                core = s.conflict()
                assert set(core) <= set(assumptions)
                assert not _models(clauses, n, core)


def test_random_entails_vs_bruteforce():
    for rng, n, clauses in _instances(3, 200):
        s, _ = _load(clauses)
        k = rng.randint(0, min(2, n))
        assumptions = [v if rng.random() < 0.5 else -v
                       for v in rng.sample(range(1, n + 1), k)]
        models = _models(clauses, n, assumptions)
        if not models:
            with pytest.raises(ValueError):
                s.entails(1, assumptions)
            continue
        ent = _entailed(models, n)
        for v in range(1, n + 1):
            expect = True if v in ent else (False if -v in ent else None)
            assert s.entails(v, assumptions) is expect, (clauses, assumptions, v)
            neg = None if expect is None else (not expect)
            assert s.entails(-v, assumptions) is neg
        # Solver must be back at root and consistent afterwards.
        assert s.solve(assumptions)


def test_random_implied_semantics():
    for rng, n, clauses in _instances(4, 200):
        s, ok = _load(clauses)
        root = s.root_trail()
        for _ in range(3):
            k = rng.randint(0, min(3, n))
            assumptions = [v if rng.random() < 0.5 else -v
                           for v in rng.sample(range(1, n + 1), k)]
            models = _models(clauses, n, assumptions)
            imp = s.implied(assumptions)
            if imp is None:
                assert not models or not ok
                continue
            ent = _entailed(models, n)
            assert set(imp) <= ent, (clauses, assumptions, imp)
            assert set(root) <= set(imp)
            if models:
                assert set(assumptions) <= set(imp)
            # No duplicates, no contradictions in the returned list.
            assert len(set(imp)) == len(imp)
            assert not any(-l in imp for l in imp)
            # The solver is unchanged at root.
            assert s.root_trail() == root


def test_implied_no_learning_and_root_unchanged():
    s = Solver()
    s.add_clause([1, 2])
    s.add_clause([1, -2])
    assert s.implied([-1]) is None
    assert s.root_trail() == []
    assert s.implied([2]) == [2, 1]
    assert s.root_trail() == []
    assert s.implied([1]) == [1]


def test_implied_with_root_facts():
    s = Solver()
    s.add_clause([1])
    s.add_clause([-1, -3, 4])
    assert s.implied() == [1]
    assert s.implied([3]) == [1, 3, 4]
    assert s.implied([-4]) == [1, -4, -3]
    assert s.implied([3, -4]) is None
    assert s.root_trail() == [1]


# ----------------------------------------------------------------------
# Incremental use
# ----------------------------------------------------------------------

def test_incremental_add_between_solves():
    rng = random.Random(5)
    for _ in range(60):
        n = rng.randint(3, 9)
        s = Solver()
        clauses = []
        alive = True
        for _step in range(6):
            batch = _random_3sat(rng, n, rng.randint(1, n))
            for c in batch:
                alive = s.add_clause(c) and alive
            clauses.extend(batch)
            models = _models(clauses, n)
            if not alive:
                assert not models
                assert s.solve() is False
                break
            k = rng.randint(0, 2)
            assumptions = [v if rng.random() < 0.5 else -v
                           for v in rng.sample(range(1, n + 1), k)]
            res = s.solve(assumptions)
            assert res == bool(_models(clauses, n, assumptions))
            if res:
                _check_model(s.model(), clauses)
            ent = _entailed(models, n)
            for l in s.root_trail():
                assert l in ent
            assert s.solve() == bool(models)


def test_learned_unit_appears_in_root_trail():
    s = Solver()
    s.add_clause([1, 2])
    s.add_clause([1, -2])
    s.add_clause([3, 4])
    assert s.root_trail() == []
    # Under assumption -1 the conflict is immediate; the learned clause is
    # the unit [1], which becomes a root fact.
    assert s.solve([-1]) is False
    assert s.conflict() == [-1]
    assert 1 in s.root_trail()
    assert s.value(1) is True
    assert s.value(-1) is False
    assert s.solve()
    assert s.model()[1] is True
    # A clause added later is simplified against the new root fact.
    n = len(s.root_trail())
    assert s.add_clause([-1, 5])
    assert s.root_trail()[n:] == [5]


def test_learned_units_from_plain_search_are_root_facts():
    # x1 is entailed but not by propagation; whatever the search does,
    # anything it puts on the root trail must be entailed.
    s = Solver()
    clauses = [[1, 2], [1, -2], [-1, 3], [-3, 4, 5], [-3, 4, -5], [-4, -6], [6, 7]]
    for c in clauses:
        s.add_clause(c)
    assert s.solve()
    models = _models(clauses, 7)
    ent = _entailed(models, 7)
    for l in s.root_trail():
        assert l in ent
    assert s.solve([-1]) is False
    assert s.value(1) is True
    assert s.entails(4) is True
    assert s.entails(-6) is True
    assert s.entails(7) is True
    assert s.entails(5) is None


def test_clauses_added_after_solve_are_watched():
    s = Solver()
    s.add_clause([1, 2, 3])
    assert s.solve()
    s.add_clause([-1, 4])
    s.add_clause([-2, 4])
    s.add_clause([-3, 4])
    assert s.solve()
    assert s.model()[4] is True
    assert s.solve([-4]) is False
    assert s.conflict() == [-4]
    assert s.entails(4) is True
    assert s.value(4) is True


# ----------------------------------------------------------------------
# Pigeonhole
# ----------------------------------------------------------------------

def _php(pigeons, holes):
    def var(p, h):
        return p * holes + h + 1
    clauses = []
    for p in range(pigeons):
        clauses.append([var(p, h) for h in range(holes)])
    for h in range(holes):
        for p in range(pigeons):
            for q in range(p + 1, pigeons):
                clauses.append([-var(p, h), -var(q, h)])
    return clauses


def test_pigeonhole():
    s, ok = _load(_php(4, 3))
    assert ok
    assert s.solve() is False
    assert s.stats()["conflicts"] > 0
    assert s.solve() is False
    assert s.add_clause([1]) is False

    s, ok = _load(_php(3, 3))
    assert ok
    assert s.solve() is True
    _check_model(s.model(), _php(3, 3))
    # Every pigeon assignment is a permutation; forcing two into one hole fails.
    assert s.solve([1, 4]) is False
    assert set(s.conflict()) == {1, 4}


# ----------------------------------------------------------------------
# Conflict analysis under assumptions
# ----------------------------------------------------------------------

def test_conflict_is_relevant_subset():
    s = Solver()
    s.add_clause([-1, -2])
    s.add_clause([-3, 4])
    s.add_clause([-4, 5])
    s.add_clause([-5, -6])
    assumptions = [7, 1, 8, 2, 9]
    assert s.solve(assumptions) is False
    core = s.conflict()
    assert set(core) == {1, 2}
    assert s.solve(core) is False
    # a chain: 3 -> 4 -> 5 -> -6, together with 6
    assumptions = [7, 3, 8, 6]
    assert s.solve(assumptions) is False
    core = s.conflict()
    assert set(core) == {3, 6}
    assert s.solve(core) is False
    # contradictory assumptions
    assert s.solve([10, -10]) is False
    assert set(s.conflict()) == {10, -10}
    # assumption already false at root
    s.add_clause([-11])
    assert s.solve([12, 11]) is False
    assert s.conflict() == [11]


def test_conflict_subset_random():
    for rng, n, clauses in _instances(6, 100, nmin=4, nmax=10):
        s, ok = _load(clauses)
        if not ok:
            continue
        k = rng.randint(1, n)
        assumptions = [v if rng.random() < 0.5 else -v
                       for v in rng.sample(range(1, n + 1), k)]
        if s.solve(assumptions):
            continue
        core = s.conflict()
        assert set(core) <= set(assumptions)
        assert s.solve(core) is False
        assert not _models(clauses, n, core)


def test_entails_raises_on_inconsistent_assumptions():
    s = Solver()
    s.add_clause([-1, -2])
    s.add_clause([3, 4])
    with pytest.raises(ValueError, match="inconsistent assumptions"):
        s.entails(3, [1, 2])
    # inconsistency only detectable by search
    s.add_clause([5, 6])
    s.add_clause([5, -6])
    s.add_clause([-5, 7])
    s.add_clause([-5, -7])
    with pytest.raises(ValueError, match="inconsistent assumptions"):
        s.entails(3, [3])
    assert s.solve() is False
    with pytest.raises(ValueError):
        s.entails(3)


def test_entails_basic():
    s = Solver()
    s.add_clause([-1, 2])
    s.add_clause([-2, 3])
    assert s.entails(3, [1]) is True
    assert s.entails(-3, [1]) is False
    assert s.entails(1, [-3]) is False
    assert s.entails(3) is None
    assert s.entails(2, [-3]) is False
    assert s.root_trail() == []


def test_model_satisfies_and_is_copy():
    s = Solver()
    s.add_clause([1, 2])
    s.add_clause([-1, 2])
    assert s.solve()
    m = s.model()
    assert m[2] is True
    m[2] = False
    assert s.model()[2] is True


# ----------------------------------------------------------------------
# Performance smoke test
# ----------------------------------------------------------------------

def test_performance_smoke_300_vars():
    # Random 3-SAT at ratio 4.0 with 300 variables is near the phase
    # transition and instance hardness varies by orders of magnitude (the
    # reference MiniSat needs 2k-400k conflicts on such instances), so the
    # seed is fixed to a moderate one (a few hundred conflicts).
    rng = random.Random(3)
    n = 300
    clauses = _random_3sat(rng, n, 4 * n)
    s, ok = _load(clauses)
    assert ok
    t0 = time.perf_counter()
    res = s.solve()
    dt = time.perf_counter() - t0
    assert dt < 5.0, dt
    assert res is True
    _check_model(s.model(), clauses)
    assert s.stats()["conflicts"] > 0


def test_performance_many_tiny_queries():
    # Under-constrained instance (ratio 3.0): many small incremental
    # queries mixing the propagation fast path and short searches.
    rng = random.Random(3)
    n = 300
    clauses = _random_3sat(rng, n, 3 * n)
    s, ok = _load(clauses)
    assert ok
    t0 = time.perf_counter()
    for v in range(1, 101):
        w = -((v % n) + 1)
        imp = s.implied([v, w])
        if imp is not None:
            assert v in imp and w in imp
        s.entails(v, [w])
    dt = time.perf_counter() - t0
    assert dt < 5.0, dt


def test_performance_implication_chains():
    # A Horn-like implication forest (typical assumptions-engine shape):
    # root-level inference via ``implied`` must be cheap.
    rng = random.Random(9)
    n = 2000
    s = Solver()
    for v in range(2, n + 1):
        for _ in range(2):
            s.add_clause([-v, rng.randint(1, v - 1)])
    t0 = time.perf_counter()
    total = 0
    for _ in range(500):
        v = rng.randint(1, n)
        imp = s.implied([v])
        assert imp is not None and imp[0] == v
        total += len(imp)
    dt = time.perf_counter() - t0
    assert total > 500
    assert dt < 3.0, dt
    assert s.implied([n, -1]) is None
    assert s.entails(1, [n]) is True
