"""Fixed in phase 3 (ri/fixes), split from ``needs/test_default_pow_of_pow.py``:
``sqrt(1/x) -> 1/sqrt(x)`` for positive ``x`` (SymPy's ``test_pow1``), by the rule
``(b**a)**e -> b**(a*e)`` for ``b > 0`` and real ``a`` (``a*log(b)`` is real).
"""
from __future__ import annotations

from sympy import Q, sqrt
from sympy.abc import x

from satrefine import refine


def test_sqrt_of_reciprocal_of_positive():
    assert refine(sqrt(1/x), Q.positive(x)) == 1/sqrt(x)
