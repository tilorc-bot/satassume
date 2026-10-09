"""Rigorous rational bounds of closed real constants (``pi``, ``log(2)``,
``sqrt(2)*exp(3)``, ...) by interval evaluation (mpmath's interval
context), for :mod:`satassume.theories.lra.lra_adapter`: a constant that is no element
of :mod:`satassume.theories.lra.constfield` becomes an LRA term between its bounds
(``LRAAdapter.register_bounds``), and constfield encloses such a
constant at any precision (:func:`constant_enclosure`).  A module of its
own because only a query with such a constant needs it.
"""
from __future__ import annotations

from fractions import Fraction

from sympy import S
from sympy.core.add import Add
from sympy.core.mul import Mul

from ...state.memos import adopt as _adopt_memo

__all__ = ["constant_bounds", "constant_enclosure"]

#: bound of each memo below (as ``lra_adapter._INTERPRETED_MAX``)
_INTERPRETED_MAX = 100_000

#: working precision (bits) of the interval evaluation behind a constant's bounds
_IV_PREC = 128
#: constants of magnitude beyond ``2**±_MAX_BITS`` get no bounds: the
#: exact rationals would be integers of that many bits
#: (``exp(exp(exp(5)))`` is about ``2**(4e64)``)
_MAX_BITS = 4096
#: constant -> (lo, hi) or None (see constant_bounds); shared, pure
_BOUNDS: dict = {}
_adopt_memo(__name__, "_BOUNDS")


def constant_bounds(c):
    """Rational bounds ``(lo, hi)`` with ``lo < c < hi`` for a closed
    expression ``c`` that SymPy says is a finite (extended) real number, or
    None: not such a constant, or no rigorous bound.

    The value comes from interval arithmetic (:func:`_interval`: mpmath's
    interval context at 128 bits, outward rounded at every step, over
    rationals, pi, E, ``+``, ``*``, ``**``, exp, log, sin, cos, tan, atan);
    the interval is widened outward to rationals on a grid 72 bits below
    its magnitude.  A constant that SymPy cannot show to be zero still gets
    a narrow interval around 0.  Memoized per constant."""
    try:
        return _BOUNDS[c]
    except KeyError:
        pass
    except TypeError:
        return _bounds(c)
    if len(_BOUNDS) >= _INTERPRETED_MAX:
        _BOUNDS.clear()
    r = _BOUNDS[c] = _bounds(c)
    return r


def _bounds(c):
    iv = _interval(c)
    if iv is None:
        return None
    a, b = iv._mpi_
    lo, hi = _rational(a), _rational(b)
    top = max(_mag(a), _mag(b), -_MAX_BITS)
    q = Fraction(2) ** (top - 72)            # a coarse grid, strictly outside
    return ((lo / q).__floor__() - 1) * q, ((hi / q).__ceil__() + 1) * q


#: precision -> mpmath interval context at that precision
_IV: dict = {}
_adopt_memo(__name__, "_IV")


def _iv_context(prec: int = _IV_PREC):
    ctx = _IV.get(prec)
    if ctx is None:
        from mpmath.ctx_iv import MPIntervalContext
        ctx = _IV[prec] = MPIntervalContext()
        ctx.prec = prec
    return ctx


#: (constant, working precision) -> rational enclosure or None
_ENCLOSURES: dict = {}
_adopt_memo(__name__, "_ENCLOSURES")


def constant_enclosure(c, prec: int):
    """Rational ``(lo, hi)`` with ``lo <= c <= hi`` and ``hi - lo`` about
    ``2**-prec`` relative, for a closed constant with
    :func:`constant_bounds` (None otherwise): the interval evaluation of
    :func:`_interval` at working precision ``prec + 16`` bits, rounded
    outward.  Used to refine a constant of :mod:`satassume.theories.lra.constfield`
    beyond the 128 bits of its bounds."""
    key = (c, prec)
    try:
        return _ENCLOSURES[key]
    except KeyError:
        pass
    except TypeError:
        return _enclosure(c, prec)
    if len(_ENCLOSURES) >= _INTERPRETED_MAX:
        _ENCLOSURES.clear()
    r = _ENCLOSURES[key] = _enclosure(c, prec)
    return r


def _enclosure(c, prec: int):
    if constant_bounds(c) is None:           # also: SymPy says a finite real
        return None
    iv = _interval(c, max(prec + 16, _IV_PREC))
    if iv is None:
        return None
    a, b = iv._mpi_
    return _rational(a), _rational(b)


def _rational(x) -> Fraction:
    """The exact value of a finite raw mpf (bounded by the caller)."""
    from mpmath.libmp import to_rational
    p, q = to_rational(x)
    return Fraction(p, q)


def _mag(x) -> float:
    """``k`` with ``|x| < 2**k`` for a raw mpf; -inf for zero, inf for an
    infinity or nan."""
    sign, man, exp, bc = x
    if man:
        return exp + bc
    return float("-inf") if not exp else float("inf")


def _sign(x) -> int:
    from mpmath.libmp import mpf_sign
    return mpf_sign(x)


