"""Upper bounds on the number of formulas the templates emit per node.

Formula construction and compilation is a large share of query time, so
every template change must stay within these budgets.  The test also
reports the actual numbers (run with ``-s`` to see them).
"""
import pytest

sympy = pytest.importorskip("sympy")

from sympy import exp
from sympy.abc import x, y

from satassume.knowledge.templates import registry

BUDGETS = [
    # 45: 38 structural rules plus the two infinite-sum rules per term, the
    # nonzero-real-plus-imaginaries rule per term and the even-sum rule;
    # 48: plus the extended-real-term rule per term (#53, W2B1);
    # 52: plus the signed-infinite-summand rule per term and sign (family B);
    # 54 after #187: the two signed infinite-sum rules per term became one
    # with finite other terms, plus the extended-real sum with an infinite
    # term and "an infinite term makes the sum no complex number".
    # 55 after #180 S7 G5: a sum of positive integers is prime or composite.
    ("x + y", x + y, 55),
    # 51 after #180 S7: nonzero reals times k imaginary only for imaginary k.
    # 59 after #180 S7 G5: two integers >= 2 (3**2 premise alternatives).
    ("x*y", x * y, 59),
    ("2*x", 2 * x, 60),
    ("x**2", x**2, 40),
    # 63 after #180 S7: an integer power of an integer to a negative integer
    # power is +-1 (odd, no prime or composite, odd base).
    # 74 after #180 S7 G5: integer >= 2 to a power >= 2 is composite (3**2
    # premise alternatives), an integer to such a power is no prime, b <= -2
    # to an even power is composite.
    ("x**y", x**y, 74),
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
