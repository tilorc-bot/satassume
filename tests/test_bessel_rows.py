"""The rows of the Airy functions and of ``besselj``, ``bessely``,
``besseli`` and ``besselk`` (``templates/bessel.py``, compiled by
``templates/wiring.py``, #249): the slots of their templates (the order
and the argument, then the node), and the family compiled on its own first
use.  Whether each compiled rule is true is checked at concrete points in
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
    Basic, Symbol, airyai, airyaiprime, airybi, airybiprime, besseli, besselj, besselk, bessely,
)

HEADS = (airyai, airybi, airyaiprime, airybiprime, besselj, bessely, besseli, besselk)


def test_the_node_of_a_bessel_function_is_slot_2():
    t = rows_templates(HEADS, "bessel")
    nu, z = Symbol('nu'), Symbol('z')
    for h in (besselj, bessely, besseli, besselk):
        e = h(nu, z, evaluate=False)
        assert [(c.objs, c.pattern.node) for c in compiled(t, e)[0]] == [((nu, z, e), 2)]


def test_a_node_of_another_number_of_arguments_gets_no_facts():
    t = rows_templates(HEADS, "bessel")
    a = Symbol('a')
    for h in HEADS:
        args = (a,) if h in (besselj, bessely, besseli, besselk) else (a, a)
        assert t[h](Basic.__new__(h, *args)) is None


def test_bessel_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Symbol, airyai, airyaiprime, airybi, airybiprime, besseli, besselj, besselk, bessely
from satassume import DictCache, Engine
from satassume.knowledge.templates.registry import registry
BESSEL = "satassume.knowledge.templates.bessel"
ZETA = "satassume.knowledge.templates.zeta_functions"
WIRING = "satassume.knowledge.templates.wiring"
nn = Symbol('nn', nonnegative=True)
assert Engine(cache=DictCache()).is_(airyai(nn), 'positive') is True
pending = {m for _, m in registry._lazy}
assert WIRING + ":bessel" not in pending and WIRING + ":zeta_functions" in pending
# the rows are read compiled: no family module is imported
assert BESSEL not in sys.modules and ZETA not in sys.modules
for h in (airyai, airybi, airyaiprime, airybiprime, besselj, bessely, besseli, besselk):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":bessel"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
