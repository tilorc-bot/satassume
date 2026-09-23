"""Handlers for matrix expressions: ``Determinant``, ``Inverse``,
``Transpose``, ``Trace``, ``MatAdd``, ``MatMul``, ``HadamardProduct`` and
``MatrixElement``.

These are deliberately conservative.  Matrix predicates are answered by
SymPy's ``ask`` only (the satassume engine returns ``None`` for them), and
``Q.orthogonal(X)`` implies ``Q.unitary(X)`` in SymPy's fact system.

``Determinant`` rules:

T1  ``-> 0`` for a singular matrix.
T2  ``-> 1`` for a unit-triangular matrix (all diagonal entries are 1).
T3  ``Determinant(Inverse(X)) -> 1/Determinant(X)`` for invertible ``X``.
    An orthogonal determinant is ``+1`` or ``-1`` and a unitary one lies on
    the unit circle, so neither is simplified (only ``Abs`` of it, and even
    powers of an orthogonal one, are; see the ``Abs`` and ``Pow`` handlers).

``Inverse`` rules:

N1  ``Inverse(X) -> Transpose(X)`` for orthogonal ``X``.
N2  ``Inverse(X) -> Adjoint(X)`` (conjugate transpose) for unitary ``X``.

``Transpose`` rules:

R1  ``Transpose(X) -> X`` for symmetric ``X`` (diagonal implies symmetric).

``Trace`` rules:

C1  ``Trace(X) -> 0`` for a zero matrix.
C2  ``Trace(X) -> X.rows`` for a unit-triangular ``X``.

``MatAdd`` rules:

A1  Provably zero terms are dropped (``ZeroMatrix`` if all are).

``MatMul`` rules:

M1  ``-> ZeroMatrix`` when a factor is a zero matrix.
M2  Adjacent ``X*X.T`` or ``X.T*X`` ``-> Identity`` for orthogonal ``X``;
    adjacent ``X*Adjoint(X)`` or ``Adjoint(X)*X`` ``-> Identity`` for
    unitary ``X`` (the conjugate *transpose*, not the plain conjugate);
    adjacent ``X*Inverse(X)`` or ``Inverse(X)*X`` ``-> Identity`` for
    invertible ``X``.

``HadamardProduct`` rules:

H1  ``-> ZeroMatrix`` when a factor is a zero matrix.

``MatrixElement`` rules (``X[i, j]``):

E1  ``-> 0`` for a zero matrix.
E2  ``-> 0`` for a diagonal matrix when ``i - j`` is provably nonzero.
E3  ``-> 0`` for an upper (lower) triangular matrix when ``i - j`` is
    positive (negative).
E4  ``-> 1`` for a unit-triangular matrix when ``i - j`` is zero.
E5  ``-> X[j, i]`` for a symmetric matrix, in the canonical index order
    chosen by ``could_extract_minus_sign`` (the vendored SymPy rule).
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Basic, S
from sympy.matrices.expressions.adjoint import Adjoint
from sympy.matrices.expressions.determinant import Determinant
from sympy.matrices.expressions.inverse import Inverse
from sympy.matrices.expressions.matadd import MatAdd
from sympy.matrices.expressions.matmul import MatMul
from sympy.matrices.expressions.special import Identity, ZeroMatrix
from sympy.matrices.expressions.transpose import Transpose

from .. import _upstream
from .._upstream import handlers_dict
from ._common import Assumptions, holds, is_nonzero


def _is_zero_matrix(matrix: Basic, assumptions: Assumptions) -> bool:
    return holds(Q.zero(matrix), assumptions)


def refine_Determinant(expr: Basic, assumptions: Assumptions) -> Basic | None:
    X = expr.arg
    if holds(Q.singular(X), assumptions):                               # T1
        return S.Zero
    if holds(Q.unit_triangular(X), assumptions):                        # T2
        return S.One
    if isinstance(X, Inverse) and holds(Q.invertible(X.arg), assumptions):  # T3
        return 1 / Determinant(X.arg)
    return None


def refine_Inverse(expr: Basic, assumptions: Assumptions) -> Basic | None:
    X = expr.arg
    if holds(Q.orthogonal(X), assumptions):                             # N1
        return Transpose(X)
    if holds(Q.unitary(X), assumptions):                                # N2
        return Adjoint(X)
    return None


def refine_Transpose(expr: Basic, assumptions: Assumptions) -> Basic | None:
    if holds(Q.symmetric(expr.arg), assumptions):                       # R1
        return expr.arg
    return None


def refine_Trace(expr: Basic, assumptions: Assumptions) -> Basic | None:
    X = expr.arg
    if _is_zero_matrix(X, assumptions):                                 # C1
        return S.Zero
    if holds(Q.unit_triangular(X), assumptions):                        # C2
        return X.rows
    return None


def refine_MatAdd(expr: Basic, assumptions: Assumptions) -> Basic | None:
    kept = [term for term in expr.args if not _is_zero_matrix(term, assumptions)]  # A1
    if len(kept) == len(expr.args):
        return None
    if not kept:
        return ZeroMatrix(*expr.shape)
    return kept[0] if len(kept) == 1 else MatAdd(*kept)


def _cancels(left: Basic, right: Basic, assumptions: Assumptions) -> bool:
    """``left*right == Identity`` by rule M2."""
    for X, partner in ((left, right), (right, left)):
        if partner == Transpose(X) and holds(Q.orthogonal(X), assumptions):
            return True
        if partner == Adjoint(X) and holds(Q.unitary(X), assumptions):
            return True
        if partner == Inverse(X) and holds(Q.invertible(X), assumptions):
            return True
    return False


def refine_MatMul(expr: Basic, assumptions: Assumptions) -> Basic | None:
    scalars = [factor for factor in expr.args if not factor.is_Matrix]
    matrices = [factor for factor in expr.args if factor.is_Matrix]
    if any(_is_zero_matrix(factor, assumptions) for factor in matrices):  # M1
        return ZeroMatrix(*expr.shape)
    result: list[Basic] = []
    changed = False
    for factor in matrices:                                             # M2
        if result and _cancels(result[-1], factor, assumptions):
            result[-1] = Identity(result[-1].rows)
            changed = True
        else:
            result.append(factor)
    if not changed:
        return None
    if len(result) > 1:
        result = [factor for factor in result if not isinstance(factor, Identity)] or result[:1]
    if not scalars and len(result) == 1:
        return result[0]
    return MatMul(*scalars, *result)


def refine_HadamardProduct(expr: Basic, assumptions: Assumptions) -> Basic | None:
    if any(_is_zero_matrix(factor, assumptions) for factor in expr.args):  # H1
        return ZeroMatrix(*expr.shape)
    return None


def refine_MatrixElement(expr: Basic, assumptions: Assumptions) -> Basic | None:
    X, i, j = expr.args
    difference = i - j
    if _is_zero_matrix(X, assumptions):                                 # E1
        return S.Zero
    if holds(Q.diagonal(X), assumptions) and is_nonzero(difference, assumptions):  # E2
        return S.Zero
    if holds(Q.upper_triangular(X), assumptions) and holds(Q.positive(difference), assumptions):  # E3
        return S.Zero
    if holds(Q.lower_triangular(X), assumptions) and holds(Q.negative(difference), assumptions):
        return S.Zero
    if holds(Q.unit_triangular(X), assumptions) and holds(Q.zero(difference), assumptions):  # E4
        return S.One
    return _upstream.refine_matrixelement(expr, assumptions)            # E5


handlers_dict['Determinant'] = refine_Determinant
handlers_dict['Inverse'] = refine_Inverse
handlers_dict['Transpose'] = refine_Transpose
handlers_dict['Trace'] = refine_Trace
handlers_dict['MatAdd'] = refine_MatAdd
handlers_dict['MatMul'] = refine_MatMul
handlers_dict['HadamardProduct'] = refine_HadamardProduct
handlers_dict['MatrixElement'] = refine_MatrixElement
