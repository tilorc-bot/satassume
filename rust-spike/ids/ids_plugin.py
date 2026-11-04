"""pytest -p ids_plugin: the test suite with ids installed. IDS_MODE (default live), IDS_SCOPE (default sa),
IDS_EXEMPT (a file of "file.py:qualname" lines; # comments)."""
import os

import ids_core

_ex = os.environ.get("IDS_EXEMPT")
_ex = [ln.split("#")[0].strip() for ln in open(_ex)] if _ex else []
ids_core.install(os.environ.get("IDS_MODE", "live"), os.environ.get("IDS_SCOPE", "sa"), [e for e in _ex if e])


def pytest_sessionfinish(session, exitstatus):
    if os.environ.get("IDS_REPORT"):
        import json
        json.dump(ids_core.report(), open(f"{os.environ['IDS_REPORT']}.{os.getpid()}.json", "w"))
