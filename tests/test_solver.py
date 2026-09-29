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


# ----------------------------------------------------------------------
# The rule block as a propagator (set_rule_block / register_block)
# ----------------------------------------------------------------------

from satassume.rules import NPRED, RULE_INTERNAL  # noqa: E402


class _CountingSolver(Solver):
    """Counts the rule-block reasons read by conflict analysis."""
    n_rb_reasons = 0

    def _rb_reason(self, v, r):
        self.n_rb_reasons += 1
        return super()._rb_reason(v, r)


def _block_pair(block, n, bases, clauses=()):
    """A solver with ``block`` registered on ``bases`` and one with the
    same block as ``add_pattern`` clauses; both get ``clauses``."""
    p = _CountingSolver()
    p.set_rule_block(block, n)
    c = Solver()
    for b in bases:
        assert p.register_block(b)
        assert c.add_pattern(block, b, n)
    for cl in clauses:
        p.add_clause(cl)
        c.add_clause(cl)
    return p, c


def _block_clauses(block, base):
    return [[Solver._to_ext(l + 2 * base) for l in cl] for cl in block]


def _implied_agrees(p, c, A, ment):
    """``implied`` of the propagator solver ``p`` against the clause solver
    ``c``: the same conflict, every literal of ``c`` on a variable in
    ``ment`` (mentioned outside the blocks: ``p`` writes block
    implications only for those), and nothing unsound beyond ``c``'s (the
    exact closure may add literals)."""
    a = p.implied(A)
    b = c.implied(A)
    assert (a is None) == (b is None), A
    if a is None:
        return
    a, b = set(a), set(b)
    assert {x for x in b if abs(x) in ment} <= a, (A, sorted(b - a))
    for x in a - b:
        assert c.entails(x, A) is True, (A, x)


def test_rule_block_implied_like_clauses():
    """Every predicate literal of a node, alone and with a second node
    linked to the first: the same implied literals on mentioned variables
    (the links, the assumption, the queried literals), same entails
    answers."""
    link = [[1 + 5, -(NPRED + 1 + 7)], [-(1 + 3), NPRED + 1 + 12]]
    p, c = _block_pair(RULE_INTERNAL, NPRED, [1, NPRED + 1], link)
    assert p.stats()["rule_blocks"] == 2
    assert p.stats()["clauses"] == len(link)
    p.mention([3, 9, NPRED + 4])
    ment = {abs(x) for cl in link for x in cl} | {3, 9, NPRED + 4}
    for v in range(1, 2 * NPRED + 1):
        for x in (v, -v):
            _implied_agrees(p, c, [x], ment | {v})
            for y in (3, -9, NPRED + 4):
                try:
                    ea = p.entails(y, [x])
                except ValueError:
                    ea = "inconsistent"
                try:
                    eb = c.entails(y, [x])
                except ValueError:
                    eb = "inconsistent"
                assert ea == eb, (x, y)


def test_rule_block_conflict_in_the_propagator():
    """Both clauses of a block fire from one literal and clash: the
    block's closure of -x1 is empty, a conflict found by the propagator.
    x1 is in every model of the block, so the search needs no conflict
    to find a model with it (the clause solver needs one)."""
    block = ((0, 2), (0, 3))              # (x1 | x2), (x1 | -x2)
    p, c = _block_pair(block, 2, [1])
    assert p.solve()
    assert p.model()[1] is True
    assert p.stats()["conflicts"] == 0
    assert c.solve() and c.model()[1] is True
    assert p.implied([-1]) is None and c.implied([-1]) is None
    assert not p.solve([-1]) and p.conflict() == [-1]


def test_rule_block_conflict_analysis_reads_propagator_reasons():
    """-x1 (the first decision) implies x2 and x3 through the block; a
    problem clause forbids both.  Analysis resolves through both
    propagator reasons down to the decision and learns the unit x1.
    (x1 is mentioned by a clause: an unmentioned block variable is not
    decided.)"""
    block = ((0, 2), (0, 4))              # (x1 | x2), (x1 | x3)
    p, c = _block_pair(block, 3, [1], [[-2, -3], [1, 4]])
    assert p.solve()
    m = p.model()
    assert m[1] is True and not (m[2] and m[3])
    assert p.stats()["conflicts"] == 1
    assert p.n_rb_reasons == 2
    assert p.value(1) is True
    assert c.solve() and c.value(1) is True


