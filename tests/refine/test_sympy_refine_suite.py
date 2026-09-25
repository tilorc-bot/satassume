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
    ("test_matrixelement", "matrixelement_index_order", "x[i, j] under Q.symmetric(x) is not swapped to x[j, i]"),
]:
    globals()[_name] = pytest.mark.default_xfail(
        f"tests/refine_identities/needs/test_default_{_topic}.py", _reason)(globals()[_name])
