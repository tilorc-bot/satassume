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
from types import MemberDescriptorType

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


_MISSING = object()


def constructed_noncommutative(t) -> int:
    """How far SymPy builds ``t`` non-commutative, read without evaluating
    any assumption (see :func:`_fixed_noncommutative`): 0 if not known to;
    1 if ``t.is_commutative`` is False by construction; 2 if moreover none
    of the facts :func:`noncommutative_false` holds, as SymPy's fact rules
    derive from it.

    2: a non-commutative symbol, or a class fixing ``is_commutative =
    False`` (an ``Operator``, a ``MatrixExpr``: SymPy's fact rules apply to
    it) unless it may be an operation that evaluates to a number
    (:func:`_fixed_level`: ``Commutator(a, b)``, ``TensMul(0, x)``, 1).
    The ``is_commutative`` slot that ``Add`` and ``Mul`` fill when built:
    1 if False, 2 if evaluating it cannot cancel its
    non-commutative part (:func:`_nc_sum_level`, :func:`_nc_product_level`:
    ``A + x``, ``A - B``, ``-c``, ``A*B``, ``2*sin(A)``; not ``A - A``,
    ``exp(A)*exp(-A)``, ``x*A``, ``0.0*A`` or ``A + nan``, which may be
    numbers).
    ``Function``'s ``_eval_is_commutative`` (the ``fuzzy_and`` of the
    arguments): an undefined function (``f(A)``, ``f(A, 0)``), which never
    evaluates, the highest level of an argument; a function of one argument
    (``sin(A)``, ``adjoint(A)``, ``exp(M)``), its argument's level if
    SymPy defines it, as none but ``stieltjes`` evaluates a term at 2 to a
    number (a sweep of SymPy's functions; a user's ``eval`` may); any
    other 1, since a special value of another argument may make it a number
    (``rf(A, 0)`` is 1, ``binomial(A, -1)`` is 0, ``binomial(A, A)`` is 1).
    ``E**e`` (``exp(e)`` built as a power) as ``exp(e)``.  The slot of
    other powers, integrals, sums and products: 1 if False, never 2, since
    their own evaluators may make a non-commutative term a number
    (``Integral(A, (x, 0, 0)).is_zero``, ``Pow(1, A, evaluate=False)
    .is_complex``).  0 for anything else: a class fixing True or None
    (``re(A)``, ``Abs(A)``), its own property or evaluator."""
    from sympy.core.add import Add
    from sympy.core.basic import Basic
    from sympy.core.function import AppliedUndef, Function
    from sympy.core.mul import Mul
    from sympy.core.operations import AssocOp
    from sympy.core.power import Pow
    from sympy.core.singleton import S
    from sympy.core.symbol import Symbol
    if isinstance(t, Symbol):
        return 2 if _fixed_noncommutative(t) else 0
    cls = type(t)
    for k in cls.__mro__:
        v = k.__dict__.get("is_commutative", _MISSING)
        if v is _MISSING:
            continue
        if v is False:
            return _fixed_level(t)
        if v is Basic.__dict__["is_commutative"]:
            break
        if not isinstance(v, MemberDescriptorType):
            return 0
        try:
            # the construction-time slot: a plain read, no assumption is
            # evaluated or cached
            if v.__get__(t, cls) is not False:
                return 0
        except AttributeError:
            return 0
        if k is AssocOp:
            if isinstance(t, Mul):
                return _nc_product_level(t)
            if isinstance(t, Add):
                return _nc_sum_level(t)
            return 1
        if k is Pow and t.args[0] is S.Exp1:
            # exp(e) built as a power: as Function's exp(e)
            return max(1, constructed_noncommutative(t.args[1]))
        return 1
    # sympy-boundary: compares the class's evaluator, does not call it
    if getattr(cls, "_eval_is_commutative", None) is Function._eval_is_commutative:
        levels = [constructed_noncommutative(a) for a in t.args]
        top = max(levels, default=0)
        if top < 2 or isinstance(t, AppliedUndef):
            return top
        if (len(levels) == 1 and cls.__module__.startswith("sympy.")
                and cls.__name__ != "stieltjes"):
            # stieltjes(A) is zoo (A.is_integer is False)
            return 2
        return 1
    return 0


def _fixed_level(t) -> int:
    """The level of a term whose class fixes ``is_commutative = False``: 2
    for a matrix expression, which is never a number, and for a term built
    from labels, which is its own value: its class defines no evaluator
    (:func:`_evaluates`), and every argument is commutative by construction
    (:func:`_constructed_commutative`) and unchanged by evaluation
    (:func:`_unchanged_by_doit`: ``Operator('a')``, ``JzKet(j, m)``,
    ``CreateBoson(i)``); else 1.  An operation over
    non-commutative terms may evaluate to a number (#232):
    ``Commutator(a, b - b)`` and ``AntiCommutator(a, b - b)`` are 0, and
    ``Commutator(a, Dagger(a))`` is 1 for a boson operator ``a``; so may an
    operation over commutative terms whose class evaluates
    (:func:`_evaluates`: ``TensMul(0, x)`` is 0, ``TensAdd(1, 1)`` is 2,
    secondquant ``Commutator(x, y, evaluate=False)`` is 0; re-review R2)."""
    if _is_matrix(t):
        return 2
    if _evaluates(type(t)):
        return 1
    return 2 if all(_constructed_commutative(a) and _unchanged_by_doit(a) for a in t.args) else 1


