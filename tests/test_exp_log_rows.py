"""The rows of ``exp`` and ``log`` (``templates/exp_log.py``, compiled by
``templates/wiring.py``, #249): the slots of their templates (``exp``'s
rules of ``I*pi*c*s``, ``wiring.I_PI_ROOT``, and ``log``'s ``x - 1``),
``log`` of two arguments, and the family compiled on its own first use.
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
from sympy import I, Symbol, exp, log, pi  # noqa: E402

from satassume.knowledge.templates._rows import x  # noqa: E402

HEADS = (exp, log)


def test_the_slots_of_the_templates():
    t = rows_templates(HEADS, "exp_log")
    s = Symbol('s')
    for e, objs in ((exp(I*pi*s, evaluate=False), (I*pi*s, exp(I*pi*s), s)),
                    (exp(s, evaluate=False), (s, exp(s))),
                    (log(s, evaluate=False), (s, log(s), s - 1))):
        assert [c.objs for c in compiled(t, e)[0]] == [objs], e


def test_log_of_two_arguments_gets_no_facts():
    # log(x, b, evaluate=False) is log(x)/log(b), not log(x) (#191)
    t = rows_templates((log,), "exp_log")[log]
    node = log(x, 2, evaluate=False)
    assert len(node.args) == 2
    assert t(node) is None


def test_exp_log_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Q, Symbol, exp, log
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
TRIG = "satassume.knowledge.templates.trig"
EXP_LOG = "satassume.knowledge.templates.exp_log"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.positive(log(x)), Q.positive(x - 1)) is True
pending = {m for _, m in registry._lazy}
assert WIRING + ":exp_log" not in pending and WIRING + ":trig" in pending
# the rows are read compiled: no family module is imported
assert EXP_LOG not in sys.modules and TRIG not in sys.modules
for h in (exp, log):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":exp_log"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
