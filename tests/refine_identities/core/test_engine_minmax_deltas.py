"""Matcher forms the ``minmax_deltas`` table needs from the engine."""
from __future__ import annotations

from sympy import Function, KroneckerDelta, Max, Min, Q, S, symbols

from satrefine.identities.core.rewrite import rule_handler

a, b, i, j, r, x, y, z = symbols('a b i j r x y z')
G = Function('G')
H = Function('H')


def test_minmax_pair_with_the_other_arguments_kept():
    """``Max(a, b)`` against a ``Max`` of any arity binds ``a`` and ``b`` to
    two distinct arguments (every ordered pair); the right side replaces
    those two and the others are kept: ``Max(x, y, z) -> Max(rhs, z)``."""
    rule = rule_handler([(Max(a, b), a, Q.extended_nonpositive(b) & Q.extended_nonnegative(a))])
    assert rule(Max(x, y, z), Q.negative(x) & Q.positive(y)) == Max(y, z)
    assert rule_handler([(Min(a, b), a, Q.le(a, b))])(Min(x, y), Q.le(x, y)) == x


def test_three_argument_head():
    """``KroneckerDelta(i, j, range)``: all three arguments bound."""
    rule = rule_handler([(H(i, j, r), S.Zero, Q.ne(i, j))])
    assert rule(KroneckerDelta(x, y, (1, 3)), Q.ne(x, y)) == 0


def test_unless_condition():
    """A row ``(lhs, rhs, hypothesis, unless)`` fires when the hypothesis is
    provable and ``unless`` is not.  SymPy answers ``Q.eq(i, j)`` "True" for
    ``i = -oo`` and ``j`` extended-nonpositive; v3 refuses relation queries
    for an argument *known* infinite, which no provable hypothesis states."""
    rows = [(G(i, j), S.One, Q.eq(i, j), Q.infinite(i) | Q.infinite(j))]
    handler = rule_handler(rows)
    assert handler(KroneckerDelta(x, y), Q.eq(x, y)) == 1
    bad = Q.negative_infinite(x) & Q.extended_nonpositive(y) & Q.eq(z, a)
    assert handler(KroneckerDelta(x, y), bad) is None
