"""Refine handlers for matrix expressions.

Registered keys: ``Determinant``, ``HadamardProduct``, ``Inverse``,
``MatAdd``, ``MatMul``, ``MatrixElement``, ``Trace``, ``Transpose``.

Every predicate question goes through ``_upstream.ask``; only ``True``
answers are acted on (SymPy answers ``Q.zero(X)`` with ``False`` for any
bare ``MatrixSymbol``, so a ``False`` must never be read as information).
"Known zero" below means the argument is a ``ZeroMatrix`` or
``ask(Q.zero(A))`` is ``True``.

Conventions.  SymPy's ``Q.orthogonal`` means ``M.T*M = M*M.T = I`` and its
``ask`` derives ``Q.unitary`` from it, which is only right for real
matrices (a complex orthogonal matrix, ``M.T*M = I``, is in general not
unitary).  The unitary rules therefore refuse to fire when ``M`` is known
orthogonal but not known to have real elements: for those the orthogonal
rules (which use ``M.T``) apply instead; this is checked for every matrix
inside ``M`` too, since ``ask`` also derives ``Q.unitary(X*Y)`` and
``Q.unitary(-X)`` from ``Q.orthogonal(X)``.  Two more ``ask`` answers are
not trusted: ``Q.orthogonal``/``Q.unitary`` of an expression containing a
``MatrixSlice`` (a diagonal block of an orthogonal matrix is not
orthogonal), and ``Q.symmetric`` of a product (``ask`` calls any product
of symmetric factors symmetric); see ``_symmetric`` for what is accepted.

Rules and preconditions
=======================

Transpose
    ``A.T -> A``                         ``Q.symmetric(A)``
    ``A.T -> ZeroMatrix(cols, rows)``    ``A`` known zero
Inverse
    ``A**-1 -> A.T``                     ``Q.orthogonal(A)``
    ``A**-1 -> Adjoint(A)``              ``Q.unitary(A)`` (see conventions;
                                         never ``conjugate(A)``)
    A singular argument is left alone (no exception is raised).
Determinant
    ``det(A) -> 0``                      ``Q.singular(A)``
    ``det(A) -> 0``                      ``A`` known zero and its size a
                                         positive integer literal
    ``det(A) -> 1``                      ``Q.unit_triangular(A)``
Trace
    ``tr(A) -> 0``                       ``A`` known zero
MatAdd
    drop every term known zero; if all are, ``ZeroMatrix`` of the shape
HadamardProduct
    ``ZeroMatrix`` of the shape          some factor known zero
MatMul (scalar factors kept, matrix factors in order)
    ``ZeroMatrix(rows, cols)``           a matrix factor known zero, or a
                                         scalar factor with ``Q.zero``
    adjacent ``A.T*A`` / ``A*A.T -> I``  ``Q.orthogonal(A)``, ``A`` square
    adjacent ``A.H*A`` / ``A*A.H -> I``  ``Q.unitary(A)`` (conventions), square
    adjacent ``A*A**-1`` / ``A**-1*A -> I``  ``Q.invertible(A)``, square
    Cancellation is greedy left to right on adjacent factors only.
MatAdd, MatMul (no rule fired)
    the structural ``doit(deep=False)`` canonical form, so that terms made
    equal by refining the arguments collect (``X - X.T -> 0``)
MatrixElement ``A[i, j]``
    ``-> 0``                             ``A`` known zero
    ``-> 0``                             ``Q.diagonal(A)`` and ``i != j``
                                         provable: ``i - j`` a nonzero
                                         number, or ``Q.ne(i, j)``, or
                                         ``Q.nonzero(i - j)``; and, as
                                         negative indices wrap, both
                                         indices of one sign or
                                         ``i - j != +-n``
    ``-> A[j, i]`` canonical order       ``Q.symmetric(A)``: delegated to
                                         the vendored
                                         ``_upstream.refine_matrixelement``

Deliberately not implemented
============================

* ``det(A) -> 1`` for orthogonal ``A`` (SymPy's upstream rule): wrong, the
  determinant is +-1 (the rotation ``Matrix([[0, 1], [-1, 0]])`` has
  det 1, the reflection ``Matrix([[0, 1], [1, 0]])`` has det -1).
* ``conjugate(A)*A -> I`` / ``A**-1 -> conjugate(A)`` for unitary ``A``
  (SymPy's upstream rules): wrong, the inverse is the conjugate transpose.
* ``A[i, j] -> 0`` for diagonal ``A`` with merely distinct symbols.
* Triangular element rules (``A[i, j] -> 0`` above/below the diagonal):
  SymPy's own ``Q.upper_triangular`` docstring states the lower-triangular
  condition, so the intended meaning is ambiguous.
* ``tr``/``det`` identities that need no assumptions (not refine's job).
"""
from __future__ import annotations

