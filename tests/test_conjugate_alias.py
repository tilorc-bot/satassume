"""``conjugate(a)`` shares the variable block of ``a`` (``compile.alias_of``).

Every basis predicate is invariant under conjugation, so the node has no
block, rule block or template clauses of its own; the transfer theory gets
a mirror block for it when it is a term of a relation (``VarTable.mirror``).
The expected answers are those of the per-node encoding it replaces.
"""
import pytest
from sympy import Q, conjugate, exp, symbols, I

from satassume.compile import VarTable, alias_of
from satassume.sympy_api import ask
from satassume.templates.registry import registry

x, y = symbols("x y")
c, d = conjugate(x), conjugate(y)


def test_alias_and_no_template_rules():
    assert alias_of(c) is x and alias_of(x) is x
    t = VarTable()
    assert t.node_base(c) == t.node_base(x)
    assert t.new_nodes == [x]
    compiled, formulas = registry.clauses_for(c)
    assert not formulas
    # at most the rule every function has (numbers in, number out)
    assert sum(len(comp.pattern.rules) for comp in compiled) <= 1


CASES = [
    (Q.positive(c), Q.positive(x), True),
    (Q.positive(x), Q.positive(c), True),
    (Q.imaginary(c), Q.imaginary(x), True),
    (Q.real(c), Q.imaginary(x), False),
    (Q.positive(c + y), Q.positive(x) & Q.positive(y), True),
    (Q.integer(c * d), Q.integer(x) & Q.integer(y), True),
    (Q.nonzero(c), Q.nonzero(x), True),
    (Q.even(c), Q.odd(x), False),
    (Q.positive(exp(c)), Q.real(x), True),
    # relations: c is a term of its own for EUF / transfer
    (Q.positive(c), Q.eq(c, 2), True),
    (Q.positive(x), Q.eq(c, 2), True),
    (Q.positive(c + 1), Q.eq(c, 2), True),
    (Q.real(c), Q.eq(c, y) & Q.positive(y), True),
    (Q.positive(x * c), Q.eq(c, 2), True),
    (Q.real(c - d), Q.eq(x, y) & Q.real(y), True),
    (Q.zero(c - d), Q.eq(x, y), None),
    (Q.positive(d), Q.eq(x, y) & Q.positive(c), True),
]


@pytest.mark.parametrize("prop, assumptions, expected", CASES)
def test_answers(prop, assumptions, expected):
    assert ask(prop, assumptions) is expected
