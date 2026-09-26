"""The acceptance battery (``tests/refine_identities/battery_v3.py``): loading it and classifying a case.

A battery is a list of ``(expr, assumptions, expected, source)``.  For each
case the dispatcher's output is compared with ``expected`` by ``simplify`` of
the difference, checked numerically with the harness oracle, and classified
as one of ``KEYS``.  The numeric check follows ``test_battery.py``'s
conventions: matrix symbols, unsampleable assumptions, a raising sampler and
the oracle's known limits are unchecked, not wrong; a checker counts what it
could not check.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / "tests" / "refine_identities"
DEFAULT = TESTS / "battery_v3.py"

KEYS = ("fired, same as v3", "fired, other form", "did not fire, v3 expects a result",
        "unchanged as expected", "fired where v3 expects unchanged", "fired, numerically wrong", "crash")
SHORT = {"fired, same as v3": "same", "fired, other form": "other", "did not fire, v3 expects a result": "miss",
         "unchanged as expected": "quiet", "fired where v3 expects unchanged": "extra",
         "fired, numerically wrong": "wrong", "crash": "crash"}
UNCHECKED = "numerically unchecked (matrix symbols, no sample, or the sampler raised)"


def load_battery(path) -> tuple[list, int]:
    """(the cases of the battery module at ``path``, the number of cases in its ``SKIPPED``)."""
    spec = importlib.util.spec_from_file_location("battery", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return list(mod.BATTERY), len(getattr(mod, "SKIPPED", ()))


def family_of(source: str) -> str:
    """``test_trig.py::test_x`` -> ``trig``."""
    name = source.split("::", 1)[0]
    return name[len("test_"):-len(".py")] if name.startswith("test_") and name.endswith(".py") else name


def same(got, expected) -> bool:
    from sympy import simplify
    if got == expected:
        return True
    try:
        return simplify(got - expected) == 0
    except Exception:  # noqa: BLE001
        return False


def known_oracle_limit():
    """``test_battery._known_oracle_limit``: mismatches the numeric oracle is known to report wrongly."""
    if str(TESTS) not in sys.path:
        sys.path.insert(0, str(TESTS))
    try:
        return importlib.import_module("test_battery")._known_oracle_limit
    except Exception as e:  # noqa: BLE001  (test_battery needs pytest; without it every mismatch counts as wrong)
        print(f"  (known oracle limits unavailable: {type(e).__name__}: {e}; run with pytest installed)")
        return lambda expr, assumptions, expected, source: None


@dataclass
class Outcome:
    """How one battery case came out.

    ``key`` is one of ``KEYS``; ``got`` the result (None after a crash, whose
    exception is ``error``).  ``unchecked``: fired, but not checked
    numerically; then ``limit`` is the oracle's known limit that excused a
    mismatch, or ``unsampled`` the exception the sampler raised."""
    key: str
    got: object = None
    error: BaseException | None = None
    unchecked: bool = False
    limit: str | None = None
    unsampled: BaseException | None = None


def classify(expr, assumptions, expected, source, known_limit) -> Outcome:
    """Refine one battery case and classify the result (``known_limit`` from :func:`known_oracle_limit`)."""
    from sympy import MatrixSymbol, sympify

    from satrefine import refine
    from satrefine.testing.harness import assert_refinement_valid
    try:
        got = sympify(refine(expr, assumptions))
    except Exception as e:  # noqa: BLE001
        return Outcome("crash", error=e)
    out = Outcome("", got)
    fired = got != expr
    valid = True
    if fired:
        if expr.has(MatrixSymbol) or got.has(MatrixSymbol):
            out.unchecked = True
        else:
            try:
                assert_refinement_valid(expr, assumptions, got)
            except AssertionError as e:
                nosample = str(e).startswith("no satisfying sample")
                out.limit = None if nosample else known_limit(expr, assumptions, got, source)
                if nosample or out.limit:
                    out.unchecked = True
                else:
                    valid = False
            except Exception as e:  # noqa: BLE001  (e.g. the oracle's sampler asking about a relation at a complex point)
                out.unchecked = True
                out.unsampled = e
    if not valid:
        out.key = "fired, numerically wrong"
    elif expected is None:
        out.key = "unchanged as expected" if not fired else "fired where v3 expects unchanged"
    elif not fired:
        out.key = "did not fire, v3 expects a result"
    else:
        out.key = "fired, same as v3" if same(got, expected) else "fired, other form"
    return out
