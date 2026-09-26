"""The matcher's "one and the rest" forms remove the bound argument by
position (phase 3, ri/matfixes).

``HadamardProduct(X, X)`` keeps both copies (``MatAdd`` folds them into
``2*X``).  Binding ``Z`` in ``HadamardProduct(Z, R)`` used to drop every
argument equal to the bound one, so the rest was empty and
``HadamardProduct()`` raised.  The ``refine`` cases are the rows
``matfixes: Hadamard of a repeated atom`` of ``regressions.py``.
"""
from __future__ import annotations

from sympy import Add, HadamardProduct, MatMul, MatrixSymbol, symbols

from satrefine.identities.compat.matrices import HADAMARD, MATMUL, R, Z
from satrefine.identities.core.match import bindings

X = MatrixSymbol("X", 2, 2)


def test_matcher_keeps_the_other_copies():
    a, u, v = symbols("a u v")
    rests = [b[R] for b in bindings(HADAMARD[0][0], HadamardProduct(X, X))]
    assert rests and all(r == X for r in rests)
    rests = [b[Z] for b in bindings(MATMUL[0][0], MatMul(a, a, X))]
    assert rests and all(r == MatMul(a, X) for r in rests)
    got = [(b[u], b[v]) for b in bindings(u + v, Add(a, a, evaluate=False))]
    assert got and all(pair == (a, a) for pair in got)