def _interval(e, prec: int = _IV_PREC):
    """An interval (mpmath, outward rounded at every step) that holds the
    real value of the closed expression ``e``, or None.

    Only rationals, pi, E, ``+``, ``*``, ``**``, exp, log, sin, cos, tan and
    atan are evaluated; a step outside its real domain (log of an interval
    that reaches 0, a fractional power of one that reaches below 0, tan
    across a pole, 1/x across 0) gives None, so a result is also a proof
    that the value is real.  Every intermediate value must stay within
    ``2**±_MAX_BITS`` (exp is checked before it is applied), so nothing huge
    is built: ``exp(exp(exp(5)))`` and ``sin(exp(exp(exp(5))))`` are None
    at once.  No error estimate of SymPy's evalf is trusted (it claims full
    accuracy for ``sign``, ``tanh``, ``tan`` next to a pole, ``log`` next to
    1)."""
    iv = _iv_context(prec)
    from sympy import Pow, exp, log, sin, cos, tan, atan
    if e.is_Rational:
        if e.p and abs(e.p.bit_length() - e.q.bit_length()) > _MAX_BITS:
            return None
        return iv.mpf(e.p) / iv.mpf(e.q)
    if e is S.Pi:
        return iv.pi + 0
    if e is S.Exp1:
        return iv.e + 0
    head = type(e)
    if head not in (Add, Mul, Pow, exp, log, sin, cos, tan, atan):
        return None
    args = []
    for a in e.args:
        x = _interval(a, prec)
        if x is None:
            return None
        args.append(x)
    try:
        if head is Add:
            r = args[0]
            for x in args[1:]:
                r = r + x
        elif head is Mul:
            r = args[0]
            for x in args[1:]:
                r = r * x
        elif head is Pow:
            b, x = args
            n = e.args[1]
            ba, bb = b._mpi_
            if n.is_Integer:
                if n < 0 and _sign(ba) <= 0 <= _sign(bb):
                    return None
                if abs(int(n)).bit_length() > prec:
                    return None              # not exact at this precision: mpmath goes through log/exp
                r = b ** int(n)
            else:
                if _sign(ba) <= 0:
                    return None
                r = _iv_exp(x * _loose(iv.log(b), prec), prec)
        elif head is exp:
            r = _iv_exp(args[0], prec)
        elif head is log:
            if _sign(args[0]._mpi_[0]) <= 0:
                return None
            r = _loose(iv.log(args[0]), prec)
        elif head is atan:
            from mpmath.libmp import mpf_atan
            x = args[0]
            import mpmath
            mk = mpmath.mp.make_mpf       # atan is increasing: round the ends outward
            xa, xb = args[0]._mpi_
            r = _loose(iv.mpf([mk(mpf_atan(xa, prec, "f")), mk(mpf_atan(xb, prec, "c"))]), prec)
        else:
            r = _loose({sin: iv.sin, cos: iv.cos, tan: iv.tan}[head](args[0]), prec)
    except Exception:                        # noqa: BLE001 - a step mpmath refuses decides nothing
        return None
    if r is None or type(r) is not type(args[0]):
        return None                          # complex
    a, b = r._mpi_
    if max(_mag(a), _mag(b)) > _MAX_BITS:
        return None                          # huge, infinite or nan
    if (a[1] and _mag(a) < -_MAX_BITS) or (b[1] and _mag(b) < -_MAX_BITS):
        # a tiny end moves outward to 0 or 2**-_MAX_BITS: its exact rational
        # would be huge (``pi**-(10**9)``, ``tan(22)**(10**100)``)
        from mpmath.libmp import fzero
        if a[1] and _mag(a) < -_MAX_BITS:
            a = (1, 1, -_MAX_BITS, 1) if a[0] else fzero
        if b[1] and _mag(b) < -_MAX_BITS:
            b = fzero if b[0] else (0, 1, -_MAX_BITS, 1)
        r = iv.make_mpf((a, b))
    return r


def _loose(r, prec: int = _IV_PREC):
    """``r`` widened outward by ``2**(8 - prec)`` relative at each end
    (``2**-120`` at the 128 bits of :func:`constant_bounds`).  mpmath's
    exp, log, atan, sin, cos and tan round an approximation (a few units in
    the last place at 10 to 30 guard bits) in the requested direction,
    which is wrong when the true value is that close to a 128-bit number:
    ``exp(891)`` and ``log(156434)`` come out with an upper end below the
    value, and a cancelling parent (``pi*(log(156434) - Y)``) exposes it."""
    from mpmath.libmp import mpf_abs, mpf_add, mpf_shift, mpf_sub
    a, b = r._mpi_
    a = mpf_sub(a, mpf_shift(mpf_abs(a), 8 - prec), prec, "f")
    b = mpf_add(b, mpf_shift(mpf_abs(b), 8 - prec), prec, "c")
    return _iv_context(prec).make_mpf((a, b))


def _iv_exp(x, prec: int = _IV_PREC):
    # exp of anything beyond about 2839 in size would be beyond 2**±4096;
    # the check allows |x| < 2048
    if x is None or max(_mag(x._mpi_[0]), _mag(x._mpi_[1])) > 11:
        return None                          # |x| >= 2048
    return _loose(_iv_context(prec).exp(x), prec)
