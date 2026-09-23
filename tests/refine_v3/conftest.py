"""Fixtures for the ``handlers_v3`` tests.

These tests target ``handlers_v3``; the module below selects it before
``satrefine`` is imported so a plain ``pytest tests/refine_v3`` works.
Setting ``SATREFINE_HANDLERS`` to another package runs this suite as a
cross-check of that package; ``SATREFINE_BACKEND`` selects the ask backend
(default ``combined``) as everywhere else.
"""
from __future__ import annotations

import os
import sys

import pytest

os.environ.setdefault("SATREFINE_HANDLERS", "handlers_v3")
if "satrefine" in sys.modules and "satrefine." + os.environ["SATREFINE_HANDLERS"] not in sys.modules:
    raise RuntimeError("satrefine was imported before conftest selected the handler package")

from satrefine.harness import query_scope_recorder  # noqa: E402


@pytest.fixture(autouse=True)
def _record_query_scope(request: pytest.FixtureRequest):
    """Count each test's queries by satassume scope category (see the harness)."""
    yield from query_scope_recorder()(request)
