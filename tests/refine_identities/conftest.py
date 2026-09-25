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


FULL_ENV = "SATREFINE_FULL_TESTS"
"""Set to ``1`` to run the tests marked ``full`` (the gates do, as their own task)."""


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: regenerates a rule table with the live identity engine")
    config.addinivalue_line("markers", f"full: a long check (the fixpoint of a family's generated table, a battery "
                                       f"case the sampler needs half a minute for); skipped unless {FULL_ENV}=1")


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    """Skip the ``full`` tests unless :data:`FULL_ENV` is ``1``: they were most
    of the suite's wall time, and the default run keeps a smaller check of the
    same property (the fixpoint of one family, ``test_generated.py``).  Run
    them alone with ``SATREFINE_FULL_TESTS=1 pytest -m full tests/refine_identities``."""
    if os.environ.get(FULL_ENV) == "1":
        return
    skip = pytest.mark.skip(reason=f"long check: run with {FULL_ENV}=1")
    for item in items:
        if item.get_closest_marker("full"):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def shared(tmp_path_factory: pytest.TempPathFactory):
    """``shared(name, compute)``: see :func:`session_shared`."""
    return lambda name, compute: session_shared(tmp_path_factory, name, compute)


def session_shared(tmp_path_factory: pytest.TempPathFactory, name: str, compute):
    """``compute()`` once per test session, shared by the xdist workers.

    The first worker to get here computes the value and pickles it next to the
    session's temporary directory (the one all workers of a run share), under
    a lock; the others wait for it and load it.  Without xdist this is a plain
    session-scoped value."""
    import fcntl
    import pickle
    root = tmp_path_factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        root = root.parent
    path = root / f"shared-{name}.pickle"
    with open(root / f"shared-{name}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            return pickle.loads(path.read_bytes())
        value = compute()
        path.write_bytes(pickle.dumps(value))
        return value
