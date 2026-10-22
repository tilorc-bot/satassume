"""The rows of ``expm1`` and ``log1p`` (``sympy.codegen.cfunctions``;
``templates/cfunctions.py``, compiled by ``templates/wiring.py``, #249):
``log1p``'s slot ``x + 1``, and the family, declared by name, compiled on
its own first use.  Whether each compiled rule is true is checked at
concrete points in ``tests/test_rows_numeric.py``.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _rows_templates import compiled, rows_templates  # noqa: E402
from sympy import Symbol  # noqa: E402
from sympy.codegen.cfunctions import expm1, log1p  # noqa: E402

HEADS = (expm1, log1p)


def test_log1p_has_the_slot_x_plus_1():
    t = rows_templates(HEADS, "cfunctions")
    x = Symbol('x')
    assert [c.objs for c in compiled(t, log1p(x, evaluate=False))[0]] == [(x, log1p(x), x + 1)]
    assert [c.objs for c in compiled(t, expm1(x, evaluate=False))[0]] == [(x, expm1(x))]


def test_cfunctions_is_compiled_on_its_own_first_use():
    # sympy.codegen is imported by no other family: the family is declared
    # by name, and compiled with the first node of one of its functions
    code = """
import sys
from sympy import Q, Symbol, exp
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
CF = "satassume.knowledge.templates.cfunctions"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.positive(exp(x)), Q.real(x)) is True
assert "sympy.codegen" not in sys.modules and CF not in sys.modules
assert WIRING + ":cfunctions" in {m for _, m in registry._lazy}
from sympy.codegen.cfunctions import expm1, log1p
assert CF not in sys.modules
assert ask(Q.negative(log1p(x)), Q.negative(x) & Q.positive(x + 1)) is True
assert WIRING + ":cfunctions" not in {m for _, m in registry._lazy}
# the rows are read compiled: the family module is not imported
assert CF not in sys.modules
for h in (expm1, log1p):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":cfunctions"]
assert ask(Q.positive(expm1(x)), Q.positive(x)) is True
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
