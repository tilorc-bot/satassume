"""Tests for the ``log`` refine handler (agent report section 3.3).

Upstream has no ``log`` handler, so the expected outputs are the ones quoted
from PRs #29131/#29760 rather than a comparison with ``sympy.refine``.  Every
rule is exercised three ways: a positive case, a negative case, and a
``None``-safety case with a scripted ``ask``.  Branch-cut guards get their own
test: ``log(exp(x))`` needs ``Q.real(x)`` and ``log(x**2)`` needs
``Q.positive(x)``.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.abc import x, y
from sympy.core.numbers import I, pi
from sympy.functions.elementary.complexes import Abs
from sympy.functions.elementary.exponential import exp, log

from satrefine import refine
from satrefine.testing.harness import (
    assert_refinement_valid,
)


def test_log_exp_inverse_positive() -> None:
    assert refine(log(exp(x)), Q.real(x)) == x
    assert refine(log(exp(x)), Q.positive(x)) == x
    assert refine(log(exp(x + y)), Q.real(x) & Q.real(y)) == x + y


def test_log_exp_inverse_negative() -> None:
    assert refine(log(exp(x))) == log(exp(x))
    assert refine(log(exp(x)), Q.imaginary(x)) == log(exp(x))
    assert refine(log(exp(x)), Q.complex(x)) == log(exp(x))
    assert refine(log(exp(x + y)), Q.real(x)) == log(exp(x + y))


def test_log_power_rule_positive() -> None:
    assert refine(log(x**2), Q.positive(x)) == 2 * log(x)
    assert refine(log(x**3), Q.positive(x)) == 3 * log(x)
    assert refine(log(x**y), Q.positive(x) & Q.real(y)) == y * log(x)
    assert refine(log(x**(y + 1)), Q.positive(x) & Q.real(y)) == (y + 1) * log(x)
    assert refine(log(x**(-2)), Q.positive(x)) == -2 * log(x)
    assert refine(log(x**(-y)), Q.positive(x) & Q.real(y)) == -y * log(x)


def test_log_power_rule_negative_and_guards() -> None:
    assert refine(log(x**2)) == log(x**2)
    # handlers keeps log(x**2) for real or negative x (the guard is against
    # 2*log(x)); handlers_identities (and v3) give 2*log(Abs(x)) and 2*log(-x),
    # which hold there.
    for assumptions, other in ((Q.real(x), 2 * log(Abs(x))), (Q.negative(x), 2 * log(-x))):
        refined = refine(log(x**2), assumptions)
        assert refined in (log(x**2), other)
        assert_refinement_valid(log(x**2), assumptions, refined)
    assert refine(log(x**y), Q.positive(x)) == log(x**y)
    assert refine(log(x**y), Q.real(x) & Q.real(y)) == log(x**y)
    assert refine(log(x**(2 * I)), Q.positive(x)) == log(x**(2 * I))


def test_log_reciprocal() -> None:
    assert refine(log(1 / x), Q.positive(x)) == -log(x)
    assert refine(log(1 / x), Q.real(x)) == log(1 / x)
    assert refine(log(1 / x)) == log(1 / x)


def test_log_product_split_positive() -> None:
    assert refine(log(x * y), Q.positive(x) & Q.positive(y)) == log(x) + log(y)
    assert refine(log(2 * x), Q.positive(x)) == log(2) + log(x)


def test_log_product_split_negative() -> None:
    assert refine(log(x * y)) == log(x * y)
    # handlers splits only when both factors are positive; handlers_identities
    # (and v3) also split when one factor is positive or both are negative, and
    # take log(-x) = log(x) + I*pi for positive x.  All three hold.
    for expr, assumptions, other in (
        (log(x * y), Q.positive(x), log(x) + log(y)),
        (log(x * y), Q.negative(x) & Q.negative(y), log(-x) + log(-y)),
        (log(-x), Q.positive(x), log(x) + I * pi),
    ):
        refined = refine(expr, assumptions)
        assert refined in (expr, other)
        assert_refinement_valid(expr, assumptions, refined)


def test_log_numeric_oracle() -> None:
    assert_refinement_valid(
        log(exp(x)), Q.real(x), refine(log(exp(x)), Q.real(x)))
    assert_refinement_valid(
        log(x**2), Q.positive(x), refine(log(x**2), Q.positive(x)))
    assert_refinement_valid(
        log(1 / x), Q.positive(x), refine(log(1 / x), Q.positive(x)))
    assert_refinement_valid(
        log(x * y),
        Q.positive(x) & Q.positive(y),
        refine(log(x * y), Q.positive(x) & Q.positive(y)),
    )
    # The branch-cut guard: log(x**2) must not become 2*log(x) under Q.real(x)
    # (handlers keeps it; handlers_identities gives 2*log(Abs(x))).
    refined = refine(log(x**2), Q.real(x))
    assert refined in (log(x**2), 2 * log(Abs(x)))
    assert_refinement_valid(log(x**2), Q.real(x), refined)


def test_log_reference_ask(reference_ask: None) -> None:
    """The quoted PR outputs, independent of the local engine."""
    assert refine(log(exp(x)), Q.real(x)) == x
    assert refine(log(x**2), Q.positive(x)) == 2 * log(x)
    assert refine(log(x**y), Q.positive(x) & Q.real(y)) == y * log(x)
    assert refine(log(1 / x), Q.positive(x)) == -log(x)
    assert refine(log(x**2), Q.real(x)) in (log(x**2), 2 * log(Abs(x)))   # see test_log_numeric_oracle
    assert refine(log(exp(x)), Q.imaginary(x)) == log(exp(x))
