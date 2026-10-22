"""The rules of the Airy functions and of ``besselj``, ``bessely``,
``besseli`` and ``besselk``, written as ``for_all`` statements
(``templates/bessel.py``, compiled by ``templates/wiring.py``, #249),
against the generators they replace (``tests/_legacy_bessel_rules.py``,
verbatim from d149951: the factories ``_airy(kind)`` and
``_bessel(kind)``).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators entail each other on every node of its corpus (the
Bessel functions on every pair of arguments), though the clauses differ.
The rows add no fact.  A fact of the legacy generators the rows leave out
because the other rows imply it: ``besselk``'s ``real(nu) & positive(z) ->
real`` (it is positive there).
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_bessel_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import (  # noqa: E402
    Basic, Symbol, airyai, airyaiprime, airybi, airybiprime, besseli, besselj, besselk, bessely,
)

HEADS = (airyai, airybi, airyaiprime, airybiprime, besselj, bessely, besseli, besselk)

#: facts the rows give and the legacy rules did not
ADDED = {}


def _bessel(kind):
    """``legacy._bessel(kind)``, registered with ``functions.nary`` for two
    arguments (a node of another number gets no facts either way)."""
    gen = legacy._bessel(kind)

    def bessel(R, n):
        gen(R, n)
    bessel.arity = 2
    return bessel


LEGACY_GEN = {
    airyai: legacy._airy('ai'), airybi: legacy._airy('bi'),
    airyaiprime: legacy._airy('aiprime'), airybiprime: legacy._airy('biprime'),
    besselj: _bessel('j'), bessely: _bessel('y'), besseli: _bessel('i'), besselk: _bessel('k'),
}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "bessel", LEGACY_GEN, ADDED)
    # the Bessel functions' node is slot 2, after the order and the argument
    assert {c.pattern.node for e, (cs, _) in new.items() if len(e.args) == 2 for c in cs} == {2}


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_a_node_of_another_number_of_arguments_gets_no_facts():
    t = eq.rows_templates(HEADS, "bessel")
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
