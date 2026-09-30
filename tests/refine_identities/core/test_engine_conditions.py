"""The engine's condition decider, ``Piecewise`` refinement, the result cache.

Moved here from needs tests: ``test_checker_atan2_power_firing_cap.py`` (checker)
and ``test_piecewise_conditions.py`` (branch ``ri/piecewise``).  The ``atan2``
firing-cap inputs and a head refusing a refined child are rows of
``regressions.py``.
"""
from __future__ import annotations

from sympy import Abs, Function, Max, Or, Piecewise, Q, S, floor, im, re, symbols

from satrefine import refine
from satrefine.identities.compat import backend
from satrefine.identities.core import driver as _dispatch
from satrefine.identities.core.prove import by_cases, decide, provable
from satrefine.identities.core.rewrite import identity_handler, rule_handler

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
    cond = Q.integer(x) & Q.le(x, 3)
    assert provable(cond, Q.gt(x, 3)) is None
    assert decide(cond, Q.gt(x, 3)) is False
    assert refine(Piecewise((1, cond), (0, True)), Q.gt(x, 3)) == 0
    assert decide(Q.le(1, x) & Q.le(x, 3), Q.gt(x, 3)) is False


def test_an_or_marked_by_cases_is_asked_whole():
    """``floor(y)`` is a Gaussian integer for a finite ``y`` and ``y`` for an
    infinite one: no alternative is provable alone, the ``Or`` is (issue #18),
    when a table marks it (``by_cases``).  SymPy's ``ask`` does not split cases;
    under inconsistent assumptions, where it calls an ``Or`` true, the combined
    backend raises and nothing is proved."""
    f = floor(y)
    cond = by_cases(Q.integer(f) | (Q.integer(re(f)) & Q.integer(im(f))), Q.infinite(f))
    assert isinstance(cond, Or) and len(cond.args) == 3 and str(cond).startswith("by_cases(")
    for name in ("combined", "satassume"):
        with backend.using(name):
            assert provable(cond, S.true) is True
            assert provable(cond.xreplace({y: x}), S.true) is True      # the mark survives substitution
            assert provable(Or(*cond.args), S.true) is None              # unmarked: alternative by alternative
            assert decide(cond, S.true) is None                          # not in a Piecewise condition
    with backend.using("sympy"):
        assert provable(cond, S.true) is None
    for name in ("combined", "satassume"):
        with backend.using(name):
            assert provable(by_cases(Q.nonnegative(x), Q.zero(x)), Q.positive(x) & Q.negative(x)) is None
            assert refine(Abs(x), Q.positive(x) & Q.negative(x)) == Abs(x)


def test_only_a_marked_or_is_asked_whole(monkeypatch):
    """Any other ``Or`` costs no whole ask (#50 asked every ``Or`` with two
    undecided alternatives: +10% on the battery, nothing proved there)."""
    from satrefine.identities.core import hooks
    asked = []
    real = hooks.ask_whole
    monkeypatch.setattr(hooks, "ask_whole", lambda c, a: asked.append(c) or real(c, a))
    with backend.using("combined"):
        assert provable(Q.le(x, 0) | Q.gt(x, 0), Q.real(x)) is None
        assert provable(Q.extended_nonnegative(x) | Q.nonnegative(x), Q.real(x)) is None
        assert asked == []
        assert provable(by_cases(Q.le(x, 0), Q.gt(x, 0)), Q.real(x)) is True   # a hypothesis asks relations bare
        assert asked == [Q.le(x, 0) | Q.gt(x, 0)]


def test_a_row_marked_by_cases_fires():
    """The #18 row: ``F(k) -> k`` for a Gaussian integer or infinite ``k`` fires on
    ``F(floor(y))`` for any ``y`` when its hypothesis is marked, not otherwise."""
    F = Function('F')
    k = symbols('k')
    integer = Q.integer(k) | (Q.integer(re(k)) & Q.integer(im(k)))
    marked = rule_handler([(F(k), k, by_cases(integer, Q.infinite(k)))])
    plain = rule_handler([(F(k), k, integer | Q.infinite(k))])
    with backend.using("combined"):
        assert marked(F(floor(y)), S.true) == floor(y)
        assert plain(F(floor(y)), S.true) is None
        assert marked(F(y), S.true) is None


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
