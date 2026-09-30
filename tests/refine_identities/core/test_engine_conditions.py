"""The engine's condition decider, ``Piecewise`` refinement, the result cache.

Moved here from needs tests: ``test_checker_atan2_power_firing_cap.py`` (checker)
and ``test_piecewise_conditions.py`` (branch ``ri/piecewise``).  The ``atan2``
firing-cap inputs and a head refusing a refined child are rows of
``regressions.py``.
"""
from __future__ import annotations

from sympy import Abs, Function, Max, MatrixSymbol, Piecewise, Q, S, floor, im, pi, re, symbols

from satrefine import refine
from satrefine.identities.compat import backend
from satrefine.identities.core import driver as _dispatch
from satrefine.identities.core.prove import decide, provable
from satrefine.identities.core.rewrite import identity_handler

a, b, n, x, y, z = symbols('a b n x y z')


# --- relation conditions ------------------------------------------------------

def test_relation_decided_from_signs_and_relations():
    """SymPy refines a ``Piecewise`` condition with a bare ``ask``, which derives
    ``Q.ge`` neither from signs (it raises ``ValueError`` on these facts) nor
    from ``Q.lt``; the engine decides it from its proof forms."""
    pw = Piecewise((x, Q.ge(x, y)), (y, True))
    assert refine(pw, Q.positive(x) & Q.negative(y)) == x
    assert refine(pw, Q.lt(y, x)) == x
    assert refine(Piecewise((x, x >= y), (y, True)), Q.positive(x) & Q.negative(y)) == x   # a relational
    assert refine(pw, Q.lt(x, y)) == y                                        # refuted by the negation
    assert decide(Q.le(x, y), Q.eq(x, y) & Q.real(x)) is True                 # le from eq
    assert decide(Q.lt(x, y), Q.le(y, x)) is False


def test_relation_proofs_unused_for_a_known_infinite_argument():
    """SymPy's ``ask`` answers ``Q.eq(x, y)`` "True" for ``x = -oo`` and ``y <= 0``."""
    wrong = Q.negative_infinite(x) & Q.extended_nonpositive(y)
    assert refine(Piecewise((1, Q.eq(x, y)), (0, True)), wrong) != 1
    assert decide(Q.eq(x, y), wrong) is None
    assert decide(Q.lt(y, x), Q.positive_infinite(x) & Q.real(y)) is True    # the sign forms still apply


def test_a_condition_is_refuted_past_an_undecided_conjunct():
    """Connective by connective (SymPy's ``ask``), ``provable`` stops a hypothesis
    at its first undecided conjunct and a condition (``decide``) goes on
    looking for a refutation; a whole ``ask`` refutes the conjunction either way."""
    cond = Q.integer(x) & Q.le(x, 3)
    with backend.using("sympy"):
        assert provable(cond, Q.gt(x, 3)) is None
        assert decide(cond, Q.gt(x, 3)) is False
    for name in ("combined", "satassume"):
        with backend.using(name):
            assert provable(cond, Q.gt(x, 3)) is False
            assert decide(cond, Q.gt(x, 3)) is False
    assert refine(Piecewise((1, cond), (0, True)), Q.gt(x, 3)) == 0
    assert decide(Q.le(1, x) & Q.le(x, 3), Q.gt(x, 3)) is False


def test_le_from_eq_needs_real_sides():
    """A relation says its sides are extended reals (satassume's #26), so ``x <= y``
    follows from ``x = y`` only for a real ``x``; SymPy's ``ask`` (the ``sympy``
    backend, connective by connective) proves it for any ``x``."""
    for name in ("combined", "satassume"):
        with backend.using(name):
            assert decide(Q.le(x, y), Q.eq(x, y)) is None
    with backend.using("sympy"):
        assert decide(Q.le(x, y), Q.eq(x, y)) is True


# --- whole conditions (issue #18) ---------------------------------------------

F = floor(y)
BY_CASES = Q.integer(F) | (Q.integer(re(F)) & Q.integer(im(F))) | Q.infinite(F)


def test_a_condition_holding_by_cases_is_proved():
    """``floor(y)`` is a Gaussian integer for a finite ``y`` and ``y`` for an
    infinite one: no alternative is provable alone, the ``Or`` is.  satassume
    and ``combined`` ask the condition whole; SymPy's ``ask`` does not split
    cases, and the ``sympy`` and ``union`` backends decide connective by connective."""
    for name, proved in (("combined", True), ("satassume", True), ("sympy", None), ("union", None)):
        with backend.using(name):
            assert provable(BY_CASES, S.true) is proved
            assert decide(BY_CASES, S.true) is proved


