"""Matrix expressions as rule tables: ``Determinant``, ``HadamardProduct``,
``Inverse``, ``MatAdd``, ``MatMul``, ``MatrixElement``, ``Trace``,
``Transpose``.

A row is ``(lhs, rhs, hypothesis)`` or ``(lhs, rhs, hypothesis, unless)``:
it fires when the hypothesis is provable through ``_upstream.ask`` and the
``unless`` condition is not.  The rules are those stated in
``handlers_v3/matrices.py`` (356 lines), in **30 rows**: Transpose 5,
Inverse 4, Determinant 2, Trace 1, MatAdd 3, HadamardProduct 1, MatMul 11,
MatrixElement 3.

Pattern forms (requested in
``tests/refine_identities/needs/test_matrices_needs.py``):

* a ``MatrixSymbol`` pattern of symbolic shape binds a ``MatrixSymbol``
  (an atom) and its shape symbols bind that matrix's shape, so a right side
  can say ``ZeroMatrix(q, m)`` or ``Identity(m)``;
* in ``Z + R`` and ``HadamardProduct(Z, R)``, ``Z`` binds one term (an atom)
  and ``R`` the sum (product) of the others, whatever they are; in ``c*Z``
  over a ``MatMul``, ``c`` binds one scalar factor and ``Z`` the rest;
* a ``MatMul`` pattern of matrix factors matches a run of adjacent factors;
  the right side replaces the run, scalars and the other factors are kept in
  order and the product is put in canonical form (``doit(deep=False)``);
* the ``unless`` element (see below); literal ``0``/``1`` bindings
  (``X[0, 1]``).

Atoms, not arbitrary matrix expressions, are what makes the rows sound:
SymPy's ``ask`` calls every product of symmetric matrices symmetric, a
diagonal block (``MatrixSlice``) of an orthogonal matrix orthogonal, and
``-X`` or ``X*Y`` unitary for a (complex) orthogonal ``X``.  v3 defends
against each by walking the expression; a row whose variable binds only
atoms never sees those expressions, and the products v3 does accept get
rows of their own.  The one ``ask`` answer wrong for atoms too is
``Q.unitary(X)`` from ``Q.orthogonal(X)`` (a complex orthogonal matrix is
not unitary): the unitary rows carry ``unless Q.orthogonal(A)``, plus a row
for the real case.

Minimizations against v3: ``det -> 0`` for singular and for a known zero
matrix of positive size is one row (the size need not be a literal: a
provably positive symbolic size is enough, and exactly true); the orthogonal
``Inverse`` rows come first, so ``Inverse``'s unitary row needs no guard;
a zero factor on either side of a product is one row (``Z*W`` with
``Q.zero(Z) | Q.zero(W)``; merged 2026-09-24 after the row ablation in
``agent-reports/archive/data/2026-09-24-ablation-plain.md``: no battery case, test
or fuzz input moved).

Not expressible as rows:

* v3's ``_symmetric`` is recursive (palindromic products of any length,
  sums, transposes, inverses and powers of symmetric parts); rows give its
  instances: ``A*M*A``, ``A.T*M*A`` and a product of two diagonals.  A sum
  of symmetric matrices is left out: in ``Transpose(A + B)`` the split binds
  ``B`` to the rest of the sum, which may be a product ``ask`` wrongly calls
  symmetric (``X + Y*X``).
* The canonical form v3 falls back to when no rule fires
  (``MatAdd``/``MatMul`` ``doit(deep=False)``) is structural, not a rule;
  two instances are rows (``A - A -> 0`` and ``A*A -> A**2``), which is what
  refining ``X - X.T`` and ``X.T*X`` under ``Q.symmetric(X)`` needs.
* ``A[i, j] -> A[j, i]`` for symmetric ``A`` in a canonical index order
  (the vendored rule v3 delegates to): the order is a property of the
  printed form, not a hypothesis; the row orients by ``Q.gt(i, j)``, which
  decides numeric indices and leaves symbolic ones.
Checked (adversarial pass, 2026-09-24): 0x0, 1x1, 2x2, 3x3 and symbolic
shapes; ``det`` of a 0x0 zero matrix (refused); non-square, negated, scaled,
summed and longer-palindrome ``Transpose`` arguments (refused); ``Inverse``
of ``-X``, ``2*X``, ``X**2``, ``X.T``, ``Adjoint(X)`` and of products
under orthogonal/unitary/real facts (the orthogonal rows first, the
``unless`` guards hold); runs inside longer ``MatMul`` with scalars;
duplicate atoms in ``MatAdd``/``HadamardProduct`` (the rest drops every
copy of the atom, harmless for the zero rows: the copies are zero too);
``MatrixElement`` with negative indices that wrap onto the diagonal
(``X1[0, -1]``, ``X3[0, -3]`` refused; the symmetric swap is valid under
wrapping); plus ``tools/refine_differential.py`` seeds 2, 3, 7.  Found
nothing wrong for matrices over C.  Outside that domain: an infinite scalar
factor (``c*w*X`` under ``Q.zero(c) & Q.infinite(w)`` gives the zero
matrix, as in v3, since ``ask`` proves ``Q.zero(c*w)``).
"""
from __future__ import annotations

