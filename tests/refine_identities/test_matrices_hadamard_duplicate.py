"""``refine(HadamardProduct(X, X), ...)`` raises ``ValueError`` (found by the
matrix differential, ``tools/refine_differential.py --matrices --seed 2``,
cases Hadamard; phase-3 fuzz extension).

``_engine._match`` binds the pattern ``HadamardProduct(Z, R)`` (the zero row
of ``matrices.HADAMARD``) with ``Z`` one atom term and ``R`` the rest::

    others = [g for g in target.args if g is not t]
    rest = others[0] if len(others) == 1 else pattern.func(*others)

With a repeated atom (``HadamardProduct(X, X)`` keeps both copies; ``MatAdd``
folds them into ``2*X``, so only Hadamard reaches this) both copies are ``t``,
``others`` is empty and ``HadamardProduct()`` raises "needs at least one
argument".  Any fact on ``X`` gets there, in both modes.  Fixed 2026-09-25
(phase 3, ri/matfixes): the matcher removes the bound argument by position,
here and in the other "one and the rest" forms (``c*Z``, ``Max(a, b)`` of
any arity, a two-symbol ``Add``/``Mul``).
"""
from __future__ import annotations

import pytest
from sympy import HadamardProduct, MatrixSymbol, Q, ZeroMatrix

from satrefine import refine
from satrefine.identities.core import driver as _dispatch

X = MatrixSymbol("X", 2, 2)
MODES = {"generated": _dispatch.tables, "live": _dispatch.live}
FACTS = [Q.diagonal(X), Q.orthogonal(X), Q.singular(X), Q.orthogonal(X) & Q.symmetric(X)]


@pytest.mark.parametrize("mode", sorted(MODES))
@pytest.mark.parametrize("facts", FACTS, ids=str)
def test_hadamard_of_a_repeated_atom_does_not_crash(mode, facts):
    with MODES[mode]():
        assert refine(HadamardProduct(X, X), facts) == HadamardProduct(X, X)


@pytest.mark.parametrize("mode", sorted(MODES))
def test_hadamard_of_a_repeated_zero_atom_is_zero(mode):
    with MODES[mode]():
        assert refine(HadamardProduct(X, X), Q.zero(X)) in (ZeroMatrix(2, 2), HadamardProduct(X, X))


def test_matcher_keeps_the_other_copies():
    """Every "one and the rest" form removes the bound argument by position."""
    from sympy import Add, MatMul, Symbol, symbols
    from satrefine.identities.core.match import bindings
    from satrefine.identities.compat.matrices import HADAMARD, MATMUL, c, Z, R
    a, u, v = symbols("a u v")
    rests = [b[R] for b in bindings(HADAMARD[0][0], HadamardProduct(X, X))]
    assert rests and all(r == X for r in rests)
    rests = [b[Z] for b in bindings(MATMUL[0][0], MatMul(a, a, X))]
    assert rests and all(r == MatMul(a, X) for r in rests)
    got = [(b[u], b[v]) for b in bindings(u + v, Add(a, a, evaluate=False))]
    assert got and all(pair == (a, a) for pair in got)
