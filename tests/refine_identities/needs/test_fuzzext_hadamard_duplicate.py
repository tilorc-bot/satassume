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
argument".  Any fact on ``X`` gets there, in both modes.  Removing only the
matched copy (by position, not identity) would fix it; the zero row stays
sound either way.
"""
from __future__ import annotations

import pytest
from sympy import HadamardProduct, MatrixSymbol, Q, ZeroMatrix

from satrefine import refine
from satrefine.handlers_identities import _dispatch

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
