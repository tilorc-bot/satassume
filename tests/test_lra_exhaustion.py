"""Integer branch and bound runs out of budget along a path that depends
on the solver state: a query's answer must still be the one a fresh
engine gives.

``LRATheory.check`` branches at most ``BRANCH_BUDGET`` times; which checks
run and in which order they branch depends on the tableau basis and the
learnt clauses the session carries.  When a contextual session was reused
across queries both directions happened: a warm None where a fresh engine
is definite (the warm search ran out) and a warm definite answer where a
fresh engine gives None (the fresh search runs out); the engine then
answered such queries again in a freshly built session.  Since issue #97
every contextual query is answered in the session built for its set
(``Engine._build_context``) and that session is discarded, so the path is
the fresh engine's by construction; these tests pin that on the streams
that used to diverge, and that every query builds exactly one session.

With constants in the LRA payloads the theory can give up (an undecided
sign, constfield's size budget) at points the search path decides; the
same argument covers it.  ``LRATheory.certified`` (no search over the
atoms can give up) is tested below on its own.
"""
from fractions import Fraction as F

import pytest

from sympy import E, And, Q, Rational, pi, sqrt, symbols

from satassume.theories.lra import constfield as cf
from satassume.theories.lra import lra
from satassume.engine import CONSISTENT, INCONSISTENT, UNKNOWN, _exhausted
from satassume.theories.lra.lra import Integral, LRATheory, constraint
from satassume.sympy_api import Engine, _formula, ask

x, y, u0, v0, u1, v1, n = symbols('x y u0 v0 u1 v1 n', integer=True)
A = Q.gt(x, y + Rational(1, 3)) & Q.ge(y, 0) & Q.le(y, 5)
B = And(*[Q.gt(u, v + Rational(1, 3)) & Q.ge(v, 0) & Q.ne(u, v + 1)
          for u, v in ((u0, v0), (u1, v1))])
C = And(*[Q.ge(u, Rational(1, 2)) & Q.le(u, 100) & Q.ne(u, 1) & Q.ne(u, 2)
          & Q.ne(u, 3) for u in (u0, u1)])
QUERIES = [Q.ge(x, y + 1), Q.gt(u0, 1), Q.ge(u0, v0 + 2), Q.ge(u0, 4), Q.gt(u1, 1)]


def _a(p, s, e):
    try:
        return ask(p, s, e)
    except ValueError:
        return "raise"


def _reached(p, s, e, flag):
    """Whether the session ``e`` answers ``p`` under ``s`` in reaches the
    path ``flag`` detects (``_exhausted``: this query's branch and bound
    ran out of budget; ``_uncertified``: its atoms are not certified).
    ``Engine.ask`` discards that session, so it is built here exactly as
    ``ask`` builds it (``_build_context``, then ``_ask``) and inspected;
    ``exhausted`` is cleared between the two (the set's own check may run
    out, and only the caller clears the flag) so that it reports the
    query's search.  The sweeps count the queries for which this holds,
    so that ``out == []`` is not vacuous."""
    rel = bool(e.relation_specs)
    try:
        sess, lits = e._build_context(_formula(s, rel, True))
        for t in sess.solver._theories:
            t.exhausted = False
        e._ask(sess, lits, _formula(p, rel), True)
    except ValueError:
        return False
    return flag(sess)


def _uncertified(s):
    """An LRA theory of the session is not certified (a search over its
    atoms can give up)."""
    return any(not t.certified for t in s.solver._theories
               if isinstance(t, LRATheory))


def test_warm_equals_fresh(monkeypatch):
    # on main (80c91c0): warm True (the first query's search left a basis
    # and clauses along which the second stays within the budget), fresh
    # None (the fresh search runs out)
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 5)
    e = Engine()
    ask(Q.gt(u0, 1), A & C, e)
    warm = ask(Q.ge(u0, 4), A & C, e)
    fresh = ask(Q.ge(u0, 4), A & C, Engine())
    assert warm == fresh
    assert fresh is None
    assert not e._context_sessions           # no session survives a query


def _divergences(flag=_exhausted):
    """Warm-versus-fresh disagreements over every ordered pair of QUERIES
    under the sets, the most sessions any engine kept between queries
    (0 since issue #97), and the number of warm queries whose session
    reached the path ``flag`` detects (:func:`_reached`)."""
    return _sweep((A & B, A & C), QUERIES, flag)


def test_no_warm_fresh_divergence_budget_5(monkeypatch):
    # on main (80c91c0): 1 warm definite/fresh None (A & C, Q.gt(u0, 1)
    # then Q.ge(u0, 4)); budgets 1-4, 7-24 show none there with this probe
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 5)
    out, kept, reached = _divergences()
    assert out == []
    assert kept == 0
    assert reached >= 1                      # the budget did run out


def test_no_warm_fresh_divergence_budget_6(monkeypatch):
    # on main (80c91c0): the same divergence as at budget 5
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 6)
    out, kept, reached = _divergences()
    assert out == []
    assert kept == 0
    assert reached >= 1                      # the budget did run out


