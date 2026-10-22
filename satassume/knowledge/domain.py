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

import sys
from collections import Counter
from types import MemberDescriptorType

from sympy.core.basic import Basic as _Basic
from sympy.core.containers import Tuple as _Tuple
from sympy.core.expr import Expr as _Expr
from sympy.core.singleton import S as _S

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


_MISSING = object()


def constructed_noncommutative(t) -> int:
    """How far SymPy builds ``t`` non-commutative, read without evaluating
    any assumption (see :func:`_fixed_noncommutative`): 0 if not known to;
    1 if ``t.is_commutative`` is False by construction
    (:func:`_built_noncommutative`); 2 if moreover none of the facts
    :func:`noncommutative_false` holds.

    The spec's truth standard (docs/spec.md, "Truth standard"; #247): a
    term built non-commutative stands for an element of a non-commutative
    algebra (an operator, a matrix), never for a number.  Its zero and its
    identity (``A - A``, ``0*A``, ``A**0``, ``rf(A, 0)``, an empty sum,
    ``Integral(A, (x, 0, 0))``) are the algebra's, not the scalars 0 and
    1, whatever ``doit()`` or automatic evaluation writes for them.  So a
    term built non-commutative is at 2 (a matrix always), unless it is
    held at 1 (:func:`_held_at_one`): a function of nan, a class whose
    evaluators are the user's own, or a relation between operators that
    may stand for the identity (both pending Tilo's decision, #247)."""
    if not _built_noncommutative(t):
        return 0
    if _is_matrix(t):
        return 2
    return 1 if _held_at_one(t) else 2


def _built_noncommutative(t) -> bool:
    """Whether SymPy builds ``t`` non-commutative: a non-commutative
    symbol; a class fixing ``is_commutative = False`` (an ``Operator``, a
    ``MatrixExpr``, ``Function('g', commutative=False)``); the
    ``is_commutative`` slot that ``Add``, ``Mul``, ``Pow`` and integrals,
    sums and products fill when built, if False; ``Function``'s
    ``_eval_is_commutative`` (the ``fuzzy_and`` of the arguments: ``f(A)``,
    ``adjoint(A)``, ``exp(M)``) with an argument built non-commutative.
    Not a class fixing True or None (``re(A)``, ``Abs(A)``), nor its own
    property or evaluator."""
    from sympy.core.basic import Basic
    from sympy.core.function import Function
    from sympy.core.symbol import Symbol
    if isinstance(t, Symbol):
        return _fixed_noncommutative(t)
    cls = type(t)
    for k in cls.__mro__:
        v = k.__dict__.get("is_commutative", _MISSING)
        if v is _MISSING:
            continue
        if v is False:
            return True
        if v is Basic.__dict__["is_commutative"]:
            break
        if not isinstance(v, MemberDescriptorType):
            return False
        try:
            # the construction-time slot: a plain read, no assumption is
            # evaluated or cached
            return v.__get__(t, cls) is False
        except AttributeError:
            return False
    # sympy-boundary: compares the class's evaluator, does not call it
    if getattr(cls, "_eval_is_commutative", None) is Function._eval_is_commutative:
        return any(_built_noncommutative(a) for a in t.args)
    return False


#: whether a relation between operators with a commutation rule is held at
#: level 1 (#247, open question 4: ``[c, c†]`` and ``{d, d†}`` stand for the
#: identity, which SymPy writes as the number 1; Tilo's decision pending).
#: False puts them at 2 like any term built non-commutative.
IDENTITY_RELATIONS_HELD = True

#: whether a class with the user's own evaluators is held at level 1 (#247,
#: open question 3, #239: a user's ``Function`` whose ``eval`` returns
#: ``S.Zero``; Tilo's decision pending).
USER_EVALUATORS_HELD = True


def _held_at_one(t) -> bool:
    """Whether a term built non-commutative stays at level 1:

    - it may be nan (:func:`may_be_nan`: ``A + nan``, ``oo*A``, ``A + 0*oo``,
      ``Integral(A, (x, -oo, oo))``): nan is no number, and a function of
      nan has no facts (design.md, "Extended reals and nan"; #189);
    - with :data:`USER_EVALUATORS_HELD`, a subterm's class is not SymPy's
      own (:func:`_sympy_class`) nor a plain undefined function
      (:func:`_plain_undefined`): the user's ``eval``, ``doit`` or property
      (``Function('g', eval=...)(A)``, a ``Function`` subclass of a test
      module, #239);
    - with :data:`IDENTITY_RELATIONS_HELD`, a proper subterm is an operator
      with a commutation rule (:func:`_has_relations`: ``Commutator(c,
      Dagger(c))`` for a boson operator ``c``, ``c*Dagger(c) -
      Dagger(c)*c``); the operator itself (``BosonOp('c')``) is not held;
      and ``IdentityOperator()``, which SymPy 1.14 deprecates for ``S.One``.

    An argument nan only at some values of its symbols (``A + x + y`` at
    ``x = oo, y = -oo``) is not held: the facts of level 2 are numeric
    predicates False, and the soundness oracle makes them False of nan
    too."""
    if may_be_nan(t):
        return True
    stack = [t]
    while stack:
        s = stack.pop()
        if not isinstance(s, _Basic):
            continue
        cls = type(s)
        if USER_EVALUATORS_HELD and not (_sympy_class(cls) or _plain_undefined(cls)):
            return True
        if IDENTITY_RELATIONS_HELD and (_identity_operator(s) or s is not t and _has_relations(s)):
            return True
        stack.extend(s.args)
    return False


