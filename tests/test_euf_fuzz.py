"""Differential and stress tests for the EUF theory solver.

Everything is compared against the naive congruence closure in
``test_euf.py`` (``naive_roots``/``oracle_consistent``), never against the
implementation itself:

* ``test_conjunctions_match_oracle``: random ground problems (constants,
  distinct values, f/1, h/1, g/2 and f/2 -- the same name at two arities on
  purpose), random literals asserted in random order over random levels;
  SAT/UNSAT, ``equal`` on every pair of terms, the ``check`` model and
  every ``explain`` are checked.
* conflict clauses: (a) made of negated asserted literals, (b) inconsistent
  by themselves under the oracle, (c) minimal -- (c) lives in its own
  ``xfail(strict=False)`` test so a non-minimal explanation is reported
  (XFAIL with the counterexample) without failing the suite.
* ``test_mixed_arity_universe_matches_oracle``: a dense universe where f
  is used at arity 1 and 2 on the same arguments (curried encodings).
* ``test_backtracking_torture``: random push/assert/pop/check/propagate
  sequences; after every step the state must equal a theory rebuilt from
  scratch with the literals currently asserted.
  ``test_backtracking_torture_late_terms`` also creates terms and registers
  atoms while levels are open.
* ``test_dpll_t_matches_enumeration``: random CNF over equality atoms solved
  by satassume's CDCL solver with the theory attached (through
  ``theory_harness``), against brute-force enumeration with the oracle.
* performance guard rails (chains, towers, deep terms).

Set ``EUF_FUZZ_EXAMPLES`` to raise the Hypothesis example count for a
slow, thorough run (default 150).
"""
from __future__ import annotations

import os
import random
import sys
import time

import pytest
from hypothesis import HealthCheck, example, given, settings, strategies as st

euf = pytest.importorskip("satassume.euf")
EUFTheory = euf.EUFTheory
EqAtom = euf.EqAtom

from test_euf import (build, is_conflict, naive_roots,  # noqa: E402
                      oracle_consistent, oracle_for_harness, split_lits,
                      solver_case, lit_meaning)
from theory_harness import (check_solve, check_entails, check_implied,  # noqa: E402
                            check_protocol)

N_EXAMPLES = int(os.environ.get("EUF_FUZZ_EXAMPLES", "150"))
FUZZ = settings(max_examples=N_EXAMPLES, deadline=None,
                suppress_health_check=[HealthCheck.too_slow,
                                       HealthCheck.data_too_large])
HAS_PROPAGATE = hasattr(EUFTheory, "propagate")

# f is used at two arities on purpose (see test_euf.test_arity_is_part_of_the_head)
HEADS = [("f", 1), ("h", 1), ("g", 2), ("f", 2)]


# ======================================================================
# Strategies
# ======================================================================

@st.composite
def problems(draw, max_terms=11, max_atoms=8, values=True, min_apps=0):
    """Random ground problems.  With ``min_apps`` > 0 at least that many
    applications are made and half of the atoms are between constants
    (the equalities that make applications congruent)."""
    nconst = draw(st.integers(1, 4))
    # constants named like the heads on purpose (a head is not a constant)
    terms = [("c", ("k0", "f", "g", "h")[i]) for i in range(nconst)]
    if values:
        terms += [("v", i) for i in range(draw(st.integers(0, 2)))]
    lo = min(min_apps, max(0, max_terms - len(terms)))
    for _ in range(draw(st.integers(lo, max(lo, max_terms - len(terms))))):
        head, arity = draw(st.sampled_from(HEADS))
        args = tuple(draw(st.integers(0, len(terms) - 1)) for _ in range(arity))
        spec = ("a", head, args)
        if spec not in terms:
            terms.append(spec)
        if head == "f" and draw(st.booleans()):
            # the same first argument under f/1 and f/2: a curried encoding
            # that shares the partial application f(t) conflates the two
            other = (args[0],) if arity == 2 else (args[0], draw(st.integers(0, len(terms) - 1)))
            twin = ("a", "f", other)
            if twin not in terms:
                terms.append(twin)
    n = len(terms)
    atoms = []
    for _ in range(draw(st.integers(1, max_atoms))):
        if min_apps and nconst > 1 and draw(st.booleans()):
            i, j = draw(st.permutations(range(nconst)))[:2]
            atoms.append((i, j, True))
            continue
        i = draw(st.integers(0, n - 1))
        j = draw(st.integers(0, n - 1))
        # mostly distinct sides, positive atoms; some reflexive / negative ones
        if i == j and draw(st.integers(0, 3)):
            j = (i + 1) % n
        atoms.append((i, j, draw(st.sampled_from([True, True, True, False]))))
    return terms, atoms