def test_exhausted_set_check_is_unknown(monkeypatch):
    # 0 <= n <= 1, n != 0, n != 1 over the integers needs two branchings
    d = _formula(Q.ge(n, 0) & Q.le(n, 1) & Q.ne(n, 0) & Q.ne(n, 1), True)
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 1)
    assert Engine().verdict(d) is UNKNOWN          # was CONSISTENT
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 2)
    assert Engine().verdict(d) is INCONSISTENT
    assert Engine().verdict(_formula(A, True)) is CONSISTENT


# -- constants ----------------------------------------------------------------

def _sweep(sets, queries, flag=_exhausted):
    """Warm-versus-fresh disagreements over every ordered pair of
    ``queries`` under ``sets``, the most sessions any engine kept between
    queries (0 since issue #97), and the number of warm queries whose
    session reached the path ``flag`` detects (:func:`_reached`)."""
    out, kept, reached = [], 0, 0
    for s in sets:
        fresh = {p: _a(p, s, Engine()) for p in queries}
        for p1 in queries:
            for p2 in queries:
                e = Engine()
                _a(p1, s, e)
                w = _a(p2, s, e)
                kept = max(kept, len(e._context_sessions))
                reached += _reached(p2, s, e, flag)
                if w != fresh[p2]:
                    out.append((s, p1, p2, w, fresh[p2]))
    return out, kept, reached


def _t(c):
    return (Q.gt(x, y + c) & Q.ge(y, 0) & Q.le(y, 5) & Q.lt(x, 3 * c + 9)
            & Q.gt(u0, c) & Q.lt(u0, x - c))


CQUERIES = [Q.ge(x, y + 1), Q.ge(x, y + 2), Q.ge(u0, 2), Q.lt(x, 13), Q.ge(u0, y),
            Q.gt(x - u0, 1)]


def test_constants_no_warm_fresh_divergence(monkeypatch):
    # certified (pi, 1/pi: rational rows, bounds in Q + Q*pi or Q + Q/pi)
    # and not (sqrt(2): algebraic; pi and E together)
    sets = [_t(pi / 3), _t(1 / pi), _t(7 * pi / 2), _t(sqrt(2) / 3), _t((pi + E) / 7)]
    out, kept, reached = _sweep(sets, CQUERIES)
    assert out == []
    assert kept == 0
    # with the basis encoding the default budget suffices for every query
    # here; a smaller one makes the uncertified sets' searches run out
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 10)
    out, kept, reached = _sweep(sets, CQUERIES)
    assert out == []
    assert kept == 0
    assert reached >= 1                      # the uncertified sets' searches ran out


def test_constants_no_warm_fresh_divergence_budget_3(monkeypatch):
    # the integer part runs out of budget, with constants in the payloads;
    # a row with a pi coefficient is never certified
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 3)
    sets = [Q.gt(x, y + c) & Q.ge(y, 0) & Q.le(y, 5) & B for c in (pi / 3, 1 / pi)]
    sets.append(Q.gt(x, pi * y / 4) & Q.ge(y, 0) & Q.le(y, 5) & B)
    out, kept, reached = _sweep(sets, QUERIES[:4])
    assert out == []
    assert kept == 0
    assert reached >= 1                      # the budget did run out


def test_certified_constants_warm_equals_fresh():
    # certified atoms (pi: rational rows, bounds in Q + Q*pi)
    s = _t(7 * pi / 2)
    e = Engine()
    for p in CQUERIES:
        assert _a(p, s, e) == _a(p, s, Engine())
    assert not e._context_sessions


def test_uncertified_constants_warm_equals_fresh():
    # sqrt(2): algebraic, never certified; the theory may give up at a
    # point of the path, which is the fresh engine's path
    s = _t(sqrt(2) / 3)
    e = Engine()
    for p in CQUERIES:
        assert _a(p, s, e) == _a(p, s, Engine())
    assert not e._context_sessions


def test_constants_after_a_rational_branch_and_bound_in_the_set_check():
    # the set check branches with no constant in the payloads and leaves
    # rational values in the assignment (n = 4 here); the queries bring
    # constants.  Every query builds the set's session and runs the same
    # check (Engine._build_context), so it starts from the same values as
    # the fresh engine does
    s = Q.ge(n, 0) & Q.le(n, 3) & Q.ne(n, 1) & Q.ne(n, 2) & Q.gt(x, n + Rational(1, 2)) \
        & Q.lt(x, n + 3)
    queries = [Q.gt(x, pi), Q.ge(x, n + pi / 4), Q.ge(x, n + 1), Q.lt(x, 6 + pi)]
    built, _ = Engine()._build_context(_formula(s, True))
    lras = [t for t in built.solver._theories if hasattr(t, "branched_rational")]
    assert [t.branched_rational for t in lras] == [True]
    assert [t.rational_values() for t in lras] == [(F(4), 1)]
    out, kept, _ = _sweep([s], queries)
    assert out == []
    assert kept == 0


