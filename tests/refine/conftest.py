"""Shared fixtures for the refine-handler tests (``tests/refine``).

The suite runs against the default handler package
(:data:`satrefine.DEFAULT_HANDLERS`, ``handlers_identities``) unless
``SATREFINE_HANDLERS`` selects another one.  It was written for the original
package, ``satrefine.handlers``, and still passes with
``SATREFINE_HANDLERS=handlers``.  Three markers record where the two differ
(see ``agent-reports/2026-09-25-phase3-default-report.md``):

``@pytest.mark.handlers("handlers")``
    tests the internals of that package (its modules, the order of its
    ``ask`` queries, its use of a patched ``satrefine._upstream.ask``);
    skipped under any other package.
``@pytest.mark.default_xfail("tests/refine_identities/needs/test_default_x.py", reason)``
    the default package gives a worse result; strict xfail under
    ``handlers_identities``, the needs test names the request.
``@pytest.mark.original_wrong(reason)``
    the expectation was corrected because ``handlers`` gives a wrong result;
    strict xfail under ``handlers``.
"""
from __future__ import annotations

import re
import sys
from collections.abc import Iterator

import pytest

from satrefine import HANDLERS_PACKAGE
from satrefine.testing.harness import query_scope_recorder
from satrefine.testing.harness import reference_ask as _reference_ask

_ORIGINAL_MODULE = re.compile(r"satrefine\.handlers\.[a-z]")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "handlers(name): tests the internals of satrefine.<name>; "
                            "skipped unless that package is loaded")
    config.addinivalue_line("markers", "default_xfail(needs, reason): strict xfail under handlers_identities; "
                            "needs names the needs/ test that asks for the fix")
    config.addinivalue_line("markers", "original_wrong(reason): corrected expectation; strict xfail under "
                            "the original handlers package")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        for mark in item.iter_markers("handlers"):
            if HANDLERS_PACKAGE != mark.args[0]:
                item.add_marker(pytest.mark.skip(
                    reason=f"tests the internals of satrefine.{mark.args[0]} "
                           f"(run with SATREFINE_HANDLERS={mark.args[0]})"))
        for mark in item.iter_markers("default_xfail"):
            needs, reason = mark.args
            item.add_marker(pytest.mark.xfail(HANDLERS_PACKAGE == "handlers_identities", strict=True,
                                              reason=f"{reason} (see {needs})"))
        for mark in item.iter_markers("original_wrong"):
            item.add_marker(pytest.mark.xfail(HANDLERS_PACKAGE == "handlers", strict=True,
                                              reason=f"satrefine.handlers is wrong here: {mark.args[0]}"))


@pytest.fixture
def reference_ask() -> Iterator[None]:
    """Run the local dispatcher with SymPy's ``ask`` bound."""
    with _reference_ask():
        yield


@pytest.fixture(autouse=True)
def _original_handlers_not_imported(request: pytest.FixtureRequest) -> Iterator[None]:
    """Importing a ``satrefine.handlers`` module registers its handler over the
    loaded package's, which silently changes every later test in the process."""
    yield
    if HANDLERS_PACKAGE != "handlers":
        leaked = sorted(name for name in sys.modules if _ORIGINAL_MODULE.match(name))
        assert not leaked, (f"{request.node.nodeid} imported {leaked} under "
                            f"SATREFINE_HANDLERS={HANDLERS_PACKAGE}; mark it @pytest.mark.handlers('handlers')")


@pytest.fixture(autouse=True)
def _record_query_scope(request: pytest.FixtureRequest) -> Iterator[None]:
    """Count each test's queries by satassume scope category (see the harness)."""
    yield from query_scope_recorder()(request)
