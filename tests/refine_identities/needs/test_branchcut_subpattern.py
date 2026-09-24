"""Needs (branch-cut author): a structural sub-pattern inside a product, with a rest.

``exp(e*log(b))`` should match ``exp(a*b*log(x))`` with ``e`` bound to the
other factors, so the exponential fold sees a logarithm inside a longer
product (the ``Pow`` fact then derives ``(x**a)**b -> x**(a*b)`` for a
positive base instead of needing a rule).  Likewise ``w*conjugate(w)``
should match inside ``2*x*y*conjugate(x)`` with the rest bound, for the
conjugate-pair rule of ``Mul``.
"""
from __future__ import annotations

import pytest
from sympy import conjugate, exp, log, symbols

from satrefine.handlers_identities._engine import bindings

x, y, a, b, e, w, r = symbols('x y a b e w r')


@pytest.mark.xfail(reason="needs: sub-pattern with a rest inside a product", strict=True)
def test_log_factor_inside_a_longer_product():
    found = list(bindings(exp(e*log(b)), exp(a*b*log(x))))
    assert any(m[b] == x and m[e] == a*b for m in found)


@pytest.mark.xfail(reason="needs: sub-pattern with a rest inside a product", strict=True)
def test_conjugate_pair_inside_a_longer_product():
    found = list(bindings(w*conjugate(w)*r, 2*x*y*conjugate(x)))
    assert any(m[w] == x and m[r] == 2*y for m in found)