def test_a_whole_condition_is_one_ask(monkeypatch):
    from satrefine.identities.compat import upstream
    asked = []
    real_ask = upstream.ask
    monkeypatch.setattr(upstream, "ask", lambda p, a=True: asked.append(p) or real_ask(p, a))
    cond = Q.positive(x) & (Q.integer(y) | Q.lt(x, y))
    with backend.using("combined"):
        provable(cond, Q.gt(x, 1) & Q.real(x))
    assert asked == [cond]


def test_inconsistent_assumptions_prove_nothing():
    """Under inconsistent assumptions SymPy calls an ``Or`` true, and a row
    conditioned on one fired (``Abs(x) -> x``); the ``combined`` backend raises
    instead of asking SymPy, the ask counts as undecided and refine returns its
    input (B9)."""
    for name in ("combined", "satassume"):
        with backend.using(name):
            assert provable(Q.nonnegative(x) | Q.zero(x), Q.positive(x) & Q.negative(x)) is None
            assert refine(Abs(x), Q.positive(x) & Q.negative(x)) == Abs(x)


def test_integer_in_an_interval_is_the_one_fallback():
    """satassume does not refute ``Q.integer(u)`` over an interval holding no
    integer (the poles of ``tan``: ``atan(tan(x)) = x`` on the principal branch);
    the stated bounds do, also inside a compound condition."""
    bounds = Q.gt(x, -pi/2) & Q.lt(x, pi/2)
    pole = Q.integer(x/pi + S.Half)
    for name in ("combined", "satassume", "sympy"):
        with backend.using(name):
            assert provable(pole, bounds) is False
            assert provable(~pole & Q.real(x), bounds) is True
            assert provable(pole | Q.positive(x), bounds & Q.negative(x)) is False


def test_an_untranslatable_atom_leaves_the_rest_to_satassume(monkeypatch):
    """A matrix predicate makes the condition connective by connective: satassume
    answers its other parts (here by cases), SymPy the matrix atom, and SymPy
    never gets the compound condition."""
    from satrefine.identities.compat import upstream
    X = MatrixSymbol("X", 2, 2)
    cond = Q.invertible(X) | BY_CASES
    asked = []
    real_ask = upstream.ask
    monkeypatch.setattr(upstream, "ask", lambda p, a=True: asked.append(p) or real_ask(p, a))
    with backend.using("combined"):
        assert provable(cond, S.true) is True
    assert BY_CASES in asked and cond not in asked
    with backend.using("sympy"):
        assert provable(cond, S.true) is None


def test_undecided_branches_are_refined_under_their_conditions():
    assert refine(Piecewise((Abs(x), Q.ge(x, 0)), (-x, True)), Q.real(x)) == Piecewise((x, Q.ge(x, 0)), (-x, True))


# --- definitions: an undecided Piecewise is not a rewrite ---------------------

def test_undecided_definition_declines_without_a_split():
    """A candidate with a ``Piecewise`` the input did not have is rejected before
    any case split, even with ``Piecewise`` opaque (the split used to rebuild
    it by ``xreplace`` and could raise, and on refusals cost about 5x)."""
    rows = [(Max(a, b), Piecewise((a, Q.ge(a, b)), (b, Q.lt(a, b))), S.true)]
    handler = identity_handler(rows, measure=lambda e, _: (len(e.args), 0), opaque=(Piecewise,))
    assert handler(Max(x, y, z), Q.positive_infinite(z) & Q.real(x)) in (Max(y, z), z)   # z: the Max(oo, b) row
    assert handler(Max(x, y), Q.real(x) & Q.real(y)) is None
    before = _dispatch.MAX_SPLITS
    assert refine(Max(x, y), Q.real(x) & Q.real(y)) == Max(x, y)
    assert _dispatch.MAX_SPLITS == before


def test_a_table_can_switch_the_case_split_off(monkeypatch):
    from satrefine.identities.core import rewrite as _engine
    splits = []
    monkeypatch.setattr(_engine, "case_split", lambda *args: splits.append(args) and None)
    Book = Function('Book')                                  # bookkeeping nothing collapses
    rows = [(Function('F')(x), Book(x), S.true)]
    assert identity_handler(rows, opaque=(Book,), splits=False)(Function('F')(x), Q.real(x)) is None
    assert splits == []
    assert identity_handler(rows, opaque=(Book,))(Function('F')(x), Q.real(x)) is None
    assert len(splits) == 1


# --- the result cache and the firing cap --------------------------------------

def test_repeated_work_is_done_once():
    F = Function('F')
    calls = []

    def once(expr, assumptions):
        calls.append(expr)
        return expr.args[0] if expr.args[0].is_Symbol else None

    from satrefine.identities.compat.upstream import handlers_dict
    handlers_dict['F'] = once
    try:
        big = sum(F(x)*k for k in range(1, 2*_dispatch.MAX_FIRINGS))
        assert refine(big, Q.real(x)) == big.xreplace({F(x): x})
        assert calls.count(F(x)) == 1
    finally:
        del handlers_dict['F']
