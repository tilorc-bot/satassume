"""Fixtures for the ``handlers_identities`` tests.

Selects the package before ``satrefine`` is imported so a plain
``pytest tests/refine_identities`` works; ``SATREFINE_BACKEND`` selects the
ask backend as everywhere else.
"""
from __future__ import annotations

import os
import sys

import pytest

os.environ.setdefault("SATREFINE_HANDLERS", "handlers_identities")
os.environ.setdefault("SATREFINE_STRICT_LOOPS", "1")   # a tripped loop guard fails the test
if "satrefine" in sys.modules and "satrefine." + os.environ["SATREFINE_HANDLERS"] not in sys.modules:
    raise RuntimeError("satrefine was imported before conftest selected the handler package")

from satrefine.harness import query_scope_recorder  # noqa: E402


@pytest.fixture(autouse=True)
def _record_query_scope(request: pytest.FixtureRequest):
    yield from query_scope_recorder()(request)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: regenerates a rule table with the live identity engine (about a minute per family)")