from sympy import (Adjoint, Determinant, HadamardProduct, Identity, Inverse,
                   MatAdd, MatMul, MatrixSymbol, Q, S, Trace, Transpose,
                   ZeroMatrix, symbols)
from sympy.matrices.expressions.matexpr import MatrixElement

from .._upstream import handlers_dict
from ._specialize import compile_table

c, i, j, m, p, q, s = symbols('c i j m p q s')
A = MatrixSymbol('A', m, m)     # square
B = MatrixSymbol('B', m, m)
M = MatrixSymbol('M', p, p)
N = MatrixSymbol('N', p, m)     # for N.T*M*N
Z = MatrixSymbol('Z', m, q)     # general shape
R = MatrixSymbol('R', m, q)
W = MatrixSymbol('W', q, s)     # a right neighbour of Z

TRANSPOSE = [
    # The transpose of a zero matrix is the zero matrix of the transposed shape.
    (Transpose(Z), ZeroMatrix(q, m), Q.zero(Z)),
    # A.T = A for a symmetric (e.g. diagonal) A.
    (Transpose(A), A, Q.symmetric(A)),
    # Products v3 accepts as symmetric: palindromes A*M*A, N.T*M*N with M
    # symmetric, and products of diagonal matrices (which commute).
    (Transpose(A*M*A), A*M*A, Q.symmetric(A) & Q.symmetric(M)),
    (Transpose(N.T*M*N), N.T*M*N, Q.symmetric(M)),
    (Transpose(A*B), A*B, Q.diagonal(A) & Q.diagonal(B)),
]

INVERSE = [
    # An orthogonal matrix is inverted by its transpose (so (A.T)**-1 = A).
    (Inverse(A), A.T, Q.orthogonal(A)),
    (Inverse(A.T), A, Q.orthogonal(A)),
    # A unitary matrix is inverted by its conjugate transpose, never by its
    # conjugate.  After the orthogonal rows, so SymPy's derivation of unitary
    # from orthogonal cannot reach it for an atom.
    (Inverse(A), Adjoint(A), Q.unitary(A)),
    # (A*B)**-1 = B.H*A.H for unitary A, B, refused when either may be a complex
    # orthogonal matrix ask called unitary.
    (Inverse(A*B), Adjoint(B)*Adjoint(A), Q.unitary(A) & Q.unitary(B),
     Q.orthogonal(A) | Q.orthogonal(B)),
]

DETERMINANT = [
    # det A = 0 for singular A, and for a zero matrix of positive size (a 0x0
    # matrix has determinant 1).
    (Determinant(A), S.Zero, Q.singular(A) | (Q.zero(A) & Q.positive(m))),
    # A unit triangular matrix has determinant 1.  (det A = 1 for orthogonal A,
    # SymPy's rule, is wrong: the determinant is +-1.)
    (Determinant(A), S.One, Q.unit_triangular(A)),
]

TRACE = [
    # The trace of a zero matrix is 0.
    (Trace(A), S.Zero, Q.zero(A)),
]

