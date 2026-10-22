"""The rules of ``LambertW``, written as ``for_all`` statements
(``templates/lambertw.py``, compiled by ``templates/wiring.py``, #249),
against the generator they replace (``tests/_legacy_lambertw_rules.py``,
verbatim from d149951).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generator entail each other on every node of its corpus, of one
argument and of two, though the clauses differ.  ``Q.ge(x, -1/E)`` is
``extended_nonnegative(x + 1/E)`` where the legacy rules said
``nonnegative(x + 1/E)`` next to a premise making ``x`` finite; the
comparison links ``x`` and ``x + 1/E`` for that.  The rows add no fact.
A fact of the legacy generator the rows leave out because the other rows
imply it: ``complex(x) & ~extended_real(x) -> complex`` for ``LambertW(x)``
(``W_0`` is complex wherever ``x`` is: "Entire on the principal
branch").
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_lambertw_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import Basic, LambertW, Symbol, exp  # noqa: E402

from satassume.knowledge.templates import _common  # noqa: E402

HEADS = (LambertW,)

#: facts the rows give and the legacy rules did not
ADDED = {}


def _lambertw(R, n):
    legacy._lambertw(R, n)


# nary's, for LambertW(x) and LambertW(x, k), with the slots of
# legacy._lambertw_slots: x + 1/E, and k + 1 with a branch k
_lambertw.arity = (1, 2)
_lambertw.terms = {1: ((0, exp(-1)),), 2: ((0, exp(-1)), (1, 1))}

LEGACY_GEN = {LambertW: _lambertw}

#: LambertW(x) and LambertW(x, k)
ARITIES = {LambertW: (1, 2)}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "lambertw", LEGACY_GEN, ADDED, ARITIES)
    # LambertW(x): x, node, x + 1/E; LambertW(x, k): x, k, node, x + 1/E, k + 1
    assert {(len(e.args), len(c.objs)) for e, (cs, _) in new.items() for c in cs} == {(1, 3), (2, 5)}


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_the_slots_are_those_of_the_legacy_template():
    t = eq.rows_templates(HEADS, "lambertw")[LambertW]
    a, k = Symbol('a'), Symbol('k')
    try:
        for node in (LambertW(a, evaluate=False), LambertW(a, k, evaluate=False)):
            _common._CACHE.clear()
            assert t(node).objs == (*node.args, node, *legacy._lambertw_slots(node.args))
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
