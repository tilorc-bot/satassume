"""Rules E1-E2 and L1-L5 of :mod:`satrefine.handlers_v2.exp_log`."""
from __future__ import annotations

from sympy import Abs, I, Q, Rational, S, exp, log, pi, zoo
from sympy.abc import n, x, y

from .conftest import NONZERO_SAMPLES


class TestExp:
    def test_E1_zero(self, check):
        check(exp(x), Q.zero(x), S.One)

    def test_E2_integer_multiples_of_pi_i(self, check):
        check(exp(2 * pi * I * x), Q.integer(x), S.One)
        check(exp(pi * I * x), Q.odd(x), S.NegativeOne)
        check(exp(pi * I * x), Q.integer(x), (-1)**x)
        check(exp(pi * I * (x + S.Half)), Q.integer(x), I * (-1)**x)
        check(exp(2 * pi * I * (x + Rational(1, 4))), Q.integer(x), I)
        check(exp(2 * pi * I * (x + y + Rational(1, 4))), Q.integer(x) & Q.integer(y), I)

    def test_E2_sum_arguments(self, check):
        check(exp(x + 2 * pi * I * n), Q.integer(n), exp(x))
        check(exp(x + pi * I * n), Q.integer(n), (-1)**n * exp(x))
        check(exp(x + pi * I * n), Q.odd(n), -exp(x))

    def test_does_not_fire(self, unchanged):
        unchanged(exp(pi * I * x), Q.real(x))
        unchanged(exp(x + pi * I * n), Q.rational(n))
        unchanged(exp(pi * x), Q.integer(x))


class TestLog:
    def test_L1_zero(self, check):
        check(log(x), Q.zero(x), zoo)

    def test_L2_log_exp_for_real(self, check, unchanged):
        check(log(exp(x)), Q.real(x), x)
        unchanged(log(exp(x)), Q.complex(x))
        unchanged(log(exp(x)), Q.imaginary(x))
        assert log(exp(4 * I)) != 4 * I

    def test_L3_L4_powers(self, check, unchanged):
        check(log(x**y), Q.positive(x) & Q.real(y), y * log(x))
        check(log(1 / x), Q.positive(x), -log(x))
        check(log(x**2), Q.real(x), 2 * log(Abs(x)))
        check(log(x**n), Q.real(x) & Q.even(n), n * log(Abs(x)), values={x: NONZERO_SAMPLES})
        check(log(x**2), Q.positive(x), 2 * log(x))
        unchanged(log(x**y), Q.positive(x))
        unchanged(log(x**2), Q.complex(x))
        unchanged(log(x**3), Q.real(x))
        assert log((-1)**2) != 2 * log(S(-1))

    def test_L5_positive_factors(self, check, unchanged):
        check(log(x * y), Q.positive(x) & Q.positive(y), log(x) + log(y))
        check(log(2 * x * y), Q.positive(x), log(2) + log(x) + log(y))
        unchanged(log(2 * x), True)
        unchanged(log(x * y), Q.real(x))
