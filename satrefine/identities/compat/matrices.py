"""Matrix expressions as rule tables: ``Determinant``, ``HadamardProduct``,
``Inverse``, ``MatAdd``, ``MatMul``, ``MatrixElement``, ``Trace``,
``Transpose``.

A row is ``(lhs, rhs)``, in an ``add_rules`` block whose ``assuming`` facts are
its hypothesis and whose ``unless`` is its exception: it fires when the
hypothesis, with the facts ``ASSUMED`` about the variables of its left side, is
provable through the dispatcher's ``ask`` and the ``unless`` condition is not.  The rules are those stated in
``handlers_v3/matrices.py`` (356 lines), in **32 rows**: Transpose 5,
Inverse 4, Determinant 2, Trace 1, MatAdd 4, HadamardProduct 1, MatMul 12,
MatrixElement 3.

Pattern forms (requested in
``tests/refine_identities/needs/test_matrices_needs.py``):

* a ``MatrixSymbol`` pattern of symbolic shape binds a ``MatrixSymbol``
  (an atom) and its shape symbols bind that matrix's shape, so a right side
  can say ``ZeroMatrix(n, m)`` or ``Identity(m)``;
* in ``Z + R`` and ``HadamardProduct(Z, R)``, ``Z`` binds one term (an atom)
  and ``R`` the sum (product) of the others, whatever they are; in ``c*X``
  over a ``MatMul``, ``c`` binds one scalar factor and ``X`` the rest;
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
not unitary): the unitary rows carry ``unless Q.orthogonal(U)``, plus a row
for the real case.

Minimizations against v3: ``det -> 0`` for singular and for a known zero
matrix of positive size is one row (the size need not be a literal: a
provably positive symbolic size is enough, and exactly true); the orthogonal
``Inverse`` rows come first, so ``Inverse``'s unitary row needs no guard;
a zero factor on either side of a product is one row (``X*W`` with
``Q.zero(X) | Q.zero(W)``; merged 2026-09-24 after the row ablation in
``agent-reports/archive/data/2026-09-24-ablation-plain.md``: no battery case, test
or fuzz input moved).

Not expressible as rows:

* v3's ``_symmetric`` is recursive (palindromic products of any length,
  sums, transposes, inverses and powers of symmetric parts); rows give its
  instances: ``S*M*S``, ``N.T*M*N`` and a product of two diagonals.  A sum
  of symmetric matrices is left out: in ``Transpose(A + B)`` the split binds
  ``B`` to the rest of the sum, which may be a product ``ask`` wrongly calls
  symmetric (``X + Y*X``).
* The canonical form v3 falls back to when no rule fires
  (``MatAdd``/``MatMul`` ``doit(deep=False)``) is structural, not a rule;
  three instances are rows (``A - A -> 0``, ``A*A -> A**2`` and scalars
  to the front, ``c*X -> c*X`` rebuilt canonically), which is what refining
  ``X - X.T``, ``X.T*X`` under ``Q.symmetric(X)`` and ``X.T*2*X`` under
  ``Q.orthogonal(X)`` needs.

``A[i, j] -> A[j, i]`` for symmetric ``A`` goes to SymPy's canonical index
order (the vendored rule v3 delegates to).  The order is a property of the
form, which ``ask`` cannot decide, so the row's hypothesis carries
:class:`_SwappedOrder`, a condition that evaluates itself once the indices
are bound (phase 3, 2026-09-25; before, the row oriented by ``Q.gt(i, j)``
and left symbolic indices).
Checked (adversarial pass, 2026-09-24): 0x0, 1x1, 2x2, 3x3 and symbolic
shapes; ``det`` of a 0x0 zero matrix (refused); non-square, negated, scaled,
summed and longer-palindrome ``Transpose`` arguments (refused); ``Inverse``
of ``-X``, ``2*X``, ``X**2``, ``X.T``, ``Adjoint(X)`` and of products
under orthogonal/unitary/real facts (the orthogonal rows first, the
``unless`` guards hold); runs inside longer ``MatMul`` with scalars;
duplicate atoms in ``MatAdd``/``HadamardProduct`` (the rest keeps the
other copies: the matcher removes the bound term by position, 2026-09-25,
B11; before it dropped every copy, and ``HadamardProduct(X, X)`` crashed);
``MatrixElement`` with negative indices that wrap onto the diagonal
(``X1[0, -1]``, ``X3[0, -3]`` refused; the symmetric swap is valid under
wrapping); plus ``python -m satrefine.tools.refine_differential`` seeds 2, 3, 7.  Found
nothing wrong for matrices over C.  Outside that domain: an infinite scalar
factor (``c*w*X`` under ``Q.zero(c) & Q.infinite(w)`` gives the zero
matrix, as in v3, since ``ask`` proves ``Q.zero(c*w)``).
"""
from __future__ import annotations

