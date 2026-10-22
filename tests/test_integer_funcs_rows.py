"""The rows of ``RoundFunction``, ``floor``, ``ceiling``, ``factorial``
and ``Mod`` (``templates/integer_funcs.py``, compiled by
``templates/wiring.py``, #249): a base class bound unevaluated, ``Mod``'s
node, and the family compiled on its own first use (``RoundFunction``'s
rules apply to ``floor`` and ``ceiling`` through the MRO).  Whether each
compiled rule is true is checked at concrete points in
``tests/test_rows_numeric.py``.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _rows_templates import compiled, rows_templates  # noqa: E402
from sympy import Mod, Q, Symbol, ceiling, factorial, floor  # noqa: E402
from sympy.functions.elementary.integers import RoundFunction  # noqa: E402

from satassume.knowledge.templates._rows import bind, f, x  # noqa: E402

HEADS = (RoundFunction, floor, ceiling, factorial, Mod)


def test_the_node_of_mod_is_slot_2():
    t = rows_templates(HEADS, "integer_funcs")
    a, b = Symbol('a'), Symbol('b')
    e = Mod(a, b, evaluate=False)
    assert [(c.objs, c.pattern.node) for c in compiled(t, e)[0]] == [((a, b, e), 2)]


def test_a_base_class_is_bound_unevaluated():
    # RoundFunction(x) raises: f stands for the class, unevaluated
    row = bind(Q.real(f(x)) >> Q.integer(f(x)), RoundFunction)
    assert row.args[1].arguments[0] == RoundFunction(x, evaluate=False)


def test_integer_funcs_is_compiled_on_its_own_first_use():
    # the rows of RoundFunction apply to floor and ceiling through the MRO,
    # after their own, as when functions.py registered them
    code = """
import sys
from sympy import Mod, Q, Symbol, ceiling, factorial, floor
from sympy.functions.elementary.integers import RoundFunction
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
INTEGER = "satassume.knowledge.templates.integer_funcs"
COMPLEX = "satassume.knowledge.templates.complex_parts"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.integer(floor(x)), Q.real(x)) is True
pending = {m for _, m in registry._lazy}
assert WIRING + ":integer_funcs" not in pending and WIRING + ":complex_parts" in pending
# the rows are read compiled: no family module is imported
assert INTEGER not in sys.modules and COMPLEX not in sys.modules
for h in (RoundFunction, floor, ceiling, factorial, Mod):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":integer_funcs"]
for h in (floor, ceiling):
    assert [t.__name__ for t in registry.templates_for(h)] == [
        h.__name__ + "_templates", "RoundFunction_templates"]
assert ask(Q.even(factorial(x)), Q.prime(x)) is True
y = Symbol('y')
assert ask(Q.nonnegative(Mod(x, y)), Q.real(x) & Q.positive(y)) is True
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
