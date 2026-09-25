"""``tools/refine_fuzz.py``'s matrix mode: the samplers satisfy the predicates
they are drawn for, the checker finds a wrong rewrite, and a rewrite with no
checkable point is counted as unchecked, not as passed.
"""
from __future__ import annotations

import importlib
import random
import sys
from pathlib import Path

import pytest
from sympy import (Determinant, I, Identity, ImmutableMatrix, MatrixSymbol, Q, Rational, S, Symbol, ZeroMatrix,
                   symbols)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
_argv, sys.argv = sys.argv, sys.argv[:1]
fz = importlib.import_module("refine_fuzz")
sys.argv = _argv

X = MatrixSymbol('X', 2, 2)
n = fz.SIZE_SYMS[0]


@pytest.mark.parametrize("combo", fz.MCOMBOS)
@pytest.mark.parametrize("k", [1, 2, 3])
def test_square_samples_satisfy_their_predicates(combo, k):
    rng = random.Random(f"{combo}-{k}")
    for _ in range(3):
        M = fz.mdraw(combo, (k, k), rng)
        assert M is not None, (combo, k)
        assert all(fz.MPREDS[p][1](M) for p in combo)


def test_predicate_definitions_tell_complex_orthogonal_from_unitary():
    orth, unit = fz.MPREDS["orthogonal"][1], fz.MPREDS["unitary"][1]
    for M in fz.CORTH2:
        assert orth(M) and not unit(M)
    for M in fz.UNIT2:
        assert unit(M) and not orth(M)
    for M in fz.ORTH2:
        assert orth(M) and unit(M)


def test_zero_by_zero_determinant_is_one():
    pt = {n: S.Zero}
    assert fz.mat_value(Determinant(ZeroMatrix(n, n)), pt) == 1
    assert fz.mat_value(Determinant(Identity(n)), pt) == 1


def test_a_wrong_rewrite_is_found():
    # det X = 1 for orthogonal X is SymPy's wrong rule: the reflections have -1
    rng = random.Random(0)
    pts = fz.mat_points({X: ("orthogonal", "real_elements")}, None, rng, count=20)
    n_ok, ce = fz.mat_compare(Determinant(X), S.One, pts)
    assert ce is not None


def test_a_right_rewrite_passes_and_counts_points():
    rng = random.Random(1)
    pts = fz.mat_points({X: ("orthogonal",)}, None, rng)
    n_ok, ce = fz.mat_compare(X.T*X, Identity(2), pts)
    assert ce is None and n_ok == len(pts) > 0


def test_undefined_input_is_skipped_not_checked():
    rng = random.Random(2)
    pts = fz.mat_points({X: ("singular",)}, None, rng)
    n_ok, ce = fz.mat_compare(X.I + X, X + X.I, pts)
    assert ce is None and n_ok == 0          # unchecked: the caller counts it


def test_scalar_and_index_points_respect_their_predicates():
    c, i, j = symbols('c i j')
    combos = {X: ("diagonal",), fz._mc: ("imaginary",), fz._mi: ("negative", "integer"), fz._mj: ("integer",)}
    rel = Q.gt(fz._mi, fz._mj)
    for p in fz.mat_points(combos, rel, random.Random(3)):
        assert p[fz._mi] < 0 and p[fz._mi] > p[fz._mj] >= -2
        assert fz.c_imag(p[fz._mc])


def test_generation_is_deterministic_and_separate_from_the_scalar_stream():
    assert fz.mat_generate(4, 17) == fz.mat_generate(4, 17)
    head, e, a, combos, rel = next(g for g in (fz.mat_generate(4, c) for c in range(50)) if g)
    assert any(isinstance(s, MatrixSymbol) for s in combos)


def test_values_come_from_explicit_matrices_not_symbolic_rules():
    # SymPy turns 0*X*Y into ZeroMatrix(0, 0) and calls its determinant 0; an
    # explicit 0x0 matrix has determinant 1 (the checker once flagged the right
    # rewrite det(0*X*Y) -> det(ZeroMatrix(n, n)) as unsound at n = 0)
    X0, Y0 = MatrixSymbol('X', n, n), MatrixSymbol('Y', n, n)
    pt = {n: S.Zero, fz._mc: S.Zero, X0: ImmutableMatrix.zeros(0, 0), Y0: ImmutableMatrix.zeros(0, 0)}
    assert fz.mat_value(Determinant(fz._mc*X0*Y0), pt) == 1
    assert fz.mat_value(Determinant(ZeroMatrix(n, n)), pt) == 1


def test_row_coverage_names_the_firing_row():
    cov = fz.MatrixRowCoverage()
    with cov:
        from satrefine import refine
        refine(X.T*X, Q.orthogonal(X))
    assert any("Q.orthogonal(A)" in str(row) and n_ == 1 for row, n_ in cov.counts.items())
