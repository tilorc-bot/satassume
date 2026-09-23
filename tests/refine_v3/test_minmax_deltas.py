"""Tests for ``satrefine.handlers_v3.minmax_deltas``.

Each rule has a positive test whose result is also checked numerically:
the original expression and the refined one are substituted with explicit
values satisfying the assumptions (zero and infinite values where the
assumptions allow them) and must agree.
"""
from __future__ import annotations

from collections import Counter

import pytest
from sympy import (
    Abs, DiracDelta, Eq, Heaviside, KroneckerDelta, Max, Min, Q, S, Symbol, exp,
    integrate, nan, oo, symbols,
)

from satrefine import _upstream, refine
from satrefine.handlers_v3 import minmax_deltas as mod

x, y, z, k, i, j = symbols("x y z k i j")


def check(expr, assumptions, expected, samples):
    """``refine`` gives ``expected``; both agree at every sample point."""
    got = refine(expr, assumptions)
    assert got == expected, (expr, assumptions, got)
    assert samples, "every rule needs a numeric check"
    for values in samples:
        before = expr.subs(values)
        after = got.subs(values)
        assert before == after, (values, before, after)


# ---------------------------------------------------------------- Max / Min

@pytest.mark.parametrize("func, assumptions, expected, samples", [
    # negative vs nonnegative (includes zero)
    (Max, Q.negative(x) & Q.nonnegative(y), y, [{x: -2, y: 0}, {x: -1, y: 5}]),
    (Min, Q.negative(x) & Q.nonnegative(y), x, [{x: -2, y: 0}, {x: -1, y: 5}]),
    # nonpositive vs positive
    (Max, Q.nonpositive(x) & Q.positive(y), y, [{x: 0, y: 1}, {x: -3, y: 2}]),
    (Min, Q.nonpositive(x) & Q.positive(y), x, [{x: 0, y: 1}, {x: -3, y: 2}]),
    # nonpositive vs nonnegative, both may be zero
    (Max, Q.nonpositive(x) & Q.nonnegative(y), y, [{x: 0, y: 0}, {x: -1, y: 0}, {x: 0, y: 4}]),
    # contradictory-looking sign facts (SymPy's relation ask raises here)
    (Max, Q.positive(x) & Q.negative(y), x, [{x: 1, y: -1}, {x: S(1)/2, y: -7}]),
    (Min, Q.positive(x) & Q.negative(y), y, [{x: 1, y: -1}, {x: S(1)/2, y: -7}]),
    # positive infinite argument vs a real one
    (Max, Q.positive_infinite(x) & Q.real(y), x, [{x: oo, y: -5}, {x: oo, y: 0}]),
    (Min, Q.positive_infinite(x) & Q.real(y), y, [{x: oo, y: -5}, {x: oo, y: 0}]),
    # negative infinite argument vs a real one
    (Max, Q.negative_infinite(x) & Q.real(y), y, [{x: -oo, y: 3}, {x: -oo, y: 0}]),
    (Min, Q.negative_infinite(x) & Q.real(y), x, [{x: -oo, y: 3}, {x: -oo, y: 0}]),
    # infinite vs signed via extended signs
    (Max, Q.negative_infinite(x) & Q.positive_infinite(y), y, [{x: -oo, y: oo}]),
    (Min, Q.positive_infinite(x) & Q.nonpositive(y), y, [{x: oo, y: 0}, {x: oo, y: -1}]),
    # relations
    (Max, Q.le(x, y), y, [{x: 1, y: 1}, {x: -2, y: 3}]),
    (Min, Q.le(x, y), x, [{x: 1, y: 1}, {x: -2, y: 3}]),
    (Max, Q.lt(y, x), x, [{x: 1, y: 0}]),
    (Min, Q.gt(x, y), y, [{x: 1, y: 0}]),
    # equal only through Q.eq -> either argument
    (Min, Q.eq(x, y), x, [{x: 2, y: 2}, {x: 0, y: 0}]),
    (Max, Q.eq(x, y), x, [{x: 2, y: 2}, {x: -oo, y: -oo}]),
])
def test_minmax_two_arguments(func, assumptions, expected, samples):
    check(func(x, y), assumptions, expected, samples)


def test_max_zero_versus_signed():
    check(Max(x, 0), Q.negative(x), S.Zero, [{x: -1}, {x: -oo}])
    check(Max(x, 0), Q.nonnegative(x), x, [{x: 0}, {x: 3}])
    check(Min(x, 0), Q.positive(x), S.Zero, [{x: 1}])
    check(Min(x, 0), Q.nonpositive(x), x, [{x: 0}, {x: -2}])
    check(Max(x, 0), Q.negative_infinite(x), S.Zero, [{x: -oo}])
    check(Min(x, 0), Q.positive_infinite(x), S.Zero, [{x: oo}])


