"""Needs (branch-cut author): ``arg(exp(w))`` in the simple layer wraps onto ``[-pi, pi)``.

SymPy's ``arg`` takes values in ``(-pi, pi]``: ``arg(exp(I*pi))`` is ``pi``.
``_simple.refine_arg`` rewrites ``arg(exp(I*t))`` to ``sawtooth(t, 2*pi)``,
which is ``-pi`` at ``t = pi``, so the rewrite is wrong at every odd
multiple of ``pi``.  The wrap should be ``principal``'s: ``t + 2*pi*floor(1/2
- t/(2*pi))``.
"""
from __future__ import annotations

import pytest
from sympy import I, N, Q, arg, exp, pi, symbols

from satrefine import refine

t = symbols('t')


@pytest.mark.xfail(reason="needs: arg(exp) wrap closed at pi", strict=True)
def test_arg_of_exp_at_pi():
    refined = refine(arg(exp(I*t)), Q.real(t))
    assert N(refined.subs(t, pi)) == N(pi)
