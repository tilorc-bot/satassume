"""The rows of ``zeta``, ``dirichlet_eta`` and ``polylog``
(``templates/zeta_functions.py``, compiled by ``templates/wiring.py``,
#249): the slots of their templates (``s - 1`` of ``zeta(s)`` and
``zeta(s, a)``, ``z - 1`` of ``polylog(s, z)``), a node of another number
of arguments, and the family compiled on its own first use.  Whether each
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
from sympy import dirichlet_eta, polylog, zeta  # noqa: E402

from satassume.knowledge.templates._rows import x, y  # noqa: E402

HEADS = (zeta, dirichlet_eta, polylog)


def test_the_slots_of_the_templates():
    t = rows_templates(HEADS, "zeta_functions")
    for e, objs in ((zeta(x, evaluate=False), (x, zeta(x), x - 1)),
                    (zeta(x, y, evaluate=False), (x, y, zeta(x, y), x - 1)),
                    (polylog(x, y, evaluate=False), (x, y, polylog(x, y), y - 1)),
                    (dirichlet_eta(x, evaluate=False), (x, dirichlet_eta(x)))):
        assert [c.objs for c in compiled(t, e)[0]] == [objs], e


def test_a_node_of_another_number_of_arguments_gets_no_facts():
    from sympy import Basic
    t = rows_templates(HEADS, "zeta_functions")
    for h, args in ((zeta, (x, y, x)), (dirichlet_eta, (x, y)), (polylog, (x,))):
        assert t[h](Basic.__new__(h, *args)) is None


def test_zeta_functions_are_compiled_on_their_own_first_use():
    code = """
import sys
from sympy import Q, Symbol, dirichlet_eta, polylog, zeta
from satassume import DictCache, Engine
from satassume.knowledge.templates.registry import registry
ZETA = "satassume.knowledge.templates.zeta_functions"
BESSEL = "satassume.knowledge.templates.bessel"
WIRING = "satassume.knowledge.templates.wiring"
s = Symbol('s', positive=True)
assert Engine(cache=DictCache()).is_(zeta(s + 1), 'positive') is True
pending = {m for _, m in registry._lazy}
assert WIRING + ":zeta_functions" not in pending and WIRING + ":bessel" in pending
# the rows are read compiled: no family module is imported
assert ZETA not in sys.modules and BESSEL not in sys.modules
for h in (zeta, dirichlet_eta, polylog):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":zeta_functions"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
