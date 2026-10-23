"""The rows of ``sinh``, ``cosh``, ``tanh``, ``coth``, ``sech`` and
``csch`` (``templates/hyperbolic.py``, compiled by ``templates/wiring.py``,
#249): the slots of ``cosh``'s templates, and the family compiled on its
own first use.  Whether each compiled rule is true is checked at concrete
points in ``tests/test_rows_numeric.py``.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _rows_templates import compiled, rows_templates  # noqa: E402
from sympy import I, Symbol, cosh, coth, csch, pi, sech, sinh, tanh  # noqa: E402


HEADS = (sinh, cosh, tanh, coth, sech, csch)


def test_cosh_has_the_rules_of_i_pi_c_s_and_r_plus_i_pi_c_s():
    # wiring.I_PI_MULTIPLE: the slot s of I*pi*c*s, and r and n of r + I*pi*n
    t = rows_templates(HEADS, "hyperbolic")
    s, r, n = Symbol('s'), Symbol('r', real=True), Symbol('n', integer=True)
    for arg, slots in ((s, ()), (I*pi*s, (s,)), (r + I*pi*n, (r, n))):
        e = cosh(arg, evaluate=False)
        assert [c.objs for c in compiled(t, e)[0]] == [(arg, e, *slots)]


def test_hyperbolic_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Q, Symbol, cosh, coth, csch, sech, sinh, tanh
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
TRIG = "satassume.knowledge.templates.trig"
HYPERBOLIC = "satassume.knowledge.templates.hyperbolic"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.positive(cosh(x)), Q.real(x)) is True
pending = {m for _, m in registry._lazy}
assert WIRING + ":hyperbolic" not in pending and WIRING + ":trig" in pending
# the rows are read compiled: no family module is imported
assert HYPERBOLIC not in sys.modules and TRIG not in sys.modules
for h in (sinh, cosh, tanh, coth, sech, csch):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":hyperbolic"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
