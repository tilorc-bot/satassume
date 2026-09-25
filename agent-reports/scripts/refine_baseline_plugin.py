"""Pytest plugin: log every refine ``ask`` with the combined backend's routing.

Used by ``2026-09-25-refine-capability-baseline.md``.  Load it with
``PYTEST_ADDOPTS="-p refine_baseline_plugin"`` and this directory on
``PYTHONPATH``; ``REFINE_BASELINE_QLOG=path`` names the JSON-lines output.

One line per query that reaches ``satrefine.backend.ask``::

    {"b": backend, "p": str(prop), "a": str(assumptions),
     "ans": answer, "route": reason}

``route`` is only present under the ``combined`` backend: ``null`` when
satassume's answer stands (including an undecided None), otherwise the
reason SymPy was asked (``matrix``, ``relation``, ``custom``, ``other``,
``no-theory``, ``inconsistent``, ``error``), as returned by
``satrefine.backend.route``.
"""
from __future__ import annotations

import json
import os

_log = None
_pending: list = []


def pytest_configure(config):
    global _log
    path = os.environ.get("REFINE_BASELINE_QLOG")
    if not path:
        return
    _log = open(path, "w")
    from satrefine import backend

    original_route = backend.route

    def route(proposition, assumptions=True):
        answer, reason = original_route(proposition, assumptions)
        _pending.append(reason)
        return answer, reason

    backend.route = route

    def observe(proposition, assumptions, name, answer):
        rec = {"b": name, "p": str(proposition), "a": str(assumptions),
               "ans": answer if answer in (True, False, None) else str(answer)}
        if name == "combined":
            rec["route"] = _pending.pop() if _pending else "?"
        _pending.clear()
        _log.write(json.dumps(rec) + "\n")

    backend.observers.append(observe)


def pytest_unconfigure(config):
    if _log is not None:
        _log.close()