def test_rule_block_final_conflict_reads_propagator_reasons():
    """The assumption -x3 is false by the chain x1 -> x2 -> x3 of block
    implications: the core is {x1, -x3}, found through the reason of x3
    (x2 is mentioned by nothing: the chain runs in the closure, x3's
    reason is x1 directly)."""
    block = ((1, 2), (3, 4))              # (-x1 | x2), (-x2 | x3)
    p, c = _block_pair(block, 3, [1], [[1, 4], [1, -4]])
    assert not p.solve([1, 5, -3])
    assert sorted(p.conflict()) == [-3, 1]
    assert p.n_rb_reasons >= 1
    assert p._val[2 * 2] is None or p.value(2) is not None
    assert not c.solve([1, 5, -3]) and sorted(c.conflict()) == [-3, 1]


def test_rule_block_random_search_like_clauses():
    """Random blocks and random 3-clauses near the threshold: solve and
    conflict cores agree with brute force, and analysis reads propagator
    reasons."""
    rng = random.Random(4)
    read = 0
    for _ in range(40):
        k = rng.randint(3, 4)
        block = tuple(tuple(2 * v + rng.randint(0, 1) for v in rng.sample(range(k), rng.choice([2, 2, 3])))
                      for _ in range(rng.randint(k, 2 * k)))
        bases = [1, 1 + k, 1 + 2 * k]
        n = 3 * k
        extra = [[v * rng.choice([1, -1]) for v in rng.sample(range(1, n + 1), 3)]
                 for _ in range(int(3.0 * n))]
        cls = [cl for b in bases for cl in _block_clauses(block, b)] + extra
        models = _models(cls, n)
        p, c = _block_pair(block, k, bases, extra)

        def sat(A):
            return any(all(m[abs(a) - 1] == (a > 0) for a in A) for m in models)
        for _ in range(4):
            A = [v * rng.choice([1, -1]) for v in rng.sample(range(1, n + 1), 2)]
            want = sat(A)
            assert p.solve(A) == want == c.solve(A)
            if want:
                m = p.model()
                assert all(any(m[abs(l)] == (l > 0) for l in cl) for cl in cls)
            else:
                assert not sat(p.conflict())
        read += p.n_rb_reasons
    assert read > 0


def test_rule_block_with_held_levels():
    """Held levels over registered blocks: clauses added while held,
    queries answered from the held levels, search continuing from them."""
    link = [[1 + 5, -(NPRED + 1 + 7)]]
    p, c = _block_pair(RULE_INTERNAL, NPRED, [1, NPRED + 1], link)
    A = [1 + 2]
    ment = {1 + 5, NPRED + 1 + 7, 1 + 2}
    _implied_agrees(p, c, A, ment)
    assert p._held is not None
    p.add_clause([-(1 + 2), NPRED + 1 + 20])
    c.add_clause([-(1 + 2), NPRED + 1 + 20])
    ment.add(NPRED + 1 + 20)
    assert p._held is not None                      # attached while held
    _implied_agrees(p, c, A, ment)
    # a variable implied at the held level becomes mentioned: written there
    x = next(v for v in range(NPRED + 2, 2 * NPRED + 1)
             if v not in ment and c.value(v) is None
             and (v in c.implied(A) or -v in c.implied(A)))
    p.mention([x])
    ment.add(x)
    assert p._held is not None and p._n_late_written == 1
    _implied_agrees(p, c, A, ment)
    for y in range(1, 2 * NPRED + 1):
        assert p.entails(y, A) == c.entails(y, A)
    assert p.solve(A + [-(NPRED + 1 + 30)]) == c.solve(A + [-(NPRED + 1 + 30)])


