"""The rules of ``zeta``, ``dirichlet_eta`` and ``polylog``, written as
``for_all`` statements (``templates/zeta_functions.py``, compiled by
``templates/wiring.py``, #249), against the generators they replace
(``tests/_legacy_zeta_functions_rules.py``, verbatim from d149951).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus (``zeta`` and ``polylog`` on every pair of arguments too),
though the clauses differ.  ``Q.gt(x, 1)`` is ``extended_positive(x -
1)`` where the legacy rules said ``positive(x - 1)`` next to a premise
making ``x`` finite; the comparison links ``x`` and ``x - 1`` for that.
No row of the legacy generators is left out as implied.  :data:`ADDED`
are the facts the rows give that the legacy rules did not, each with its
argument; a test checks that each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_zeta_functions_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import Q, dirichlet_eta, polylog, zeta  # noqa: E402

from satassume.knowledge.templates._rows import x, y  # noqa: E402

HEADS = (zeta, dirichlet_eta, polylog)

#: facts the rows give and the legacy rules did not
ADDED = {
    # dirichlet_eta is entire: (1 - 2**(1 - s))*zeta(s), whose only pole,
    # at s = 1, the zero of the factor cancels; finite at every finite s
    dirichlet_eta: (Q.finite(x) >> Q.finite(dirichlet_eta(x)),),
}


def _legacy(gen, terms):
    """``gen`` as ``functions.nary`` called it, with the slots it was
    registered with (``zeta``: ``s - 1``; ``polylog``: ``z - 1``), as
    ``wiring.template`` takes them from ``gen.arity`` and ``gen.terms``."""
    def legacy_gen(R, n):
        gen(R, n)
    legacy_gen.arity = tuple(terms) if len(terms) > 1 else next(iter(terms))
    legacy_gen.terms = terms
    return legacy_gen


LEGACY_GEN = {
    zeta: _legacy(legacy._zeta, {1: ((0, -1),), 2: ((0, -1),)}),
    # nary's, of one argument: functions._unary's has the same objects
    dirichlet_eta: lambda R, c: legacy._dirichlet_eta(R, 1),
    polylog: _legacy(legacy._polylog, {2: ((1, -1),)}),
}

#: zeta(s) and zeta(s, a)
ARITIES = {zeta: (1, 2)}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "zeta_functions", LEGACY_GEN, ADDED, ARITIES)
    # the corpus reaches the slot s - 1 of zeta(s) (3 objects) and of
    # zeta(s, a) and polylog(s, z) (4 objects)
    for h, n in ((zeta, 3), (zeta, 4), (polylog, 4)):
        assert any(len(c.objs) == n for e, (cs, _) in new.items() if type(e) is h for c in cs)


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_a_node_of_another_number_of_arguments_gets_no_facts():
    from sympy import Basic
    t = eq.rows_templates(HEADS, "zeta_functions")
    for h, args in ((zeta, (x, y, x)), (dirichlet_eta, (x, y)), (polylog, (x,))):
        assert t[h](Basic.__new__(h, *args)) is None


def test_zeta_functions_are_compiled_on_their_own_first_use():
    code = """
import sys
from sympy import Q, Symbol, dirichlet_eta, polylog, zeta
from satassume import DictCache, Engine
from satassume.knowledge.templates.registry import registry
ZETA = "satassume.knowledge.templates.zeta_functions"
BESSEL = "satassume.knowledge.templates.bessel"
WIRING = "satassume.knowledge.templates.wiring"
s = Symbol('s', positive=True)
assert Engine(cache=DictCache()).is_(zeta(s + 1), 'positive') is True
assert ZETA in sys.modules and BESSEL not in sys.modules
for h in (zeta, dirichlet_eta, polylog):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":zeta_functions"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
