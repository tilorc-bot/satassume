"""Needs (branch-cut author): ``_simple.refine_re``/``refine_im`` must not fall
through to the vendored handler on a power.

The vendored ``_refine_reim`` calls ``expand(complex=True)`` and re-refines,
which recurses without bound on ``re(x**n)`` (real ``x``, integer ``n``) and
``re(x**z)``; ``handlers_v3`` avoids the vendored fallback for that reason.
The rows chain to the simple layer for exponentials, logarithms, sums and
products, so the simple layer should return ``None`` for anything else.
"""
from __future__ import annotations

import pytest
from sympy import Q, re, symbols

from satrefine import refine

x, n, z = symbols('x n z')


@pytest.mark.xfail(reason="needs: simple re/im must not recurse on powers", strict=True, raises=RecursionError)
def test_re_of_real_integer_power_terminates():
    assert refine(re(x**n), Q.real(x) & Q.integer(n)) == re(x**n)
