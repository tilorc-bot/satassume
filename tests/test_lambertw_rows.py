"""The rows of ``LambertW`` (``templates/lambertw.py``, compiled by
``templates/wiring.py``, #249): the slots of its template for one argument
and for two (``x + 1/E``, and ``k + 1`` with a branch ``k``), and the
family compiled on its own first use.  Whether each compiled rule is true
is checked at concrete points in ``tests/test_rows_numeric.py``.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _rows_templates import rows_templates  # noqa: E402
from sympy import Basic, LambertW, Symbol, exp  # noqa: E402

from satassume.knowledge.templates import _common  # noqa: E402
from satassume.knowledge.templates.functions import shifted  # noqa: E402

HEADS = (LambertW,)


def test_the_slots_are_x_plus_1_over_e_and_k_plus_1():
    t = rows_templates(HEADS, "lambertw")[LambertW]
    a, k = Symbol('a'), Symbol('k')
    try:
        for node, slots in ((LambertW(a, evaluate=False), (shifted(a, exp(-1)),)),
                            (LambertW(a, k, evaluate=False), (shifted(a, exp(-1)), shifted(k, 1)))):
            _common._CACHE.clear()
            assert t(node).objs == (*node.args, node, *slots)
    finally:
        _common._CACHE.clear()
    # Basic.__new__(LambertW) and three arguments: no facts
    assert t(Basic.__new__(LambertW)) is None
    assert t(Basic.__new__(LambertW, a, k, a)) is None


def test_lambertw_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import LambertW, Symbol
from satassume import DictCache, Engine
from satassume.knowledge.templates.registry import registry
LAMBERTW = "satassume.knowledge.templates.lambertw"
ZETA = "satassume.knowledge.templates.zeta_functions"
WIRING = "satassume.knowledge.templates.wiring"
p = Symbol('p', positive=True)
assert Engine(cache=DictCache()).is_(LambertW(p), 'positive') is True
# (exp_log is loaded: the slot p + 1/E is p + exp(-1))
pending = {m for _, m in registry._lazy}
assert WIRING + ":lambertw" not in pending and WIRING + ":zeta_functions" in pending
# the rows are read compiled: no family module is imported
assert LAMBERTW not in sys.modules and ZETA not in sys.modules
assert [t.__module__ for t in registry._by_class[LambertW]] == [WIRING + ":lambertw"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