# -- the certificate (LRATheory.certified) --------------------------------------

PI, SQRT2 = cf.PI, cf.radical(F(2), 2)


def _theory(atoms):
    t = LRATheory()
    for v, p in atoms.items():
        t.register_atom(v, p)
    return t


def _certified_atoms():
    # x - y < pi/3, 0 <= y <= 5, x and y and x/pi and x + pi/3 integral:
    # the rows are rational, the bounds in Q + Q*pi, branch bounds of x/pi
    # in Q*pi, floors of x/pi in Q + Q/pi
    return {1: constraint({"x": 1, "y": -1}, "<", PI / 3), 2: constraint({"y": 1}, ">=", 0),
            3: constraint({"y": 1}, "<=", 5), 4: Integral((("x", 1),)),
            5: Integral((("y", 1),)), 6: Integral((("x", 1 / PI),)),
            7: Integral((("x", 1),), PI / 3), 8: constraint({"x": 1, "y": 1}, "=", 3 * PI)}


def test_certificate_rational_rows_and_pi_bounds():
    t = _theory(_certified_atoms())
    assert t.undecidable and t.certified
    assert t.certified_with((F(7), 3))
    assert not t.certified_with((F(2) ** 200, 1))        # left-behind values too large
    assert _theory({1: constraint({"x": 1}, "<", 1 / PI),
                    2: constraint({"x": 1, "y": 2}, ">", -2 / PI)}).certified


def test_certificate_refused():
    for bad in (constraint({"x": 1, "y": PI}, "<", 1),        # a row with pi
                constraint({"z": 1}, "<", SQRT2),               # algebraic
                constraint({"z": 1}, "<", 1 / PI),              # with pi*x/3: Q*pi + Q/pi
                constraint({"z": 1}, "<", PI * 2 ** 120),       # Mahler's bound too weak
                constraint({"z": 1, "y": 1}, "<", PI + cf.E),   # two constants
                Integral((("x", 1 + PI),))):                    # a multiplier no monomial
        atoms = _certified_atoms()
        atoms[9] = bad
        t = _theory(atoms)
        assert not t.certified, bad
        # monotone: more atoms never certify
        t.register_atom(10, constraint({"w": 1}, ">=", 1))
        assert not t.certified


def test_split_beyond_the_certificate_bound_counts_as_exhausted(monkeypatch):
    # 3/2 <= x <= pi, x integral: the point x = 3/2 splits, x = 2
    atoms = {1: constraint({"x": 1}, ">=", F(3, 2)), 2: constraint({"x": 1}, "<=", PI),
             3: Integral((("x", 1),))}
    for small in (False, True):
        if small:
            monkeypatch.setattr(LRATheory, "_certificate", lambda self, values=None: (True, 1))
        t = _theory(atoms)
        for lit in (1, 2, 3):
            assert t.assert_lit(lit) is None
        r = t.check()
        assert r is not None and r[0] is True
        assert t.exhausted is small          # |3/2| > 1: no split, as if out of budget


def test_certificate_reads_the_constfield_limits(monkeypatch):
    # the certificate covers the configuration in force when it is asked,
    # not the one of an earlier (memoized) certification
    t = _theory(_certified_atoms())
    assert t.certified
    for name, small in (("MAX_DEGREE", 1), ("MAX_TERMS", 2), ("MAX_WORK", 8),
                        ("MAX_BITS", 256), ("PREC_CAP", 512)):
        with monkeypatch.context() as m:
            m.setattr(cf, name, small)
            assert not t.certified, name
            assert not _theory(_certified_atoms()).certified, name
        assert t.certified


def test_constants_small_limits_are_not_certified(monkeypatch):
    # with constfield's size budget shrunk, a search over atoms certified
    # at the default limits (where it cannot give up, see
    # test_certified_constants_warm_equals_fresh) can give up: they are not
    # certified then, and the answer is still the fresh engine's
    monkeypatch.setattr(cf, "MAX_DEGREE", 1)
    out, kept, reached = _sweep([_t(7 * pi / 2)], CQUERIES, _uncertified)
    assert out == []
    assert kept == 0
    assert reached >= 1                      # the atoms were not certified


@pytest.mark.parametrize("policy", ["root-only", "none"])
def test_writeback_policies_warm_equals_fresh(policy, monkeypatch):
    # writeback="root-only" memoizes the answer of is_, "none" memoizes
    # nothing (the "provenance"/"all" policies, a session writing its root
    # facts back, were removed by #97 P2); nothing is held for a re-answer
    # since issue #97 (there is none), and no contextual session writes
    # or reads a fact, so the warm engine answers as a fresh one
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 5)
    e = Engine(writeback=policy)
    assert not hasattr(e, "_hold_writeback")
    for p in (Q.gt(u0, 1), Q.ge(u0, 4), Q.gt(u0, 1)):
        assert _a(p, A & C, e) == _a(p, A & C, Engine(writeback=policy))
    assert _a(Q.ge(u0, 4), A & C, Engine(writeback=policy)) is None
    assert not e._context_sessions
