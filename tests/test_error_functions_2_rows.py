"""The rules of ``erfinv``, ``erfcinv``, ``li`` and ``Li``, written as
``for_all`` statements in ``templates/error_functions.py`` (compiled by
``templates/wiring.py``, #249), against the generators they replace
(``tests/_legacy_error_functions_2_rules.py``, verbatim from d149951).
``tests/test_error_functions_rows.py`` tests the family's other functions.

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus, though the clauses differ.  Rows the rows state in another
form: ``li``'s ``positive & positive(x - 1) -> real`` is ``Q.positive(x)
& Q.ne(x, 1) -> real``, ``Li``'s row (``li`` is negative on (0, 1)).  No
row is dropped as implied: ``Li``'s ``Q.positive(x) & Q.ne(x, 1) ->
real`` follows from its signs on (0, 1) and beyond 1 only through the
links of ``x`` and ``x - 1`` (``_rows_equivalence._shift_links``), so it
is kept.
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
from sympy import Li, erfcinv, erfinv, li  # noqa: E402

HEADS = (erfinv, erfcinv, li, Li)

#: facts the rows give and the legacy rules did not
ADDED = {}

LEGACY_GEN = {erfinv: legacy._erfinv, erfcinv: legacy._erfcinv, li: legacy._li, Li: legacy._Li}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "error_functions", LEGACY_GEN, ADDED)
    # the corpus reaches the slots x - 1 and x + 1 or x - 2 (4 objects)
    assert any(len(c.objs) == 4 for cs, _ in new.values() for c in cs)


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_the_inverse_and_logarithmic_integrals_are_compiled_with_the_family():
    code = """
import sys
from sympy import Li, Q, Symbol, erfcinv, erfinv, li
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
ROWS = "satassume.knowledge.templates.error_functions"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.negative(li(x)), Q.positive(x) & Q.negative(x - 1)) is True
for other in ("trig", "inverse", "special"):
    assert "satassume.knowledge.templates." + other not in sys.modules, other
assert ROWS in sys.modules
for h in (erfinv, erfcinv, li, Li):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":error_functions"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
