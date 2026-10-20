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
from functools import lru_cache

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
    the constants and functions listed there);
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


#: NumberSymbol -> attribute of mpmath's interval context
_CONSTANTS = {S.GoldenRatio: "phi", S.EulerGamma: "euler", S.Catalan: "catalan"}


@lru_cache(maxsize=None)
def _heads():
    from sympy import Pow, exp, log, sin, cos, tan, atan, asin, acos, gamma, zeta, Abs
    return frozenset((Add, Mul, Pow, exp, log, sin, cos, tan, atan, asin, acos, gamma, zeta, Abs))


def _interval(e, prec: int = _IV_PREC):
    """An interval (mpmath, outward rounded at every step) that holds the
    real value of the closed expression ``e``, or None.

    Only rationals, Floats, pi, E, GoldenRatio, EulerGamma, Catalan, ``+``,
    ``*``, ``**``, exp, log, sin, cos, tan, atan, asin, acos, gamma (of a
    positive argument), zeta (of an argument above 1) and Abs are evaluated;
    a step outside its real domain (log of an interval that reaches 0, a
    fractional power of one that reaches below 0, tan across a pole, 1/x
    across 0, asin beyond [-1, 1], zeta at or below 1) gives None, so a
    result is also a proof that the value is real.  Every intermediate value must stay within
    ``2**±_MAX_BITS`` (exp is checked before it is applied), so nothing huge
    is built: ``exp(exp(exp(5)))`` and ``sin(exp(exp(exp(5))))`` are None
    at once.  No error estimate of SymPy's evalf is trusted (it claims full
    accuracy for ``sign``, ``tanh``, ``tan`` next to a pole, ``log`` next to
    1)."""
    iv = _iv_context(prec)
    from sympy import Pow, exp, log, sin, cos, tan, atan, asin, acos, gamma, zeta, Abs
    if e.is_Rational:
        if e.p and abs(e.p.bit_length() - e.q.bit_length()) > _MAX_BITS:
            return None
        return iv.mpf(e.p) / iv.mpf(e.q)
    if e is S.Pi:
        return iv.pi + 0
    if e is S.Exp1:
        return iv.e + 0
    if e.is_Float:
        m = e._mpf_                          # exact; later steps round outward
        if m == (0, 0, 0, 0):
            return iv.mpf(0)
        if abs(_mag(m)) > _MAX_BITS:
            return None                      # also inf and nan
        return iv.make_mpf((m, m))
    const = _CONSTANTS.get(e)
    if const is not None:
        return _loose(getattr(iv, const) + 0, prec)
    head = type(e)
    if head not in _heads():
        return None
    if head in (log, zeta) and len(e.args) != 1:
        return None                          # log(x, b, evaluate=False) is log(x)/log(b); Hurwitz zeta
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
            r = _iv_atan(args[0], prec)
        elif head in (asin, acos):
            r = _iv_asin(args[0], prec)
            if r is not None and head is acos:
                r = (iv.pi + 0) / 2 - r
        elif head is gamma:
            if _sign(args[0]._mpi_[0]) <= 0:
                return None                  # the poles and the sign changes
            r = _loose(iv.gamma(args[0]), prec)
        elif head is zeta:
            r = _iv_zeta(args[0], prec)
        elif head is Abs:
            a, b = args[0]._mpi_
            if _sign(a) >= 0:
                r = args[0]
            elif _sign(b) <= 0:
                r = -args[0]
            else:
                from mpmath.libmp import fzero, mpf_cmp, mpf_neg
                r = iv.make_mpf((fzero, b if mpf_cmp(mpf_neg(a), b) < 0 else mpf_neg(a)))
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


def _iv_atan(x, prec: int = _IV_PREC):
    """atan of an interval, the ends rounded outward (atan is increasing)."""
    import mpmath
    from mpmath.libmp import mpf_atan
    mk = mpmath.mp.make_mpf
    xa, xb = x._mpi_
    return _loose(_iv_context(prec).mpf([mk(mpf_atan(xa, prec, "f")), mk(mpf_atan(xb, prec, "c"))]), prec)


#: terms summed exactly by :func:`_iv_zeta` before the tail bounds
_ZETA_TERMS = 64


def _iv_zeta(s, prec: int = _IV_PREC):
    """zeta of an interval above 1, else None.  mpmath's interval zeta is
    not used: it is not rigorous.

    zeta is decreasing on ``(1, oo)``, so the ends come from the ends of
    ``s``.  At a point ``s > 1``, ``zeta(s) = sum_{k<N} k**-s + T`` with the
    tail ``T = sum_{k>=N} f(k)``, ``f(x) = x**-s`` positive, decreasing and
    convex: the trapezoid rule overestimates each ``int_k^(k+1) f`` and the
    midpoint rule underestimates each ``int_(k-1/2)^(k+1/2) f``, so
    ``N**(1-s)/(s-1) + N**-s/2 <= T <= (N-1/2)**(1-s)/(s-1)``.  The width,
    about ``s*N**(-s-1)/8``, does not shrink with ``prec`` (a wider
    enclosure is allowed; #198)."""
    iv = _iv_context(prec)
    if _sign((s - 1)._mpi_[0]) <= 0:
        return None
    N = _ZETA_TERMS
    h = iv.mpf(2 * N - 1) / 2

    def at(x):                               # zeta at the exact point x: its (lower, upper) ends
        p = iv.make_mpf((x, x))
        man, shift = x[1], x[2]
        if shift >= 0 and shift + man.bit_length() <= 16:
            n = man << shift                  # an integer power is exact up to outward rounding
            if n * N.bit_length() > _MAX_BITS:
                return None                  # N**-n is below 2**-_MAX_BITS

            def pw(k):
                return iv.mpf(k) ** -n
        else:
            def pw(k):
                return _iv_exp(-p * _loose(iv.log(k), prec), prec)
        total = iv.mpf(0)
        for k in range(1, N):
            t = pw(iv.mpf(k))
            if t is None:
                return None
            total = total + t
        fN, fh = pw(iv.mpf(N)), pw(h)
        if fN is None or fh is None:
            return None
        return (total + fN * N / (p - 1) + fN / 2)._mpi_[0], (total + fh * h / (p - 1))._mpi_[1]

    sa, sb = s._mpi_
    top, bottom = at(sa), at(sb)
    if top is None or bottom is None:
        return None
    return iv.make_mpf((bottom[0], top[1]))


def _iv_asin(x, prec: int = _IV_PREC):
    """asin of an interval within [-1, 1] as ``2*atan(x/(1 + sqrt(1 - x**2)))``
    (mpmath's interval context has no asin), else None."""
    from mpmath.libmp import fone, fzero, mpf_abs, mpf_cmp
    iv = _iv_context(prec)
    xa, xb = x._mpi_
    if mpf_cmp(mpf_abs(xa), fone) > 0 or mpf_cmp(mpf_abs(xb), fone) > 0:
        return None
    one = iv.mpf(1)
    w = one - x * x
    wa, wb = w._mpi_
    if _sign(wa) < 0:                        # outward rounding below 0 near |x| = 1
        w = iv.make_mpf((fzero, wb))
    return 2 * _iv_atan(x / (one + iv.sqrt(w)), prec)


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
