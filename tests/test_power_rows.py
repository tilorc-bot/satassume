"""The template of the rows of ``Pow`` (``templates/power.py``,
``wiring.power``, #294): the slots it builds, the rules it adds that are not
rows, and the compilation of the rows on their first use.

The rows were shown to entail exactly the legacy Pow rules by an
equivalence test with a verbatim copy of them (``tests/_legacy_pow_rules.py``,
removed with it); now ``tests/test_rows_numeric.py`` checks that each
compiled rule is true at concrete points, and ``tests/test_rows_baseline.py``
that no clause of them is lost.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _rows_templates import compiled, rows_templates  # noqa: E402
from sympy import E, I, Pow, Rational, S, Symbol, exp, pi  # noqa: E402

from satassume.knowledge.rules import BASIS_INDEX  # noqa: E402

x, y = Symbol('x'), Symbol('y')
n = Symbol('n', integer=True)


def _blocks(e):
    return compiled(rows_templates((Pow,), 'power'), e)


def _objs(e):
    (c, *_), _ = _blocks(e)
    return c.objs


def test_the_slots_of_a_power():
    # base, exponent, node, then the terms: b - 1, b + 1, u, 2*e, the six
    # terms of a constant (resolved, no object), the s of E**(I*pi*c*s)
    none6 = (None,) * 6
    assert _objs(Pow(x, y, evaluate=False)) == (x, y, x**y, x - 1, x + 1, None, 2*y, *none6,
                                                None)
    # b**b: the base is the exponent
    b, e, *_ = _objs(Pow(x, x, evaluate=False))
    assert b is e is x
    # the u of exp(u), also of an unevaluated E**u
    for base in (exp(x), Pow(E, x, evaluate=False)):
        assert _objs(Pow(base, y, evaluate=False))[3:7] == (base - 1, base + 1, x, 2*y)
    # no b +- 1 when an argument is a number, no 2*e for a numeric exponent
    assert _objs(Pow(x, 2, evaluate=False))[3:] == (None,) * 11
    assert _objs(Pow(2, y, evaluate=False))[3:] == (None, None, None, 2*y, *none6, None)
    # E**(I*pi*c*s): s in the last slot
    assert _objs(Pow(E, I*pi*x, evaluate=False))[-1] == x


def test_the_rules_that_are_not_rows():
    # E**(I*pi*c*s) (core.ipi_rules): rules about s
    (c, *_), _ = _blocks(Pow(E, I*pi*x, evaluate=False))
    assert any(k == len(c.objs) - 1 for lits, _, _ in c.pattern.clauses for k, _, _ in lits)
    # 2**(1/2) is irrational (core.irrational_root)
    (c, *_), _ = _blocks(Pow(2, S.Half, evaluate=False))
    assert ((2, BASIS_INDEX['rational'], True),) in [lits for lits, _, _ in c.pattern.clauses]
    (c, *_), _ = _blocks(Pow(4, S.Half, evaluate=False))
    assert ((2, BASIS_INDEX['rational'], True),) not in [lits for lits, _, _ in c.pattern.clauses]
    # I**(1/3) (core._unit_power_units): the facts of its value
    _, formulas = _blocks(Pow(I, Rational(1, 3), evaluate=False))
    assert 'Not(extended_real(I**(1/3)),)' in formulas
    # (2*n + 3)**-1 (core._pow_bound_templates): a block about n
    cs, _ = _blocks(Pow(2*n + 3, -1, evaluate=False))
    assert len(cs) == 2 and cs[1].objs[0] == n


def test_power_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Pow, Q, Symbol
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
POWER = "satassume.knowledge.templates.power"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.positive(x + 1), Q.positive(x)) is True
# the rows of Add are loaded, not those of Pow
assert WIRING in sys.modules and Pow not in registry._by_class
assert ask(Q.real(x**2), Q.real(x)) is True
# the compiled rows, not the module of the rows
assert WIRING in sys.modules and POWER not in sys.modules
[t] = registry._by_class[Pow]
assert t.__module__ == WIRING + ":power", t.__module__
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stderr
