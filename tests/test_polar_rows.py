"""The rules of ``exp_polar``, ``polar_lift`` and ``principal_branch``,
written as ``for_all`` statements (``templates/polar.py``, compiled by
``templates/wiring.py``, #249), against the generators they replace
(``tests/_legacy_polar_rules.py``, verbatim from d149951).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus (``principal_branch`` on every pair of arguments), though the
clauses differ.  :data:`ADDED` are the facts the rows give that the legacy
rules did not, each with its argument; a test checks that each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_polar_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import Q, Symbol, exp_polar, polar_lift, principal_branch  # noqa: E402
from sympy.assumptions.assume import Predicate  # noqa: E402

from satassume.knowledge.templates import _common, wiring  # noqa: E402
from satassume.knowledge.templates._rows import rules, x, y  # noqa: E402

HEADS = (exp_polar, polar_lift, principal_branch)

#: facts the rows give and the legacy rules did not
ADDED = {}


def _nary(arity):
    """``legacy._polar`` as ``functions.nary`` called it: with the number of
    arguments, which ``wiring.template`` takes from ``gen.arity``."""
    def gen(R, c):
        legacy._polar(R, arity)
    gen.arity = arity
    return gen


LEGACY_GEN = {exp_polar: legacy._exp_polar, polar_lift: _nary(1),
              principal_branch: _nary(2)}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "polar", LEGACY_GEN, ADDED)
    # principal_branch's node is slot 2, after its two arguments
    assert {c.pattern.node for e, (cs, _) in new.items() if type(e) is principal_branch
            for c in cs} == {2}


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


# -- rows about a function of several arguments ------------------------------

polar = Predicate('polar')
z = Symbol('z')


def _specs(head, table):
    R = _common.Rules()
    rules(head, table, __name__)(R, 2)
    return sorted((sorted(p), c) for p, c in R.rules)


def test_the_arguments_are_slots_0_to_n_minus_1_and_the_node_n():
    pb = principal_branch
    assert _specs(pb, (Q.finite(x) & Q.positive(y)) >> polar(pb(x, y))) == [
        ([(0, 'finite', True), (1, 'positive', True)], [(2, 'polar', True)])]
    # the slots follow the order of the node's arguments, not their names
    assert _specs(pb, Q.positive(x) >> polar(pb(y, x))) == [
        ([(1, 'positive', True)], [(2, 'polar', True)])]
    assert rules(pb, Q.positive(y) >> polar(pb(x, y)), __name__).arity == 2
    assert rules(exp_polar, Q.real(x) >> Q.positive(exp_polar(x)), __name__).arity == 1


def test_the_template_of_rows_of_two_arguments_has_their_objects():
    # the objects and slots of functions.nary's template: arguments, node
    a, p = Symbol('a'), Symbol('p', positive=True)
    e = principal_branch(a, p, evaluate=False)
    gen = rules(principal_branch, (Q.finite(x) & Q.positive(y)) >> polar(principal_branch(x, y)),
                __name__)
    _common._CACHE.clear()
    [c], _ = eq.compiled({principal_branch: wiring.template(principal_branch, gen)}, e)
    assert c.objs == (a, p, e) and c.pattern.node == 2
    _common._CACHE.clear()


@pytest.mark.parametrize("row, match", [
    (Q.positive(z) >> polar(principal_branch(x, y)), "more than one argument"),
    (Q.positive(y) >> polar(principal_branch(x, x)), "not distinct"),
    ((Q.positive(y) & Q.zero(principal_branch(y, x))) >> polar(principal_branch(x, y)),
     "more than one node"),
    (Q.gt(x, 1) >> polar(principal_branch(x, y)), "compares x with an integer"),
    ((Q.zero(principal_branch(x, y)), Q.zero(principal_branch(x, y)) >> Q.zero(x)), None),
])
def test_rows_of_two_arguments_that_do_not_compile(row, match):
    if match is None:
        rules(principal_branch, row, __name__)
        return
    with pytest.raises(ValueError, match=match):
        rules(principal_branch, row, __name__)


def test_rows_of_two_arities_are_refused():
    with pytest.raises(ValueError, match="rows of"):
        rules(exp_polar, (Q.real(x) >> Q.positive(exp_polar(x)),
                          Q.real(x) >> Q.positive(exp_polar(x, y))), __name__)


def test_polar_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Q, Symbol, exp_polar, polar_lift, principal_branch
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
POLAR = "satassume.knowledge.templates.polar"
COMPLEX = "satassume.knowledge.templates.complex_parts"
WIRING = "satassume.knowledge.templates.wiring"
x, p = Symbol('x'), Symbol('p')
assert ask(Q.positive(exp_polar(x)), Q.real(x)) is True
assert POLAR in sys.modules and COMPLEX not in sys.modules
for h in (exp_polar, polar_lift, principal_branch):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":polar"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