from typing import Any

from sympy import S, preorder_traversal
from sympy.assumptions import Q
from sympy.core.basic import Basic
from sympy.matrices.expressions.adjoint import Adjoint
from sympy.matrices.expressions.hadamard import HadamardProduct
from sympy.matrices.expressions.inverse import Inverse
from sympy.matrices.expressions.matadd import MatAdd
from sympy.matrices.expressions.matmul import MatMul
from sympy.matrices.expressions.matexpr import MatrixElement
from sympy.matrices.expressions.matpow import MatPow
from sympy.matrices.expressions.slice import MatrixSlice
from sympy.matrices.expressions.special import Identity, ZeroMatrix
from sympy.matrices.expressions.transpose import Transpose

from ...identities.compat import upstream as _upstream
from ...identities.compat.upstream import handlers_dict


# ---------------------------------------------------------------- helpers

def _known_zero_matrix(m: Basic, assumptions: Any) -> bool:
    if isinstance(m, ZeroMatrix):
        return True
    return _upstream.ask(Q.zero(m), assumptions) is True


def _known_zero_scalar(c: Basic, assumptions: Any) -> bool:
    if c.is_zero is True:
        return True
    return _upstream.ask(Q.zero(c), assumptions) is True


def _is_square(m: Basic) -> bool:
    return m.is_square is True


def _matrix_subexprs(m: Basic) -> list[Basic]:
    return [s for s in preorder_traversal(m) if getattr(s, 'is_Matrix', False)]


def _orthogonal(m: Basic, assumptions: Any) -> bool:
    """``Q.orthogonal(m)``, refusing any ``MatrixSlice``: SymPy's ``ask``
    calls a diagonal block of an orthogonal matrix orthogonal, which is
    false (the block ``[1/2]`` of the 60 degree rotation)."""
    if m.has(MatrixSlice):
        return False
    return _upstream.ask(Q.orthogonal(m), assumptions) is True


def _unitary(m: Basic, assumptions: Any) -> bool:
    """``Q.unitary(m)``, refusing when it could come from orthogonality of
    ``m`` or of any matrix inside it (``X*Y``, ``-X``) not known to be real
    (see the module docstring), and refusing any ``MatrixSlice`` (as for
    ``_orthogonal``)."""
    if m.has(MatrixSlice):
        return False
    if _upstream.ask(Q.unitary(m), assumptions) is not True:
        return False
    for s in _matrix_subexprs(m):
        if _upstream.ask(Q.orthogonal(s), assumptions) is True and \
                _upstream.ask(Q.real_elements(s), assumptions) is not True:
            return False
    return True


