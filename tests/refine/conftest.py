"""Shared fixtures for the refine-handler tests (``tests/refine``).

The suite runs against the default handler package
(:data:`satrefine.DEFAULT_HANDLERS`, ``handlers_identities``) unless
``SATREFINE_HANDLERS`` selects another one.  It was written for the original
package, ``satrefine.handlers``, which was removed in phase 3 with the tests of
its internals (``agent-reports/archive/2026-09-26-phase3-refactor-retire-report.md``;
``agent-reports/archive/2026-09-25-phase3-default-report.md`` for how the suite was
moved to the default package).  One marker remains:

``@pytest.mark.default_xfail("tests/refine_identities/needs/test_default_x.py", reason)``
    the default package gives a worse result; strict xfail under
    ``handlers_identities``, the needs test names the request.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from satrefine import HANDLERS_PACKAGE
from satrefine.testing.harness import query_scope_recorder
from satrefine.testing.harness import reference_ask as _reference_ask


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "default_xfail(needs, reason): strict xfail under handlers_identities; "
                            "needs names the needs/ test that asks for the fix")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        for mark in item.iter_markers("default_xfail"):
            needs, reason = mark.args
            item.add_marker(pytest.mark.xfail(HANDLERS_PACKAGE == "handlers_identities", strict=True,
                                              reason=f"{reason} (see {needs})"))


@pytest.fixture
def reference_ask() -> Iterator[None]:
    """Run the local dispatcher with SymPy's ``ask`` bound."""
    with _reference_ask():
        yield


@pytest.fixture(autouse=True)
def _record_query_scope(request: pytest.FixtureRequest) -> Iterator[None]:
    """Count each test's queries by satassume scope category (see the harness)."""
    yield from query_scope_recorder()(request)
