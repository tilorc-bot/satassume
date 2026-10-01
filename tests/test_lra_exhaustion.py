"""Integer branch and bound runs out of budget along a history-dependent
path: a query's answer must still be the one a fresh engine gives.

``LRATheory.check`` branches at most ``BRANCH_BUDGET`` times; which checks
run and in which order they branch depends on the tableau basis and the
learnt clauses a reused contextual session carries from earlier queries.
Both directions happened: a warm None where a fresh engine is definite (the
warm search ran out) and a warm definite answer where a fresh engine gives
None (the fresh search runs out).  ``Engine.ask`` answers such queries
again in a freshly built session (``exhaust_reanswers``).

With constants in the LRA payloads the theory can give up (an undecided
sign, constfield's size budget) at points the search path decides; a
query is answered again unless the session's atoms are certified
(``LRATheory.certified``: no search over them can give up).
"""
from fractions import Fraction as F

from sympy import E, And, Q, Rational, pi, sqrt, symbols

from satassume import constfield as cf
from satassume import lra
from satassume.engine import CONSISTENT, INCONSISTENT, UNKNOWN
from satassume.lra import Integral, LRATheory, constraint
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


def test_warm_equals_fresh():
    # on main: warm None (the second search ran out), fresh True
    e = Engine()
    ask(Q.ge(x, y + 1), A & B, e)
    warm = ask(Q.gt(u0, 1), A & B, e)
    fresh = ask(Q.gt(u0, 1), A & B, Engine())
    assert warm == fresh
    assert fresh is True


def _divergences():
    out, reanswers = [], 0
    for s in (A & B, A & C):
        fresh = {p: _a(p, s, Engine()) for p in QUERIES}
        for p1 in QUERIES:
            for p2 in QUERIES:
                e = Engine()
                _a(p1, s, e)
                w = _a(p2, s, e)
                reanswers += e.stats.get("exhaust_reanswers", 0)
                if w != fresh[p2]:
                    out.append((s, p1, p2, w, fresh[p2]))
    return out, reanswers


def test_no_warm_fresh_divergence_budget_3(monkeypatch):
    # on main: 1 warm None/fresh definite, 4 warm definite/fresh None
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 3)
    out, reanswers = _divergences()
    assert out == []
    assert reanswers


def test_no_warm_fresh_divergence_budget_16(monkeypatch):
    # on main: 2 warm None/fresh definite, 11 warm definite/fresh None
    out, reanswers = _divergences()
    assert out == []
    assert reanswers


def test_exhausted_set_check_is_unknown(monkeypatch):
    # 0 <= n <= 1, n != 0, n != 1 over the integers needs two branchings
    d = _formula(Q.ge(n, 0) & Q.le(n, 1) & Q.ne(n, 0) & Q.ne(n, 1), True)
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 1)
    assert Engine().verdict(d) is UNKNOWN          # was CONSISTENT
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 2)
    assert Engine().verdict(d) is INCONSISTENT
    assert Engine().verdict(_formula(A, True)) is CONSISTENT


# -- constants ----------------------------------------------------------------

def _sweep(sets, queries):
    out, reanswers = [], 0
    for s in sets:
        fresh = {p: _a(p, s, Engine()) for p in queries}
        for p1 in queries:
            for p2 in queries:
                e = Engine()
                _a(p1, s, e)
                w = _a(p2, s, e)
                reanswers += e.stats.get("exhaust_reanswers", 0)
                if w != fresh[p2]:
                    out.append((s, p1, p2, w, fresh[p2]))
    return out, reanswers


def _t(c):
    return (Q.gt(x, y + c) & Q.ge(y, 0) & Q.le(y, 5) & Q.lt(x, 3 * c + 9)
            & Q.gt(u0, c) & Q.lt(u0, x - c))


CQUERIES = [Q.ge(x, y + 1), Q.ge(x, y + 2), Q.ge(u0, 2), Q.lt(x, 13), Q.ge(u0, y),
            Q.gt(x - u0, 1)]


def test_constants_no_warm_fresh_divergence():
    # certified (pi, 1/pi: rational rows, bounds in Q + Q*pi or Q + Q/pi)
    # and not (sqrt(2): algebraic; pi and E together)
    sets = [_t(pi / 3), _t(1 / pi), _t(7 * pi / 2), _t(sqrt(2) / 3), _t((pi + E) / 7)]
    out, reanswers = _sweep(sets, CQUERIES)
    assert out == []
    assert reanswers


def test_constants_no_warm_fresh_divergence_budget_3(monkeypatch):
    # the integer part runs out of budget, with constants in the payloads;
    # a row with a pi coefficient is never certified
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 3)
    sets = [Q.gt(x, y + c) & Q.ge(y, 0) & Q.le(y, 5) & B for c in (pi / 3, 1 / pi)]
    sets.append(Q.gt(x, pi * y / 4) & Q.ge(y, 0) & Q.le(y, 5) & B)
    out, reanswers = _sweep(sets, QUERIES[:4])
    assert out == []
    assert reanswers


def test_certified_constants_are_not_answered_again():
    s = _t(7 * pi / 2)
    e = Engine()
    for p in CQUERIES:
        assert _a(p, s, e) == _a(p, s, Engine())
    assert e.stats["exhaust_reanswers"] == 0


def test_uncertified_constants_are_answered_again():
    s = _t(sqrt(2) / 3)
    e = Engine()
    for p in CQUERIES:
        assert _a(p, s, e) == _a(p, s, Engine())
    assert e.stats["exhaust_reanswers"]


def test_constants_after_a_rational_branch_and_bound_in_the_set_check():
    # the set check branches with no constant in the payloads; the values
    # it leaves behind are recorded (Session.build_values) and certified
    # with the queries' constants
    s = Q.ge(n, 0) & Q.le(n, 3) & Q.ne(n, 1) & Q.ne(n, 2) & Q.gt(x, n + Rational(1, 2)) \
        & Q.lt(x, n + 3)
    queries = [Q.gt(x, pi), Q.ge(x, n + pi / 4), Q.ge(x, n + 1), Q.lt(x, 6 + pi)]
    # (a verdict stores no session since R2: build one as a query does)
    built, _ = Engine()._build_context(_formula(s, True))
    assert built.build_values == [(F(4), 1)]
    out, _ = _sweep([s], queries)
    assert out == []


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