def test_register_block_while_levels_are_held():
    """A block registered while levels are held: over unassigned variables
    the held levels stay (and later propagate into it); over a variable
    assigned at a held level, or over root values that make the block
    imply a root fact, they are dropped; the answers match clauses."""
    p = Solver()
    p.set_rule_block(RULE_INTERNAL, NPRED)
    c = Solver()
    b1, b2, b3 = 1, 1 + NPRED, 1 + 2 * NPRED
    X, Y = 1 + 5 * NPRED, 2 + 5 * NPRED            # beyond every block
    for s in (p, c):
        s.ensure_vars(Y)
        s.add_clause([-X, b2 + 4])                # linked into block 2
        s.add_clause([-X, b3 + 9])                # linked into block 3
        s.add_clause([-Y, X])
    assert p.register_block(b1) and c.add_pattern(RULE_INTERNAL, b1, NPRED)
    A = [Y]
    ment = {X, Y, b2 + 4, b3 + 9}
    _implied_agrees(p, c, A, ment)
    assert p._held is not None and p._val[2 * (b2 + 4)] is True
    # (a) b3 + 9 is assigned at the held level: held levels dropped
    assert p._level[b3 + 9] == 1
    assert p.register_block(b3) and c.add_pattern(RULE_INTERNAL, b3, NPRED)
    assert p._held is None
    _implied_agrees(p, c, A, ment)
    # (b) over unassigned variables while held: levels kept
    assert p._held is not None
    b4 = 1 + 3 * NPRED
    assert p._val[2 * b4] is None
    assert p.register_block(b4) and c.add_pattern(RULE_INTERNAL, b4, NPRED)
    assert p._held is not None
    _implied_agrees(p, c, A, ment)
    p.add_clause([-Y, b4 + 2])                    # propagates into block 4
    c.add_clause([-Y, b4 + 2])
    ment.add(b4 + 2)
    _implied_agrees(p, c, A, ment)
    # (c) over root values, with a root implication: held levels dropped
    for s in (p, c):
        s.add_clause([b2 + 3])                      # root fact on block 2
    _implied_agrees(p, c, A, ment)
    assert p._held is not None
    n0 = len(p.root_trail())
    assert p.register_block(b2) and c.add_pattern(RULE_INTERNAL, b2, NPRED)
    assert p._held is None and len(p.root_trail()) > n0
    # at root every block implication is written (the exact closure may
    # have more than clause propagation, all of it entailed)
    pr, cr = set(p.root_trail()), set(c.root_trail())
    assert cr <= pr and all(c.entails(x) is True for x in pr - cr)
    _implied_agrees(p, c, A, ment)
    for y in range(b1, b4 + NPRED):
        assert p.entails(y, A) == c.entails(y, A)


def test_register_block_conflict_at_registration():
    block = ((0, 2),)                                # (x1 | x2)
    s = Solver()
    s.set_rule_block(block, 2)
    s.add_clause([-1])
    s.add_clause([-2])
    assert s.register_block(1) is False
    assert not s.solve()


def _unsat_through_mentions(s, base):
    """Clauses over variables 2 and 3 of the block (x1 | x2), (-x1 | -x3)
    at 1 that make the problem unsatisfiable, mentioned by a mask at
    ``base`` (1 or 2): only found if variables 2 and 3 are decided."""
    d = 2 - base
    mask = 1 << (2 * d + 1) | 1 << (2 * d + 3)      # negative bits of 2 and 3
    s.add_internal([[4, 6], [5, 6], [4, 7], [5, 7]], [(base, mask)])
    return s.solve()


def _small_block_solver():
    s = Solver()
    s.set_rule_block(((0, 2), (1, 5)), 3)
    s.ensure_vars(3)
    return s


def test_register_block_mentions_either_literal_bit():
    """A mention mask with only the negative literal's bit of a variable
    mentions the variable (as in mention_blocks): it is decided, and the
    unsatisfiable problem is found so (regression: it stayed lazy)."""
    s = _small_block_solver()
    assert s.register_block(1, 1 << 3 | 1 << 5)
    assert not s._lazy[2] and not s._lazy[3]
    assert _unsat_through_mentions(s, 1) is False


def test_mention_blocks_inside_a_registered_block():
    """mention_blocks with a base inside a registered block mentions the
    variables (regression: the mask was kept at that base and lost)."""
    s = _small_block_solver()
    assert s.register_block(1)
    s.mention_blocks([(2, 3 | 12)])
    assert not s._lazy[2] and not s._lazy[3]
    assert _unsat_through_mentions(s, 2) is False


