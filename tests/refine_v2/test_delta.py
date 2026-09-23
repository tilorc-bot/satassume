"""Rules of :mod:`satrefine.handlers_v2.delta`."""
from __future__ import annotations

from sympy import DiracDelta, Heaviside, KroneckerDelta, Q, S
from sympy.abc import i, j, x

from .conftest import REAL_SAMPLES

REAL = {x: REAL_SAMPLES}


def test_V1_dirac_delta(check, unchanged):
    check(DiracDelta(x), Q.nonzero(x), S.Zero, values=REAL)
    check(DiracDelta(x), Q.positive(x), S.Zero, values=REAL)
    check(DiracDelta(x, 2), Q.negative(x), S.Zero, values=REAL)
    unchanged(DiracDelta(x), Q.real(x))
    unchanged(DiracDelta(x), Q.zero(x))
    unchanged(DiracDelta(2 * x), Q.real(x))


def test_W1_W2_kronecker_delta(check, unchanged):
    check(KroneckerDelta(i, j), Q.zero(i - j), S.One)
    check(KroneckerDelta(i, j), Q.nonzero(i - j), S.Zero)
    check(KroneckerDelta(i, j), Q.positive(i - j), S.Zero)
    check(KroneckerDelta(i, j), Q.integer(i) & ~Q.integer(j), S.Zero,
          values={i: (S.Zero, S.One, S(-2)), j: (S.Half, S(7) / 3)})
    check(KroneckerDelta(i, j, (0, 3)), Q.nonzero(i - j), S.Zero)
    unchanged(KroneckerDelta(i, j, (0, 3)), Q.zero(i - j))
    assert KroneckerDelta(-1, -1, (0, 3)) == 0
    unchanged(KroneckerDelta(i, j), Q.integer(i) & Q.integer(j))
    unchanged(KroneckerDelta(i, j), Q.real(i - j))


def test_Z1_heaviside(check, unchanged):
    check(Heaviside(x), Q.positive(x), S.One, values=REAL)
    check(Heaviside(x), Q.negative(x), S.Zero, values=REAL)
    check(Heaviside(x), Q.zero(x), S.Half, values=REAL)
    check(Heaviside(x, 1), Q.zero(x), S.One, values=REAL)
    unchanged(Heaviside(x), Q.nonnegative(x))
    unchanged(Heaviside(x), Q.real(x))
