"""Rules of :mod:`satrefine.handlers_v2.factorials`."""
from __future__ import annotations

from sympy import FallingFactorial, Q, RisingFactorial, S, binomial, factorial, gamma, zoo
from sympy.abc import k, n, x

from .conftest import INTEGER_SAMPLES

NONNEG_INTEGERS = tuple(v for v in INTEGER_SAMPLES if v >= 0)


def test_K1_K2_factorial(check, unchanged):
    check(factorial(n), Q.zero(n), S.One)
    check(factorial(n), Q.integer(n) & Q.negative(n), zoo)
    unchanged(factorial(n), Q.integer(n))
    unchanged(factorial(n), Q.negative(n))


def test_Y1_Y2_gamma(check, unchanged):
    check(gamma(x), Q.integer(x) & Q.positive(x), factorial(x - 1))
    check(gamma(x + 1), Q.integer(x) & Q.nonnegative(x), factorial(x))
    check(gamma(x), Q.integer(x) & Q.nonpositive(x), zoo)
    check(gamma(x), Q.zero(x), zoo)
    unchanged(gamma(x), Q.positive(x))
    unchanged(gamma(x), Q.integer(x))


def test_B1_B4_binomial(check, unchanged):
    nonneg = Q.integer(n) & Q.nonnegative(n)
    check(binomial(n, k), Q.zero(k), S.One)
    check(binomial(n, k), Q.integer(k) & Q.negative(k), S.Zero)
    check(binomial(n, k), nonneg & Q.integer(k) & Q.negative(n - k), S.Zero)
    check(binomial(n, k), nonneg & Q.zero(n - k), S.One)
    unchanged(binomial(n, k), Q.integer(n) & Q.integer(k))
    unchanged(binomial(n, k), Q.zero(n - k))
    unchanged(binomial(n, k), Q.negative(k))
    assert binomial(-1, -1) == 0


def test_P1_P4_pochhammer(check, unchanged):
    positive = Q.integer(k) & Q.positive(k)
    check(RisingFactorial(x, k), Q.zero(k), S.One)
    check(FallingFactorial(x, k), Q.zero(k), S.One)
    check(RisingFactorial(x, k), Q.zero(x) & positive, S.Zero)
    check(FallingFactorial(x, k), Q.zero(x) & positive, S.Zero)
    check(RisingFactorial(x, k), Q.zero(x - 1), factorial(k))
    check(FallingFactorial(x, k), Q.zero(x - k) & Q.integer(k) & Q.nonnegative(k), factorial(k))
    unchanged(RisingFactorial(x, k), Q.zero(x))
    unchanged(FallingFactorial(x, k), Q.zero(x - k))
    unchanged(FallingFactorial(x, k), Q.integer(k) & Q.positive(k))
