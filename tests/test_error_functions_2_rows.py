"""The rows of ``erfinv``, ``erfcinv``, ``li``, ``Li``, ``erf2``,
``expint`` and ``owens_t`` (``templates/error_functions.py``, compiled by
``templates/wiring.py``, #249): the slots of their templates, ``owens_t``
declared by name, and the functions compiled with the family.  Whether
each compiled rule is true is checked at concrete points in
``tests/test_rows_numeric.py``.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _rows_templates import compiled, rows_templates  # noqa: E402
from sympy import Li, Symbol, erf2, erfcinv, erfinv, expint, li  # noqa: E402

try:  # new in SymPy 1.15
    from sympy.functions.special.error_functions import owens_t
except ImportError:  # pragma: no cover - depends on the SymPy version
    owens_t = None

UNARY = (erfinv, erfcinv, li, Li)
#: the functions of two arguments (each compared on every pair of arguments
#: of the corpus)
BINARY = (erf2, expint) + ((owens_t,) if owens_t is not None else ())
HEADS = UNARY + BINARY


def test_the_slots_of_the_templates():
    t = rows_templates(HEADS, "error_functions")
    a, b = Symbol('a'), Symbol('b')
    # the terms x - 1 and x + 1 or x - 2 of the functions of one argument
    for h, terms in ((erfinv, (a - 1, a + 1)), (erfcinv, (a - 1, a - 2)), (li, (a - 1,)),
                     (Li, (a - 1, a - 2))):
        e = h(a, evaluate=False)
        assert [c.objs for c in compiled(t, e)[0]] == [(a, e, *terms)], h
    # the node of a function of two arguments is slot 2
    for h in BINARY:
        e = h(a, b, evaluate=False)
        assert [(c.objs, c.pattern.node) for c in compiled(t, e)[0]] == [((a, b, e), 2)], h


def test_owens_t_is_declared_by_name():
    # new in SymPy 1.15: templates/__init__.py declares it by name, and with
    # an older SymPy its statements hold for no function
    from satassume.knowledge.templates import ROW_FAMILIES, wiring
    name = "sympy.functions.special.error_functions:owens_t"
    assert name in dict(ROW_FAMILIES)["error_functions"]
    assert (owens_t in wiring.functions("error_functions")) is (owens_t is not None)


def test_these_functions_are_compiled_with_the_family():
    code = """
import sys
from sympy import Li, Q, Symbol, erf2, erfcinv, erfinv, expint, li
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
ROWS = "satassume.knowledge.templates.error_functions"
WIRING = "satassume.knowledge.templates.wiring"
x, y = Symbol('x'), Symbol('y')
assert ask(Q.negative(li(x)), Q.positive(x) & Q.negative(x - 1)) is True
assert ask(Q.positive(expint(x, y)), Q.real(x) & Q.positive(y)) is True
for other in ("trig", "inverse", "special"):
    assert "satassume.knowledge.templates." + other not in sys.modules, other
pending = {m for _, m in registry._lazy}
assert WIRING + ":error_functions" not in pending and WIRING + ":trig" in pending
# the rows are read compiled: the family module is not imported
assert ROWS not in sys.modules
for h in (erfinv, erfcinv, li, Li, erf2, expint):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":error_functions"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
