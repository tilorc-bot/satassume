"""SymPy's own ``test_refine.py`` run against :mod:`satrefine`.

The suite is imported from the SymPy on ``sys.path``; ``refine`` and
``refine_sin_cos`` are rebound to satrefine's in the imported module, and
the test functions are re-exported so pytest collects them.  Which engine
answers the handlers' questions is chosen by :mod:`satrefine.backend`.
"""
import pytest

from satrefine import refine as _refine
from satrefine import refine_sin_cos as _refine_sin_cos
from sympy.assumptions.tests import test_refine as _suite

_suite.refine = _refine
_suite.refine_sin_cos = _refine_sin_cos

from sympy.assumptions.tests.test_refine import *  # noqa: E402,F401,F403


# Where handlers_identities falls short of SymPy's expectations (the needs
# tests name each case).  The functions are SymPy's; the marks are added here.
for _name, _topic, _reason in [
    ("test_pow1", "pow_of_pow", "sqrt(1/x) for positive x, and (-1)**((-1)**x/2 + c), see also needs/test_default_neg_one_power_exponent.py"),
    ("test_pow2", "neg_one_power_exponent", "(-1)**((-1)**x/2 + c) is not reduced for integer x"),
    ("test_sin_cos", "odd_half_pi_sign_form", "odd multiples of pi/2 give -(-1)**(n/2 + 3/2) instead of (-1)**((n + 1)/2)"),
    ("test_floor_ceiling", "floor_ceiling", "floor/ceiling of an infinite argument or of a sum of floors is not simplified"),
]:
    globals()[_name] = pytest.mark.default_xfail(
        f"tests/refine_identities/needs/test_default_{_topic}.py", _reason)(globals()[_name])
