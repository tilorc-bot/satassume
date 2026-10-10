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

from fractions import Fraction
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
    #: range of ``f(u)`` for a real ``u`` whose image is real:
    #: ``(lo, lo_strict, hi, hi_strict)``, None ends unbounded
    bounds: Optional[tuple] = None
    #: a real ``u`` with a real ``f(u)`` lies in the only piece
    #: (``log``, non-integer powers: the principal branch)
    covered: bool = False
    #: a real ``f(u)`` has a real ``u``: ``f`` has a left inverse real on
    #: reals (``exp(log(z)) = z``, ``sinh(asinh(z)) = z``, ``(z**k)**(1/k)
    #: = z`` on the principal branch for ``0 < k < 1``) and no real value
    #: at ``+-oo``/``zoo`` (so not ``atan``, ``acot`` or ``k < 0``:
    #: ``atan(oo) = pi/2``, ``1/oo = 0``)
    real_arg: bool = False


_WHOLE = (Piece("-oo", "oo", 1),)


def _app(u, a):
    return a


def _const(v):
    return lambda u, a: v


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

#: functions with a left inverse on their whole domain (``exp(log(z)) =
#: z``, ``tan(atan(z)) = z``): ``f(u) = f(c)`` gives ``u = c`` with no
#: piece guard (``Relations._mono_lemmas``), as the templates' unguarded
#: ``zero(log(x)) <-> zero(x - 1)`` and ``zero(atan(x)) <-> zero(x)`` do
INJECTIVE = frozenset({"log", "atan"})


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
                    (), True, (S.Zero, True, None, False))
    if name == "log":
        return Spec(("log",), u, (Piece("0+", "oo", 1),), log,
                    lambda d: (exp(d),), _ANY, (), True, None, True, True)
    if name == "atan":
        return Spec(("atan",), u, _WHOLE, atan,
                    lambda d: (tan(d),), (-half, half, False),
                    (), True, (-half, True, half, True))
    if name == "tanh":
        return Spec(("tanh",), u, _WHOLE, tanh,
                    lambda d: (atanh(d),), (S.NegativeOne, S.One, False),
                    (), True, (S.NegativeOne, True, S.One, True))
    if name == "sinh":
        return Spec(("sinh",), u, _WHOLE, sinh, lambda d: (asinh(d),), _ANY, (), True)
    if name == "asinh":
        return Spec(("asinh",), u, _WHOLE, asinh, lambda d: (sinh(d),), _ANY, (), True,
                    None, False, True)
    if name == "cosh":
        return Spec(("cosh",), u, (Piece("0", "oo", 1), Piece("-oo", "0", -1)), cosh,
                    lambda d: (acosh(d), -acosh(d)), (S.One, None, False),
                    (), True, (S.One, False, None, False))
    if name == "acot":
        return Spec(("acot",), u, (Piece("0+", "oo", -1), Piece("-oo", "0-", -1)), acot,
                    lambda d: (cot(d),), (-half, half, True),
                    (), True, (-half, True, half, False))
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
    # the image of a real u is real only at u >= 0 (u > 0 for k < 0) for a
    # non-integer k, and only at u != 0 for an integer k < 0
    bounds = None
    if not k.is_Integer or not k % 2:
        bounds = (S.Zero, k < 0, None, False)
    inv = 1 / k

    def inverse(d):
        r = Pow(Abs(d), inv)
        return (r, -r)

    return Spec(("Pow", k), u, pieces, lambda c: Pow(c, k), inverse, _ANY, (),
                False, bounds, not k.is_Integer, 0 < k < 1)


# -- the field-number view LRA uses (lra.MonoLink) ------------------------

def _field(e):
    """The exact-field number of the closed SymPy constant ``e`` if it is a
    finite real the field reads, else None."""
    from .lra.constfield import from_sympy
    return from_sympy(e, generic=True)


def _sympy_of(q):
    if type(q) is Fraction:
        from sympy import Rational
        return Rational(q.numerator, q.denominator)
    return q.to_sympy()


def _fsign(q) -> Optional[int]:
    from .lra.constfield import Undecided, sign
    if type(q) is Fraction:
        return (q > 0) - (q < 0)
    try:
        return sign(q)
    except Undecided:
        return None


#: bit size above which a rational gets no image or preimage: the bounds
#: branch and bound tries can grow without end through links (``n**3`` of
#: an integer ``n``), and SymPy's powers and roots of such numbers are slow
_BITS = 64