MATADD = [
    # A sum of zero matrices is the zero matrix of its shape.
    (Z + R, ZeroMatrix(m, q), Q.zero(Z) & Q.zero(R)),
    # A zero term drops out of a sum.
    (Z + R, R, Q.zero(Z)),
    # Canonical form: A - A = 0 (refining X - X.T under Q.symmetric(X) leaves -X + X).
    (MatAdd(Z, -Z), ZeroMatrix(m, q), S.true),
    # Canonical form: a one-term sum is its term (the zero case first, since
    # nothing refines a zero matrix symbol on its own).
    (MatAdd(Z), ZeroMatrix(m, q), Q.zero(Z)),
    (MatAdd(Z), Z, S.true),
]

HADAMARD = [
    # An elementwise product with a zero factor is the zero matrix of its shape.
    (HadamardProduct(Z, R), ZeroMatrix(m, q), Q.zero(Z)),
]

MATMUL = [
    # A product with a zero factor, scalar or matrix, is the zero matrix of its shape.
    (c*Z, ZeroMatrix(m, q), Q.zero(c)),
    (Z*W, ZeroMatrix(m, s), Q.zero(Z) | Q.zero(W)),
    # Adjacent A.T*A and A*A.T cancel for orthogonal A.
    (A.T*A, Identity(m), Q.orthogonal(A)),
    (A*A.T, Identity(m), Q.orthogonal(A)),
    # Adjacent A.H*A and A*A.H cancel for unitary A: for real A from Q.orthogonal,
    # otherwise refused when A may be a complex orthogonal matrix ask calls unitary.
    (Adjoint(A)*A, Identity(m), Q.unitary(A) & Q.real_elements(A)),
    (A*Adjoint(A), Identity(m), Q.unitary(A) & Q.real_elements(A)),
    (Adjoint(A)*A, Identity(m), Q.unitary(A), Q.orthogonal(A)),
    (A*Adjoint(A), Identity(m), Q.unitary(A), Q.orthogonal(A)),
    # Adjacent A**-1*A and A*A**-1 cancel for invertible A (spelled MatMul(...):
    # the operator form cancels while the pattern is built).
    (MatMul(Inverse(A), A), Identity(m), Q.invertible(A)),
    (MatMul(A, Inverse(A)), Identity(m), Q.invertible(A)),
    # Canonical form: A*A = A**2, written MatMul(A, A) since A*A is built as A**2 (refining X.T*X under Q.symmetric(X) leaves X*X).
    (MatMul(A, A), A**2, S.true),
]

MATRIXELEMENT = [
    # Every element of a zero matrix is 0.
    (MatrixElement(Z, i, j), S.Zero, Q.zero(Z)),
    # An off-diagonal element of a diagonal matrix is 0.  Negative indices wrap
    # (A[0, -1] of a 1x1 matrix is A[0, 0]), so i != j must hold after wrapping:
    # both indices of one sign, or i - j != +-m.
    (MatrixElement(A, i, j), S.Zero,
     Q.diagonal(A) & (Q.ne(i, j) | Q.nonzero(i - j))
     & ((Q.nonnegative(i) & Q.nonnegative(j)) | (Q.negative(i) & Q.negative(j))
        | (Q.nonzero(i - j - m) & Q.nonzero(i - j + m)))),
    # A symmetric matrix's elements A[i, j] = A[j, i], oriented to the smaller
    # first index where the order is provable.
    (MatrixElement(A, i, j), MatrixElement(A, j, i), Q.symmetric(A) & Q.gt(i, j)),
]

RULES: list[tuple] = (TRANSPOSE + INVERSE + DETERMINANT + TRACE + MATADD
                      + HADAMARD + MATMUL + MATRIXELEMENT)

handlers_dict['Determinant'] = compile_table(DETERMINANT)
handlers_dict['HadamardProduct'] = compile_table(HADAMARD)
handlers_dict['Inverse'] = compile_table(INVERSE)
handlers_dict['MatAdd'] = compile_table(MATADD)
handlers_dict['MatMul'] = compile_table(MATMUL)
handlers_dict['MatrixElement'] = compile_table(MATRIXELEMENT)
handlers_dict['Trace'] = compile_table(TRACE)
handlers_dict['Transpose'] = compile_table(TRANSPOSE)
