"""Rules D1-D5 and M1-M4 of :mod:`satrefine.handlers_v2.mod_rem`."""
from __future__ import annotations

import pytest
from sympy import Mod, Q, Rem, S
from sympy.abc import k, n, x, y

from .conftest import INTEGER_SAMPLES, REAL_SAMPLES

NONZERO_REALS = tuple(v for v in REAL_SAMPLES if v != 0)
RATIONALS = (S.Zero, S.One, S(-1), S(2), S(-3), S(7), S.Half, S(-5) / 2, S(7) / 3)
NONZERO_RATIONALS = tuple(v for v in RATIONALS if v != 0)
NONZERO_INTEGERS = tuple(v for v in INTEGER_SAMPLES if v != 0)


class TestMod:
    def test_D1_D2_zero(self, check):
        check(Mod(x, y), Q.zero(x) & Q.nonzero(y), S.Zero, values={y: NONZERO_REALS})
        check(Mod(x, y), Q.integer(x / y), S.Zero, values={y: NONZERO_REALS})
        check(Mod(x, 1), Q.integer(x), S.Zero)
        check(Mod(n, 2), Q.even(n), S.Zero)

    def test_D3_multiples_of_the_modulus_drop(self, check):
        check(Mod(x + k * y, y), Q.integer(k), Mod(x, y), values={y: NONZERO_REALS})
        check(Mod(x + k, 1), Q.integer(k), Mod(x, 1))
        check(Mod(x + 2 * k + 1, 2), Q.integer(k), Mod(x + 1, 2))

    def test_D4_odd_mod_two(self, check):
        check(Mod(n, 2), Q.odd(n), S.One)
        check(Mod(n + 1, 2), Q.even(n), S.One)

    def test_D5_within_one_period(self, check):
        check(Mod(x, y), Q.nonnegative(x) & Q.positive(y) & Q.lt(x, y), x,
              values={x: (S.Zero, S.One, S.Half), y: (S(2), S(3), S(5) / 2)})
        check(Mod(x, y), Q.nonpositive(x) & Q.negative(y) & Q.gt(x, y), x,
              values={x: (S.Zero, S(-1), -S.Half), y: (S(-2), S(-3))})

    @pytest.mark.parametrize("expr, assumptions", [
        (Mod(x, y), Q.integer(x) & Q.integer(y)),
        (Mod(x, y), Q.zero(x)),
        (Mod(x + k, y), Q.integer(k)),
        (Mod(n, 2), Q.integer(n)),
        (Mod(x, y), Q.nonnegative(x) & Q.positive(y)),
        (Mod(x, y), Q.negative(x) & Q.positive(y) & Q.lt(x, y)),
    ])
    def test_does_not_fire(self, unchanged, expr, assumptions):
        unchanged(expr, assumptions)


class TestRem:
    def test_M1_M2_zero(self, check):
        check(Rem(x, y), Q.zero(x) & Q.nonzero(y), S.Zero, values={y: NONZERO_RATIONALS})
        check(Rem(x, y), Q.integer(x / y), S.Zero, values={y: NONZERO_RATIONALS})

    def test_M3_negative_odd_mod_two(self, check):
        check(Rem(n, 2), Q.odd(n) & Q.negative(n), S.NegativeOne)

    def test_M4_same_sign_is_mod(self, check):
        check(Rem(x, y), Q.nonnegative(x) & Q.positive(y), Mod(x, y),
              values={x: RATIONALS, y: NONZERO_RATIONALS})
        check(Rem(x, y), Q.nonpositive(x) & Q.negative(y), Mod(x, y),
              values={x: RATIONALS, y: NONZERO_RATIONALS})
        check(Rem(n, 2), Q.odd(n) & Q.positive(n), S.One)
        check(Rem(x, y), Q.nonnegative(x) & Q.positive(y) & Q.lt(x, y), x,
              values={x: (S.Zero, S.One, S.Half), y: (S(2), S(3))})

    def test_multiples_are_not_dropped_from_rem(self, unchanged):
        unchanged(Rem(x + 2 * k, 2), Q.integer(k))
        assert Rem(S(-1) + 2, 2) != Rem(S(-1), 2)

    @pytest.mark.parametrize("expr, assumptions", [
        (Rem(x, y), Q.real(x) & Q.positive(y)),
        (Rem(n, 2), Q.odd(n)),
        (Rem(x, y), Q.nonnegative(x) & Q.negative(y)),
    ])
    def test_does_not_fire(self, unchanged, expr, assumptions):
        unchanged(expr, assumptions)
