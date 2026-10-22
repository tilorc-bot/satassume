"""The rules of ``expm1`` and ``log1p`` (``sympy.codegen.cfunctions``),
written as ``for_all`` statements (``templates/cfunctions.py``, compiled by
``templates/wiring.py``, #249), against the generators they replace
(``tests/_legacy_cfunctions_rules.py``, verbatim from d149951).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus, though the clauses differ.  Rows of the legacy generators the
rows leave out because the rule base and the other rows imply them:
``expm1``'s ``real -> real``, ``extended_real -> extended_real`` and
``zero -> zero`` (finite where finite, and the sign of the argument on the
extended reals) and its ``infinite & extended_negative -> negative`` (odd
there, so finite, and extended negative by the sign of the argument);
``log1p``'s ``real & positive(x + 1) -> real`` (positive at a positive
argument, negative at a negative one beyond -1, and 0 at 0).
:data:`ADDED` are the facts the rows give that the legacy rules
did not, each with its argument; a test checks that each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_cfunctions_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import Symbol  # noqa: E402
from sympy.codegen.cfunctions import expm1, log1p  # noqa: E402

HEADS = (expm1, log1p)

#: facts the rows give and the legacy rules did not
ADDED = {}


def _shifts(gen, *shifts):
    """``gen`` with the terms ``x + c`` its slots 2, 3, ... are (the legacy
    ``slots=``), which ``wiring.template`` takes from ``gen.shifts``."""
    def shifted_gen(R, c):
        gen(R, c)
    shifted_gen.shifts = shifts
    return shifted_gen


LEGACY_GEN = {expm1: legacy._expm1, log1p: _shifts(legacy._log1p, 1)}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "cfunctions", LEGACY_GEN, ADDED)
    # log1p's slot x + 1
    x = Symbol('x')
    assert [c.objs for c in new[log1p(x, evaluate=False)][0]] == [(x, log1p(x), x + 1)]


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_cfunctions_is_compiled_on_its_own_first_use():
    # sympy.codegen is imported by no other family: the family is declared
    # by name, and compiled with the first node of one of its functions
    code = """
import sys
from sympy import Q, Symbol, exp
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
CF = "satassume.knowledge.templates.cfunctions"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.positive(exp(x)), Q.real(x)) is True
assert "sympy.codegen" not in sys.modules and CF not in sys.modules
from sympy.codegen.cfunctions import expm1, log1p
assert CF not in sys.modules
assert ask(Q.negative(log1p(x)), Q.negative(x) & Q.positive(x + 1)) is True
assert CF in sys.modules
for h in (expm1, log1p):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":cfunctions"]
assert ask(Q.positive(expm1(x)), Q.positive(x)) is True
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
