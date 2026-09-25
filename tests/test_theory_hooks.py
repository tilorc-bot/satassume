"""The DPLL(T) hooks of satassume.solver.Solver (see satassume/theory.py)."""
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from satassume.solver import Solver
from satassume.theory import TheorySolver, PropagatingTheory

from theory_harness import (TheoryCase, ForbidTheory, Recorder, check_protocol,
                            check_solve, check_entails, check_implied)


def test_dummy_theories_satisfy_protocol():
    assert isinstance(ForbidTheory(), TheorySolver)
    assert isinstance(ForbidTheory((), "propagate"), PropagatingTheory)
    assert isinstance(Recorder(ForbidTheory()), TheorySolver)


# ----------------------------------------------------------------------
# Exact hook sequences on small inputs
# ----------------------------------------------------------------------

def test_exact_sequence_eager():
    # 1 and 2 may not both hold; clause 3 -> 1, 3 -> 2 forces 3 false.
    t = Recorder(ForbidTheory([{1, 2}], "eager"))
    c = TheoryCase(t, {1: None, 2: None, 3: None}, [[1, 2, 3], [-3, 1], [-3, 2]])
    assert c.solve() is True
    assert t.events == [
        ("register", 1), ("register", 2), ("register", 3),
        ("push",),                        # decision -1 (default phase)
        ("assert", -1, None),
        ("assert", -3, None),             # propagated by [-3, 1]
        ("assert", 2, None),              # propagated by [1, 2, 3]
        ("check", (True, [-3, -1, 2])),
        ("pop",),                         # solve() returns at root
    ]
    assert c.solver.theory_models() == [[-3, -1, 2]]
    check_protocol(t)


def test_exact_sequence_lazy_conflict_is_learnt():
    t = Recorder(ForbidTheory([{-1, -2}], "lazy"))
    c = TheoryCase(t, {1: None, 2: None}, [])
    assert c.solve() is True
    assert t.events == [
        ("register", 1), ("register", 2),
        ("push",), ("assert", -1, None),
        ("push",), ("assert", -2, None),
        ("check", (False, [1, 2])),
        ("pop",),                         # backjump to level 1
        ("assert", 2, None),              # asserted by the learnt clause [1, 2]
        ("check", (True, [-1, 2])),
        ("pop",),
    ]
    check_protocol(t)
    # The learnt theory clause is kept: the same conflict is not found again.
    t.events.clear()
    assert c.solve() is True
    assert all(e[0] != "check" or e[1][0] for e in t.events)


def test_root_facts_are_reported_once_without_levels():
    t = Recorder(ForbidTheory([{1, 2}]))
    s = Solver()
    s.add_clause([1])                     # fixed before registration
    s.attach_theory(t)
    t.solver = s
    s.propagate()
    s.register_atom(t, 1, None)           # reported at once, at level 0
    assert t.events == [("register", 1), ("assert", 1, None)]
    s.register_atom(t, 2, None)
    s.add_clause([3, -2])
    s.add_clause([-3])                    # root unit: -3, then -2 by propagation
    assert t.events[-1] == ("register", 2)   # not yet reported ...
    assert s.solve() is True               # ... reported by the next public call
    assert ("assert", -2, None) in t.events
    assert not any(e[0] == "push" for e in t.events)
    counts = check_protocol(t)
    assert counts["assert"] == 2
    t.events.clear()
    assert s.solve() is True               # root facts are not re-reported
    assert [e[0] for e in t.events] == ["check"]


def test_registration_after_cursor_is_not_double_reported():
    t = Recorder(ForbidTheory())
    s = Solver()
    s.attach_theory(t)
    t.solver = s
    s.add_clause([1])                     # on the trail, not yet reported
    s.register_atom(t, 1, None)
    assert s.solve()
    assert [e for e in t.events if e[0] == "assert"] == [("assert", 1, None)]
    check_protocol(t)


def test_root_conflict_makes_solver_unsat():
    t = Recorder(ForbidTheory([{1, -2}]))
    c = TheoryCase(t, {1: None, 2: None}, [[1], [-2]])
    assert c.solve() is False
    assert c.solve() is False
    assert c.implied() is None
    with pytest.raises(ValueError):
        c.entails(1)
    check_protocol(t)


def test_root_conflict_at_registration():
    t = ForbidTheory([{1, 2}])
    s = Solver()
    s.attach_theory(t)
    s.add_clause([1])
    s.add_clause([2])
    s.register_atom(t, 1, None)
    s.propagate()
    assert s.register_atom(t, 2, None) is False
    assert s.solve() is False


