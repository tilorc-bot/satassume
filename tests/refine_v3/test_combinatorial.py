"""Tests for ``satrefine.reference.v3.combinatorial``.

Each rule has a positive test, a numeric check that the original and the
refined expression agree at explicit points satisfying the precondition
(integers including 0 and negatives, and non-integer/complex points where
the rule allows them), and negative tests where a tempting rule is wrong.
"""
from __future__ import annotations

import itertools

import pytest
from sympy import (I, Q, Rational, S, Symbol, binomial, factorial, ff, gamma,
                   nan, oo, rf, symbols, zoo)

from satrefine import refine

n, k, x, y = symbols('n k x y')
HALF = Rational(1, 2)


def _value(e):
    """Numeric value, with every infinity folded to ``zoo``."""
    v = e.doit()
    if not v.has(zoo, oo, -oo, nan):
        v = v.evalf(30)
    if v is nan:
        return nan
    if v.has(zoo, oo, -oo):
        return zoo
    return v


def agree(orig, refined, points):
    """``orig`` and ``refined`` agree at every substitution in ``points``."""
    for pt in points:
        # simultaneous substitution: a sequential ``subs`` can hit SymPy's
        # eager ``binomial(-2, n) -> zoo`` (n of unknown integrality) and
        # make the comparison vacuous
        pt = {s: S(v) for s, v in pt.items()}
        a = _value(orig.xreplace(pt))
        b = _value(refined.xreplace(pt))
        if a is zoo or b is zoo or a is nan or b is nan:
            assert a == b, (orig, refined, pt, a, b)
        else:
            assert abs(complex(a) - complex(b)) < 1e-20 * max(1, abs(complex(a))), \
                (orig, refined, pt, a, b)


INTS = range(-5, 7)


# --------------------------------------------------------------------------
# factorial

def test_factorial_zero():
    assert refine(factorial(n), Q.zero(n)) == 1
    assert refine(factorial(n), Q.eq(n, 0)) == 1
    agree(factorial(n), S.One, [{n: 0}])


def test_factorial_one():
    assert refine(factorial(n), Q.eq(n, 1)) == 1
    assert refine(factorial(n - 1), Q.zero(n - 1)) == 1


def test_factorial_negative_integer():
    assert refine(factorial(n), Q.integer(n) & Q.negative(n)) is zoo
    agree(factorial(n), zoo, [{n: v} for v in range(-6, 0)])


def test_factorial_left_alone():
    # not rewritten to gamma
    for a in (Q.positive(n), Q.integer(n) & Q.positive(n), True,
              Q.negative(n), Q.integer(n), Q.nonnegative(n) & Q.integer(n)):
        assert refine(factorial(n), a) == factorial(n)
    # negative but not integer: finite (gamma extension)
    assert refine(factorial(n), Q.negative(n) & ~Q.integer(n)) == factorial(n)
    assert factorial(-HALF) is not zoo


# --------------------------------------------------------------------------
# binomial

def test_binomial_k_zero():
    assert refine(binomial(n, k), Q.zero(k)) == 1
    assert refine(binomial(n, k), Q.eq(k, 0)) == 1
    agree(binomial(n, k), S.One,
          [{n: v, k: 0} for v in list(INTS) + [HALF, I, 2 + 3*I]])


def test_binomial_k_one():
    assert refine(binomial(n, k), Q.eq(k, 1)) == n
    agree(binomial(n, k), n, [{n: v, k: 1} for v in list(INTS) + [HALF, I]])


def test_binomial_negative_k():
    a = Q.integer(k) & Q.negative(k)
    assert refine(binomial(n, k), a) == 0
    assert refine(binomial(n, k), a & Q.integer(n) & Q.nonnegative(n)) == 0
    # SymPy's convention: zero for negative integer k whatever n is,
    # including n == k (binomial(-1, -1) == 0).
    agree(binomial(n, k), S.Zero,
          [{n: a_, k: b} for a_ in list(INTS) + [HALF, I] for b in range(-4, 0)])


