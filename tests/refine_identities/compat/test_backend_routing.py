"""The combined backend asks SymPy only where satassume has no model (issue #7).

Before the routing, every ``None`` from satassume was re-asked of SymPy's
``ask``; that took 82% of refine's time over the battery (179 of 219 s,
``Q.eq`` alone 116 s) and SymPy decided 10% of those queries.  Now SymPy is
asked only for queries satassume cannot translate (matrix predicates,
predicates on matrix arguments, unregistered custom predicates, relations over
matrices), for relations no satassume theory interprets (bounds such as
``pi/2``, floats, ``AccumBounds``), and when satassume raises.  Assumptions
satassume finds inconsistent raise (issue #18).  ``union`` keeps the old behaviour.
Since satassume reads irrational constants as bounded LRA variables (main's
b208af3), bounds such as ``pi/2`` are interpreted and stay with satassume,
and since relations are read over the extended reals (main's #26) so are
``oo`` bounds; floats and ``AccumBounds`` still route to SymPy.
"""
from __future__ import annotations

import pytest
from sympy import Abs, AccumBounds, MatrixSymbol, Q, Symbol, asin, oo, pi, sin, sqrt
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
    (Q.ne(x, y), Q.lt(x, y), True, None),     # a relation's sides are extended reals (main's #26)
    (Q.positive(x), Q.gt(x, 1), None, None),  # x not known real: None is right
    (Q.integer(x), True, None, None),
    # an irrational bound is a bounded LRA variable (b208af3): no SymPy fallback
    (Q.nonnegative(x), Q.nonnegative(x) & Q.le(x, pi/2), True, None),
    (Q.positive(x), Q.real(x) & Q.gt(x, pi/2), True, None),
    # an infinite bound is read on the extended reals (main's #26): no SymPy fallback
    (Q.real(x), Q.nonnegative(x) & Q.lt(x, oo), True, None),
    (Q.finite(x), Q.gt(x, 1) & Q.lt(x, oo), True, None),
    # no model in satassume: SymPy is asked
    (Q.invertible(X), Q.orthogonal(X), None, "matrix"),
    (Q.real(x), Q.symmetric(X), None, "matrix"),
    # out_of_scope would report "relation" first here, but the matrix part decides
    (Q.positive(x), Q.lt(x, 1) & Q.symmetric(X), None, "matrix"),
    (Q.eq(X, Y), True, None, "relation"),
    (_Unregistered()(x), True, None, "custom"),
    # a relation no theory interprets drops the whole query in satassume
    (Q.nonnegative(x), Q.nonnegative(x) & Q.le(x, 1.5), None, "no-theory"),
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
        assert backend.ask(Q.nonnegative(x), Q.nonnegative(x) & Q.le(x, 1.5)) is True
    with backend.using("satassume"):
        assert backend.ask(Q.nonnegative(x), Q.nonnegative(x) & Q.le(x, 1.5)) is None


def test_inconsistent_assumptions_raise_without_asking_sympy(monkeypatch):
    """SymPy calls an ``Or`` true under inconsistent assumptions (issue #18)."""
    monkeypatch.setattr(backend, "_guarded_sympy_ask", _sympy_forbidden)
    with backend.using("combined"), pytest.raises(ValueError, match="inconsistent assumptions"):
        backend.ask(Q.nonnegative(x) | Q.zero(x), Q.positive(x) & Q.negative(x))


def test_a_whole_condition_is_asked_of_satassume_only(monkeypatch):
    """``ask_whole`` (the engine's whole-``Or`` ask, issue #18) is satassume's
    answer, and ``None`` where ``combined`` would ask SymPy or under the
    ``sympy`` and ``union`` backends."""
    monkeypatch.setattr(backend, "_guarded_sympy_ask", _sympy_forbidden)
    by_cases = Q.positive(x) | Q.nonpositive(x)
    for name, answer in (("combined", True), ("satassume", True), ("sympy", None), ("union", None)):
        with backend.using(name):
            assert backend.ask_whole(by_cases, Q.real(x)) is answer
    with backend.using("combined"):
        assert backend.ask_whole(Q.invertible(X) | Q.positive(x), Q.real(x)) is None      # matrix
        assert backend.ask_whole(by_cases, Q.real(x) & Q.lt(x, 1.5)) is None             # no theory
        assert backend.ask_whole(by_cases, Q.positive(x) & Q.negative(x)) is None         # inconsistent


def test_a_whole_answer_follows_satassume_state():
    """``ask_whole`` remembers answers only while satassume's own answer memo
    would: a predicate (un)registration or a new default engine forgets them."""
    from satassume import Engine
    from satassume.sympy_api import default_engine, register, set_default_engine, unregister

    class WholeKey(Predicate):
        name = 'whole_key'

    relation = Q.lt(x, 1) | Q.gt(x, 0)
    engine = default_engine()
    try:
        Q.whole_key = WholeKey()
        custom = Q.whole_key(x) | Q.negative(x)
        with backend.using("combined"):
            assert backend.ask_whole(custom, Q.positive(x)) is None   # unregistered: custom

            @register(Q.whole_key, Symbol)
            def _(e):
                return True

            assert backend.ask_whole(custom, Q.positive(x)) is True
            unregister(Q.whole_key)
            assert backend.ask_whole(custom, Q.positive(x)) is None
            assert backend.ask_whole(relation, Q.real(x)) is True
            set_default_engine(Engine(relations=[]))                 # no theory: relations out of scope
            assert backend.ask_whole(relation, Q.real(x)) is None
            set_default_engine(engine)
            assert backend.ask_whole(relation, Q.real(x)) is True
    finally:
        set_default_engine(engine)
        unregister(Q.whole_key)
        del Q.whole_key


def test_union_still_asks_sympy_for_every_none(monkeypatch):
    seen = []
    monkeypatch.setattr(backend, "_guarded_sympy_ask", lambda p, a=True: seen.append(p))
    with backend.using("union"):
        backend.ask(Q.eq(x, 1), Q.positive(x))
    assert seen == [Q.eq(x, 1)]


def test_rewrite_under_a_pi_bound():
    # the one battery case satassume alone used to lose
    # (test_inverse.py::test_results_are_re_refined); since b208af3 it needs no SymPy
    for name in ("combined", "satassume"):
        with backend.using(name):
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
