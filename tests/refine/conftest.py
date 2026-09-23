"""Shared fixtures for the refine-handler tests (``tests/refine``)."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterator

import pytest

from satrefine import backend
from satrefine.harness import reference_ask as _reference_ask


@pytest.fixture
def reference_ask() -> Iterator[None]:
    """Run the local dispatcher with SymPy's ``ask`` bound."""
    with _reference_ask():
        yield


@pytest.fixture(autouse=True)
def _record_query_scope(request: pytest.FixtureRequest) -> Iterator[None]:
    """Count the queries each test makes, by satassume scope category.

    The counts land in the junit XML as ``ask_<category>`` properties
    (``in_scope``, ``relation``, ``matrix``, ``custom``, ``other``, plus
    ``undecided`` for in-scope queries satassume answered ``None``), which
    ``tools/refine_scoreboard.py`` uses to tell out-of-scope failures from
    in-scope engine gaps.  Queries answered under a patched ``ask`` (the
    ``reference_ask`` fixture and the harness stubs) are not seen here.
    """
    from satassume.sympy_api import out_of_scope

    counts: Counter[str] = Counter()

    def observe(proposition, assumptions, name, answer) -> None:
        try:
            category = out_of_scope(proposition, assumptions)
        except Exception:  # noqa: BLE001 - classification must never fail a test
            category = "other"
        counts[category or "in_scope"] += 1
        if category is None and answer is None and name == "satassume":
            counts["undecided"] += 1

    backend.observers.append(observe)
    try:
        yield
    finally:
        backend.observers.remove(observe)
    for category, n in sorted(counts.items()):
        request.node.user_properties.append((f"ask_{category}", n))