from sympy import (Adjoint, Determinant, HadamardProduct, Identity, Inverse,
                   MatAdd, MatMul, MatrixSymbol, Q, S, Trace, Transpose,
                   ZeroMatrix, symbols)
from sympy import Symbol
from sympy.logic.boolalg import BooleanFunction
from sympy.matrices.expressions.matexpr import MatrixElement

from ..rules._tables import Family, Rules, add_rules

# c is a scalar, zero a zero scalar, i and j are indices; m, n, l and h are sizes.
c, zero, i, j, m, n, l, h = symbols('c zero i j m n l h')
A = MatrixSymbol('A', m, m)     # square, arbitrary
S_ = MatrixSymbol('S', m, m)    # symmetric
D = MatrixSymbol('D', m, m)     # diagonal
E = MatrixSymbol('E', m, m)     # diagonal
O = MatrixSymbol('O', m, m)     # orthogonal
U = MatrixSymbol('U', m, m)     # unitary
V = MatrixSymbol('V', m, m)     # unitary
G = MatrixSymbol('G', m, m)     # invertible
T = MatrixSymbol('T', m, m)     # unit triangular
Zs = MatrixSymbol('Zs', m, m)   # a square zero matrix
M = MatrixSymbol('M', l, l)     # symmetric
N = MatrixSymbol('N', l, m)     # for N.T*M*N
X = MatrixSymbol('X', m, n)     # general shape, arbitrary
R = MatrixSymbol('R', m, n)     # general shape, arbitrary (the rest of a sum or product)
Z = MatrixSymbol('Z', m, n)     # a zero matrix of general shape
Y = MatrixSymbol('Y', m, n)     # a zero matrix of general shape
W = MatrixSymbol('W', n, h)     # a right neighbour of X

# Assumed throughout: a row takes each fact whose variables are all in its left side.
ASSUMED = {Q.symmetric(S_), Q.symmetric(M), Q.diagonal(D), Q.diagonal(E), Q.orthogonal(O),
           Q.unitary(U), Q.unitary(V), Q.invertible(G),
           Q.unit_triangular(T), Q.zero(Zs), Q.zero(Z), Q.zero(Y),
           Q.zero(zero)}       # zero is a zero scalar

class _Index(Symbol):
    """An index variable of the symmetric-swap row: :class:`_SwappedOrder` of
    two of these stays unevaluated, so the row's hypothesis is decided only
    once the indices are bound."""


class _SwappedOrder(BooleanFunction):
    """True when ``A[i, j]`` is out of SymPy's canonical index order and
    ``A[j, i]`` is in it (SymPy's ``refine_matrixelement``: keep ``A[i, j]``
    when ``i - j`` has a minus sign to extract).  The order is a property of
    the form, not of the values, so ``ask`` cannot decide it; this evaluates
    it on construction, i.e. when the row's binding is substituted.  It asks
    for both directions, so a pair of forms both reading as unsigned (none is
    known) cannot swap back and forth."""

    @classmethod
    def eval(cls, i, j):
        if isinstance(i, _Index) or isinstance(j, _Index):
            return None
        d = i - j
        return S.true if not d.could_extract_minus_sign() and (-d).could_extract_minus_sign() else S.false


ii, jj = _Index('i'), _Index('j')

TRANSPOSE = add_rules([
    # The transpose of a zero matrix is the zero matrix of the transposed shape.
    (Transpose(Z), ZeroMatrix(n, m)),
    # S.T = S for a symmetric (e.g. diagonal) S.
    (Transpose(S_), S_),
    # Products v3 accepts as symmetric: palindromes S*M*S, N.T*M*N, and products
    # of diagonal matrices (which commute).
    (Transpose(S_*M*S_), S_*M*S_),
    (Transpose(N.T*M*N), N.T*M*N),
    (Transpose(D*E), D*E),
])

INVERSE = (
    add_rules([
        # An orthogonal matrix is inverted by its transpose (so (O.T)**-1 = O).
        (Inverse(O), O.T),
        (Inverse(O.T), O),
        # A unitary matrix is inverted by its conjugate transpose, never by its
        # conjugate.  After the orthogonal rows, so SymPy's derivation of unitary
        # from orthogonal cannot reach it for an atom.
        (Inverse(U), Adjoint(U)),
    ])
    # (U*V)**-1 = V.H*U.H, refused when either may be a complex orthogonal matrix
    # ask called unitary.
    + add_rules([
        (Inverse(U*V), Adjoint(V)*Adjoint(U)),
    ], unless=Q.orthogonal(U) | Q.orthogonal(V))
)