@st.composite
def assertion_runs(draw, **kw):
    """A problem, one literal per atom (a subset of the atoms, random
    polarity), an order and a push-before-this-literal flag per literal."""
    kw.setdefault("min_apps", draw(st.integers(0, 4)))
    terms, atoms = draw(problems(**kw))
    vars_ = draw(st.permutations(range(1, len(atoms) + 1)))
    k = draw(st.integers(max(1, len(atoms) // 2), len(atoms)))
    lits = [v if draw(st.booleans()) else -v for v in vars_[:k]]
    pushes = [draw(st.booleans()) for _ in lits]
    return terms, atoms, lits, pushes


# ======================================================================
# Checks shared by the tests
# ======================================================================

def check_clause(terms, atoms, clause, asserted):
    """(a) negated asserted literals, (b) inconsistent by itself."""
    clause = list(clause)
    assert clause, "empty conflict clause"
    assert len(set(clause)) == len(clause), f"duplicate literals in {clause}"
    live = set(asserted)
    assert all(-l in live for l in clause), \
        f"clause {clause} has a literal whose negation was not asserted ({sorted(live)})"
    core = [-l for l in clause]
    assert not oracle_consistent(terms, atoms, core), \
        f"conflict clause {clause} is not a theory conflict (oracle finds a model)"
    eqs, neqs = split_lits(atoms, core)
    assert len(neqs) <= 1, f"conflict {clause} uses {len(neqs)} disequalities"


def clause_is_minimal(terms, atoms, clause):
    core = [-l for l in clause]
    for k in range(len(core)):
        if not oracle_consistent(terms, atoms, core[:k] + core[k + 1:]):
            return False, core[k]
    return True, None


def check_explain(th, terms, atoms, ids, i, j, asserted):
    ex = list(th.explain(ids[i], ids[j]))
    live = set(asserted)
    assert set(ex) <= live, f"explain({i}, {j}) = {ex} not within asserted {sorted(live)}"
    eqs, neqs = split_lits(atoms, ex)
    assert not neqs, f"explain({i}, {j}) = {ex} contains a disequality"
    roots = naive_roots(terms, eqs)
    assert roots[i] == roots[j], f"explain({i}, {j}) = {ex} does not imply the equality"
    return ex


def check_model(model, terms, atoms, ids, asserted):
    """The check() model must be a congruence model of the asserted literals
    over every interned term."""
    assert isinstance(model, dict)
    cls = [model[t] for t in ids]
    for l in asserted:
        e, i, j = lit_meaning(atoms, l)
        if e:
            assert cls[i] == cls[j], f"model splits asserted equality {l}"
        else:
            assert cls[i] != cls[j], f"model merges asserted disequality {l}"
    vals = [cls[i] for i, t in enumerate(terms) if t[0] == "v"]
    assert len(vals) == len(set(vals)), "model merges distinct values"
    apps = [i for i, t in enumerate(terms) if t[0] == "a"]
    for p in apps:
        for q in apps:
            tp, tq = terms[p], terms[q]
            if (tp[1] == tq[1] and len(tp[2]) == len(tq[2])
                    and all(cls[x] == cls[y] for x, y in zip(tp[2], tq[2]))):
                assert cls[p] == cls[q], f"model is not congruence-closed at {tp}, {tq}"


def check_state(th, terms, atoms, ids, asserted):
    """equal() on every pair equals the oracle closure of ``asserted``."""
    eqs, _ = split_lits(atoms, asserted)
    roots = naive_roots(terms, eqs)
    n = len(terms)
    for i in range(n):
        for j in range(i + 1, n):
            got = th.equal(ids[i], ids[j])
            want = roots[i] == roots[j]
            assert got == want, (f"equal(t{i}, t{j}) = {got}, oracle {want}; "
                                 f"terms {terms}, asserted {asserted}")
            assert (th.find(ids[i]) == th.find(ids[j])) == want


def check_propagations(th, terms, atoms, asserted):
    if not HAS_PROPAGATE:
        return
    live = set(asserted)
    for lit, reason in th.propagate():
        reason = list(reason)
        assert lit in reason, (lit, reason)
        assert -lit not in live, f"propagated {lit} although its negation is asserted"
        others = [l for l in reason if l != lit]
        assert all(-l in live for l in others), \
            f"reason {reason} for {lit} has a literal that is not false"
        assert not oracle_consistent(terms, atoms, [-l for l in others] + [-lit]), \
            f"reason {reason} does not imply {lit}"


# ======================================================================
# Random conjunctions against the oracle
# ======================================================================

@FUZZ
@given(assertion_runs())
def test_conjunctions_match_oracle(run):
    terms, atoms, lits, pushes = run
    th, ids = build(terms, atoms)
    asserted = []
    levels = 0
    conflict = None
    for lit, push in zip(lits, pushes):
        if push:
            th.push_level()
            levels += 1
        asserted.append(lit)
        r = th.assert_lit(lit)
        if is_conflict(r):
            assert not oracle_consistent(terms, atoms, asserted), \
                f"assert_lit({lit}) reported a conflict on a consistent set {asserted}"
            conflict = r[1]
            break
        assert r is None, f"assert_lit returned {r!r}"
    if conflict is None:
        r = th.check()
        consistent = oracle_consistent(terms, atoms, asserted)
        if consistent:
            assert r is not None and r[0] is True, \
                f"check() = {r!r} on the consistent set {asserted}"
            check_model(r[1], terms, atoms, ids, asserted)
            check_state(th, terms, atoms, ids, asserted)
            eqs, _ = split_lits(atoms, asserted)
            roots = naive_roots(terms, eqs)
            for i in range(len(terms)):
                for j in range(len(terms)):
                    if roots[i] == roots[j]:
                        check_explain(th, terms, atoms, ids, i, j, asserted)
            check_propagations(th, terms, atoms, asserted)
        else:
            assert is_conflict(r), \
                f"check() = {r!r} on the inconsistent set {asserted} (terms {terms})"
            conflict = r[1]
    if conflict is not None:
        check_clause(terms, atoms, conflict, asserted)
    for _ in range(levels):
        th.pop_level()


MIXED = ([("c", n) for n in ("a", "b", "c")]
         + [("a", "f", (i,)) for i in range(3)]
         + [("a", "f", (i, j)) for i in range(3) for j in range(3)])


@FUZZ
@given(st.lists(st.tuples(st.integers(0, len(MIXED) - 1), st.integers(0, len(MIXED) - 1),
                          st.booleans()), min_size=1, max_size=6))
def test_mixed_arity_universe_matches_oracle(lits):
    """A dense universe where f is used at arity 1 and 2 on the same
    arguments: every f(t) is also the first half of f(t, u).  Targets
    curried encodings that share partial applications across arities."""
    atoms = [(i, j, True) for i, j, _ in lits]
    asserted = [(k + 1) if pos else -(k + 1) for k, (_, _, pos) in enumerate(lits)]
    th, ids = build(MIXED, atoms)
    r = None
    for l in asserted:
        r = th.assert_lit(l)
        if is_conflict(r):
            break
    if not is_conflict(r):
        r = th.check()
    if oracle_consistent(MIXED, atoms, asserted):
        assert not is_conflict(r), f"conflict {r} on consistent {lits}"
        check_state(th, MIXED, atoms, ids, asserted)
    else:
        assert is_conflict(r), f"missed inconsistency of {lits}"
        check_clause(MIXED, atoms, r[1], asserted)


@pytest.mark.xfail(strict=False, reason="minimal explanations are preferred, "
                   "not required; an XFAIL here shows a non-minimal one")
@settings(max_examples=N_EXAMPLES, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(assertion_runs(max_terms=8, max_atoms=6))
@example(run=([("c", "k0"), ("a", "f", (0,)), ("a", "f", (1,))],   # k0 = f(f(k0)), then
               [(0, 1, True), (0, 2, False)], [-2, 1], [False, False]))  # k0 = f(k0)
def test_conflicts_and_explanations_are_minimal(run):
    terms, atoms, lits, _ = run
    th, ids = build(terms, atoms)
    asserted = []
    for lit in lits:
        asserted.append(lit)
        r = th.assert_lit(lit)
        if is_conflict(r):
            break
    else:
        r = th.check()
        if not is_conflict(r):
            eqs, _ = split_lits(atoms, asserted)
            roots = naive_roots(terms, eqs)
            for i in range(len(terms)):
                for j in range(i + 1, len(terms)):
                    if roots[i] == roots[j]:
                        ex = list(th.explain(ids[i], ids[j]))
                        for k in range(len(ex)):
                            e2, _ = split_lits(atoms, ex[:k] + ex[k + 1:])
                            r2 = naive_roots(terms, e2)
                            assert r2[i] != r2[j], \
                                f"explain(t{i}, t{j}) = {ex}: {ex[k]} is redundant; terms {terms}"
            return
    ok, redundant = clause_is_minimal(terms, atoms, r[1])
    assert ok, f"conflict {r[1]} is not minimal: {-redundant} is redundant; terms {terms}"


def test_minimality_reference_example_10():
    """Nieuwenhuis & Oliveras RTA'05 Example 10, where the classical proof
    forest explanation is redundant (30010 accepted it).  Reported via
    xfail rather than failing, like the fuzz test."""
    terms = [("c", "a1"), ("c", "b1"), ("c", "c1"), ("c", "a"), ("c", "b"), ("c", "c"),
             ("a", "f", (0,)), ("a", "f", (1,)), ("a", "f", (2,))]
    atoms = [(0, 1, True), (0, 2, True), (6, 3, True), (7, 4, True), (8, 5, True)]
    th, ids = build(terms, atoms)
    for lit in (1, 2, 3, 4, 5):
        assert th.assert_lit(lit) is None
    ex = check_explain(th, terms, atoms, ids, 3, 5, [1, 2, 3, 4, 5])
    if set(ex) != {2, 3, 5}:
        pytest.xfail(f"explain(a, c) = {sorted(ex)}, minimal is [2, 3, 5]")


# ======================================================================
# Backtracking torture
# ======================================================================

ops = st.lists(st.one_of(
    st.just(("push",)), st.just(("pop",)), st.just(("check",)),
    st.just(("propagate",)),
    st.tuples(st.just("assert"), st.integers(0, 63), st.booleans()),
    st.tuples(st.just("assert"), st.integers(0, 63), st.booleans()),
), min_size=15, max_size=45)


@FUZZ
@given(st.integers(0, 4).flatmap(
    lambda m: problems(max_terms=10, max_atoms=9, min_apps=m)), ops)
def test_backtracking_torture(problem, script):
    terms, atoms = problem
    th, ids = build(terms, atoms)
    levels = [[]]
    blocked = False

    def current():
        return [l for lv in levels for l in lv]

    def compare_with_rebuild():
        cur = current()
        fresh, fids = build(terms, atoms)
        for l in cur:
            assert not is_conflict(fresh.assert_lit(l))
        n = len(terms)
        for i in range(n):
            for j in range(i + 1, n):
                assert th.equal(ids[i], ids[j]) == fresh.equal(fids[i], fids[j]), \
                    f"after {script}: equal(t{i}, t{j}) differs from a rebuilt theory"
        check_state(th, terms, atoms, ids, cur)

    for op in script:
        if blocked and op[0] != "pop":
            continue
        if op[0] == "push":
            th.push_level()
            levels.append([])
        elif op[0] == "pop":
            if len(levels) == 1:
                continue
            th.pop_level()
            levels.pop()
            blocked = False
        elif op[0] == "check":
            r = th.check()
            cur = current()
            if oracle_consistent(terms, atoms, cur):
                assert r is not None and r[0] is True, f"check() = {r!r} on {cur}"
                check_model(r[1], terms, atoms, ids, cur)
            else:
                assert is_conflict(r)
                check_clause(terms, atoms, r[1], cur)
                blocked = True
        elif op[0] == "propagate":
            check_propagations(th, terms, atoms, current())
        else:
            var = op[1] % len(atoms) + 1
            if any(abs(l) == var for l in current()):
                continue
            lit = var if op[2] else -var
            if len(levels) == 1 and not oracle_consistent(terms, atoms, current() + [lit]):
                continue            # keep level 0 consistent (a root conflict ends the run)
            levels[-1].append(lit)
            cur = current()
            r = th.assert_lit(lit)
            if is_conflict(r):
                assert not oracle_consistent(terms, atoms, cur), \
                    f"assert_lit({lit}) conflict on consistent {cur}"
                check_clause(terms, atoms, r[1], cur)
                blocked = True
            elif not oracle_consistent(terms, atoms, cur):
                r = th.check()
                assert is_conflict(r), f"check() missed the inconsistency of {cur}"
                check_clause(terms, atoms, r[1], cur)
                blocked = True
        if not blocked:
            compare_with_rebuild()
    while len(levels) > 1:
        th.pop_level()
        levels.pop()
    compare_with_rebuild()
    r = th.check()
    assert r is not None and r[0] is True


late_ops = st.lists(st.one_of(
    st.just(("push",)), st.just(("pop",)), st.just(("check",)),
    st.just(("propagate",)), st.just(("intern",)), st.just(("intern",)),
    st.tuples(st.just("assert"), st.integers(0, 63), st.booleans()),
    st.tuples(st.just("assert"), st.integers(0, 63), st.booleans()),
), min_size=20, max_size=50)


@FUZZ
@given(problems(max_terms=9, max_atoms=8, min_apps=3), st.integers(1, 3), late_ops)
def test_backtracking_torture_late_terms(problem, n0, script):
    """Terms and atoms are created while levels are open (the adapter may
    intern lazily).  A term made at a level that is later popped must
    survive with the congruences of the remaining state."""
    terms, atoms = problem
    th = EUFTheory()
    ids = []
    registered = []
    levels = [[]]
    blocked = False

    def intern_next():
        i = len(ids)
        t = terms[i]
        if t[0] == "c":
            ids.append(th.term(t[1]))
        elif t[0] == "v":
            ids.append(th.value(t[1]))
        else:
            ids.append(th.term(t[1], tuple(ids[k] for k in t[2])))
        for k, (a, b, pos) in enumerate(atoms):
            if k + 1 not in registered and a < len(ids) and b < len(ids):
                th.register_atom(k + 1, EqAtom(ids[a], ids[b], pos))
                registered.append(k + 1)

    def current():
        return [l for lv in levels for l in lv]

    def compare():
        n = len(ids)
        cur = current()
        fresh = EUFTheory()
        fids = build(terms[:n], [], fresh)[1]
        for k in registered:
            a, b, pos = atoms[k - 1]
            fresh.register_atom(k, EqAtom(fids[a], fids[b], pos))
        for l in cur:
            assert not is_conflict(fresh.assert_lit(l))
        for i in range(n):
            for j in range(i + 1, n):
                assert th.equal(ids[i], ids[j]) == fresh.equal(fids[i], fids[j]), \
                    f"after {script}: equal(t{i}, t{j}) differs from a rebuilt theory"
        check_state(th, terms[:n], atoms, ids, cur)

    while len(ids) < min(n0, len(terms)):
        intern_next()
    for op in script:
        if blocked and op[0] != "pop":
            continue
        n = len(ids)
        if op[0] == "intern":
            if n < len(terms):
                intern_next()
        elif op[0] == "push":
            th.push_level()
            levels.append([])
        elif op[0] == "pop":
            if len(levels) == 1:
                continue
            th.pop_level()
            levels.pop()
            blocked = False
        elif op[0] == "check":
            r = th.check()
            cur = current()
            if oracle_consistent(terms[:n], atoms, cur):
                assert r is not None and r[0] is True, f"check() = {r!r} on {cur}"
                check_model(r[1], terms[:n], atoms, ids, cur)
            else:
                assert is_conflict(r)
                check_clause(terms[:n], atoms, r[1], cur)
                blocked = True
        elif op[0] == "propagate":
            check_propagations(th, terms[:n], atoms, current())
        else:
            if not registered:
                continue
            var = registered[op[1] % len(registered)]
            if any(abs(l) == var for l in current()):
                continue
            lit = var if op[2] else -var
            if len(levels) == 1 and not oracle_consistent(terms[:n], atoms, current() + [lit]):
                continue
            levels[-1].append(lit)
            cur = current()
            r = th.assert_lit(lit)
            if is_conflict(r):
                assert not oracle_consistent(terms[:n], atoms, cur), \
                    f"assert_lit({lit}) conflict on consistent {cur}"
                check_clause(terms[:n], atoms, r[1], cur)
                blocked = True
            elif not oracle_consistent(terms[:n], atoms, cur):
                r = th.check()
                assert is_conflict(r), f"check() missed the inconsistency of {cur}"
                check_clause(terms[:n], atoms, r[1], cur)
                blocked = True
        if not blocked:
            compare()
    while len(levels) > 1:
        th.pop_level()
        levels.pop()
    compare()


# ======================================================================
# End to end through the CDCL solver
# ======================================================================

@st.composite
def cnf_problems(draw):
    terms, atoms = draw(problems(max_terms=9, max_atoms=7,
                                 min_apps=draw(st.integers(0, 4))))
    nv = len(atoms) + draw(st.integers(0, 2))           # a couple of plain variables
    lit = st.builds(lambda v, s: v if s else -v, st.integers(1, nv), st.booleans())
    clauses = draw(st.lists(st.lists(lit, min_size=1, max_size=3), max_size=7))
    return terms, atoms, clauses, nv


@FUZZ
@given(cnf_problems(), st.data())
def test_dpll_t_matches_enumeration(prob, data):
    terms, atoms, clauses, nv = prob
    case, rec, cons = solver_case(terms, atoms, clauses)
    case.solver.ensure_vars(nv)
    case.nvars = max(case.nvars, nv)
    check_solve(case, cons)
    for v in range(1, len(atoms) + 1):
        assumptions = data.draw(st.lists(
            st.builds(lambda u, s: u if s else -u, st.integers(1, nv), st.booleans()),
            max_size=3, unique_by=abs))
        check_entails(case, cons, v, assumptions)
    check_implied(case, cons, data.draw(st.lists(
        st.builds(lambda u, s: u if s else -u, st.integers(1, nv), st.booleans()),
        max_size=3, unique_by=abs)))
    check_protocol(rec)


@settings(max_examples=max(20, N_EXAMPLES // 3), deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(problems(max_terms=9, max_atoms=6))
def test_every_full_assignment_through_solver(problem):
    """solve(assumptions = a full assignment of the atoms) is exactly the
    oracle's verdict on that conjunction: check() is complete."""
    terms, atoms = problem
    case, rec, cons = solver_case(terms, atoms, [])
    n = len(atoms)
    for mask in range(1 << n):
        lits = [(v if mask >> (v - 1) & 1 else -v) for v in range(1, n + 1)]
        assert case.solve(lits) == oracle_consistent(terms, atoms, lits), lits
    check_protocol(rec)


# ======================================================================
# Performance guard rails (pure Python; budgets are generous)
# ======================================================================

def _timed(fn, budget):
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    assert dt < budget, f"took {dt:.2f}s, budget {budget}s"
    return out


def test_perf_chain_levels_balanced():
    # A 400-link chain asserted one link per level, in random order, under
    # the disequality of its ends; then everything popped.  Five rounds.
    n = 400
    rng = random.Random(11)
    th = EUFTheory()
    v = [th.term(f"a{i}") for i in range(n)]
    for i in range(n - 1):
        th.register_atom(i + 1, EqAtom(v[i], v[i + 1]))
    th.register_atom(n, EqAtom(v[0], v[n - 1]))
    order = list(range(1, n))

    def run():
        for _ in range(5):
            rng.shuffle(order)
            th.push_level()
            depth = 1
            th.assert_lit(-n)
            r = None
            for lit in order:
                th.push_level()
                depth += 1
                r = th.assert_lit(lit)
                if is_conflict(r):
                    break
            if not is_conflict(r):
                r = th.check()
            assert is_conflict(r)
            for _ in range(depth):
                th.pop_level()
            assert not th.equal(v[0], v[1])
    _timed(run, 6.0)


def test_perf_function_towers():
    depth = 300

    def run():
        th = EUFTheory()
        a, b = th.term("a"), th.term("b")
        ta, tb = [a], [b]
        for _ in range(depth):
            ta.append(th.term("f", (ta[-1],)))
            tb.append(th.term("f", (tb[-1],)))
        th.register_atom(1, EqAtom(a, b))
        th.register_atom(2, EqAtom(ta[-1], tb[-1], False))
        for _ in range(10):
            th.push_level()
            assert th.assert_lit(2) is None
            th.push_level()
            r = th.assert_lit(1)
            if not is_conflict(r):
                r = th.check()
            assert is_conflict(r) and set(r[1]) == {-1, -2}
            th.pop_level()
            assert not th.equal(ta[5], tb[5])
            th.pop_level()
        th.push_level()
        th.assert_lit(1)
        assert all(th.equal(x, y) for x, y in zip(ta, tb))
        assert list(th.explain(ta[-1], tb[-1])) == [1]
        th.pop_level()
    _timed(run, 4.0)


def test_perf_deep_term_no_recursion_limit():
    # REF-FLAW 30010/30327-recursion: _flatten recursed once per nesting
    # level.  Terms are interned bottom-up here, but merging/explaining a
    # deep tower must not recurse per level either.
    depth = max(3000, sys.getrecursionlimit() * 2)

    def run():
        th = EUFTheory()
        a, b = th.term("a"), th.term("b")
        ta, tb = a, b
        for _ in range(depth):
            ta = th.term("f", (ta,))
            tb = th.term("f", (tb,))
        th.register_atom(1, EqAtom(a, b))
        th.push_level()
        assert th.assert_lit(1) is None
        assert th.equal(ta, tb)
        assert list(th.explain(ta, tb)) == [1]
        th.pop_level()
        assert not th.equal(ta, tb)
    _timed(run, 10.0)


def test_perf_many_disequalities():
    n = 250
    rng = random.Random(3)

    def run():
        th = EUFTheory()
        v = [th.term(f"x{i}") for i in range(n)]
        var = 0
        neqs = []
        for _ in range(600):
            i, j = rng.sample(range(n), 2)
            var += 1
            th.register_atom(var, EqAtom(v[i], v[j]))
            neqs.append(var)
        eq_first = var + 1
        for i in range(n - 1):
            var += 1
            th.register_atom(var, EqAtom(v[i], v[i + 1]))
        th.push_level()
        for l in neqs:
            assert th.assert_lit(-l) is None
        r = None
        for l in range(eq_first, var + 1):
            th.push_level()
            r = th.assert_lit(l)
            if is_conflict(r):
                break
        if not is_conflict(r):
            r = th.check()
        assert is_conflict(r)
        assert sum(1 for l in r[1] if l in set(neqs)) == 1
        for _ in range(l - eq_first + 2):
            th.pop_level()
    _timed(run, 6.0)


def test_perf_through_solver_chain():
    n = 200
    terms = [("c", f"a{i}") for i in range(n)]
    atoms = [(i, i + 1, True) for i in range(n - 1)] + [(0, n - 1, True)]
    clauses = [[v] for v in range(1, n)] + [[-n]]

    def run():
        case, rec, cons = solver_case(terms, atoms, clauses)
        assert case.solve() is False
        check_protocol(rec)
    _timed(run, 6.0)


def test_perf_through_solver_disjunctive_chain():
    # a_i = a_{i+1} or a_i = b_i (b_i = b_{i+1}); a_0 != a_n forces search.
    n = 40
    terms = [("c", f"a{i}") for i in range(n + 1)] + [("c", f"b{i}") for i in range(n + 1)]
    atoms = []
    clauses = []
    for i in range(n):
        atoms.append((i, i + 1, True))
        atoms.append((i, n + 1 + i, True))
        clauses.append([len(atoms) - 1, len(atoms)])
    for i in range(n):
        atoms.append((n + 1 + i, n + 2 + i, True))
        clauses.append([len(atoms)])
    atoms.append((n + 1 + n, n, True))         # b_n = a_n
    clauses.append([len(atoms)])
    atoms.append((0, n, True))
    clauses.append([-len(atoms)])              # a_0 != a_n

    def run():
        case, rec, cons = solver_case(terms, atoms, clauses)
        r = case.solve()
        # a_0 = b_0 = ... = b_n = a_n is forced unless some a_i = a_{i+1}
        # route is used; either way a_0 = a_n: UNSAT.
        assert r is False
        check_protocol(rec)
    _timed(run, 10.0)


# ======================================================================
# Suspected flaws in the SymPy references and the tests that target them
# ======================================================================

REFERENCE_FLAWS = {
    "30010-currying": (
        "f(a, b) is curried to EUFApp(EUFApp(f, a), b) with the head f a term, "
        "so the unary f(a) is the partial application inside f(a, c): "
        "f(a) = f(b) wrongly yields f(a, c) = f(b, c) when one name is used at "
        "two arities (legal for SymPy Functions); a constant named like a head "
        "is the head.  The 30010 test only documents 'give each head a single "
        "arity'.",
        ["test_euf.py::test_arity_is_part_of_the_head",
         "test_euf.py::test_arity_unary_value_does_not_leak_into_binary",
         "test_euf.py::test_constant_named_like_a_head_is_a_different_symbol",
         "test_euf_fuzz.py::test_mixed_arity_universe_matches_oracle",
         "test_euf_fuzz.py (HEADS uses f at arity 1 and 2 in every random test)",
         "test_euf_adapter.py::test_mixed_arity_function_is_not_curried"]),
    "30010-rebuild": (
        "backtrack(n) rebuilds the whole closure from the remaining equations: "
        "O(everything) per backtrack, no push/pop levels, and it is the only "
        "undo tested (against a rebuild, so it could not find an undo bug).",
        ["test_euf_fuzz.py::test_backtracking_torture",
         "test_euf_fuzz.py::test_backtracking_torture_late_terms",
         "test_euf.py::test_term_made_at_a_popped_level_keeps_congruence",
         "test_euf_fuzz.py::test_perf_chain_levels_balanced",
         "test_euf_fuzz.py::test_perf_function_towers",
         "test_euf.py::test_term_ids_survive_push_pop"]),
    "30010-no-disequalities": (
        "the engine has no disequalities or distinct constants at all, so "
        "none of its tests exercise conflicts; 30327 adds disequalities but "
        "never treats numbers as distinct (x = 1 & x = 2 is SAT there).",
        ["test_euf.py::test_values_are_distinct",
         "test_euf.py::test_value_clash_through_congruence",
         "test_euf_adapter.py::test_distinct_numbers"]),
    "30010-explain-not-minimal": (
        "classical proof-forest explain is accepted as possibly redundant "
        "(Example 10); nothing measures redundancy of conflict clauses.",
        ["test_euf_fuzz.py::test_conflicts_and_explanations_are_minimal (xfail, non-strict)",
         "test_euf_fuzz.py::test_minimality_reference_example_10"]),
    "30010-oracle-first-order-only": (
        "the reference differential oracle is first order and 'only sound "
        "because every head is used at a single arity', so the random tests "
        "cannot catch the currying flaw; explanations are checked by the "
        "engine under test (EUFCongruenceClosure(expl).are_congruent), not "
        "independently.",
        ["test_euf.py::naive_roots (arity-aware, independent)",
         "test_euf_fuzz.py::check_explain / check_clause"]),
    "30010/30327-recursion": (
        "_flatten recurses once per nesting level; a term nested deeper than "
        "the recursion limit raises RecursionError.",
        ["test_euf_fuzz.py::test_perf_deep_term_no_recursion_limit",
         "test_euf_adapter.py::test_deep_expression"]),
    "30010-queries-mutate": (
        "are_congruent/explain call _flatten, so a query interns new terms and "
        "may trigger merges; the 30010 test 'explain() is not read-only' "
        "accepts that.  Here queries go through term ids only and check() is "
        "tested not to change what pop restores.",
        ["test_euf.py::test_check_does_not_change_state",
         "test_euf_fuzz.py::test_backtracking_torture (check/propagate ops)"]),
    "30327-sticky-result": (
        "EUFTheorySolver caches the first conflict in self.result and only "
        "reset() clears it; there is no push/pop, so the solver rebuilt the "
        "theory at every full assignment (dpll2 asserts everything then "
        "check()+reset()); an assert_lit conflict is ignored by dpll2's loop "
        "(it breaks and calls check()).",
        ["test_euf.py::test_pop_after_conflict_restores_consistency",
         "test_euf.py::test_pop_after_value_conflict",
         "test_euf_fuzz.py::test_backtracking_torture"]),
    "30327-eq-literal-map": (
        "eq_literal is keyed by Q.eq(lhs, rhs): two atoms for the same "
        "equation (Q.eq(a, b) and ~Q.ne(a, b)) share one entry, so the "
        "explanation can name a literal that was not asserted (or was "
        "retracted).",
        ["test_euf.py::test_same_merge_twice_on_different_levels",
         "test_euf.py::test_tuple_payload",
         "test_euf_adapter.py::test_eq_and_not_ne_are_both_explained"]),
    "30327-binders": (
        "_flatten treats every non-atomic expression as f(args), including "
        "Sum/Integral/Subs whose arguments bind variables: from x = y it "
        "derives Sum(x, (x, 1, 2)) = Sum(y, (x, 1, 2)), i.e. 3 = 2*x, which "
        "is unsound.",
        ["test_euf_adapter.py::test_binders_are_not_congruent",
         "test_euf_adapter.py::test_engine_nan_and_binders_never_wrong"]),
    "30327-reflexive-nan": (
        "Q.eq(t, t) is decided True syntactically, also for t = nan where "
        "SymPy's Eq(nan, nan) is False.",
        ["test_euf_adapter.py::test_nan_is_not_reflexive"]),
    "30327-numbers-by-structure": (
        "numbers become fresh opaque constants keyed by the expression; "
        "numerically equal numbers of different types (2 and 2.0) must not "
        "be distinct values if values are made distinct.",
        ["test_euf_adapter.py::test_equal_numbers_of_different_types"]),
    "30327-substitution-scope": (
        "test_eq_ask.py makes predicate substitution (Q.prime(x) from "
        "Q.eq(x, y) & Q.prime(y)) the main feature via reification "
        "Q.prime(x) = TRUE; SymPy marks this as needing a redesign "
        "(issue 25485) and it is out of scope here: those queries must stay "
        "None, never False.",
        ["test_euf_adapter.py::test_equality_failing_cases_are_not_wrong",
         "test_euf_adapter.py::test_engine_equality_failing_is_not_wrong"]),
    "30327-random-test-unseeded": (
        "test_random_formulas_match_brute_force uses sympy.core.random with "
        "25 cases and no shrinking; failures are not reproducible or minimal.",
        ["test_euf_fuzz.py (Hypothesis, shrinking)"]),
}


def test_reference_flaw_table_points_at_existing_tests():
    here = os.path.dirname(__file__)
    for key, (_, targets) in REFERENCE_FLAWS.items():
        for t in targets:
            if "::" not in t or " " in t.split("::")[1]:
                continue
            fname, name = t.split("::")
            with open(os.path.join(here, fname)) as fh:
                assert f"def {name}(" in fh.read(), (key, t)