def test_binomial_k_equals_n():
    assert refine(binomial(n, n), Q.nonnegative(n)) == 1
    assert refine(binomial(n, k), Q.eq(n, k) & Q.nonnegative(n)) == 1
    assert refine(binomial(n, n), ~Q.integer(n)) == 1
    assert refine(binomial(n + 1, n + 1), Q.integer(n) & Q.nonnegative(n)) == 1
    agree(binomial(n, n), S.One,
          [{n: v} for v in [0, 1, 2, 5, HALF, Rational(-3, 2), I, 1 + I]])


def test_binomial_k_equals_n_negative_integer_not_one():
    # binomial(-1, -1) == 0 in SymPy: no rule when n may be a negative integer
    assert binomial(-1, -1) == 0
    assert refine(binomial(n, n), Q.integer(n)) == binomial(n, n)
    assert refine(binomial(n, n), True) == binomial(n, n)
    # for a negative integer n the negative-k rule applies instead
    assert refine(binomial(n, n), Q.integer(n) & Q.negative(n)) == 0


def test_binomial_k_equals_n_minus_one():
    assert refine(binomial(n, n - 1), Q.nonnegative(n)) == n
    assert refine(binomial(n, n - 1), ~Q.integer(n)) == n
    agree(binomial(n, n - 1), n, [{n: v} for v in [0, 1, 2, 5, HALF, I]])
    assert binomial(-1, -2) == 0
    assert refine(binomial(n, n - 1), Q.integer(n)) == binomial(n, n - 1)


def test_binomial_k_greater_than_n():
    a = Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.gt(k, n)
    assert refine(binomial(n, k), a) == 0
    a2 = Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.positive(k - n)
    assert refine(binomial(n, k), a2) == 0
    agree(binomial(n, k), S.Zero,
          [{n: a_, k: b} for a_ in range(0, 6) for b in range(a_ + 1, a_ + 5)])


def test_binomial_k_greater_than_n_negative():
    # k not an integer: nonzero
    a = Q.integer(n) & Q.nonnegative(n) & Q.gt(k, n)
    assert refine(binomial(n, k), a) == binomial(n, k)
    assert binomial(2, Rational(5, 2)) != 0
    # n a negative integer: binomial(-1, 2) == 1
    a = Q.integer(n) & Q.negative(n) & Q.integer(k) & Q.gt(k, n) & Q.positive(k)
    assert refine(binomial(n, k), a) == binomial(n, k)
    assert binomial(-1, 2) == 1


def test_binomial_negative_n_noninteger_k():
    a = Q.integer(n) & Q.negative(n) & ~Q.integer(k)
    assert refine(binomial(n, k), a) is zoo
    agree(binomial(n, k), zoo,
          [{n: a_, k: b} for a_ in range(-4, 0) for b in [HALF, Rational(-7, 3), I]])


def test_binomial_left_alone():
    a = Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.nonnegative(k)
    assert refine(binomial(n, k), a) == binomial(n, k)   # no symmetry, no factorials
    assert refine(binomial(n, k), Q.le(k, n) & a) == binomial(n, k)


# --------------------------------------------------------------------------
# RisingFactorial

def test_rf_k_zero_one():
    assert refine(rf(x, k), Q.zero(k)) == 1
    assert refine(rf(x, k), Q.eq(k, 1)) == x
    pts = list(INTS) + [HALF, I]
    agree(rf(x, k), S.One, [{x: v, k: 0} for v in pts])
    agree(rf(x, k), x, [{x: v, k: 1} for v in pts])


def test_rf_x_one():
    assert refine(rf(x, n), Q.eq(x, 1) & Q.integer(n) & Q.nonnegative(n)) == factorial(n)
    assert refine(rf(x, n), Q.eq(x, 1)) == factorial(n)
    agree(rf(x, n), factorial(n),
          [{x: 1, n: v} for v in list(INTS) + [HALF, Rational(-3, 2), I]])