DETERMINANT = (
    # det A = 0 for singular A, and for a zero matrix of positive size (a 0x0
    # matrix has determinant 1).
    add_rules([
        (Determinant(A), S.Zero),
    ], assuming={Q.singular(A) | (Q.zero(A) & Q.positive(m))})
    + add_rules([
        # A unit triangular matrix has determinant 1.  (det O = 1 for orthogonal O,
        # SymPy's rule, is wrong: the determinant is +-1.)
        (Determinant(T), S.One),
    ])
)

TRACE = add_rules([
    # The trace of a zero matrix is 0.
    (Trace(Zs), S.Zero),
])

MATADD = add_rules([
    # A sum of zero matrices is the zero matrix of its shape.
    (Z + Y, ZeroMatrix(m, n)),
    # A zero term drops out of a sum.
    (Z + R, R),
    # Canonical form: X - X = 0 (refining X - X.T under Q.symmetric(X) leaves -X + X).
    (MatAdd(X, -X), ZeroMatrix(m, n)),
    # A one-term sum of a zero matrix is the zero matrix (Z + R needs a rest;
    # a one-term sum is otherwise kept, as the handlers package keeps it).
    (MatAdd(Z), ZeroMatrix(m, n)),
])

HADAMARD = add_rules([
    # An elementwise product with a zero factor is the zero matrix of its shape.
    (HadamardProduct(Z, R), ZeroMatrix(m, n)),
])

MATMUL = (
    # A product with a zero factor, scalar or matrix, is the zero matrix of its shape.
    add_rules([
        (zero*X, ZeroMatrix(m, n)),
    ])
    # either factor is zero
    + add_rules([
        (X*W, ZeroMatrix(m, h)),
    ], assuming={Q.zero(X) | Q.zero(W)})
    + add_rules([
        # Adjacent O.T*O and O*O.T cancel for orthogonal O.
        (O.T*O, Identity(m)),
        (O*O.T, Identity(m)),
    ])
    # Adjacent U.H*U and U*U.H cancel for unitary U: for real U from Q.orthogonal,
    # otherwise refused when U may be a complex orthogonal matrix ask calls unitary.
    # here U has real elements
    + add_rules([
        (Adjoint(U)*U, Identity(m)),
        (U*Adjoint(U), Identity(m)),
    ], assuming={Q.real_elements(U)})
    + add_rules([
        (Adjoint(U)*U, Identity(m)),
        (U*Adjoint(U), Identity(m)),
    ], unless=Q.orthogonal(U))
    + add_rules([
        # Adjacent G**-1*G and G*G**-1 cancel for invertible G (spelled MatMul(...):
        # the operator form cancels while the pattern is built).
        (MatMul(Inverse(G), G), Identity(m)),
        (MatMul(G, Inverse(G)), Identity(m)),
        # Canonical form: A*A = A**2, written MatMul(A, A) since A*A is built as A**2 (refining X.T*X under Q.symmetric(X) leaves X*X).
        (MatMul(A, A), A**2),
        # Canonical form: scalar factors in front and combined (MatMul(X, 2, Y) ->
        # 2*X*Y; the c*X form rebuilds its right side canonically), so a scalar
        # between factors no longer separates a cancelling pair.
        (c*X, c*X),
    ])
)

MATRIXELEMENT = (
    add_rules([
        # Every element of a zero matrix is 0.
        (MatrixElement(Z, i, j), S.Zero),
    ])
    # An off-diagonal element of a diagonal matrix is 0.  Negative indices wrap
    # (D[0, -1] of a 1x1 matrix is D[0, 0]), so i != j must hold after wrapping:
    # both indices of one sign, or i - j != +-m.
    + add_rules([
        (MatrixElement(D, i, j), S.Zero),
    ], assuming={Q.ne(i, j) | Q.nonzero(i - j),
                 (Q.nonnegative(i) & Q.nonnegative(j)) | (Q.negative(i) & Q.negative(j))
                 | (Q.nonzero(i - j - m) & Q.nonzero(i - j + m))})
    # A symmetric matrix's elements S[i, j] = S[j, i], oriented to SymPy's
    # canonical index order (a structural condition, see _SwappedOrder).
    + add_rules([
        (MatrixElement(S_, ii, jj), MatrixElement(S_, jj, ii)),
    ], assuming={_SwappedOrder(ii, jj)})
)

RULES: list[tuple] = (TRANSPOSE + INVERSE + DETERMINANT + TRACE + MATADD
                      + HADAMARD + MATMUL + MATRIXELEMENT)

SPEC = Family({'Determinant': Rules(DETERMINANT), 'HadamardProduct': Rules(HADAMARD), 'Inverse': Rules(INVERSE),
               'MatAdd': Rules(MATADD), 'MatMul': Rules(MATMUL), 'MatrixElement': Rules(MATRIXELEMENT),
               'Trace': Rules(TRACE), 'Transpose': Rules(TRANSPOSE)},
              rules=RULES, assumed=ASSUMED)
