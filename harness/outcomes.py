"""The observable answer of one query, as a short string.

``True`` / ``False`` / ``None`` / ``ValueError`` (inconsistent assumptions)
are the four answers ``ask`` is specified to give; anything else is an
engine error and is reported as ``Error:<ExceptionType>``.  Two queries
agree iff their strings are equal, so a None against a definite answer is a
disagreement like any other.
"""
from __future__ import annotations

import satassume.sympy_api as _api

OUTCOMES = ("True", "False", "None", "ValueError")


def _ask():
    # the engine's own ask, even when harness.selfcheck has wrapped it
    return getattr(_api, "_selfcheck_original", None) or _api.ask


def outcome(prop, assum, engine) -> str:
    try:
        r = _ask()(prop, assum, engine)
    except ValueError:
        return "ValueError"
    except RecursionError:
        return "Error:RecursionError"
    except Exception as e:  # noqa: BLE001 - any other exception is an engine defect
        return f"Error:{type(e).__name__}"
    if r is True:
        return "True"
    if r is False:
        return "False"
    if r is None:
        return "None"
    return f"Value:{r!r}"
