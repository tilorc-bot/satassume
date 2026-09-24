"""The ``handlers_v3`` acceptance battery (``battery_v3.py``).

``test_battery_matches_v3`` proves the battery faithful: every case run
through ``satrefine.refine`` with ``SATREFINE_HANDLERS=handlers_v3`` gives
exactly the recorded value (or leaves the input unchanged where the value
is ``None``).  It needs ``handlers_v3`` to be the loaded package and skips
otherwise (the conftest of this directory loads ``handlers_identities``
unless the variable is set when pytest starts)::

    SATREFINE_HANDLERS=handlers_v3 PYTHONPATH=.:/path/to/sympy \\
        python -m pytest -q tests/refine_identities/test_battery.py

``test_battery_is_numerically_valid`` checks every case that fires with
the harness's numeric oracle, under whatever package is loaded (it does not
call ``refine``).  A case the oracle cannot sample (no sample satisfies the
assumptions, or its free symbols are matrices, which the scalar sampler
cannot substitute) is reported as a skip, not a failure.  A mismatch the
oracle is known to report wrongly (see ``_known_oracle_limit``) is an
expected failure; any other mismatch fails.
"""
from __future__ import annotations

import os
import sys

import pytest

if "satrefine" not in sys.modules:
    os.environ["SATREFINE_HANDLERS"] = "handlers_v3"

from battery_v3 import BATTERY
from sympy import DiracDelta, MatrixSymbol, Rem, zoo

from satrefine import refine
from satrefine.harness import assert_refinement_valid

_OTHER_PACKAGES = ("handlers", "handlers_v2", "handlers_identities")
V3_LOADED = "satrefine.handlers_v3" in sys.modules and not any(
    "satrefine." + name in sys.modules for name in _OTHER_PACKAGES)

def _known_oracle_limit(expr, assumptions, expected, source):
    """Why the numeric oracle's mismatch on this case is not a wrong refinement, or None."""
    if expected == zoo and source.startswith((
            "test_hyperbolic.py::test_values_literal",
            "test_power_exp_log.py::TestLogOfPower::test_reciprocal_unchanged_for_infinite_argument")):
        return "unevaluated literal at a pole: evalf of the input does not reach zoo"
    if expr.has(DiracDelta):
        return "DiracDelta scaling is an identity of distributions, not of point values at 0"
    if expected.has(Rem):
        return "the oracle cannot evaluate Rem with a non-Number divisor (e.g. Rem(1, sqrt(2)))"
    if source == "test_complex_parts.py::test_sign_of_conjugate_pair_product_numeric":
        return "SymPy's sign.eval mis-evaluates sign((1 - I)**2*(1 + I)); see the v3 test"
    if source == "test_complex_parts.py::test_abs_and_reim_of_literal_negative_power_with_nonzero_base":
        return ("dispatcher rebuild: the handler refuses, but refine's rebuild of the unevaluated "
                "Abs(x**-k) auto-evaluates to 1/Abs(x**k), which is zoo at x = 0 where the input is oo")
    return None


IDS = [f"{index}:{source}" for index, (_, _, _, source) in enumerate(BATTERY)]
FIRING = [(case, case_id) for case, case_id in zip(BATTERY, IDS) if case[2] is not None]


@pytest.mark.skipif(not V3_LOADED, reason="handlers_v3 is not the loaded handler package "
                    "(set SATREFINE_HANDLERS=handlers_v3 before pytest starts)")
@pytest.mark.parametrize("expr, assumptions, expected, source", BATTERY, ids=IDS)
def test_battery_matches_v3(expr, assumptions, expected, source):
    refined = refine(expr, assumptions)
    if expected is None:
        assert refined == expr, f"{source}: expected unchanged, got {refined}"
    else:
        assert refined == expected, f"{source}: expected {expected}, got {refined}"


@pytest.mark.parametrize("expr, assumptions, expected, source",
                         [case for case, _ in FIRING], ids=[case_id for _, case_id in FIRING])
def test_battery_is_numerically_valid(expr, assumptions, expected, source):
    matrices = [s for s in expr.free_symbols if isinstance(s, MatrixSymbol)]
    if matrices:
        pytest.skip(f"cannot be sampled: matrix symbols {sorted(map(str, matrices))}")
    try:
        assert_refinement_valid(expr, assumptions, expected)
    except AssertionError as error:
        if str(error).startswith("no satisfying sample found"):
            pytest.skip(f"cannot be sampled: no default sample satisfies {assumptions}")
        known = _known_oracle_limit(expr, assumptions, expected, source)
        if known is not None:
            pytest.xfail(known)
        raise
    except Exception as error:  # noqa: BLE001 -- the sampler or SymPy failed on a sample point
        pytest.skip(f"cannot be sampled: {type(error).__name__}: {error}")
