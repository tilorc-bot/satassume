"""The rules of ``erfinv``, ``erfcinv``, ``li``, ``Li`` and of the
functions of two arguments ``erf2``, ``expint`` and ``owens_t`` (SymPy
1.15), written as ``for_all`` statements in
``templates/error_functions.py`` (compiled by ``templates/wiring.py``,
#249), against the generators they replace
(``tests/_legacy_error_functions_2_rules.py``, verbatim from d149951).
``tests/test_error_functions_rows.py`` tests the family's other functions.

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus, though the clauses differ.  Rows the rows state in another
form: ``li``'s ``positive & positive(x - 1) -> real`` is ``Q.positive(x)
& Q.ne(x, 1) -> real``, ``Li``'s row (``li`` is negative on (0, 1)).
Rows of the legacy generators the rows leave out because the rule base and
the other rows imply them: ``owens_t``'s ``extended_real(h) &
extended_real(a) -> real`` (its sign for real ``h``, 0 at ``a == 0`` and
at a real infinite ``h``), ``extended_real(h) & zero(a) -> zero`` (0 at
``a == 0`` for a complex ``h`` and at a real infinite ``h``) and
``imaginary(h) & real(a) -> real`` (its sign for imaginary ``h``, 0 at ``a
== 0``).  ``Li``'s ``Q.positive(x) & Q.ne(x, 1) -> real`` follows from its
signs on (0, 1) and beyond 1 only through the links of ``x`` and ``x -
1`` (``_rows_equivalence._shift_links``), so it is kept.
:data:`ADDED` are the facts the rows give that the legacy rules did not,
each with its argument; a test checks that each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_error_functions_2_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import Li, erf2, erfcinv, erfinv, expint, li  # noqa: E402

try:  # new in SymPy 1.15
    from sympy.functions.special.error_functions import owens_t
except ImportError:  # pragma: no cover - depends on the SymPy version
    owens_t = None

UNARY = (erfinv, erfcinv, li, Li)
#: the functions of two arguments (each compared on every pair of arguments
#: of the corpus)
BINARY = (erf2, expint) + ((owens_t,) if owens_t is not None else ())
HEADS = UNARY + BINARY

#: facts the rows give and the legacy rules did not
ADDED = {}

LEGACY_GEN = {erfinv: legacy._erfinv, erfcinv: legacy._erfcinv, li: legacy._li, Li: legacy._Li,
              erf2: legacy._erf2, expint: legacy._expint}
if owens_t is not None:
    LEGACY_GEN[owens_t] = legacy._owens_t


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(UNARY, "error_functions", LEGACY_GEN, ADDED)
    # the corpus reaches the slots x - 1 and x + 1 or x - 2 (4 objects)
    assert any(len(c.objs) == 4 for cs, _ in new.values() for c in cs)


@pytest.mark.parametrize("head", BINARY, ids=lambda h: h.__name__)
def test_rows_of_two_arguments_entail_exactly_the_legacy_rules(head):
    new = eq.check_rows_entail_exactly((head,), "error_functions", LEGACY_GEN, ADDED)
    # the node is slot 2, after the two arguments
    assert {c.pattern.node for cs, _ in new.values() for c in cs} == {2}


def test_owens_t_is_declared_by_name():
    # new in SymPy 1.15: templates/__init__.py declares it by name, and with
    # an older SymPy its statements hold for no function
    from satassume.knowledge.templates import ROW_FAMILIES, wiring
    name = "sympy.functions.special.error_functions:owens_t"
    assert name in dict(ROW_FAMILIES)["error_functions"]
    assert (owens_t in wiring.functions("error_functions")) is (owens_t is not None)


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


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
assert ROWS in sys.modules
for h in (erfinv, erfcinv, li, Li, erf2, expint):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":error_functions"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
