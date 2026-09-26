"""A pytest suite under each ``ask`` backend: running it and reading its junit file.

Each backend runs in its own pytest subprocess with ``SATREFINE_BACKEND`` set
(and ``SATREFINE_HANDLERS``, if given), so the environment of the calling
shell (``PYTHONPATH`` in particular) is what the runs see.  The junit file
also carries the ``ask`` query counts per test (properties ``ask_<kind>``).
"""
from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[3]
BACKENDS = ("sympy", "satassume", "combined")
PASSING = ("passed", "xpassed")
OUT_OF_SCOPE = ("relation", "matrix", "custom", "other")


def run_backend(backend: str, suite: str, junit: Path, pytest_args: list[str], handlers: str | None = None) -> float:
    """Run ``suite`` under ``backend``, writing ``junit``; the wall time."""
    env = dict(os.environ, SATREFINE_BACKEND=backend)
    if handlers:
        env["SATREFINE_HANDLERS"] = handlers
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
           "--junitxml", str(junit), suite, *pytest_args]
    start = perf_counter()
    subprocess.run(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return perf_counter() - start


def parse_junit(path: Path) -> tuple[dict[str, str], dict[str, str], dict[str, dict[str, int]], float]:
    """Return {test id: outcome}, {test id: failure message}, {test id: ask counts}, total time."""
    outcomes: dict[str, str] = {}
    messages: dict[str, str] = {}
    counts: dict[str, dict[str, int]] = {}
    total = 0.0
    for case in ET.parse(path).getroot().iter("testcase"):
        test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
        total += float(case.get("time", 0) or 0)
        outcome = "passed"
        counts[test_id] = {}
        for child in case:
            tag = child.tag
            if tag == "properties":
                for prop in child:
                    name = prop.get("name", "")
                    if name.startswith("ask_"):
                        counts[test_id][name[4:]] = int(prop.get("value", 0))
                continue
            if tag == "failure":
                outcome = "failed"
            elif tag == "error":
                outcome = "error"
            elif tag == "skipped":
                outcome = "xfailed" if child.get("type") == "pytest.xfail" else "skipped"
            else:
                continue
            messages[test_id] = (child.get("message") or "").strip().splitlines()[0][:160] if child.get("message") else (child.text or "").strip().splitlines()[-1][:160] if child.text else ""
        outcomes[test_id] = outcome
    return outcomes, messages, counts, total


def module_of(test_id: str) -> str:
    return test_id.split("::")[0].rsplit(".", 1)[-1]
