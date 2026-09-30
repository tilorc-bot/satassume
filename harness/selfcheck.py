"""Runtime self-check: every ``ask`` re-answered in a clean engine.

Off unless installed from code (a script, or a ``conftest.py``)::

    from harness import selfcheck
    selfcheck.install()                  # raise HistoryDependence on a mismatch
    selfcheck.install(mode="warn")       # print a warning per mismatch, keep going
    selfcheck.install(mode="log", log_path="mismatches.jsonl")
                                         # only record (``mismatches``, the file)
    selfcheck.install(level=2)           # also clear the module memos and
                                         # SymPy's cache before each reference

The engine itself is not touched: ``install`` replaces
``satassume.sympy_api.ask`` with a wrapper.  The wrapped ``ask`` answers
as before (the engine under test's answer is returned, or its ValueError
raised); the reference costs about one fresh query per call.  Level 2
clears process-wide state in the middle of other queries, so it is for
single-threaded use only.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional


class HistoryDependence(AssertionError):
    pass


mismatches: List[Dict[str, Any]] = []


def _normalize(r) -> str:
    return {True: "True", False: "False", None: "None"}.get(r, f"Value:{r!r}")


def install(level: int = 1, mode: str = "raise", log_path: Optional[str] = None) -> None:
    import satassume.sympy_api as api
    if getattr(api, "_selfcheck_original", None) is not None:
        return
    orig = api.ask
    api._selfcheck_original = orig

    def ask(proposition, assumptions=True, engine=None):
        from .state import config_of, reset_module_state
        eng = engine or api.default_engine()
        exc = None
        try:
            r = orig(proposition, assumptions, eng)
            warm = _normalize(r)
        except ValueError as e:
            exc, warm = e, "ValueError"
        cfg = config_of(eng)
        if level >= 2:
            reset_module_state()
        try:
            ref = _normalize(orig(proposition, assumptions, cfg.make()))
        except ValueError:
            ref = "ValueError"
        if warm != ref:
            from .sympy_io import to_srepr
            rec = {"prop": to_srepr(proposition), "assum": to_srepr(assumptions),
                   "engine": warm, "reference": ref, "config": cfg.to_dict()}
            mismatches.append(rec)
            if log_path:
                with open(log_path, "a") as fh:
                    fh.write(json.dumps(rec) + "\n")
            msg = (f"history-dependent answer: ask({proposition}, {assumptions}) = {warm} "
                   f"in the long-lived engine, {ref} in a fresh one")
            if mode == "raise":
                raise HistoryDependence(msg)
            if mode == "warn":
                print("satassume selfcheck: " + msg, file=sys.stderr)
        if exc is not None:
            raise exc
        return r

    ask.__doc__ = orig.__doc__
    api.ask = ask