def _sympy_class(cls) -> bool:
    """Whether ``cls`` is SymPy's own: the class that a SymPy module outside
    its test modules defines under its name (not a class with a borrowed
    ``__module__`` or ``__qualname__``, #239)."""
    mod = cls.__module__ or ""
    if not mod.startswith("sympy.") or ".tests." in mod:
        return False
    return getattr(sys.modules.get(mod), cls.__qualname__, None) is cls


_RELATIONS = _PROCESS.table(f"{__name__}._RELATIONS", "pure", 1024)


def _has_relations(s) -> bool:
    """Whether ``s`` is an operator whose class states commutation rules
    (quantum operators with ``_eval_commutator_*`` or
    ``_eval_anticommutator_*`` methods: ``BosonOp``, ``FermionOp``,
    ``SigmaX``, ``XOp``, ``JzOp``) or a creation or annihilation operator of
    ``secondquant``: a relation between them may be a multiple of the
    identity, which SymPy writes as a number (``[c, c†] = 1``)."""
    cls = type(s)
    r = _RELATIONS.get(cls)
    if r is None:
        r = any(n.startswith(("_eval_commutator_", "_eval_anticommutator_")) for n in dir(cls))
        sq = sys.modules.get("sympy.physics.secondquant")
        if sq is not None and issubclass(cls, sq.SqOperator):
            r = True
        if len(_RELATIONS) >= 1024:
            _RELATIONS.clear()
        _RELATIONS[cls] = r
    return r


def _identity_operator(s) -> bool:
    q = sys.modules.get("sympy.physics.quantum.operator")
    return q is not None and isinstance(s, q.IdentityOperator)


def _plain_undefined(cls) -> bool:
    """Whether ``cls`` is an undefined function as ``Function(name, ...)``
    makes it, with nothing more in its class dictionary than such a class
    has (its assumptions ``is_*`` and the bookkeeping of a reference
    class): ``Function('g', commutative=False, eval=...)``, ``doit=`` or
    ``_eval_evalf=``, and a subclass of ``AppliedUndef``, have the user's
    own evaluators (#238 review)."""
    from sympy.core.function import AppliedUndef, UndefinedFunction
    if type(cls) is not UndefinedFunction or cls.__bases__ != (AppliedUndef,):
        return False
    global _UNDEFINED_KEYS
    if _UNDEFINED_KEYS is None:
        _UNDEFINED_KEYS = frozenset(UndefinedFunction('_satassume_reference', commutative=False).__dict__)
    return all(k in _UNDEFINED_KEYS or k.startswith('is_') for k in cls.__dict__)


_UNDEFINED_KEYS = None


_SPECIAL = (_S.NaN, _S.Infinity, _S.NegativeInfinity, _S.ComplexInfinity)


def may_be_nan(a) -> bool:
    """``a`` is ``nan``, or holds an explicit ``nan`` or infinity in a part
    that carries a value, so that it may evaluate to nan: arithmetic
    (``oo - oo``, ``0*oo``, ``x + oo`` at ``x = -oo``), a function
    application (``Abs(nan)``), and every other node whose arguments feed
    its value -- ``Subs(nan, x, 1)``, ``Subs(x, x, nan)``,
    ``Limit(nan, x, 0)``, ``UnevaluatedExpr(nan)``, an integral or a sum
    over ``(-oo, oo)`` (``Integral(x, (x, -oo, oo))`` is nan), a
    ``Piecewise`` branch value, and a condition too: a ``Piecewise``
    without a ``True`` branch is nan where no condition holds, so a
    condition holding ``oo - oo`` may leave no value (#236 review).  Only
    the arguments of an atom (the range of an ``Idx``) are labels, not
    followed (#235 review; re-review R1)."""
    if a is _S.NaN:
        return True
    if not isinstance(a, _Basic) or a.is_Atom:
        return False
    return any(any(b is c for c in _SPECIAL) or may_be_nan(b) for b in a.args)


_NONCOMMUTATIVE_FALSE: frozenset = frozenset()


def noncommutative_false() -> frozenset:
    """The facts false of a term whose ``commutative`` is False: those SymPy's
    fact rules derive false from it (``complex -> commutative``, and every
    fact implying ``complex``: ``zero``, ``real``, ``integer``, ...),
    ``commutative`` included.  ``finite``, ``infinite``, ``hermitian``,
    ``antihermitian`` and ``polar`` are not among them."""
    global _NONCOMMUTATIVE_FALSE
    if not _NONCOMMUTATIVE_FALSE:
        from sympy.core.assumptions import StdFactKB
        _NONCOMMUTATIVE_FALSE = frozenset(
            k for k, v in StdFactKB({"commutative": False}).items() if v is False)
    return _NONCOMMUTATIVE_FALSE


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
