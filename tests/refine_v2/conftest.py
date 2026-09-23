"""Fixtures for the ``handlers_v2`` refine tests.

The handler package is selected through the ``SATREFINE_HANDLERS``
environment variable before :mod:`satrefine` is imported; setting it to
another package runs this suite as a cross-check of that package.
"""
from __future__ import annotations

import os
from typing import Any, Mapping, Sequence

import pytest

os.environ.setdefault("SATREFINE_HANDLERS", "handlers_v2")

import satrefine  # noqa: E402
from satrefine.harness import assert_refinement_valid  # noqa: E402
from sympy import I, Rational, S, pi, sqrt  # noqa: E402


# These tests target handlers_v2, but running them against another handler
# package (``SATREFINE_HANDLERS=handlers pytest tests/refine_v2``) is a
# deliberate cross-check, so no guard beyond the setdefault above.


@pytest.fixture(autouse=True)
def _record_query_scope(request: pytest.FixtureRequest):
    """Count each test's queries by satassume scope category (see the harness)."""
    from satrefine.harness import query_scope_recorder
    yield from query_scope_recorder()(request)


REAL_SAMPLES: tuple[Any, ...] = (
    S.Zero, S.One, S.NegativeOne, S(2), S(-2), S(3), S(-3), S(7), S(-7),
    S.Half, Rational(-1, 2), Rational(4, 3), Rational(-7, 3), sqrt(2), pi, -pi / 3,
)
"""Real samples, for assumptions stated as relations (which SymPy cannot
evaluate at complex numbers)."""

NONZERO_SAMPLES: tuple[Any, ...] = tuple(v for v in REAL_SAMPLES if v != 0) + (
    I, -I, 2 * I, 1 + I, 1 - I)

INTEGER_SAMPLES: tuple[Any, ...] = (S.Zero, S.One, S.NegativeOne, S(2), S(-2), S(3), S(-3), S(4), S(7), S(-8))


@pytest.fixture
def check():
    """``check(expr, assumptions, expected, values=None, samples=25)``:

    the local ``refine`` must produce ``expected`` (structurally) and the
    rewrite must agree numerically with ``expr`` at sample points that
    satisfy the assumptions."""

    def _check(expr: Any, assumptions: Any, expected: Any,
               values: Mapping[Any, Sequence[Any]] | None = None,
               samples: int = 25) -> Any:
        refined = satrefine.refine(expr, assumptions)
        assert refined == expected, f"refine({expr}, {assumptions}) = {refined}, expected {expected}"
        assert_refinement_valid(expr, assumptions, refined, samples=samples, values=values)
        return refined

    return _check


@pytest.fixture
def unchanged():
    """``unchanged(expr, assumptions)``: the local ``refine`` leaves ``expr``
    alone (the rule must not fire)."""

    def _unchanged(expr: Any, assumptions: Any = True) -> None:
        refined = satrefine.refine(expr, assumptions)
        assert refined == expr, f"refine({expr}, {assumptions}) = {refined}, expected no change"

    return _unchanged
