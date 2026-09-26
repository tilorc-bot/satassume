"""The combined backend asks SymPy only where satassume has no model (issue #7).

Before the routing, every ``None`` from satassume was re-asked of SymPy's
``ask``; that took 82% of refine's time over the battery (179 of 219 s,
``Q.eq`` alone 116 s) and SymPy decided 10% of those queries.  Now SymPy is
asked only for queries satassume cannot translate (matrix predicates,
predicates on matrix arguments, unregistered custom predicates, relations over
matrices), for relations no satassume theory interprets (bounds such as
``pi/2``, floats, ``AccumBounds``), for assumptions satassume finds
inconsistent, and when satassume raises.  ``union`` keeps the old behaviour.
"""
from __future__ import annotations

import pytest
from sympy import Abs, AccumBounds, MatrixSymbol, Q, Symbol, asin, pi, sin, sqrt
from sympy.assumptions.assume import Predicate

from satrefine import refine
from satrefine.identities.compat import backend
from satrefine.identities.compat.backend import route

x, y = Symbol('x'), Symbol('y')
X, Y = MatrixSymbol('X', 2, 2), MatrixSymbol('Y', 2, 2)


class _Unregistered(Predicate):
    name = "routing_test_unregistered"


ROUTES = [
    # satassume decides, or is undecided, and its answer stands
    (Q.positive(x), Q.real(x) & Q.gt(x, 1), True, None),
    (Q.positive(x), Q.negative(x), False, None),
    (Q.eq(x, 1), Q.positive(x), None, None),
    (Q.ne(x, y), Q.lt(x, y), None, None),
    (Q.positive(x), Q.gt(x, 1), None, None),  # x not known real: None is right
    (Q.integer(x), True, None, None),
    # no model in satassume: SymPy is asked
    (Q.invertible(X), Q.orthogonal(X), None, "matrix"),
    (Q.real(x), Q.symmetric(X), None, "matrix"),
    # out_of_scope would report "relation" first here, but the matrix part decides
    (Q.positive(x), Q.lt(x, 1) & Q.symmetric(X), None, "matrix"),
    (Q.eq(X, Y), True, None, "relation"),
    (_Unregistered()(x), True, None, "custom"),
    # a relation no theory interprets drops the whole query in satassume
    (Q.nonnegative(x), Q.nonnegative(x) & Q.le(x, pi/2), None, "no-theory"),
    (Q.positive(x), Q.real(x) & Q.gt(x, 1.5), None, "no-theory"),
    (Q.real(x), Q.ge(x, 0) & Q.le(x, AccumBounds(0, 1)), None, "no-theory"),
    (Q.positive(x), Q.positive(x) & Q.negative(x), None, "inconsistent"),
]


@pytest.mark.parametrize("proposition, assumptions, answer, reason", ROUTES)
def test_route(proposition, assumptions, answer, reason):
    assert route(proposition, assumptions) == (answer, reason)


def _sympy_forbidden(*args):
    raise AssertionError(f"SymPy asked for an in-scope query: {args}")


@pytest.mark.parametrize("proposition, assumptions, answer, reason",
                         [r for r in ROUTES if r[3] is None])
def test_in_scope_queries_never_reach_sympy(monkeypatch, proposition, assumptions, answer, reason):
    monkeypatch.setattr(backend, "_guarded_sympy_ask", _sympy_forbidden)
    with backend.using("combined"):
        assert backend.ask(proposition, assumptions) is answer


def test_out_of_scope_queries_reach_sympy():
    with backend.using("combined"):
        assert backend.ask(Q.invertible(X), Q.orthogonal(X)) is True
        assert backend.ask(Q.nonnegative(x), Q.nonnegative(x) & Q.le(x, pi/2)) is True
    with backend.using("satassume"):
        assert backend.ask(Q.nonnegative(x), Q.nonnegative(x) & Q.le(x, pi/2)) is None


def test_union_still_asks_sympy_for_every_none(monkeypatch):
    seen = []
    monkeypatch.setattr(backend, "_guarded_sympy_ask", lambda p, a=True: seen.append(p))
    with backend.using("union"):
        backend.ask(Q.eq(x, 1), Q.positive(x))
    assert seen == [Q.eq(x, 1)]


def test_rewrite_under_a_pi_bound_needs_the_no_theory_route():
    # the one battery case satassume alone loses (test_inverse.py::test_results_are_re_refined)
    with backend.using("combined"):
        assert refine(sqrt(asin(sin(x))**2), Q.nonnegative(x) & Q.le(x, pi/2)) == x


def test_accumbounds_bound_does_not_crash():
    with backend.using("combined"):
        refine(asin(sin(x)), Q.ge(x, 0) & Q.le(x, AccumBounds(0, 1)))


def test_a_satassume_error_is_none_not_a_crash(monkeypatch):
    import satassume.sympy_api as api

    def broken(*args, **kwargs):
        raise RuntimeError("engine bug")

    monkeypatch.setattr(api, "ask", broken)
    assert route(Q.positive(x), Q.real(x)) == (None, "error")
    monkeypatch.setattr(backend, "_guarded_sympy_ask", broken)
    with backend.using("combined"):
        assert backend.ask(Q.positive(x), Q.real(x)) is None


def test_nonzero_guard_applies_on_the_routed_sympy_path():
    # the matrix conjunct routes this to SymPy, which unguarded calls Abs(x) zero
    # for imaginary x (see test_backend_nonzero_guard.py)
    with backend.using("combined"):
        assert backend.ask(Q.zero(Abs(x)), Q.imaginary(x) & Q.symmetric(X)) is not True