def test_rf_zero_factor():
    a = Q.integer(x) & Q.nonpositive(x) & Q.integer(k) & Q.positive(x + k)
    assert refine(rf(x, k), a) == 0
    a = Q.integer(x) & Q.nonpositive(x) & Q.integer(k) & Q.gt(x + k, 0)
    assert refine(rf(x, k), a) == 0
    agree(rf(x, k), S.Zero,
          [{x: a_, k: b} for a_ in range(-4, 1) for b in range(1 - a_, 5 - a_)])


def test_rf_zero_factor_negative():
    # x + k <= 0: product misses 0, e.g. rf(-3, 2) == 6
    a = Q.integer(x) & Q.negative(x) & Q.integer(k) & Q.positive(k)
    assert refine(rf(x, k), a) == rf(x, k)
    assert rf(-3, 2) == 6


def test_rf_negative_x_noninteger_k():
    a = Q.integer(x) & Q.negative(x) & ~Q.integer(k)
    assert refine(rf(x, k), a) == 0
    agree(rf(x, k), S.Zero,
          [{x: a_, k: b} for a_ in range(-4, 0) for b in [HALF, Rational(7, 3), I]])


def test_rf_gamma_positive_x():
    assert refine(rf(x, k), Q.positive(x)) == gamma(x + k)/gamma(x)
    assert refine(rf(x, k), ~Q.integer(x)) == gamma(x + k)/gamma(x)
    pts = [{x: a_, k: b} for a_ in [HALF, 1, 2, 3, Rational(7, 2)]
           for b in [-4, -1, 0, 1, 2, 5, HALF, I]]
    pts += [{x: a_, k: b} for a_ in [-HALF, Rational(-7, 3), I, 1 + 2*I]
            for b in [-2, 0, 1, 3, HALF]]
    agree(rf(x, k), gamma(x + k)/gamma(x), pts)


def test_rf_gamma_positive_integer_x_becomes_factorials():
    a = Q.integer(x) & Q.positive(x) & Q.integer(k) & Q.nonnegative(k)
    r = refine(rf(x, k), a)
    assert r == factorial(x + k - 1)/factorial(x - 1)
    agree(rf(x, k), r, [{x: a_, k: b} for a_ in range(1, 5) for b in range(0, 5)])


def test_rf_no_gamma_for_nonpositive_integer_x():
    # rf(-2, 2) == 2 but gamma(0)/gamma(-2) is undefined
    assert rf(-2, 2) == 2
    for a in (Q.integer(x) & Q.negative(x), Q.integer(x), True,
              Q.negative(x), Q.integer(x) & Q.nonpositive(x) & Q.integer(k)):
        assert refine(rf(x, k), a) == rf(x, k)


# --------------------------------------------------------------------------
# FallingFactorial

def test_ff_k_zero_one():
    assert refine(ff(x, k), Q.zero(k)) == 1
    assert refine(ff(x, k), Q.eq(k, 1)) == x
    pts = list(INTS) + [HALF, I]
    agree(ff(x, k), S.One, [{x: v, k: 0} for v in pts])
    agree(ff(x, k), x, [{x: v, k: 1} for v in pts])


def test_ff_x_equals_k():
    assert refine(ff(x, k), Q.eq(x, k) & Q.integer(k) & Q.nonnegative(k)) == factorial(k)
    assert refine(ff(x, k), Q.eq(x, k) & Q.integer(k)) == factorial(k)
    agree(ff(x, x), factorial(x), [{x: v} for v in INTS])


def test_ff_x_equals_k_not_integer():
    assert refine(ff(x, k), Q.eq(x, k)) == ff(x, k)


def test_ff_factorial_ratio():
    a = Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.le(k, n)
    assert refine(ff(n, k), a) == factorial(n)/factorial(n - k)
    a = Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.nonnegative(n - k)
    assert refine(ff(n, k), a) == factorial(n)/factorial(n - k)
    a = Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.negative(k)
    assert refine(ff(n, k), a) == factorial(n)/factorial(n - k)
    agree(ff(n, k), factorial(n)/factorial(n - k),
          [{n: a_, k: b} for a_ in range(0, 6) for b in range(-4, a_ + 1)])


