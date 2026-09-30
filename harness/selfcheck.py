"""Runtime self-check: every ``ask`` re-answered in a clean engine.

Switched on by the environment (read by ``satassume/sympy_api.py`` at
import, off by default)::

    SATASSUME_SELFCHECK=1        raise HistoryDependence on a mismatch
    SATASSUME_SELFCHECK=log      only record mismatches (see ``mismatches``)
    SATASSUME_SELFCHECK=warn     print a warning per mismatch, keep going
    SATASSUME_SELFCHECK_LEVEL=1  reference: a fresh Engine of the same
                                 configuration (default), 2: also clear the
                                 module memos and SymPy's cache
    SATASSUME_SELFCHECK_LOG=PATH append one JSON line per mismatch

or from code with ``install()``.  The wrapped ``ask`` answers as before
(the engine under test's answer is returned, or its ValueError raised);
the reference costs about one fresh query per call.
"""
from __future__ import annotations

import json
import os
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


def install_from_env() -> None:
    v = os.environ.get("SATASSUME_SELFCHECK", "")
    if not v or v == "0":
        return
    mode = {"1": "raise", "raise": "raise", "log": "log", "warn": "warn"}.get(v, "raise")
    level = int(os.environ.get("SATASSUME_SELFCHECK_LEVEL", "1"))
    install(level=level, mode=mode, log_path=os.environ.get("SATASSUME_SELFCHECK_LOG"))