def _symmetric(m: Basic, assumptions: Any) -> bool:
    """``Q.symmetric(m)``, checked against the structure of products.

    SymPy's ``ask`` calls every product of symmetric factors symmetric,
    which is false (``(X*Y).T = Y*X``).  A product is accepted only when
    ``ask`` says it is diagonal, it has one distinct matrix factor
    (``X*X``), or it is a palindrome ``A.T*M*A`` (or ``A*M*A`` with ``A``
    symmetric) with ``M`` symmetric.
    """
    if _upstream.ask(Q.symmetric(m), assumptions) is not True:
        return False
    if isinstance(m, MatMul):
        mats = [a for a in m.args if a.is_Matrix]
        if _upstream.ask(Q.diagonal(m), assumptions) is True:
            return True
        if all(f == mats[0] for f in mats):
            return _symmetric(mats[0], assumptions)
        first, last = mats[0], mats[-1]
        if _paired_base(first, last, Transpose) is not None or \
                (first == last and _symmetric(first, assumptions)):
            return len(mats) == 2 or _symmetric(MatMul(*mats[1:-1]), assumptions)
        return False
    if isinstance(m, MatAdd):
        return all(_symmetric(t, assumptions) for t in m.args)
    if isinstance(m, (Transpose, Inverse, MatPow)):
        return _symmetric(m.args[0], assumptions)
    return True


def _transpose_of(m: Basic) -> Basic:
    return m.arg if isinstance(m, Transpose) else Transpose(m)


def _adjoint_of(m: Basic) -> Basic:
    return m.arg if isinstance(m, Adjoint) else Adjoint(m)


def _inverse_of(m: Basic) -> Basic:
    return m.arg if isinstance(m, Inverse) else Inverse(m)


def _paired_base(a: Basic, b: Basic, wrap: type) -> Basic | None:
    """``M`` when ``(a, b)`` is ``(wrap(M), M)`` or ``(M, wrap(M))``."""
    if isinstance(a, wrap) and a.arg == b:
        return b
    if isinstance(b, wrap) and b.arg == a:
        return a
    return None


def _cancels(a: Basic, b: Basic, assumptions: Any) -> bool:
    """Whether the adjacent product ``a*b`` is provably the identity."""
    if not (_is_square(a) and _is_square(b) and a.shape == b.shape):
        return False
    base = _paired_base(a, b, Transpose)
    if base is not None and _orthogonal(base, assumptions):
        return True
    base = _paired_base(a, b, Adjoint)
    if base is not None and _unitary(base, assumptions):
        return True
    base = _paired_base(a, b, Inverse)
    if base is not None and _upstream.ask(Q.invertible(base), assumptions) is True:
        return True
    return False


def _canonical(expr: Basic) -> Basic | None:
    """``expr.doit(deep=False)`` when that differs, else ``None``.

    ``refine`` rebuilds a ``MatAdd``/``MatMul`` from refined arguments without
    evaluation, so e.g. ``X - X.T`` with symmetric ``X`` arrives as the
    uncollected ``-X + X``; this collects it (no assumption is used).
    """
    new = expr.doit(deep=False)
    return None if new == expr else new


def _nonzero(e: Basic, assumptions: Any) -> bool:
    if e.is_number:
        return e.is_zero is False
    return _upstream.ask(Q.nonzero(e), assumptions) is True


def _provably_distinct(i: Basic, j: Basic, n: Basic, assumptions: Any) -> bool:
    """Whether ``A[i, j]`` of an ``n x n`` matrix is off the diagonal.

    SymPy accepts negative indices ``-n <= i < 0`` and wraps them
    (``A[0, -1]`` of a 1x1 matrix is ``A[0, 0]``), so ``i != j`` is not
    enough: ``i - j`` must also differ from ``n`` and ``-n``, unless both
    indices are known nonnegative (or both negative).
    """
    d = i - j
    if d.is_number:
        if not d.is_Integer or d.is_zero:
            return False
        if n.is_Integer:
            return d % n != 0
    elif not (_upstream.ask(Q.ne(i, j), assumptions) is True
              or _nonzero(d, assumptions)):
        return False
    for q in (Q.nonnegative, Q.negative):
        if _upstream.ask(q(i), assumptions) is True and \
                _upstream.ask(q(j), assumptions) is True:
            return True
    return _nonzero(d - n, assumptions) and _nonzero(d + n, assumptions)


