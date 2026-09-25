"""Tests for the ``gamma`` refine handler.

Rule from the missing-handler report section 3.7: ``gamma(n)`` under
``Q.integer(n) & Q.nonpositive(n)`` is ``zoo`` (a pole).  Constants already
evaluate at construction, and an ``ask`` answer of ``None`` never refines.
"""
from __future__ import annotations
import pytest

from sympy.assumptions import Q
from sympy.abc import n
from sympy.core import S
from sympy.functions.combinatorial.factorials import factorial
from sympy.functions.special.gamma_functions import gamma

from satrefine import refine
from satrefine.harness import (
    assert_refinement_valid,
    assert_refines_like_sympy,
    recording_ask,
    stub_ask,
    use_ask,
)

INTEGERS = [0, -1, -2, -3, 1, 2, 3]


def test_nonpositive_integer_is_pole() -> None:
    assert refine(gamma(n), Q.integer(n) & Q.nonpositive(n)) is S.ComplexInfinity
    assert refine(gamma(n), Q.zero(n)) is S.ComplexInfinity
    assert refine(gamma(n), Q.integer(n) & Q.negative(n)) is S.ComplexInfinity
    assert refine(gamma(n), Q.even(n) & Q.nonpositive(n)) is S.ComplexInfinity


def test_non_poles_unchanged() -> None:
    # handlers_identities (and v3) give factorial(n - 1), which is gamma(n) for
    # positive integers; handlers leaves gamma(n).
    assert refine(gamma(n), Q.integer(n) & Q.positive(n)) in (gamma(n), factorial(n - 1))
    assert refine(gamma(n), Q.integer(n)) == gamma(n)
    assert refine(gamma(n), Q.positive(n)) == gamma(n)
    assert refine(gamma(n), Q.real(n)) == gamma(n)
    assert refine(gamma(n), True) == gamma(n)


def test_none_answers_unchanged() -> None:
    with use_ask(stub_ask({})):
        assert refine(gamma(n), Q.integer(n) & Q.nonpositive(n)) == gamma(n)
        assert refine(gamma(n), Q.zero(n)) == gamma(n)


def test_numeric_oracle() -> None:
    assert_refinement_valid(
        gamma(n),
        Q.integer(n) & Q.nonpositive(n),
        S.ComplexInfinity,
        values={n: INTEGERS},
    )
    assert_refinement_valid(gamma(n), Q.zero(n), S.ComplexInfinity, values={n: [0]})


def test_fidelity_when_sympy_does_not_refine() -> None:
    assert_refines_like_sympy(gamma(n), Q.positive(n))


@pytest.mark.handlers("handlers")
def test_ask_goes_through_upstream() -> None:
    proposition = Q.integer(n) & Q.nonpositive(n)
    fake, log = recording_ask({str(proposition): True})
    with use_ask(fake):
        assert refine(gamma(n), proposition) is S.ComplexInfinity
    assert [entry[0] for entry in log] == [proposition]