def test_minmax_three_arguments():
    check(Max(x, y, z), Q.lt(x, y) & Q.le(z, y), y, [{x: 0, y: 1, z: 1}, {x: -1, y: 2, z: 0}])
    check(Min(x, y, z), Q.lt(x, y) & Q.le(x, z), x, [{x: 0, y: 1, z: 0}])
    # only one argument dropped
    check(Max(x, y, z), Q.negative(x) & Q.positive(y), Max(y, z),
          [{x: -1, y: 1, z: 5}, {x: -1, y: 1, z: -9}, {x: -1, y: 2, z: oo}])
    check(Min(x, y, z), Q.positive_infinite(z) & Q.real(x), Min(x, y),
          [{x: 1, y: 2, z: oo}, {x: 1, y: -oo, z: oo}])


def test_minmax_all_equal_keeps_one():
    got = refine(Max(x, y, z), Q.eq(x, y) & Q.eq(y, z) & Q.eq(x, z))
    assert got in (x, y, z)
    assert refine(Min(x, y), Q.le(x, y) & Q.le(y, x)) in (x, y)


def test_minmax_unknown_order_unchanged():
    assert refine(Max(x, y), Q.real(x) & Q.real(y)) == Max(x, y)
    assert refine(Min(x, y), Q.real(x) & Q.real(y)) == Min(x, y)
    assert refine(Max(x, y), Q.positive(x) & Q.positive(y)) == Max(x, y)
    assert refine(Max(x, y), Q.negative(x) & Q.negative(y)) == Max(x, y)
    assert refine(Max(x, y, z), True) == Max(x, y, z)
    # an infinite argument alone does not dominate one of unknown realness
    assert refine(Max(x, y), Q.positive_infinite(x)) == Max(x, y)
    assert mod.refine_Max(Max(x, y), Q.real(x)) is None


def test_minmax_infinite_does_not_trust_eq():
    """SymPy's ask claims ``Q.eq(y, x)`` for ``x = -oo`` and ``y <= 0``.

    That answer is wrong (``y = -1``); the handler must not use it.
    """
    assumptions = Q.negative_infinite(x) & Q.extended_nonpositive(y)
    got = refine(Max(x, y), assumptions)
    assert got in (Max(x, y), y)
    for values in ({x: -oo, y: -1}, {x: -oo, y: 0}, {x: -oo, y: -oo}):
        assert Max(x, y).subs(values) == got.subs(values)


def _count_asks(monkeypatch):
    calls = []
    real = _upstream.ask

    def counting(prop, assumptions=True):
        calls.append(prop)
        return real(prop, assumptions)

    monkeypatch.setattr(_upstream, "ask", counting)
    return calls


def test_mentions_eq():
    assert mod._mentions_eq(Q.real(x) & Q.eq(x, y))
    assert mod._mentions_eq(Eq(x, y))
    assert not mod._mentions_eq(Q.le(x, y) & Q.ne(x, z))
    assert not mod._mentions_eq(True)


def test_max_query_budget(monkeypatch):
    for assumptions in (True, Q.real(x) & Q.real(y) & Q.real(z),
                        Q.negative(x) & Q.negative(y) & Q.negative(z)):
        calls = _count_asks(monkeypatch)
        assert mod.refine_Max(Max(x, y, z), assumptions) is None
        counts = Counter(calls)
        assert max(counts.values()) == 1, counts
        relation_queries = [c for c in calls if c.func.__name__ == "Or"]
        assert len(relation_queries) <= 6
        assert len(calls) <= 18
        monkeypatch.undo()


# ---------------------------------------------------------------- DiracDelta

def test_diracdelta_nonzero():
    check(DiracDelta(x), Q.positive(x), S.Zero, [{x: 1}, {x: S(1)/3}])
    check(DiracDelta(x), Q.negative(x), S.Zero, [{x: -2}])
    check(DiracDelta(x), Q.nonzero(x), S.Zero, [{x: -2}, {x: 5}])
    check(DiracDelta(x, 2), Q.positive(x), S.Zero, [{x: 1}])
    check(DiracDelta(x - y), Q.nonzero(x - y), S.Zero, [{x: 3, y: 1}])
    check(DiracDelta(x - 1), Q.negative(x), S.Zero, [{x: -1}])


def test_diracdelta_scaling():
    check(DiracDelta(k*x), Q.nonzero(k) & Q.real(x), DiracDelta(x)/Abs(k),
          [{k: 2, x: 1}, {k: -3, x: S(1)/2}])
    check(DiracDelta(k*x), Q.positive(k) & Q.real(x), DiracDelta(x)/k, [{k: 2, x: -1}])
    check(DiracDelta(k*x), Q.negative(k) & Q.real(x), -DiracDelta(x)/k, [{k: -2, x: 1}])
    check(DiracDelta(3*x), Q.real(x), DiracDelta(x)/3, [{x: 1}, {x: -1}])
    # agrees with SymPy's own expansion convention
    assert refine(DiracDelta(k*x), Q.nonzero(k) & Q.real(x)) == \
        DiracDelta(k*x).expand(diracdelta=True, wrt=x)


@pytest.mark.parametrize("scale", [2, -3, S(1)/2])
def test_diracdelta_scaling_integral(scale):
    t = Symbol("t", real=True)
    refined = refine(DiracDelta(scale*t), Q.real(t))
    f = exp(t) + t**2 + 1
    lhs = integrate(DiracDelta(scale*t)*f, (t, -oo, oo))
    rhs = integrate(refined*f, (t, -oo, oo))
    assert lhs == rhs == 2/Abs(S(scale))


