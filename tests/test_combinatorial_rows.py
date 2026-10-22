"""The rows of ``factorial2``, ``subfactorial``, ``catalan``, ``andre``,
``partition``, ``genocchi``, ``RisingFactorial``, ``FallingFactorial`` and
``binomial`` (``templates/combinatorial.py``, compiled by
``templates/wiring.py``, #249): the slots of their templates, the hooks of
``wiring.py`` that are not rows (the facts of the value at a constant
integer argument, ``wiring.VALUE_AT_INTEGER``, and ``genocchi``'s rules
about ``n/2``, ``wiring.HALF_ARGUMENT``), and the family compiled on its
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
from sympy import (  # noqa: E402
    FallingFactorial, Integer, RisingFactorial, Symbol, andre, binomial, catalan, factorial2,
    genocchi, partition, subfactorial,
)

from satassume.knowledge.templates import wiring  # noqa: E402

HEADS = (factorial2, subfactorial, catalan, andre, partition, genocchi,
         RisingFactorial, FallingFactorial, binomial)


def test_the_slots_of_the_terms_and_of_a_constant_argument():
    # the slots x + 1 and x + 3 of factorial2, x - 1 and n/2 of genocchi
    t = rows_templates(HEADS, "combinatorial")
    n = Symbol('x')
    objs = {h: [c.objs for c in compiled(t, h(n, evaluate=False))[0]]
            for h in (factorial2, genocchi, catalan)}
    assert objs[factorial2] == [(n, factorial2(n), n + 1, n + 3)]
    assert objs[genocchi] == [(n, genocchi(n), n - 1, n/2)]
    assert objs[catalan] == [(n, catalan(n), n - 3)]
    # the facts of the value at a constant integer argument: a second block
    for h in wiring.VALUE_AT_INTEGER:
        assert len(compiled(t, h(Integer(2), evaluate=False))[0]) == 2, h


def test_genocchi_has_the_sign_of_the_parity_of_half_the_argument():
    # G_2k has the sign (-1)**k (wiring.HALF_ARGUMENT): its rules are in
    # the template of the rows, in the slot after x - 1
    n = Symbol('n')
    templates = rows_templates((genocchi,), "combinatorial")
    [c], _ = compiled(templates, genocchi(n, evaluate=False))
    assert c.objs[3] == n/2


def test_combinatorial_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import (FallingFactorial, Q, RisingFactorial, Symbol, andre, binomial, catalan,
                   factorial2, genocchi, partition, subfactorial)
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
COMB = "satassume.knowledge.templates.combinatorial"
INTEGER = "satassume.knowledge.templates.integer_funcs"
WIRING = "satassume.knowledge.templates.wiring"
n, k = Symbol('n'), Symbol('k')
assert ask(Q.integer(catalan(n)), Q.integer(n) & Q.nonnegative(n)) is True
pending = {m for _, m in registry._lazy}
assert WIRING + ":combinatorial" not in pending and WIRING + ":integer_funcs" in pending
# the rows are read compiled: no family module is imported
assert COMB not in sys.modules and INTEGER not in sys.modules
for h in (factorial2, subfactorial, catalan, andre, partition, genocchi,
          RisingFactorial, FallingFactorial, binomial):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":combinatorial"]
assert ask(Q.composite(catalan(n)), Q.integer(n) & Q.positive(n - 3)) is True
assert ask(Q.zero(binomial(n, k)), Q.integer(k) & Q.negative(k)) is True
assert ask(Q.negative(genocchi(n)), Q.even(n) & Q.positive(n) & Q.odd(n/2)) is True
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
