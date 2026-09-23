"""``arg``, ``sign``, ``conjugate``, ``re`` and ``im`` handlers."""
from __future__ import annotations

import pytest
from sympy import I, Q, S, conjugate, exp, im, log, pi, re, sign, sin, sqrt
from sympy.abc import n, x, y
from sympy.functions.elementary.complexes import arg

from .conftest import NONZERO_SAMPLES


class TestArg:
    def test_G1_to_G3(self, check):
        check(arg(x), Q.zero(x), S.NaN)
        check(arg(x), Q.positive(x), S.Zero)
        check(arg(x), Q.negative(x), pi)
        check(arg(exp(x)), Q.real(x), S.Zero)

    def test_G4_imaginary_axis(self, check):
        check(arg(x), Q.imaginary(x) & Q.positive(im(x)), pi / 2)
        check(arg(x), Q.imaginary(x) & Q.negative(im(x)), -pi / 2)

    def test_G5_positive_scaling(self, check):
        check(arg(x * y), Q.positive(x), arg(y))
        check(arg(x * y * 2), Q.positive(x), arg(y))

    @pytest.mark.parametrize("assumptions", [Q.real(x), Q.imaginary(x), Q.nonzero(x), True])
    def test_does_not_fire(self, unchanged, assumptions):
        unchanged(arg(x), assumptions)
        unchanged(arg(x * y), assumptions)


class TestSign:
    def test_S1_to_S3(self, check):
        check(sign(x), Q.zero(x), S.Zero)
        check(sign(x), Q.positive(x), S.One)
        check(sign(x), Q.negative(x), S.NegativeOne)
        check(sign(x**2), Q.real(x) & Q.nonzero(x), S.One)
        check(sign(exp(x)), Q.real(x), S.One)

    def test_S4_imaginary_axis(self, check):
        check(sign(x), Q.imaginary(x) & Q.positive(im(x)), I)
        check(sign(x), Q.imaginary(x) & Q.negative(im(x)), -I)

    def test_S5_positive_scaling(self, check):
        check(sign(x * y), Q.positive(y), sign(x))

    def test_does_not_fire(self, unchanged):
        unchanged(sign(x), Q.real(x))
        unchanged(sign(x), Q.nonzero(x))
        unchanged(sign(x * y), Q.real(y))


class TestConjugate:
    def test_C1_C2(self, check):
        check(conjugate(x), Q.real(x), x)
        check(conjugate(x), Q.imaginary(x), -x)
        check(conjugate(x + y), Q.real(x) & Q.imaginary(y), x - y)
        check(conjugate(sin(x)), Q.real(x), sin(x))
        check(conjugate(sqrt(x)), Q.nonnegative(x), sqrt(x))

    def test_C3_integer_power(self, check):
        check(conjugate(x**n), Q.integer(n), conjugate(x)**n, values={x: NONZERO_SAMPLES})

    def test_C4_C5_off_the_branch_cut(self, check):
        check(conjugate(x**y), Q.positive(x), x**conjugate(y))
        check(conjugate(x**y), Q.imaginary(x), (-x)**conjugate(y))
        check(conjugate(log(x)), Q.imaginary(x), log(-x))
        check(conjugate(log(x)), Q.positive(x), log(x))

    def test_does_not_fire(self, unchanged):
        unchanged(conjugate(x), Q.complex(x))
        unchanged(conjugate(x**y), Q.real(x))
        unchanged(conjugate(log(x)), Q.real(x))
        unchanged(conjugate(sqrt(x)), Q.real(x))

    def test_negative_real_counterexample(self):
        assert conjugate(sqrt(S(-4))) != sqrt(conjugate(S(-4)))


class TestReIm:
    def test_R1_R2(self, check):
        check(re(x), Q.real(x), x)
        check(im(x), Q.real(x), S.Zero)
        check(re(x), Q.imaginary(x), S.Zero)
        check(im(x), Q.imaginary(x), -I * x)

    def test_R3_expansion(self, check):
        check(re(x * y), Q.real(x) & Q.imaginary(y), S.Zero)
        check(im(1 / x), Q.imaginary(x), -I / x, values={x: (I, -I, 2 * I, -3 * I)})
        check(re(1 / (x + I * y)), Q.real(x) & Q.real(y), x / (x**2 + y**2),
              values={x: (1, 2, -1), y: (1, -2, 3)})

    def test_does_not_fire(self, unchanged):
        unchanged(re(x), Q.complex(x))
        unchanged(im(x), Q.complex(x))

    def test_R3_partial_expansion(self, check):
        check(im(x * y), Q.real(x), x * im(y))
