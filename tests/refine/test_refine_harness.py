"""Self-tests for :mod:`satrefine.harness`."""
from __future__ import annotations


import pytest
from sympy.assumptions.ask import Q
from sympy.assumptions.ask import ask as sympy_ask
from sympy.abc import x
from sympy.functions.elementary.complexes import Abs

from satrefine.testing.harness import (
    assert_refines_like_sympy,
    assert_refinement_valid,
    recording_ask,
    reference_ask,
    scripted_ask,
    stub_ask,
    use_ask,
)


def test_reference_ask_restores_state() -> None:
    import satrefine.identities.compat.upstream as upstream

    original = upstream.ask
    with reference_ask():
        assert upstream.ask is sympy_ask
    assert upstream.ask is original


def test_reference_ask_matches_sympy() -> None:
    assert_refines_like_sympy(Abs(x), Q.positive(x))


def test_oracle_accepts_valid_refinement() -> None:
    assert_refinement_valid(x + 1, True, 1 + x)
    assert_refinement_valid(Abs(x), Q.positive(x), x)


def test_oracle_catches_invalid_refinement() -> None:
    with pytest.raises(AssertionError, match="invalid"):
        assert_refinement_valid(x + 1, True, x - 1)


def test_oracle_parity_excludes_non_integers() -> None:
    from sympy.core.numbers import Rational

    with pytest.raises(AssertionError, match="no satisfying sample"):
        assert_refinement_valid(x, Q.odd(x), x, values={x: [Rational(1, 2)]})
    assert_refinement_valid(x, Q.odd(x), x, values={x: [3]})


def test_oracle_needs_satisfying_sample() -> None:
    from sympy.core.numbers import oo

    with pytest.raises(AssertionError, match="no satisfying sample"):
        assert_refinement_valid(x, Q.infinite(x), x)
    assert_refinement_valid(x, Q.infinite(x), x, values={x: [oo]})


def test_stub_ask() -> None:
    fake = stub_ask({str(Q.positive(x)): True})
    assert fake(Q.positive(x), True) is True
    assert fake(Q.negative(x), True) is None


def test_scripted_ask() -> None:
    fake, log = scripted_ask([True, None])
    assert fake(Q.positive(x), True) is True
    assert fake(Q.positive(x), True) is None
    assert fake(Q.positive(x), True) is None
    assert len(log) == 3


def test_recording_ask_logs_with_stub() -> None:
    fake, log = recording_ask({str(Q.positive(x)): True})
    assert fake(Q.positive(x), True) is True
    assert fake(Q.negative(x), True) is None
    assert [entry[2] for entry in log] == [True, None]


def test_use_ask_patches_module_attribute() -> None:
    import satrefine.identities.compat.upstream as upstream

    fake = stub_ask({})
    with use_ask(fake):
        assert upstream.ask is fake
    assert upstream.ask is not fake
