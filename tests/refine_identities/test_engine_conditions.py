"""The engine's condition decider, ``Piecewise`` refinement, the result cache.

Moved here from needs tests: ``test_checker_atan2_power_firing_cap.py`` (checker)
and ``test_piecewise_conditions.py`` (branch ``ri/piecewise``).
"""
from __future__ import annotations

from sympy import Function, Max, Piecewise, Q, S, atan2, symbols

from satrefine import refine
from satrefine.handlers_identities import _dispatch
from satrefine.handlers_identities._engine import decide, identity_handler, provable

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
    assert decide(Q.le(x, y), Q.eq(x, y)) is True                             # le from eq
    assert decide(Q.lt(x, y), Q.le(y, x)) is False


def test_relation_proofs_unused_for_a_known_infinite_argument():
    """SymPy's ``ask`` answers ``Q.eq(x, y)`` "True" for ``x = -oo`` and ``y <= 0``."""
    wrong = Q.negative_infinite(x) & Q.extended_nonpositive(y)
    assert refine(Piecewise((1, Q.eq(x, y)), (0, True)), wrong) != 1
    assert decide(Q.eq(x, y), wrong) is None
    assert decide(Q.lt(y, x), Q.positive_infinite(x) & Q.real(y)) is True    # the sign forms still apply


def test_a_condition_is_refuted_past_an_undecided_conjunct():
    """``provable`` stops a hypothesis at its first undecided conjunct; a
    condition goes on looking for a refutation."""
    cond = Q.le(1, x) & Q.le(x, 3)
    assert provable(cond, Q.gt(x, 3)) is None
    assert decide(cond, Q.gt(x, 3)) is False
    assert refine(Piecewise((1, cond), (0, True)), Q.gt(x, 3)) == 0


def test_undecided_branches_are_refined_under_their_conditions():
    from sympy import Abs
    assert refine(Piecewise((Abs(x), Q.ge(x, 0)), (-x, True)), Q.real(x)) == Piecewise((x, Q.ge(x, 0)), (-x, True))


# --- definitions: an undecided Piecewise is not a rewrite ---------------------

def test_undecided_definition_declines_without_a_split():
    """A candidate with a ``Piecewise`` the input did not have is rejected before
    any case split, even with ``Piecewise`` opaque (the split used to rebuild
    it by ``xreplace`` and could raise, and on refusals cost about 5x)."""
    rows = [(Max(a, b), Piecewise((a, Q.ge(a, b)), (b, Q.lt(a, b))), S.true)]
    handler = identity_handler(rows, measure=lambda e, _: (len(e.args), 0), opaque=(Piecewise,))
    assert handler(Max(x, y, z), Q.positive_infinite(z) & Q.real(x)) == Max(y, z)
    assert handler(Max(x, y), Q.real(x) & Q.real(y)) is None
    before = _dispatch.MAX_SPLITS
    assert refine(Max(x, y), Q.real(x) & Q.real(y)) == Max(x, y)
    assert _dispatch.MAX_SPLITS == before


def test_a_table_can_switch_the_case_split_off(monkeypatch):
    from satrefine.handlers_identities import _engine
    splits = []
    monkeypatch.setattr(_engine, "case_split", lambda *args: splits.append(args) and None)
    Book = Function('Book')                                  # bookkeeping nothing collapses
    rows = [(Function('F')(x), Book(x), S.true)]
    assert identity_handler(rows, opaque=(Book,), splits=False)(Function('F')(x), Q.real(x)) is None
    assert splits == []
    assert identity_handler(rows, opaque=(Book,))(Function('F')(x), Q.real(x)) is None
    assert len(splits) == 1


# --- the result cache and the firing cap --------------------------------------

def test_atan2_of_shifted_power_does_not_exhaust_the_firing_cap():
    """Each branch of ``atan2``'s ``Piecewise`` refined ``n**y`` again through the
    ``Pow`` fact and a sign split, until 500 firings; the dispatcher's result
    cache does that work once.  A refusal is right: ``y/x`` has no known sign."""
    expr = atan2(y, n**y + 1)
    assert refine(expr, Q.negative(y) & Q.nonpositive(n)) == expr


def test_atan2_of_power_does_not_exhaust_the_firing_cap_live():
    expr = atan2(y, n**y)
    with _dispatch.live():
        assert refine(expr, Q.negative(y) & Q.nonpositive(n)) == expr


def test_repeated_work_is_done_once():
    F = Function('F')
    calls = []

    def once(expr, assumptions):
        calls.append(expr)
        return expr.args[0] if expr.args[0].is_Symbol else None

    from satrefine._upstream import handlers_dict
    handlers_dict['F'] = once
    try:
        big = sum(F(x)*k for k in range(1, 2*_dispatch.MAX_FIRINGS))
        assert refine(big, Q.real(x)) == big.xreplace({F(x): x})
        assert calls.count(F(x)) == 1
    finally:
        del handlers_dict['F']
