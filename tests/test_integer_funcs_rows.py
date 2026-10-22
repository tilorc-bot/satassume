"""The rules of ``floor`` and ``ceiling`` (those of their base class
``RoundFunction``, and their own), of ``factorial`` and of ``Mod``, written as
``for_all`` statements (``templates/integer_funcs.py``, compiled by
``templates/wiring.py``, #249), against the generators they replace
(``tests/_legacy_integer_funcs_rules.py``, verbatim from d149951).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus (``Mod`` on every pair of arguments), though the clauses
differ.  ``RoundFunction``'s template is compared on nodes
``RoundFunction(a, evaluate=False)``, those of ``floor`` and ``ceiling``
on their own nodes, so each class's template matches the legacy one.  Rows of the legacy generators the rows leave out because the
rule base and the other rows imply them: ``RoundFunction``'s ``real ->
integer`` (finite and extended real there, and a real value is an
integer) and, at an integer, ``odd <-> odd`` and ``zero <-> zero`` (the
value is an integer of the same parity and sign); ``factorial``'s
``integer & nonnegative -> positive`` (positive on the nonnegatives) and
the third alternative of ``ge2_alternatives``, ``even & positive ->
even`` (the rule base makes an even positive number a prime or a
composite).  The other two alternatives are a row each.  ``Mod``'s
``real & real & ~zero -> real`` (a real ``q != 0`` is positive or
negative, and the sign of the divisor makes the value nonnegative or
nonpositive).  :data:`ADDED`
are the facts the rows give that the legacy rules did not, each with its
argument; a test checks that each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_integer_funcs_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import Mod, Q, ceiling, factorial, floor  # noqa: E402
from sympy.functions.elementary.integers import RoundFunction  # noqa: E402

from satassume.knowledge.templates._rows import bind, f, x  # noqa: E402

HEADS = (RoundFunction, floor, ceiling, factorial, Mod)

#: facts the rows give and the legacy rules did not
ADDED = {}


def _nary(gen, arity):
    """``gen`` as ``functions.nary`` called it, with the number of
    arguments, which ``wiring.template`` takes from ``gen.arity``."""
    def nary_gen(R, c):
        gen(R, arity)
    nary_gen.arity = arity
    return nary_gen


LEGACY_GEN = {RoundFunction: legacy._round, floor: legacy._floor, ceiling: legacy._ceiling,
              factorial: legacy._factorial, Mod: _nary(legacy._mod, 2)}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "integer_funcs", LEGACY_GEN, ADDED)
    # Mod's node is slot 2, after its two arguments
    assert {c.pattern.node for e, (cs, _) in new.items() if type(e) is Mod for c in cs} == {2}


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


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