def test_implied_and_entails_see_theory_conflicts():
    # 1 & 2 forbidden: under assumption 1, entails(-2); implied([1, 2]) is None.
    for mode in ("eager", "lazy", "propagate"):
        # fresh cases: no learnt clause may do the theory's work
        t = Recorder(ForbidTheory([{1, 2}], mode))
        c = TheoryCase(t, {1: None, 2: None}, [])
        imp = c.implied([1, 2])
        if mode != "lazy":
            assert imp is None             # assert_lit conflicts reach implied()
        else:
            assert set(imp) == {1, 2}      # implied() never calls check()
        c = TheoryCase(Recorder(ForbidTheory([{1, 2}], mode)), {1: None, 2: None}, [])
        imp = c.implied([1])
        assert (-2 in imp) == (mode == "propagate")   # theory propagation too
        assert c.entails(-2, [1]) is True
        with pytest.raises(ValueError):
            c.entails(2, [1, 2])
        check_protocol(t)
        check_protocol(c.theories[0])


def test_propagation_assigns_with_reason():
    t = Recorder(ForbidTheory([{1, 2, 3}], "propagate"))
    c = TheoryCase(t, {1: None, 2: None, 3: None}, [[1], [2]])
    assert c.solver.propagate()
    assert c.solver.value(-3) is True     # a root-level theory implication
    assert c.solve()
    check_protocol(t)


def test_theories_see_only_their_atoms():
    a = Recorder(ForbidTheory([{1, 2}]))
    b = Recorder(ForbidTheory([{3, 4}]))
    c = TheoryCase([(a, {1: None, 2: None}), (b, {3: None, 4: None})],
                   clauses=[[1, 3], [2, 4], [1, 4], [2, 3]])
    assert check_solve(c, lambda asg: a.inner.consistent({v: asg[v] for v in (1, 2)})
                       and b.inner.consistent({v: asg[v] for v in (3, 4)})) is False
    for rec, mine in ((a, {1, 2}), (b, {3, 4})):
        assert {abs(e[1]) for e in rec.events if e[0] == "assert"} <= mine
        check_protocol(rec)
    # both see the same levels
    assert [e for e in a.events if e[0] in ("push", "pop")] == \
           [e for e in b.events if e[0] in ("push", "pop")]


def test_contract_violations_raise():
    class Liar(ForbidTheory):
        def check(self):
            return (False, [1])           # 1 is true, not false

    t = Liar()
    c = TheoryCase(t, {1: None}, [[1]])
    with pytest.raises(RuntimeError):
        c.solve()
    with pytest.raises(ValueError):
        Solver().register_atom(ForbidTheory(), 1, None)   # not attached
    s = Solver()
    t = ForbidTheory()
    s.attach_theory(t)
    with pytest.raises(ValueError):
        s.attach_theory(t)
    s.register_atom(t, 1, None)
    with pytest.raises(ValueError):
        s.register_atom(t, 1, None)


def test_assumptions_already_true_open_levels_too():
    # Assumption 1 is already true when level 2 opens: the dummy level is
    # still pushed so the theory level always equals the solver level.
    t = Recorder(ForbidTheory())
    c = TheoryCase(t, {1: None, 2: None}, [[-1, 2]])
    assert c.solve([1, 2])
    assert [e[0] for e in t.events if e[0] != "register"] == \
        ["push", "assert", "assert", "push", "check", "pop", "pop"]
    check_protocol(t)


# ----------------------------------------------------------------------
# Random: CNF plus forbidden partial assignments versus brute force
# ----------------------------------------------------------------------

@st.composite
def cases(draw):
    n = draw(st.integers(1, 8))
    lit = st.integers(1, n).flatmap(lambda v: st.sampled_from([v, -v]))
    clauses = draw(st.lists(st.lists(lit, min_size=1, max_size=3), max_size=14))
    atoms = sorted(draw(st.sets(st.integers(1, n), min_size=1)))
    alit = st.sampled_from(atoms).flatmap(lambda v: st.sampled_from([v, -v]))
    forbidden = draw(st.lists(st.sets(alit, min_size=1, max_size=3), max_size=6))
    mode = draw(st.sampled_from(["eager", "lazy", "propagate"]))
    assumptions = draw(st.lists(lit, max_size=3, unique_by=abs))
    query = draw(lit)
    return n, clauses, atoms, forbidden, mode, assumptions, query


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(cases())
def test_random_forbid_theory_matches_brute_force(case):
    n, clauses, atoms, forbidden, mode, assumptions, query = case
    theory = ForbidTheory(forbidden, mode)
    rec = Recorder(theory)
    c = TheoryCase(rec, {v: None for v in atoms}, clauses, nvars=n)
    oracle = theory.consistent
    check_solve(c, oracle)
    rec.mark("solve")
    check_solve(c, oracle, assumptions)
    rec.mark("solve-assumptions")
    check_entails(c, oracle, query, assumptions)
    rec.mark("entails")
    check_implied(c, oracle, assumptions)
    rec.mark("implied")
    check_solve(c, oracle)                # learnt theory clauses stay sound
    check_protocol(rec)
