"""The rows of the inverse trigonometric and hyperbolic functions
(``templates/inverse.py``, compiled by ``templates/wiring.py``, #249): the
slots of their templates (the terms ``x - 1`` and ``x + 1``, and the facts
of a constant argument of ``asin`` and ``acos``,
``wiring.UNIT_INTERVAL``), and the family compiled on its own first use.
Whether each compiled rule is true is checked at concrete points in
``tests/test_rows_numeric.py``.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _rows_templates import compiled, rows_templates  # noqa: E402
from sympy import (  # noqa: E402
    Float, Symbol, acos, acosh, acot, acoth, acsc, acsch, asec, asech, asin, asinh, atan, atanh,
)


HEADS = (asin, acos, asinh, acosh, atanh, acoth, asech, acsch, asec, acsc, atan, acot)


def test_the_slots_of_the_templates():
    t = rows_templates(HEADS, "inverse")
    a = Symbol('a')
    e = atanh(a, evaluate=False)
    assert [c.objs for c in compiled(t, e)[0]] == [(a, e, a - 1, a + 1)]
    # the facts of a constant argument of asin and acos
    for h in (asin, acos):
        assert compiled(t, h(Float(0.5), evaluate=False))[1], h


def test_inverse_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Q, Symbol, acos, acosh, acot, acoth, acsc, acsch, asec, asech, asin, asinh, atan, atanh
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
TRIG = "satassume.knowledge.templates.trig"
INVERSE = "satassume.knowledge.templates.inverse"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.real(atanh(x)), Q.negative(x - 1) & Q.positive(x + 1)) is True
pending = {m for _, m in registry._lazy}
assert WIRING + ":inverse" not in pending and WIRING + ":trig" in pending
# the rows are read compiled: no family module is imported
assert INVERSE not in sys.modules and TRIG not in sys.modules
for h in (asin, acos, atan, acot, asec, acsc, asinh, acosh, atanh, acoth, asech, acsch):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":inverse"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
