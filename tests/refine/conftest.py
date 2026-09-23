"""Shared fixtures for the refine-handler tests (``tests/refine``)."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from satrefine.harness import query_scope_recorder
from satrefine.harness import reference_ask as _reference_ask


@pytest.fixture
def reference_ask() -> Iterator[None]:
    """Run the local dispatcher with SymPy's ``ask`` bound."""
    with _reference_ask():
        yield


@pytest.fixture(autouse=True)
def _record_query_scope(request: pytest.FixtureRequest) -> Iterator[None]:
    """Count each test's queries by satassume scope category (see the harness)."""
    yield from query_scope_recorder()(request)