def _evaluates(cls) -> bool:
    """Whether ``cls`` or a base defines how its terms evaluate: an
    ``eval`` (run when a ``Function`` or a quantum ``Commutator`` is built),
    a ``doit`` or an ``_eval_doit``, other than SymPy's inert defaults:
    ``Basic.doit`` rebuilds the term from its arguments, ``Atom.doit``
    returns it, ``Application.eval`` returns None.  Read from the class
    dictionaries; nothing is called."""
    from sympy.core.basic import Atom
    from sympy.core.function import Application
    inert = {"doit": (_Basic, Atom), "_eval_doit": (), "eval": (Application,)}
    return any(n in k.__dict__ and k not in ks for k in cls.__mro__ for n, ks in inert.items())


def _unchanged_by_doit(a) -> bool:
    """Whether evaluating ``a`` leaves it as it is: no class on the way
    evaluates (:func:`_evaluates`) and every argument is unchanged, down to
    atoms (``Symbol('a')``, ``1/2``, ``Tuple(0, 1)``).  Then ``Basic.doit``
    rebuilds a term over such arguments from the same arguments.  An
    unevaluated ``p + 0`` is changed, and the constructor of the term over
    it may give a number: ``FKet([p, p + 0])`` is 0, a doubly occupied
    fermion state (re-review R2).  So is an evaluated ``x + 1``, as nothing
    in the term tells the two apart."""
    if not isinstance(a, _Basic):
        return True  # Basic.doit passes it on as it is
    return not _evaluates(type(a)) and all(_unchanged_by_doit(b) for b in a.args)


def _constructed_commutative(s) -> bool:
    """Whether SymPy builds ``s`` commutative, read without evaluating any
    assumption (see :func:`_fixed_noncommutative`): a symbol declared
    commutative, a class fixing ``is_commutative = True`` (a number), the
    slot of an ``Add``, ``Mul`` or ``Pow`` filled True, and a function
    (``Function``'s ``_eval_is_commutative``) or a container (``Tuple``,
    ``Str``: not an ``Expr``) of such terms.  False for anything else: a
    class whose property or evaluator decides it (#233 review)."""
    from sympy.core.basic import Basic
    from sympy.core.function import Function
    from sympy.core.symbol import Symbol
    if isinstance(s, Symbol):
        # sympy-boundary: the declared commutative flag only
        return dict(getattr(s, "_assumptions0", ())).get("commutative") is True
    if not isinstance(s, _Basic):
        return False
    cls = type(s)
    for k in cls.__mro__:
        v = k.__dict__.get("is_commutative", _MISSING)
        if v is _MISSING:
            continue
        if v is True:
            return True
        if v is Basic.__dict__["is_commutative"]:
            break
        if not isinstance(v, MemberDescriptorType):
            return False
        try:
            return v.__get__(s, cls) is True
        except AttributeError:
            return False
    # sympy-boundary: compares the class's evaluator, does not call it
    generic = getattr(cls, "_eval_is_commutative", None) is Function._eval_is_commutative
    if generic or not isinstance(s, _Expr):
        return all(_constructed_commutative(a) for a in s.args)
    return False


def _nonzero_number(a) -> bool:
    """A nonzero rational: not ``0.0``, ``nan`` or an infinity
    (``oo*A - oo*A`` is ``nan*A``)."""
    return a.is_Rational and a.p != 0


def _nc_symbol(a) -> bool:
    from sympy.core.symbol import Symbol
    return isinstance(a, Symbol) and _fixed_noncommutative(a)


def _nc_product_level(t) -> int:
    """The level of a ``Mul`` built non-commutative: 2 if every factor is
    a nonzero number or at 2, and at most one factor is not a number unless
    they are all non-commutative symbols (``A*B*A`` evaluates to no power
    that may cancel); else 1.  A factor that may be zero (``0*A``, ``x*A``,
    a zero integral) may make the product the number 0
    (``exp(0*A).is_algebraic``), and factors of a common base may cancel
    (``exp(A)*exp(-A)``, ``A*exp(-log(A))`` evaluate to 1)."""
    rest = [a for a in t.args if not _nonzero_number(a)]
    if any(constructed_noncommutative(a) < 2 for a in rest):
        return 1
    if len(rest) > 1 and not all(_nc_symbol(a) for a in rest):
        return 1
    return 2


def _nc_sum_level(t) -> int:
    """The level of an ``Add`` built non-commutative: 2 if its commutative
    terms are rationals and at most one symbol, and a single term is
    non-commutative and at 2 (``A + x``, ``sin(A) + 1``), or every
    non-commutative term is a non-commutative symbol or a nonzero rational
    times one, no symbol twice (``A - 2*B``); else 1.  Evaluating it may
    cancel the non-commutative terms (``A - A``, ``A - A*Integral(1,
    (x, 0, 1))``, ``c - Dagger(c)`` for a Hermitian ``c``), and a nan term
    absorbs them (``A + nan``, ``A + 0*oo``, ``A + x + y`` at ``x = oo, y =
    -oo``)."""
    from sympy.core.mul import Mul
    from sympy.core.symbol import Symbol
    nc = [(a, constructed_noncommutative(a)) for a in t.args]
    rest = [a for a, lv in nc if not lv and not a.is_Rational]
    if len(rest) > 1 or (rest and not isinstance(rest[0], Symbol)):
        return 1
    nc = [(a, lv) for a, lv in nc if lv]
    if len(nc) == 1:
        return nc[0][1]
    seen = set()
    for a, _ in nc:
        if isinstance(a, Mul) and len(a.args) == 2 and _nonzero_number(a.args[0]):
            a = a.args[1]
        if not _nc_symbol(a) or a in seen:
            return 1
        seen.add(a)
    return 2


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