def test_mention_blocks_kept_until_an_overlapping_registration():
    """A mask kept at a base that is not where the block is registered
    later (the block starts one variable earlier) still reaches it."""
    s = Solver()
    s.set_rule_block(((0, 2), (1, 5)), 3)
    s.ensure_vars(4)
    s.mention_blocks([(2, 3 | 12)])               # variables 2 and 3
    assert s.register_block(1)
    assert not s._lazy[2] and not s._lazy[3] and s._lazy[1]
    assert _unsat_through_mentions(s, 1) is False


def test_rule_block_size_limit():
    with pytest.raises(ValueError):
        Solver().set_rule_block(((0, 2 * 64),), 65)


def test_rule_block_api_errors_and_shared_tables():
    s, t = Solver(), Solver()
    with pytest.raises(ValueError):
        s.register_block(1)
    s.set_rule_block(RULE_INTERNAL, NPRED)
    t.set_rule_block(RULE_INTERNAL, NPRED)
    assert s._rbc is t._rbc                         # built once per block
    s.set_rule_block(RULE_INTERNAL, NPRED)          # same block: no-op
    with pytest.raises(ValueError):
        s.set_rule_block(((0, 2),), 2)
    assert s.register_block(1)
    with pytest.raises(ValueError):
        s.register_block(NPRED)                     # overlaps block 1
    with pytest.raises(ValueError):
        Solver().set_rule_block(((0, 1),), 1)       # tautology


# ----------------------------------------------------------------------
# Witness reuse with theories
# ----------------------------------------------------------------------

class _NullTheory:
    def register_atom(self, v, p): pass
    def assert_lit(self, x): return None
    def check(self): return None
    def push_level(self): pass
    def pop_level(self): pass


class _NeverTrue(_NullTheory):
    """Every registered atom is theory-false."""
    def __init__(self):
        self.atoms = set()

    def register_atom(self, v, p):
        self.atoms.add(v)

    def assert_lit(self, x):
        return (False, [-x]) if x in self.atoms else None


def test_stored_model_not_reused_after_a_second_theory_registers_a_variable():
    """Registering a variable with a second theory changes the problem
    without a new theory variable: the stored model must not answer."""
    s = Solver()
    a = s.new_var()
    t1, t2 = _NullTheory(), _NeverTrue()
    s.attach_theory(t1)
    s.attach_theory(t2)
    s.register_atom(t1, a, None)
    assert s.solve([a])
    assert s.solve([a]) and s.stats()["witness_hits"] == 1   # reused
    s.register_atom(t2, a, None)
    assert not s.solve([a])
    assert s.stats()["witness_hits"] == 1


class _Implies(_NullTheory):
    """Theory propagation: once ``a`` is true, ``b`` is implied."""
    def __init__(self, a, b):
        self.a, self.b, self.trail, self.lims = a, b, [], []

    def assert_lit(self, x):
        self.trail.append(x)
        return None

    def push_level(self):
        self.lims.append(len(self.trail))

    def pop_level(self):
        del self.trail[self.lims.pop():]

    def propagate(self):
        return [(self.b, [-self.a, self.b])] if self.a in self.trail else []


def test_theory_propagates_after_registering_a_root_fixed_variable():
    """A variable fixed at root, then registered: the theory hears of it at
    once and is asked to propagate at the next propagation, even though no
    trail entry is new."""
    s = Solver()
    a, b = s.new_var(), s.new_var()
    t = _Implies(a, b)
    s.attach_theory(t)
    s.add_clause([a])
    s.propagate()
    s.register_atom(t, a, None)
    s.register_atom(t, b, None)
    assert b in s.implied([])


def test_entails_accepts_integral_float_assumptions_with_a_stored_model():
    """Assumptions go through int() in entails as in _assume, also on the
    witness path (a stored model exists after the first solve)."""
    s = Solver()
    s.add_clause([1, 2])
    assert s.solve([3])
    assert s.entails(2, [-1.0]) is True
    assert s.entails(1, [3.0]) is None