# ---------------------------------------------------------------- handlers

def refine_Transpose(expr: Basic, assumptions: Any) -> Basic | None:
    arg = expr.arg
    if _known_zero_matrix(arg, assumptions):
        return ZeroMatrix(arg.cols, arg.rows)
    if _symmetric(arg, assumptions):
        return arg
    return None


def refine_Inverse(expr: Basic, assumptions: Any) -> Basic | None:
    arg = expr.arg
    if not _is_square(arg):
        return None
    if _orthogonal(arg, assumptions):
        return Transpose(arg).doit(deep=False)
    if _unitary(arg, assumptions):
        return Adjoint(arg).doit(deep=False)
    return None


def refine_Determinant(expr: Basic, assumptions: Any) -> Basic | None:
    arg = expr.arg
    if _upstream.ask(Q.singular(arg), assumptions) is True:
        return S.Zero
    n = arg.rows
    if n.is_Integer and n > 0 and _known_zero_matrix(arg, assumptions):
        return S.Zero
    if _upstream.ask(Q.unit_triangular(arg), assumptions) is True:
        return S.One
    return None


def refine_Trace(expr: Basic, assumptions: Any) -> Basic | None:
    if _known_zero_matrix(expr.arg, assumptions):
        return S.Zero
    return None


def refine_MatAdd(expr: Basic, assumptions: Any) -> Basic | None:
    terms = [t for t in expr.args if not _known_zero_matrix(t, assumptions)]
    if len(terms) == len(expr.args):
        return _canonical(expr)
    if not terms:
        return ZeroMatrix(*expr.shape)
    return MatAdd(*terms).doit(deep=False)


def refine_HadamardProduct(expr: Basic, assumptions: Any) -> Basic | None:
    if any(_known_zero_matrix(f, assumptions) for f in expr.args):
        return ZeroMatrix(*expr.shape)
    return None


def refine_MatMul(expr: Basic, assumptions: Any) -> Basic | None:
    scalars = [a for a in expr.args if not a.is_Matrix]
    mats = [a for a in expr.args if a.is_Matrix]
    if any(_known_zero_scalar(c, assumptions) for c in scalars) or \
            any(_known_zero_matrix(m, assumptions) for m in mats):
        return ZeroMatrix(*expr.shape)
    out: list[Basic] = []
    changed = False
    for m in mats:
        if out and not isinstance(out[-1], Identity) and _cancels(out[-1], m, assumptions):
            prev = out.pop()
            out.append(Identity(prev.rows))
            changed = True
        else:
            out.append(m)
    if not changed:
        return _canonical(expr)
    if all(isinstance(m, Identity) for m in out):
        out = [Identity(expr.rows)]
    return MatMul(*scalars, *out).doit(deep=False)


def refine_MatrixElement(expr: Basic, assumptions: Any) -> Basic | None:
    matrix, i, j = expr.args
    if _known_zero_matrix(matrix, assumptions):
        return S.Zero
    if _upstream.ask(Q.diagonal(matrix), assumptions) is True and \
            _provably_distinct(i, j, matrix.rows, assumptions):
        return S.Zero
    if not _symmetric(matrix, assumptions):
        return None
    return _upstream.refine_matrixelement(expr, assumptions)


handlers_dict['Determinant'] = refine_Determinant
handlers_dict['HadamardProduct'] = refine_HadamardProduct
handlers_dict['Inverse'] = refine_Inverse
handlers_dict['MatAdd'] = refine_MatAdd
handlers_dict['MatMul'] = refine_MatMul
handlers_dict['MatrixElement'] = refine_MatrixElement
handlers_dict['Trace'] = refine_Trace
handlers_dict['Transpose'] = refine_Transpose