def _big(q) -> bool:
    return type(q) is Fraction and (q.numerator.bit_length() > _BITS
                                    or q.denominator.bit_length() > _BITS)


class LinkMap:
    """What LRA needs of a :class:`Spec` to relate the variable of ``f(u)``
    to the linear form of ``u`` (``satassume.theories.lra.lra.MonoLink``),
    in exact-field numbers (``Fraction`` or ``constfield.Element``):

    * ``pieces``: ``(lo, hi, dir)`` of each :class:`Piece`;
    * ``bounds``: the range ``(lo, lo_strict, hi, hi_strict)`` of ``f(u)``
      for a real ``u`` with a real image (None ends unbounded), or None;
    * ``covered``: such a ``u`` lies in the only piece;
    * ``vshape``: ``f`` decreases on ``[-oo, 0]`` and increases on
      ``[0, oo]``;
    * :meth:`image` ``(c)``: ``f(c)`` if it is a finite real the field
      reads, else None;
    * :meth:`preimage` ``(d, i)``: the ``c`` in piece ``i`` with ``f(c) =
      d``, for ``d`` inside the open inverse range, or None.

    Neither is computed for a rational of more than ``_BITS`` bits.

    Answers are memoized per instance (one per application)."""
    __slots__ = ("sp", "pieces", "bounds", "covered", "vshape", "_img", "_pre", "_rng")

    def __init__(self, sp: Spec):
        self.sp = sp
        self.pieces = tuple((p.lo, p.hi, p.dir) for p in sp.pieces)
        b = sp.bounds
        if b is not None:
            lo = None if b[0] is None else _field(b[0])
            hi = None if b[2] is None else _field(b[2])
            b = (lo, b[1], hi, b[3])
        self.bounds = b
        self.covered = sp.covered and len(sp.pieces) == 1
        #: decreasing on ``[-oo, 0]``, increasing on ``[0, oo]`` (``cosh``,
        #: even powers): on ``[a, b]`` around 0, ``f <= max(f(a), f(b))``
        self.vshape = set(self.pieces) == {("0", "oo", 1), ("-oo", "0", -1)}
        lo, hi, nz = sp.inv_range
        self._rng = (None if lo is None else _field(lo),
                     None if hi is None else _field(hi), nz)
        self._img: dict = {}
        self._pre: dict = {}

    def image(self, c):
        if _big(c):
            return None
        try:
            return self._img[c]
        except KeyError:
            pass
        if len(self._img) > 512:
            self._img.clear()
        try:
            r = _field(self.sp.apply(_sympy_of(c)))
        except Exception:                 # SymPy failing on a value: no image
            r = None
        self._img[c] = r
        return r

    def preimage(self, d, i: int):
        if _big(d):
            return None
        key = (d, i)
        try:
            return self._pre[key]
        except KeyError:
            pass
        if len(self._pre) > 512:
            self._pre.clear()
        r = None
        try:
            r = self._preimage(d, i)
        except Exception:
            r = None
        self._pre[key] = r
        return r

    def _preimage(self, d, i: int):
        lo, hi, nz = self._rng
        sp = self.sp
        if (lo is not None and _fsign(d - lo) != 1
                or hi is not None and _fsign(hi - d) != 1
                or nz and _fsign(d) != 1 and _fsign(d) != -1):
            return None
        piece = sp.pieces[i]
        ds = _sympy_of(d)
        for c in sp.inverse(ds):
            if c.is_finite is False:
                continue                  # 1/u = 0 at u = +-oo: no finite c
            v = _field(c)
            if v is None:
                continue
            sg = _fsign(v)
            if sg is None or not piece.holds(sg):
                continue
            if not sp.exact and sp.apply(c) != ds:
                continue                  # not a preimage SymPy shows
            return v
        return None


_LINKMAPS = _PROCESS.table(f"{__name__}._LINKMAPS", "pure", 100_000)


def link_map(term) -> Optional[LinkMap]:
    """The :class:`LinkMap` of an application with pieces, or None
    (memoized per term)."""
    try:
        return _LINKMAPS[term]
    except KeyError:
        pass
    except TypeError:
        return None
    sp = spec(term)
    r = LinkMap(sp) if sp is not None and sp.pieces else None
    if len(_LINKMAPS) >= _LINKMAPS.size:
        _LINKMAPS.clear()
    _LINKMAPS[term] = r
    return r
