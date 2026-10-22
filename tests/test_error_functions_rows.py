"""The rows of ``erf``, ``erfc``, ``erfi``, ``Si``, ``Shi``, the Fresnel
integrals, ``Ei``, ``Ci`` and ``Chi`` (``templates/error_functions.py``,
compiled by ``templates/wiring.py``, #249): the family compiled on its own
first use.  Whether each compiled rule is true is checked at concrete
points in ``tests/test_rows_numeric.py``.
"""
import subprocess
import sys

import pytest

pytest.importorskip("sympy")


def test_error_functions_are_compiled_on_their_own_first_use():
    code = """
import sys
from sympy import Chi, Ci, Ei, Q, Shi, Si, Symbol, erf, erfc, erfi, fresnelc, fresnels
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
ROWS = "satassume.knowledge.templates.error_functions"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.positive(erfc(x)), Q.real(x)) is True
for other in ("trig", "hyperbolic", "special"):
    assert "satassume.knowledge.templates." + other not in sys.modules, other
pending = {m for _, m in registry._lazy}
assert WIRING + ":error_functions" not in pending and WIRING + ":trig" in pending
# the rows are read compiled: the family module is not imported
assert ROWS not in sys.modules
for h in (erf, erfc, erfi, Ei, Si, Shi, Ci, Chi, fresnels, fresnelc):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":error_functions"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
