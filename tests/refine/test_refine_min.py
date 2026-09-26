"""Tests for the ``Min`` refine handler.

Rules from the missing-handler report section 3.9: two-argument order
relations, the ``0`` shortcuts when one argument is ``0``, single-minimum
selection for longer argument lists, and provably infinite arguments.  An
``ask`` answer of ``None`` never refines.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.abc import x, y, z
from sympy.core import S
from sympy.core.numbers import oo
from sympy.functions.elementary.miscellaneous import Min

from satrefine import refine
from satrefine.testing.harness import (
    assert_refinement_valid,
    assert_refines_like_sympy,
    stub_ask,
    use_ask,
)

REALS = [-2, -1, 0, 1, 2]
POSITIVE = [1, 2]


def test_two_argument_order_rules() -> None:
    assert refine(Min(x, y), Q.le(x, y)) == x
    assert refine(Min(x, y), Q.ge(x, y)) == y
    assert refine(Min(x, y), Q.lt(x, y)) == x
    assert refine(Min(x, y), Q.gt(x, y)) == y


def test_zero_argument_rules() -> None:
    assert refine(Min(x, 0), Q.positive(x)) is S.Zero
    assert refine(Min(x, 0), Q.zero(x)) is S.Zero
    assert refine(Min(x, 0), Q.nonnegative(x)) is S.Zero
    assert refine(Min(x, 0), Q.negative(x)) == x
    assert refine(Min(x, 0), Q.nonpositive(x)) == x


def test_multi_argument_single_minimum() -> None:
    assert refine(Min(x, y, z), Q.le(x, y) & Q.le(x, z)) == x
    assert refine(Min(x, y, z), Q.le(z, x) & Q.le(z, y)) == z
    assert refine(Min(x, y, z), Q.ge(y, x) & Q.ge(z, x)) == x
    assert refine(Min(x, y, z), Q.lt(x, y) & Q.lt(x, z)) == x


def test_multi_argument_without_single_minimum_unchanged() -> None:
    # x is only known to beat y; z is still a candidate for the minimum.
    # handlers leaves these; handlers_identities (and v3) drop y, which the
    # premises show is not the minimum.
    assert refine(Min(x, y, z), Q.le(x, y)) in (Min(x, y, z), Min(x, z))
    assert refine(Min(x, y, z), Q.le(x, y) & Q.le(z, y)) in (Min(x, y, z), Min(x, z))


def test_infinite_arguments() -> None:
    assert refine(Min(x, y), Q.negative_infinite(x)) == x
    assert refine(Min(x, y), Q.negative_infinite(y)) == y
    assert refine(Min(x, y), Q.positive_infinite(x)) == y
    assert refine(Min(x, y), Q.positive_infinite(y)) == x
    assert refine(
        Min(x, y), Q.positive_infinite(x) & Q.positive_infinite(y)
    ) in (S.Infinity, x, y)   # x and y are oo here
    assert refine(Min(x, 0), Q.positive_infinite(x)) is S.Zero
    # literal infinities already evaluate while the arguments are refined
    assert refine(Min(x, oo)) == x
    assert refine(Min(x, -oo)) is S.NegativeInfinity


def test_unmet_assumptions_unchanged() -> None:
    assert refine(Min(x, y), True) == Min(x, y)
    assert refine(Min(x, y), Q.real(x) & Q.real(y)) == Min(x, y)
    # x > 0 > y does decide it (the old expectation failed with every package).
    assert refine(Min(x, y), Q.positive(x) & Q.negative(y)) == y
    # handlers leaves Min(x, y) under Q.eq(x, y); handlers_identities and v3 give x.
    assert refine(Min(x, y), Q.eq(x, y)) in (Min(x, y), x)
    assert refine(Min(x, 0), Q.positive(y)) == Min(x, 0)
    assert refine(Min(x, y), Q.infinite(x)) == Min(x, y)


def test_none_answers_unchanged() -> None:
    with use_ask(stub_ask({})):
        assert refine(Min(x, y), Q.le(x, y)) == Min(x, y)
        assert refine(Min(x, 0), Q.positive(x)) == Min(x, 0)
        assert refine(Min(x, y, z), Q.le(x, y) & Q.le(x, z)) == Min(x, y, z)
        assert refine(Min(x, y), Q.positive_infinite(x)) == Min(x, y)


def test_numeric_oracle() -> None:
    assert_refinement_valid(Min(x, y), Q.le(x, y), x, values={x: REALS, y: REALS})
    assert_refinement_valid(Min(x, y), Q.ge(x, y), y, values={x: REALS, y: REALS})
    assert_refinement_valid(
        Min(x, 0), Q.positive(x), S.Zero, values={x: POSITIVE}
    )
    assert_refinement_valid(Min(x, 0), Q.zero(x), S.Zero, values={x: [0]})
    assert_refinement_valid(
        Min(x, y, z),
        Q.le(x, y) & Q.le(x, z),
        x,
        values={x: REALS, y: REALS, z: REALS},
    )
    assert_refinement_valid(
        Min(x, y), Q.negative_infinite(x), x, values={x: [-oo], y: REALS}
    )
    assert_refinement_valid(
        Min(x, y), Q.positive_infinite(x), y, values={x: [oo], y: REALS}
    )


def test_fidelity_when_sympy_does_not_refine() -> None:
    assert_refines_like_sympy(Min(x, y), Q.real(x) & Q.real(y))
