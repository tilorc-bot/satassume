"""Pinned repros from the P6 review (issue #97, branch issue-97/p6-template-tables).

The Pow row ``|b|<1.infinite`` (``POW_TABLE`` in ``satassume/knowledge/templates/core.py``:
``[b finite number, 0<|b|<1] negative_infinite(E) -> infinite(N)``) was
transcribed unchanged from ``_pow_rules`` at 876f37d, so the clause set is
identical on ``main``; the issue is pre-existing, not introduced by P6.
"""
import pytest

sympy = pytest.importorskip("sympy")
from sympy import Q, Rational, S, oo, symbols  # noqa: E402

from satassume.sympy_api import ask  # noqa: E402


@pytest.mark.xfail(strict=True, reason=(
    "Pinned repro, pre-existing on main (876f37d), not a P6 regression: row "
    "|b|<1.infinite of POW_TABLE says b**e is infinite for 0<|b|<1 and e == -oo, "
    "but SymPy at the pin gives (-1/2)**(-oo) == nan (not infinite); only 0<b<1 "
    "gives oo.  satassume answers True where a value of the node is nan.  "
    "Owner decision, issue #97 P6 review: restrict the row to positive b, or "
    "document the departure from SymPy, in a separate PR."))
def test_negative_base_below_one_to_minus_infinity_is_nan():
    y = symbols("y")
    assert Rational(-1, 2) ** (-oo) is S.NaN        # SymPy's value
    assert ask(Q.infinite(Rational(-1, 2) ** y), Q.negative_infinite(y)) is not True


def test_positive_base_below_one_to_minus_infinity_is_infinite():
    """The same row for 0 < b < 1, where SymPy agrees: (1/2)**(-oo) == oo."""
    y = symbols("y")
    assert S.Half ** (-oo) is S.Infinity
    assert ask(Q.infinite(S.Half ** y), Q.negative_infinite(y)) is True
