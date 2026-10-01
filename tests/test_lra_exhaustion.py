"""Integer branch and bound runs out of budget along a history-dependent
path: a query's answer must still be the one a fresh engine gives.

``LRATheory.check`` branches at most ``BRANCH_BUDGET`` times; which checks
run and in which order they branch depends on the tableau basis and the
learnt clauses a reused contextual session carries from earlier queries.
Both directions happened: a warm None where a fresh engine is definite (the
warm search ran out) and a warm definite answer where a fresh engine gives
None (the fresh search runs out).  ``Engine.ask`` answers such queries
again in a freshly built session (``exhaust_reanswers``).
"""
from sympy import And, Q, Rational, symbols

from satassume import lra
from satassume.engine import CONSISTENT, INCONSISTENT, UNKNOWN
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
