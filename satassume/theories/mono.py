"""MONO: monotone-function and range lemmas for the relation glue (#149, T5).

LRA reads a function application (``exp(x)``, ``log(x + 1)``, ``x**2``,
``atan(y)``) as an opaque term: ``x > 1`` and ``log(x) > 0`` are unrelated
for it.  This module is the table that relates them: for an application
``f(u)`` of a listed function it says where ``f`` is strictly monotone
(:class:`Piece`), how to compute ``f(c)`` and its inverse at a constant,
and which range or sandwich facts hold (:class:`Row`).
:class:`satassume.relations.Relations` turns that into clauses over
relation atoms (``Relations._mono_*``); this module adds no clause, holds
no state and imports SymPy only inside functions.

Meaning
-------
Values are SymPy's at every point of the extended domain, including the
infinite ends of a piece (``exp(-oo) = 0``, ``log(oo) = oo``,
``atan(oo) = pi/2``, ``oo**(-1) = 0``, ``(-oo)**2 = oo``, ``acot(-oo) = 0``):
on each :class:`Piece` (an interval of the extended reals whose ends are
``-oo``, ``0`` or ``oo``, each closed or open) ``f`` is strictly increasing
(``dir = 1``) or decreasing (``dir = -1``) *including* those infinite
ends, so for ``u``, ``c`` in the piece ``u > c <-> f(u) > f(c)`` (or ``<``)
and ``u = c <-> f(u) = f(c)``.  ``tests/test_mono.py`` checks each piece
at sample points, ``0`` and ``+-oo`` with SymPy's own evaluation.

Pieces (``u`` the argument; ``k`` a Rational exponent of a ``Pow`` whose
base has free symbols):

==========================  =============================================
``exp``, ``atan``, ``tanh``  ``[-oo, oo]`` increasing
``sinh``, ``asinh``
``log``                      ``(0, oo]`` increasing (``log(0) = zoo``,
                             ``log(-oo) = oo``: no piece below 0)
``cosh``                     ``[0, oo]`` increasing, ``[-oo, 0]``
                             decreasing
``acot``                     ``(0, oo]`` and ``[-oo, 0)`` decreasing
                             (``acot(0) = pi/2`` is outside both)
``u**k``, ``k > 0`` odd      ``[-oo, oo]`` increasing
``u**k``, ``k > 0`` even     ``[0, oo]`` increasing, ``[-oo, 0]``
                             decreasing
``u**k``, ``k > 0`` not int  ``[0, oo]`` increasing (principal branch:
                             a negative base gives a non-real value)
``u**k``, ``k < 0`` odd      ``(0, oo]`` and ``[-oo, 0)`` decreasing
``u**k``, ``k < 0`` even     ``(0, oo]`` decreasing, ``[-oo, 0)``
                             increasing
``u**k``, ``k < 0`` not int  ``(0, oo]`` decreasing
==========================  =============================================

Rows (range and sandwich facts, each ``guard(u) -> [~]lt(lhs, rhs)``;
``lt`` is the relation atom, which asserts that both sides are extended
reals, so a refuted ``lt`` holds with no guard):

* ``atan``: ``real(u) -> -pi/2 < atan(u) < pi/2``; ``~(atan(u) > pi/2)``,
  ``~(atan(u) < -pi/2)`` (``atan(+-oo) = +-pi/2``; ``atan`` of a non-real
  value is no real number outside ``[-pi/2, pi/2]``: the principal
  branch has its real part there).  ``tanh`` the same with ``+-1``
  (``tanh(z)`` real and outside ``[-1, 1]`` only at ``zoo``-free
  non-real ``z``: guarded by ``extended_real(u)``).
* ``exp``: ``real(u) -> 0 < exp(u)``; ``extended_real(u) -> ~(exp(u) < 0)``.
* ``cosh``: ``extended_real(u) -> ~(cosh(u) < 1)``.
* ``u**k`` with ``k`` a positive even integer:
  ``extended_real(u) -> ~(u**k < 0)``.
* ``acot``: ``extended_real(u) -> ~(acot(u) > pi/2)``,
  ``~(acot(u) < -pi/2)``.
* ``Abs``: ``~(Abs(u) < u)``, ``~(Abs(u) < -u)`` (unguarded: the atom is
  false unless ``u`` is an extended real, and then ``Abs(u) = |u|``,
  ``Abs(+-oo) = oo``); ``extended_nonnegative(u) -> ~(u < Abs(u))``,
  ``extended_nonpositive(u) -> ~(-u < Abs(u))``.
* ``floor``: ``~(u < floor(u))`` (``floor(+-oo) = +-oo``);
  ``real(u) -> u < floor(u) + 1``.  ``ceiling``: ``~(ceiling(u) < u)``;
  ``real(u) -> ceiling(u) - 1 < u``.

Excluded: ``tan``, ``cot`` (poles), ``asin``/``acos`` (their domain ends
are ``+-1``, which no unary predicate names), ``sin``/``cos``
(not monotone), Float exponents and Float thresholds (not read by LRA).
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Callable, NamedTuple, Optional, Tuple

from ..state.memos import PROCESS as _PROCESS

#: piece ends: lower ``'-oo'`` (closed at -oo), ``'0'`` (closed at 0),
#: ``'0+'`` (open at 0); upper ``'oo'``, ``'0'``, ``'0-'``
LOWER = ("-oo", "0", "0+")
UPPER = ("oo", "0", "0-")


class Piece(NamedTuple):
    """An interval of the extended reals where ``f`` is strictly monotone."""
    lo: str
    hi: str
    dir: int                      # 1 increasing, -1 decreasing

    def guard(self) -> Tuple[Tuple[str, bool], ...]:
        """Basis literals whose conjunction says ``u`` is in the piece."""
        return _PIECE_GUARD[(self.lo, self.hi)]

    def holds(self, sgn: int) -> bool:
        """Whether a finite ``c`` of sign ``sgn`` lies in the piece."""
        lo, hi = self.lo, self.hi
        if lo == "0" and sgn < 0 or lo == "0+" and sgn <= 0:
            return False
        if hi == "0" and sgn > 0 or hi == "0-" and sgn >= 0:
            return False
        return True


#: (lo, hi) -> the basis literals (pred, polarity) whose conjunction says
#: that an extended real ``u`` lies in the piece (and that ``u`` is one)
_PIECE_GUARD = MappingProxyType({
    ("-oo", "oo"): (("extended_real", True),),
    ("0", "oo"): (("extended_real", True), ("extended_negative", False)),
    ("0+", "oo"): (("extended_positive", True),),
    ("-oo", "0"): (("extended_real", True), ("extended_positive", False)),
    ("-oo", "0-"): (("extended_negative", True),),
})

#: guard names of :class:`Row` -> basis literals (as ``_PIECE_GUARD``)
GUARDS = MappingProxyType({
    None: (),
    "extended_real": (("extended_real", True),),
    "real": (("extended_real", True), ("finite", True)),
    "extended_nonnegative": (("extended_real", True), ("extended_negative", False)),
    "extended_nonpositive": (("extended_real", True), ("extended_positive", False)),
})


class Row(NamedTuple):
    """``guard(u) -> lt(lhs, rhs)`` (``positive``) or ``-> ~lt(lhs, rhs)``;
    ``lhs``/``rhs`` are functions of ``(u, app)``."""
    guard: Optional[str]
    lhs: Callable[[Any, Any], Any]
    rhs: Callable[[Any, Any], Any]
    positive: bool


class Spec(NamedTuple):
    """What the table knows about one application ``app = f(arg)``."""
    family: tuple                 # equal for applications of the same f
    arg: Any
    pieces: Tuple[Piece, ...]
    apply: Callable[[Any], Any]   # c -> f(c) (SymPy, evaluated)
    #: d -> candidates c with f(c) = d; the caller keeps a candidate only
    #: if ``d`` is in ``inv_range``, ``c`` in a piece and (unless
    #: ``exact``) ``apply(c) == d``
    inverse: Callable[[Any], tuple]
    #: the open interval ``(lo, hi)`` of values ``d`` the inverse is read
    #: at (None: unbounded), and whether ``d = 0`` is excluded
    inv_range: Tuple[Any, Any, bool]
    rows: Tuple[Row, ...]
    #: ``f(c) = d`` holds for every candidate ``c`` of every ``d`` in
    #: ``inv_range`` (``asinh(sinh(d)) = d``, ``atan(tan(d)) = d`` on
    #: ``(-pi/2, pi/2)``, ``cosh(+-acosh(d)) = d`` on ``(1, oo)``), which
    #: SymPy's evaluation does not always show; False for ``Pow`` (the
    #: candidates ``+-|d|**(1/k)`` are preimages only for some signs)
    exact: bool = False


_WHOLE = (Piece("-oo", "oo", 1),)


def _app(u, a):
    return a


def _const(v):
    return lambda u, a: v


def _bounded_rows(lo, hi):
    """Range rows of an increasing ``f`` on ``[-oo, oo]`` with
    ``f(-oo) = lo``, ``f(oo) = hi`` (finite)."""
    return (Row("real", _app, _const(hi), True),
            Row("real", _const(lo), _app, True),
            Row("extended_real", _const(hi), _app, False),
            Row("extended_real", _app, _const(lo), False))


_SPECS = _PROCESS.table(f"{__name__}._SPECS", "pure", 100_000)


def spec(term) -> Optional[Spec]:
    """The :class:`Spec` of ``term``, or None if it is no application of a
    listed function (memoized per term; a pure function of it)."""
    try:
        return _SPECS[term]
    except KeyError:
        pass
    except TypeError:
        return None
    r = _spec(term)
    if len(_SPECS) >= _SPECS.size:
        _SPECS.clear()
    _SPECS[term] = r
    return r


_NAMES = frozenset({"exp", "log", "atan", "tanh", "sinh", "asinh", "cosh",
                    "acot", "Abs", "floor", "ceiling"})

#: the functions whose sign rows the templates no longer carry
#: (``templates/functions.py``: ``extended_real(u) -> (positive(f(u)) <->
#: extended_positive(u))`` and the like): the threshold-0 lemmas of their
#: :class:`Spec` give them, once the glue links ``f(u)`` and ``u``
#: (:func:`sign_terms`, ``satassume.scope``)
SIGN_FUNCS = frozenset({"atan", "tanh", "sinh"})

#: functions with a left inverse on their whole domain (``exp(log(z)) =
#: z``, ``tan(atan(z)) = z``): ``f(u) = f(c)`` gives ``u = c`` with no
#: piece guard (``Relations._mono_lemmas``), as the templates' unguarded
#: ``zero(log(x)) <-> zero(x - 1)`` and ``zero(atan(x)) <-> zero(x)`` did
INJECTIVE = frozenset({"log", "atan"})

_SIGN_TERMS = _PROCESS.table(f"{__name__}._SIGN_TERMS", "pure", 100_000)


def sign_terms(e) -> frozenset:
    """The applications ``f(u)`` of a :data:`SIGN_FUNCS` function with a
    :class:`Spec`, at any depth of ``e``, and their arguments ``u`` (not
    numbers): the terms whose sign links stand in for the removed rows.
    Memoized per expression (a pure function of it)."""
    try:
        return _SIGN_TERMS[e]
    except KeyError:
        pass
    except TypeError:
        return frozenset()
    out = set()
    stack = [e]
    while stack:
        t = stack.pop()
        args = getattr(t, "args", ())
        if not args:
            continue
        if type(t).__name__ in SIGN_FUNCS and spec(t) is not None:
            out.add(t)
            u = args[0]
            if u.free_symbols:
                out.add(u)
                if u.is_Add:
                    # the opaque terms of u's linear form (xp of xp + 1):
                    # their signs bound u against the thresholds
                    for a in u.args:
                        r = a.as_coeff_Mul()[1]
                        if r.free_symbols:
                            out.add(r)
        stack.extend(args)
    r = frozenset(out)
    if len(_SIGN_TERMS) >= _SIGN_TERMS.size:
        _SIGN_TERMS.clear()
    _SIGN_TERMS[e] = r
    return r


def atom_sign_terms(atoms) -> frozenset:
    """:func:`sign_terms` of the expressions of the atoms ``atoms`` (the
    sides of a relation atom ``eq``/``lt``): the terms the glue links as if
    they were arguments of vocabulary atoms (``Relations.note_formula``,
    ``selectors_of``; ``scope.mono_terms``).  Empty without an application
    of a :data:`SIGN_FUNCS` function: then the query is as without MONO."""
    out = frozenset()
    for a in atoms:
        e = a.expr
        for side in (e if a.pred in ("eq", "lt") else (e,)):
            t = sign_terms(side)
            if t:
                out = out | t
    return out


def _spec(t) -> Optional[Spec]:
    name = type(t).__name__
    is_pow = getattr(t, "is_Pow", False)
    if name not in _NAMES and not is_pow:
        return None
    args = getattr(t, "args", ())
    if not args or not getattr(args[0], "free_symbols", None):
        return None
    if getattr(t, "is_commutative", None) is not True:
        return None
    from sympy import (Abs, S, acosh, acot, asinh, atan, atanh, ceiling, cosh,
                       cot, exp, floor, log, pi, sinh, tan, tanh)
    u = args[0]
    if getattr(u, "is_commutative", None) is not True:
        return None
    if is_pow:
        k = args[1]
        if not k.is_Rational or k == 0 or not k.free_symbols == set():
            return None
        return _pow_spec(t, u, k)
    if len(args) != 1:
        return None
    if name == "Abs":
        return Spec(("Abs",), u, (), Abs, _none, _ANY, (
            Row(None, _app, lambda u, a: u, False),
            Row(None, _app, lambda u, a: -u, False),
            Row("extended_nonnegative", lambda u, a: u, _app, False),
            Row("extended_nonpositive", lambda u, a: -u, _app, False)))
    if name == "floor":
        return Spec(("floor",), u, (), floor, _none, _ANY, (
            Row(None, lambda u, a: u, _app, False),
            Row("real", lambda u, a: u, lambda u, a: a + 1, True)))
    if name == "ceiling":
        return Spec(("ceiling",), u, (), ceiling, _none, _ANY, (
            Row(None, _app, lambda u, a: u, False),
            Row("real", lambda u, a: a - 1, lambda u, a: u, True)))
    half = pi / 2
    if name == "exp":
        return Spec(("exp",), u, _WHOLE, exp, lambda d: (log(d),), (S.Zero, None, False),
                    (Row("real", _const(S.Zero), _app, True),
                     Row("extended_real", _app, _const(S.Zero), False)), True)
    if name == "log":
        return Spec(("log",), u, (Piece("0+", "oo", 1),), log,
                    lambda d: (exp(d),), _ANY, (), True)
    if name == "atan":
        return Spec(("atan",), u, _WHOLE, atan,
                    lambda d: (tan(d),), (-half, half, False),
                    _bounded_rows(-half, half), True)
    if name == "tanh":
        return Spec(("tanh",), u, _WHOLE, tanh,
                    lambda d: (atanh(d),), (S.NegativeOne, S.One, False),
                    _bounded_rows(S.NegativeOne, S.One), True)
    if name == "sinh":
        return Spec(("sinh",), u, _WHOLE, sinh, lambda d: (asinh(d),), _ANY, (), True)
    if name == "asinh":
        return Spec(("asinh",), u, _WHOLE, asinh, lambda d: (sinh(d),), _ANY, (), True)
    if name == "cosh":
        return Spec(("cosh",), u, (Piece("0", "oo", 1), Piece("-oo", "0", -1)), cosh,
                    lambda d: (acosh(d), -acosh(d)), (S.One, None, False),
                    (Row("extended_real", _app, _const(S.One), False),), True)
    if name == "acot":
        return Spec(("acot",), u, (Piece("0+", "oo", -1), Piece("-oo", "0-", -1)), acot,
                    lambda d: (cot(d),), (-half, half, True),
                    (Row("extended_real", _const(half), _app, False),
                     Row("extended_real", _app, _const(-half), False)), True)
    return None


def _none(d) -> tuple:
    return ()


#: an unbounded inverse range
_ANY = (None, None, False)


def _pow_spec(t, u, k) -> Spec:
    from sympy import Abs, S, Pow
    if k.is_Integer:
        odd = bool(k % 2)
        if k > 0:
            pieces = _WHOLE if odd else (Piece("0", "oo", 1), Piece("-oo", "0", -1))
        else:
            pieces = ((Piece("0+", "oo", -1), Piece("-oo", "0-", -1)) if odd
                      else (Piece("0+", "oo", -1), Piece("-oo", "0-", 1)))
    else:
        pieces = (Piece("0", "oo", 1),) if k > 0 else (Piece("0+", "oo", -1),)
    rows = ()
    if k > 0 and k.is_Integer and not k % 2:
        rows = (Row("extended_real", _app, _const(S.Zero), False),)
    inv = 1 / k

    def inverse(d):
        r = Pow(Abs(d), inv)
        return (r, -r)

    return Spec(("Pow", k), u, pieces, lambda c: Pow(c, k), inverse, _ANY, rows)
