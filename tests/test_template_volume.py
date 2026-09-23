"""Upper bounds on the number of formulas the templates emit per node.

Formula construction and compilation is a large share of query time, so
every template change must stay within these budgets.  The test also
reports the actual numbers (run with ``-s`` to see them).
"""
import pytest

sympy = pytest.importorskip("sympy")

from sympy import exp
from sympy.abc import x, y

from satassume.templates import registry

BUDGETS = [
    # 45: 38 structural rules plus the two infinite-sum rules per term, the
    # nonzero-real-plus-imaginaries rule per term and the even-sum rule.
    ("x + y", x + y, 46),
    ("x*y", x * y, 50),
    ("2*x", 2 * x, 60),
    ("x**2", x**2, 40),
    ("x**y", x**y, 60),
    ("exp(x)", exp(x), 15),
]


@pytest.mark.parametrize("name,expr,budget", BUDGETS, ids=[b[0] for b in BUDGETS])
def test_formula_volume(name, expr, budget):
    n = len(registry.facts_for(expr))
    print(f"{name}: {n} formulas (budget {budget})")
    assert n <= budget, f"{name} emits {n} formulas, budget is {budget}"


def test_report_counts(capsys):
    counts = {name: len(registry.facts_for(expr)) for name, expr, _ in BUDGETS}
    print("template formula counts:", counts)
    assert all(v > 0 for v in counts.values())
