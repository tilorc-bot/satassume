"""Matcher forms the ``combinatorial`` table needs from the engine.

Beyond the forms of ``test_integer_funcs_needs.py`` (argument-wise binding,
connective-by-connective hypotheses), one: a row over a generic head.
"""
from __future__ import annotations

from sympy import Function, Q, S, binomial, ff, rf, symbols

from satrefine.identities.rules._tables import compile_rule

k, m, n, x = symbols('k m n x')
G = Function('G')


def test_a_generic_head_row_serves_every_key_it_is_registered_under():
    """``binomial(n, 0) = rf(x, 0) = ff(x, 0) = 1`` is one row over a generic
    two-argument head; the head is not compared, both arguments are bound."""
    rule = compile_rule(G(x, k), S.One, Q.zero(k))
    for f in (binomial, rf, ff):
        assert rule(f(n, m), Q.zero(m)) == 1


def test_the_second_argument_is_bound_not_captured():
    """Today ``k`` is not bound, so the hypothesis asks about the pattern
    symbol ``k`` itself: under assumptions that happen to mention a ``k``
    the row fires on ``binomial(n, m)`` with nothing known about ``m``."""
    rule = compile_rule(G(x, k), S.One, Q.zero(k))
    assert rule(binomial(n, m), Q.zero(k)) is None
