"""Pinned repros from the P6 review (issue #97, branch issue-97/p6-template-tables).

The Pow row ``|b|<1.infinite`` (``POW_TABLE`` in ``satassume/knowledge/templates/core.py``:
``[b finite number, 0<|b|<1] negative_infinite(E) -> infinite(N)``) was
transcribed unchanged from ``_pow_rules`` at 876f37d, so the clause set is
identical on ``main``; the issue is pre-existing, not introduced by P6.
The row is right for a negative base too: the value of ``b**(-oo)`` comes
from docs/special-values.md (row P4), not from SymPy's evaluation (#247).
"""
import pytest

sympy = pytest.importorskip("sympy")
from sympy import Q, Rational, S, oo, symbols  # noqa: E402

from satassume.sympy_api import ask  # noqa: E402


def test_negative_base_below_one_to_minus_infinity_is_infinite():
    """Row ``|b|<1.infinite`` for -1 < b < 0: ``|(-1/2)**t| = 2**(-t)``
    grows without bound as ``t -> -oo`` while the argument turns, so the
    value is ``zoo`` (docs/special-values.md, row P4), which is infinite.
    SymPy at the pin gives ``(-1/2)**(-oo) == nan`` but ``(-2)**oo ==
    zoo``; its nan is not the value (#247; was a strict xfail taking it
    as the truth, #97 P6)."""
    y = symbols("y")
    assert ask(Q.infinite(Rational(-1, 2) ** y), Q.negative_infinite(y)) is True


def test_positive_base_below_one_to_minus_infinity_is_infinite():
    """The same row for 0 < b < 1, where SymPy agrees: (1/2)**(-oo) == oo."""
    y = symbols("y")
    assert S.Half ** (-oo) is S.Infinity
    assert ask(Q.infinite(S.Half ** y), Q.negative_infinite(y)) is True
