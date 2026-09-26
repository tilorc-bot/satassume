"""Matcher forms the ``integer_funcs`` table needs from the engine.

Each test is the smallest input the current ``rule_handler``
gets wrong or cannot express; the table in
``satrefine/handlers_identities/integer_funcs.py`` is written in these
forms.  Requested from the engine agent; remove a test's ``needs`` status
by making it pass.
"""
from __future__ import annotations

from sympy import Mod, Q, S, floor, gamma, symbols

from satrefine.identities.core.rewrite import rule_handler

a, b, c, m, n, x, y = symbols('a b c m n x y')


def test_every_argument_of_a_two_argument_head_is_bound():
    """``rule_handler`` matches only ``lhs.args[0]``; ``b`` stays the pattern
    symbol, so the hypothesis is asked about the wrong ``b`` and the right
    side would contain it.  Wanted: argument-wise binding when the arities
    agree (the lhs head itself need not be checked: the handler is
    registered per key, so a generic head ``G(x, k)`` can serve several)."""
    rule = rule_handler([(Mod(a, b), b/2, Q.odd(2*a/b))])
    assert rule(Mod(x, y), Q.odd(2*x/y)) == y/2


def test_literal_zero_and_one_are_legal_bindings():
    """``rule_handler`` skips every binding whose value is 0 or 1, so
    ``Mod(x, 1)`` (and ``Max(x, 0)``, ``Heaviside(x, 1)``, ``X[0, 1]``)
    never fire."""
    rule = rule_handler([(Mod(a, b), S.Zero, Q.nonzero(b) & Q.integer(a/b))])
    assert rule(Mod(x, 1), Q.integer(x)) == 0


def test_a_sum_pattern_binds_one_term_and_the_rest():
    """``n + x`` inside a head: ``n`` binds one term of the target sum (every
    term in turn, as ``p*r`` does for a product), ``x`` the sum of the
    others.  Today the sum is handed to SymPy's ``match``, which binds some
    arbitrary split.  The term may be structured: ``floor(floor(c) + x)``
    (``ask`` cannot show ``floor(c)`` is an integer, so the Gaussian-integer
    shift of v3 needs that row)."""
    rule = rule_handler([(floor(n + x), n + floor(x), Q.integer(n))])
    assert rule(floor(y + m), Q.integer(m)) == m + floor(y)
    assert rule(floor(y + 2*m + a), Q.integer(m)) == 2*m + floor(y + a)


def test_ask_raising_is_not_provable(monkeypatch):
    """SymPy's relation ``ask`` raises ``ValueError('inconsistent
    assumptions')`` on consistent sign facts such as ``Q.positive(x) &
    Q.negative(y)``; ``rule_handler`` lets it escape and ``refine`` crashes.
    Wanted: read as "not provable" (v3 does).  Since satassume's relation
    theories (merged from ``main``) the combined backend answers this query
    (``Q.lt(m, y)`` is True), so the raise is simulated."""
    from sympy.assumptions import AppliedPredicate

    from satrefine.identities.compat import upstream as _upstream
    real_ask = _upstream.ask

    def raising(prop, assumptions=True):
        if isinstance(prop, AppliedPredicate) and prop.function == Q.lt:
            raise ValueError("inconsistent assumptions")
        return real_ask(prop, assumptions)
    monkeypatch.setattr(_upstream, "ask", raising)
    rule = rule_handler([(floor(a*b), S.Zero, Q.lt(a, b))])
    assert rule(floor(y*m), Q.positive(y) & Q.negative(m)) is None


def test_hypotheses_are_decided_connective_by_connective():
    """``ask(A | B)`` is ``None`` when ``A`` alone is provable and ``B`` is a
    relation (``ask(Q.nonnegative(-n) | Q.le(n, 0), Q.nonpositive(n))``).
    Wanted, and sound: an ``Or`` is provable when some disjunct is, an
    ``And`` when every conjunct is, atoms asked one at a time (each with the
    ``ValueError`` rule above)."""
    rule = rule_handler([(gamma(x), S.ComplexInfinity, Q.integer(x) & (Q.nonnegative(-x) | Q.le(x, 0)))])
    assert rule(gamma(n), Q.integer(n) & Q.nonpositive(n)) is S.ComplexInfinity