def test_ff_k_greater_than_x():
    a = Q.integer(n) & Q.nonnegative(n) & Q.integer(k) & Q.gt(k, n)
    assert refine(ff(n, k), a) == 0
    agree(ff(n, k), S.Zero,
          [{n: a_, k: b} for a_ in range(0, 5) for b in range(a_ + 1, a_ + 4)])


def test_ff_left_alone():
    # negative integer x: ff(-2, 2) == 6, factorial ratio undefined
    assert ff(-2, 2) == 6
    a = Q.integer(n) & Q.negative(n) & Q.integer(k) & Q.positive(k)
    assert refine(ff(n, k), a) == ff(n, k)
    # order unknown
    a = Q.integer(n) & Q.nonnegative(n) & Q.integer(k)
    assert refine(ff(n, k), a) == ff(n, k)
    # non-integer k
    a = Q.integer(n) & Q.nonnegative(n) & ~Q.integer(k) & Q.gt(k, n)
    assert refine(ff(n, k), a) == ff(n, k)


# --------------------------------------------------------------------------
# gamma

def test_gamma_positive_integer():
    assert refine(gamma(n), Q.integer(n) & Q.positive(n)) == factorial(n - 1)
    agree(gamma(n), factorial(n - 1), [{n: v} for v in range(1, 9)])


def test_gamma_shifted():
    assert refine(gamma(n + 1), Q.integer(n) & Q.nonnegative(n)) == factorial(n)
    agree(gamma(n + 1), factorial(n), [{n: v} for v in range(0, 8)])


def test_gamma_nonpositive_integer():
    assert refine(gamma(n), Q.integer(n) & Q.nonpositive(n)) is zoo
    assert refine(gamma(n + 3), Q.integer(n) & Q.nonpositive(n + 3)) is zoo
    assert refine(gamma(n + 3), Q.integer(n) & Q.le(n + 3, 0)) is zoo
    agree(gamma(n), zoo, [{n: v} for v in range(-6, 1)])


def test_gamma_left_alone():
    for a in (Q.positive(n), Q.integer(n), True, Q.negative(n),
              Q.integer(n) & Q.negative(n - 1)):
        assert refine(gamma(n), a) == gamma(n)
    # half-integers
    assert refine(gamma(n + HALF), Q.integer(n) & Q.nonnegative(n)) == gamma(n + HALF)
    assert refine(gamma(n + HALF), Q.integer(n) & Q.negative(n)) == gamma(n + HALF)


# --------------------------------------------------------------------------
# no handler ever claims more than its own argument grid supports

@pytest.mark.parametrize("a_, b", list(itertools.product(range(-3, 4), range(-3, 4))))
def test_grid_with_integer_assumptions(a_, b):
    """At each integer point, refine under the point's own facts agrees."""
    def facts(sym, v):
        f = Q.integer(sym)
        f &= Q.positive(sym) if v > 0 else (Q.zero(sym) if v == 0 else Q.negative(sym))
        return f
    assum = facts(x, a_) & facts(k, b)
    for f in (binomial, rf, ff):
        e = f(x, k)
        agree(e, refine(e, assum), [{x: a_, k: b}])
    for f in (factorial, gamma):
        agree(f(x), refine(f(x), facts(x, a_)), [{x: a_}])


def test_agree_substitutes_simultaneously():
    # binomial(k, n) at k = -2, n = 1 is -2; substituting k first would give
    # binomial(-2, n) == zoo and a vacuous check
    assert binomial(-2, n) is zoo
    agree(binomial(k, n), k, [{n: 1, k: v} for v in range(-4, 4)])
    with pytest.raises(AssertionError):
        agree(binomial(k, n), zoo, [{n: 1, k: -2}])