def test_diracdelta_unchanged():
    assert refine(DiracDelta(x), Q.real(x)) == DiracDelta(x)
    assert refine(DiracDelta(x), Q.nonnegative(x)) == DiracDelta(x)
    assert refine(DiracDelta(k*x), Q.real(k) & Q.real(x)) == DiracDelta(k*x)
    assert refine(DiracDelta(k*x), Q.nonzero(k)) == DiracDelta(k*x)
    # derivatives are not rescaled
    assert refine(DiracDelta(k*x, 1), Q.positive(k) & Q.real(x)) == DiracDelta(k*x, 1)
    assert mod.refine_DiracDelta(DiracDelta(x), Q.real(x)) is None


# ------------------------------------------------------------ KroneckerDelta

@pytest.mark.parametrize("assumptions, expected, samples", [
    (Q.eq(i, j), S.One, [{i: 2, j: 2}, {i: 0, j: 0}]),
    (Q.eq(j, i), S.One, [{i: -1, j: -1}]),
    (Q.zero(i - j), S.One, [{i: 4, j: 4}]),
    (Q.ne(i, j), S.Zero, [{i: 1, j: 2}]),
    (Q.ne(j, i), S.Zero, [{i: 1, j: 2}]),
    (Q.nonzero(i - j), S.Zero, [{i: 3, j: 0}]),
    (Q.positive(i - j) & Q.integer(i) & Q.integer(j), S.Zero, [{i: 3, j: 2}]),
    (Q.positive(i) & Q.negative(j), S.Zero, [{i: 1, j: -1}]),
    (Q.lt(i, j), S.Zero, [{i: 1, j: 2}]),
    (Eq(i, j), S.One, [{i: 5, j: 5}]),
])
def test_kroneckerdelta(assumptions, expected, samples):
    check(KroneckerDelta(i, j), assumptions, expected, samples)


def test_kroneckerdelta_unchanged():
    assert refine(KroneckerDelta(i, j), True) == KroneckerDelta(i, j)
    assert refine(KroneckerDelta(i, j), Q.integer(i) & Q.integer(j)) == KroneckerDelta(i, j)
    assert mod.refine_KroneckerDelta(KroneckerDelta(i, j), True) is None


def test_kroneckerdelta_infinite_does_not_trust_eq():
    """SymPy's ask claims ``Q.eq(x, y)`` for ``x = -oo`` and ``y <= 0``.

    With a ``Q.eq`` fact present (so the relation is asked at all) the
    handler used to return ``1``; ``KroneckerDelta(-oo, -1)`` is ``0``.
    """
    z_, w_ = symbols("z_ w_")
    assumptions = Q.negative_infinite(i) & Q.extended_nonpositive(j) & Q.eq(z_, w_)
    delta = KroneckerDelta(i, j)
    got = refine(delta, assumptions)
    assert got == delta
    assert delta.subs({i: -oo, j: -1}) == 0
    both = Q.negative_infinite(i) & Q.negative_infinite(j) & Q.eq(z_, w_)
    assert refine(delta, both) == delta


def test_kroneckerdelta_range():
    delta = KroneckerDelta(i, j, (1, 3))
    # equal indices may still lie outside the range: stays
    assert refine(delta, Q.eq(i, j)) == delta
    assert delta.subs({i: 7, j: 7}) == 0
    check(delta, Q.ne(i, j), S.Zero, [{i: 1, j: 2}])


# ----------------------------------------------------------------- Heaviside

@pytest.mark.parametrize("expr, assumptions, expected, samples", [
    (Heaviside(x), Q.positive(x), S.One, [{x: 1}, {x: S(1)/5}]),
    (Heaviside(x), Q.positive_infinite(x), S.One, [{x: oo}]),
    (Heaviside(x), Q.negative(x), S.Zero, [{x: -1}]),
    (Heaviside(x), Q.negative_infinite(x), S.Zero, [{x: -oo}]),
    (Heaviside(x), Q.zero(x), S.Half, [{x: 0}]),
    (Heaviside(x, 1), Q.zero(x), S.One, [{x: 0}]),
    (Heaviside(x, 0), Q.zero(x), S.Zero, [{x: 0}]),
    (Heaviside(x - y), Q.gt(x, y) & Q.positive(x - y), S.One, [{x: 2, y: 1}]),
])
def test_heaviside(expr, assumptions, expected, samples):
    check(expr, assumptions, expected, samples)


def test_heaviside_zero_nan_convention():
    assert refine(Heaviside(x, nan), Q.zero(x)) is nan


def test_heaviside_unchanged():
    assert refine(Heaviside(x), Q.real(x)) == Heaviside(x)
    assert refine(Heaviside(x), Q.nonnegative(x)) == Heaviside(x)
    assert refine(Heaviside(x), Q.nonzero(x)) == Heaviside(x)
    assert mod.refine_Heaviside(Heaviside(x), Q.real(x)) is None
