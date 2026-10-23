"""The rows of ``exp_polar``, ``polar_lift`` and ``principal_branch``
(``templates/polar.py``, compiled by ``templates/wiring.py``, #249), and
rows about a function of several arguments: their slots, the rows
refused, rows of two numbers of arguments, inequalities about an argument
of several, and the family compiled on its own first use.  Whether each
compiled rule is true is checked at concrete points in
``tests/test_rows_numeric.py``.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _rows_templates import compiled, rows_templates  # noqa: E402
from sympy import (  # noqa: E402
    Basic, E, Q, Symbol, exp, exp_polar, polar_lift, principal_branch,
)
from sympy.assumptions.assume import Predicate  # noqa: E402

from satassume.knowledge.templates import _common, wiring  # noqa: E402
from satassume.knowledge.templates._rows import rules, x, y  # noqa: E402

HEADS = (exp_polar, polar_lift, principal_branch)


def test_the_node_of_principal_branch_is_slot_2():
    t = rows_templates(HEADS, "polar")
    a, p = Symbol('a'), Symbol('p')
    e = principal_branch(a, p, evaluate=False)
    assert [(c.objs, c.pattern.node) for c in compiled(t, e)[0]] == [((a, p, e), 2)]


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
    [c], _ = compiled({principal_branch: wiring.template(principal_branch, gen)}, e)
    assert c.objs == (a, p, e) and c.pattern.node == 2


@pytest.mark.parametrize("row, match", [
    (Q.positive(z) >> polar(principal_branch(x, y)), "more than one argument"),
    (Q.positive(y) >> polar(principal_branch(x, x)), "not distinct"),
    ((Q.positive(y) & Q.zero(principal_branch(y, x))) >> polar(principal_branch(x, y)),
     "more than one node"),
    (Q.gt(z, 1) >> polar(principal_branch(x, y)), "more than one argument"),
    ((Q.zero(principal_branch(x, y)), Q.zero(principal_branch(x, y)) >> Q.zero(x)), None),
])
def test_rows_of_two_arguments_that_do_not_compile(row, match):
    if match is None:
        rules(principal_branch, row, __name__)
        return
    with pytest.raises(ValueError, match=match):
        rules(principal_branch, row, __name__)


def _rules_of(gen, n):
    R = _common.Rules()
    gen(R, n)
    return sorted((sorted(p), c) for p, c in R.rules)


def test_rows_of_two_arities_give_each_node_the_rows_of_its_number_of_arguments():
    gen = rules(exp_polar, (Q.real(x) >> Q.positive(exp_polar(x)),
                            Q.real(y) >> Q.positive(exp_polar(x, y))), __name__)
    assert gen.arity == (1, 2) and gen.terms == {1: (), 2: ()}
    assert _rules_of(gen, 1) == [([(0, 'real', True)], [(1, 'positive', True)])]
    assert _rules_of(gen, 2) == [([(1, 'real', True)], [(2, 'positive', True)])]
    assert _rules_of(gen, 3) == []
    # functions.nary's template, for those numbers of arguments only
    t = wiring.template(exp_polar, gen)
    a, b = Symbol('a'), Symbol('b')
    for args, node in (((a,), 1), ((a, b), 2)):
        [c], _ = compiled({exp_polar: t}, exp_polar(*args, evaluate=False))
        assert c.pattern.node == node
    assert t(Basic.__new__(exp_polar, a, b, a)) is None


def test_an_inequality_about_an_argument_of_several_is_a_slot_after_the_node():
    """``Q.gt(y, 1)`` in a row about ``f(x, y)`` is ``extended_positive(y -
    1)``, slot 3; the terms are by argument, then by ``|c|``, ``x - c``
    first, and ``c`` is an exact real number (``-1/E``)."""
    pb = principal_branch
    gen = rules(pb, ((Q.gt(y, 1) & Q.ge(x, -1/E) & Q.eq(y, -1) & Q.lt(x, 2))
                     >> polar(pb(x, y))), __name__)
    assert gen.terms == {2: ((0, exp(-1)), (0, -2), (1, -1), (1, 1))}
    assert _rules_of(gen, 2) == [([(3, 'extended_nonnegative', True), (4, 'extended_negative', True),
                                   (5, 'extended_positive', True), (6, 'zero', True)],
                                  [(2, 'polar', True)])]
    a, p = Symbol('a'), Symbol('p')
    [c], _ = compiled({pb: wiring.template(pb, gen)}, pb(a, p, evaluate=False))
    assert c.objs[3:] == (a + exp(-1), a - 2, p - 1, p + 1)


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
pending = {m for _, m in registry._lazy}
assert WIRING + ":polar" not in pending and WIRING + ":complex_parts" in pending
# the rows are read compiled: no family module is imported
assert POLAR not in sys.modules and COMPLEX not in sys.modules
for h in (exp_polar, polar_lift, principal_branch):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":polar"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
