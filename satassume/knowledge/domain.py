"""The domain of the rule base and the templates: commutative scalar terms.

The rule base and the templates assume that every term they reason about
stands for a number (``commutative`` is true by definition,
``rules.DEFINITIONS``).  SymPy terms outside that domain are those with a
non-commutative subterm (``Symbol('A', commutative=False)``,
``Function('g', commutative=False)``, quantum operators, and compound
terms over them such as ``re(A)``, which claim to be commutative): such a
term may stand for a matrix.  :func:`_noncommutative` decides it without
evaluating any SymPy assumption; ``sympy_api`` keeps such terms out of
scope and the engine answers None about them.

This module imports SymPy, so the engine imports it lazily.
"""
from __future__ import annotations

from collections import Counter

from sympy.core.basic import Basic as _Basic
from sympy.core.containers import Tuple as _Tuple
from sympy.core.expr import Expr as _Expr

from ..state.memos import PROCESS as _PROCESS


#: memo of :func:`_noncommutative` (a function of the expression only:
#: SymPy equality distinguishes ``Symbol('A')`` from the non-commutative
#: ``A`` and ``Function('g')`` from ``Function('g', commutative=False)``)
NONCOMM_SIZE = 4096
_NONCOMM = _PROCESS.table(f"{__name__}._NONCOMM", "pure", NONCOMM_SIZE)


def _fixed_noncommutative(t) -> bool:
    """Whether ``t`` is non-commutative by construction, read without
    evaluating any assumption (``t.is_commutative`` would compute and cache
    ``commutative`` in SymPy's ``_assumptions`` of compound expressions,
    and the engine must never write SymPy's assumption caches).  Symbols
    (``Dummy``, ``Wild``) carry their given assumptions in ``_assumptions0``;
    undefined functions (``Function('g', commutative=False)``) and atom
    types such as quantum operators fix ``is_commutative`` as a class
    attribute; anything else is decided by its arguments."""
    from sympy.core.symbol import Symbol
    if isinstance(t, Symbol):
        # sympy-boundary: the declared commutative flag only
        return dict(getattr(t, "_assumptions0", ())).get("commutative") is False
    for k in type(t).__mro__:
        v = k.__dict__.get("is_commutative", None)
        if v is not None:
            return v is False
    return False


def _is_matrix(t) -> bool:
    return bool(getattr(t, "is_Matrix", False) or getattr(t, "is_MatrixExpr", False))


def _holds_matrix(a) -> bool:
    """``a`` is a matrix, or a ``Tuple`` holding one (the ``ExprCondPair``
    of ``Piecewise((M, c), ...)``, the point of ``Subs(f(x), x, M)``, the
    variables of a derivative by ``M``)."""
    if _is_matrix(a):
        return True
    return isinstance(a, _Tuple) and any(_holds_matrix(b) for b in a.args)


_MATRIX_TO_SCALAR: tuple = ()


def _matrix_to_scalar() -> tuple:
    """The classes whose value is a number although an argument is a matrix
    (``Trace(M)``, ``Determinant(M)``, ``Permanent(M)``, ``M[0, 0]``)."""
    global _MATRIX_TO_SCALAR
    if not _MATRIX_TO_SCALAR:
        from sympy.matrices.expressions.determinant import Determinant, Permanent
        from sympy.matrices.expressions.matexpr import MatrixElement
        from sympy.matrices.expressions.trace import Trace
        from sympy.tensor.array.expressions.array_expressions import ArrayElement
        _MATRIX_TO_SCALAR = (Trace, Determinant, Permanent, MatrixElement, ArrayElement)
    return _MATRIX_TO_SCALAR


def _noncommutative(e) -> bool:
    """Whether ``e`` may stand for something other than a number: ``e`` is
    a matrix, or has a non-commutative subterm (fixed non-commutative by
    construction anywhere, see :func:`_fixed_noncommutative`, ``e`` itself
    included, entries of explicit matrices included), or an expression
    holding a matrix argument (:func:`_holds_matrix`) other than a
    scalar-valued matrix function (:func:`_matrix_to_scalar`): ``exp(M)``,
    ``sin(M)``, ``f(M)`` and ``Piecewise((M, c), (N, True))`` claim to be
    scalars but stand for matrices.  The whole expression is not
    enough (``re(A)`` claims to be commutative), so this walks the tree;
    memoized, since it runs for every applied vocabulary predicate."""
    r = _NONCOMM.get(e)
    if r is not None:
        return r
    r = _is_matrix(e)
    stack = [e]
    while stack and not r:
        t = stack.pop()
        if not isinstance(t, _Basic):
            continue
        args = t.args
        if _is_matrix(t):
            # reached only as the argument of a scalar-valued function of
            # it (Trace(M), M[0, 0]); a matrix's class is non-commutative,
            # its entries are walked
            stack.extend(args)
            continue
        if _fixed_noncommutative(t):
            r = True
            break
        if (isinstance(t, _Expr) and not isinstance(t, _matrix_to_scalar())
                and any(_holds_matrix(a) for a in args)):
            # an expression of a matrix (exp(M)); not a container such as
            # the CoordSys3D of a BaseScalar, whose args hold its rotation
            r = True
            break
        stack.extend(args)
    if len(_NONCOMM) >= NONCOMM_SIZE:
        _NONCOMM.clear()
    _NONCOMM[e] = r
    return r


def kept_product(factors):
    """``Mul(*factors)`` if the built product keeps exactly these factors
    (its commutative ones in any order), else None.  Building evaluates:
    the rest of an unevaluated ``Mul(c, x, 1/x)`` or ``Mul(c, x, 0)``
    would build to ``1`` or ``0``, but the node is nan at ``x = 0`` or
    ``x = oo``, so a block over the built rest would relate the node to a
    different value (#161)."""
    from sympy.core.mul import Mul
    t = Mul(*factors)
    if t.is_Mul and len(t.args) == len(factors) \
            and Counter(t.args) == Counter(factors):
        return t
    return None
