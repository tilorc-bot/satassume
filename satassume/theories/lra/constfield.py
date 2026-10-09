"""Exact numbers in ``Q(c1, ..., ck)``: rationals extended by real constants.

The LRA simplex (:mod:`satassume.theories.lra.lra`) needs a field with exact ``+ - * /``
and an exact sign test.  :class:`fractions.Fraction` is that field for
rational coefficients; this module extends it to coefficients such as
``pi``, ``1/pi``, ``3*pi/2 + E`` and ``sqrt(2)``, so that ``x/pi + 1/2``
is a linear form whose endpoint ties (``x = -pi/2`` makes it exactly 0)
are decided exactly rather than by interval arithmetic.  Nothing here
imports SymPy except :func:`from_sympy` and :meth:`Element.to_sympy`
(lazily), and ``sympy.polys`` for gcds beyond the small univariate
case (see Limits).

Following de Moura and Passmore, "Computation in Real Closed Infinitesimal
and Transcendental Extensions of the Rationals" (CADE 2013; z3's ``rcf``
module), a constant is an *indeterminate* ``t`` (:class:`Constant`) with a
procedure that encloses its real value in rational intervals of any
requested width, and a number is a formal rational function ``p/q`` of the
indeterminates with rational coefficients (:class:`Element`).

Representation
--------------
A polynomial is a :class:`~fractions.Fraction` or a tuple ``(v, cs)``:
``v`` the index of its main indeterminate and ``cs`` its coefficients
(lowest degree first, at least two, the last nonzero), each a polynomial
in indeterminates of smaller index (the recursive dense representation).
An :class:`Element` is ``n/d`` with ``gcd(n, d) = 1`` and the recursive
leading coefficient of ``d`` equal to 1.  That is a normal form: formally
equal numbers have equal representations, so ``==`` on the formal level
and ``hash`` are structural (``pi/pi`` is 1, ``(-pi/2)/pi + 1/2`` is 0).
The gcd (see Limits) is exact for any number of indeterminates.
The alternative the research suggested for several constants (no
multivariate gcd, only monomial and content factors removed) was not
taken: without a normal form ``hash`` would have to be invented
(evaluation at a random point can collide with a zero of a denominator)
and expressions grow along pivots; the inputs are tiny, so the gcd costs
little.

**Fast path.** A constant-free result is a plain ``Fraction``, never an
``Element`` (``pi/pi`` is ``Fraction(1)``); ``Fraction`` and ``int`` mix
with ``Element`` in every operation and comparison (``Fraction`` defers
to the reflected methods).  Code that only ever sees rationals pays
nothing.

Meaning and soundness
---------------------
Every number denotes a real: its value is ``n(c)/d(c)`` for the real
values ``c`` of the constants.  Invariant: the denominator of every
:class:`Element` has a nonzero value.  It holds because a denominator is a
product of denominators and of numerators that were shown to be nonzero
(division checks its divisor, see below) divided by common factors, so
the value map is a ring homomorphism on the numbers built and ``+ - * /``
are exact on values.

Formal equality implies equality of values, but not conversely: a
constant can satisfy a polynomial (``t**2 - 2`` for ``t = sqrt(2)``, and
nobody knows whether some ``p(pi, E)`` vanishes).  So every question about
values is answered semantically:

* ``sign(x)`` (behind ``< <= > >=``, ``bool``, ``==`` and division by
  ``x``) evaluates ``n`` and ``d`` in interval arithmetic
  (:func:`_ieval`: fixed point at ``2**-prec``, outward rounded, exact
  integers) on enclosures of the constants at ``prec = 64, 128, 256, ...``
  until both intervals exclude 0.  An interval that excludes 0 is a
  proof of the sign.  At the precision cap (:data:`PREC_CAP`, or earlier
  when the constants involved cannot be enclosed more tightly) it raises
  :class:`Undecided`: never a wrong sign.
* ``a == b`` is True if the two are formally equal and False if the
  difference has a proven nonzero value; otherwise :class:`Undecided`.
  A difference that is formally nonzero and involves a single
  *transcendental* constant (``pi``: Lindemann; ``E``: Hermite) is
  nonzero without evaluation: a nonzero rational polynomial has no
  transcendental root.  Consequently ``a == b`` is True only for formally
  equal numbers and ``hash`` agrees with ``==``; an ``Element`` never
  equals a ``Fraction``.  But ``==`` can raise: a dict or set lookup of
  an Element whose hash collides with another key's (rare, as hashes are
  structural) compares them and so can raise :class:`Undecided` when
  both involve several or algebraic constants.  ``==`` with a SymPy
  number converts it (:func:`from_sympy`); with a float, or a SymPy
  number that is not read (``Float``, ``I``), it raises TypeError instead
  of being silently False; a non-number (``None``, a bool, a string,
  ``Symbol('y')``) is never equal.
* ``floor(x)`` refines until the enclosure has one floor.  A formally
  non-rational number in a single transcendental constant is irrational,
  so it terminates (up to the cap).
* Division checks its divisor, also ``x / x`` (which is 1 only if ``x``
  is nonzero): ``z / z`` raises :class:`Undecided` exactly when ``1 / z``
  does.

The precision is *absolute* (bits after the binary point, whatever the
magnitude): a value closer to 0 than about ``2**-PREC_CAP`` is
:class:`Undecided` although nonzero (``((pi - 355/113)**400).sign()``,
about ``1e-2630``), and so is the floor of a number whose integer part
takes most of the bits (``floor(pi * 10**1300)``: the interval
evaluation then errs by more than 1).

For one transcendental constant every sign is decided (the cap only
bounds the work).  Several constants (``pi`` and ``E``, whose algebraic
independence is open) and algebraic constants (plain indeterminates here,
``sqrt(2)`` is ``t`` with no relation ``t**2 = 2``) are decided whenever
the value is nonzero and not too close to 0, and are :class:`Undecided`
when a formally nonzero expression is really zero (``t**2 - 2``).  The
caller must treat :class:`Undecided` as "no answer" (abort the query),
never as a default branch.  (z3's ``rcf`` would instead assume ``E``
transcendental over ``Q(pi)``; here no such assumption is made, the
numbers decide or nothing does.)  :func:`formally_zero` is the one test
that never raises: enough to keep rows sparse, since a formally nonzero
coefficient with value 0 is still exact.

Constants
---------
``pi`` and ``E`` are built in (:data:`PI`, :data:`E`) with enclosures at
any precision computed with integer arithmetic (Machin's formula; the
series of ``1/k!``), with explicit error bounds, so mpmath's rounding is
not trusted.  :func:`from_sympy` reads Rationals, ``pi``, ``E``,
``exp(n)`` (``E**n``), sums, products, integer powers, rational powers of
positive rationals (``sqrt(2)``, ``3**(2/3)``: a power of the
indeterminate ``r**(1/b)``, enclosed at any precision by integer roots)
and, as a last resort, any closed real constant that
:func:`satassume.theories.lra.lra_bounds.constant_bounds` bounds (``log(2)``,
``sin(1)``, ``pi**pi``): an indeterminate with those 128-bit bounds only,
so comparisons closer than about ``2**-70`` relative are
:class:`Undecided`.  Distinct spellings of one value (``log(8)`` and
``3*log(2)``) are unrelated indeterminates: a comparison that depends on
the relation is :class:`Undecided`, never wrong.

Limits
------
* A size budget (:data:`MAX_DEGREE` total degree, :data:`MAX_TERMS`
  terms, :data:`MAX_BITS` coefficient bits, :data:`MAX_WORK` term
  products per multiplication) bounds the cost of every operation: one
  that would exceed it raises :class:`TooLarge`, an :class:`Undecided`.
  Pivots on rows with several constants can blow expressions up (random
  8x8 eliminations over pi, E and sqrt(2) do); the query then gets no
  answer rather than a slow one.  :func:`from_sympy` gives None for such
  inputs (``((pi + 1)**64 + 1)**64``).
* The gcd of a normal form is Euclid (monic remainders) for univariate
  polynomials of degree at most 8, a monomial shortcut (``1/pi``), and
  otherwise SymPy's ``dmp_inner_gcd`` over ZZ (heuristic gcd with a PRS
  fallback), imported lazily: this module needs ``sympy.polys`` for
  anything beyond one small constant.
* The registry of constants is global and grows (one entry per distinct
  constant ever converted); the variable order is the registration order.
* A few hundred bits of cancellation are decided quickly; the cap
  (:data:`PREC_CAP` bits of absolute precision) bounds the work of an
  undecidable comparison to a handful of evaluations.
* No algebraic numbers as such (no minimal polynomials, no root
  isolation): ``sqrt(2)*sqrt(2) - 2`` is :class:`Undecided`.  SymPy
  already simplifies such inputs; they can only arise inside the simplex.
"""
from __future__ import annotations

from collections.abc import Callable, Hashable
from fractions import Fraction
from math import gcd as _igcd

__all__ = ["Element", "Constant", "Undecided", "TooLarge", "PI", "E", "constant",
           "radical", "from_sympy", "sign", "num", "formally_zero",
           "PREC_START", "PREC_CAP", "MAX_DEGREE", "MAX_TERMS", "MAX_BITS", "MAX_WORK"]

#: first precision (bits after the binary point) of a sign test
PREC_START = 64
#: last precision tried before :class:`Undecided`
PREC_CAP = 4096
#: size budget of an :class:`Element` (numerator and denominator each):
#: total degree, number of terms, bits of a coefficient's numerator or
#: denominator; and the work of one product (terms times terms).  An
#: operation that would exceed it raises :class:`TooLarge` (an
#: Undecided) instead of running for seconds: pivots that blow up
#: expressions make the query undecided rather than slow.
MAX_DEGREE = 64
MAX_TERMS = 512
MAX_BITS = 8192
MAX_WORK = 1 << 14

_ZERO = Fraction(0)
_ONE = Fraction(1)


class Undecided(Exception):
    """A sign, comparison or floor that the enclosures could not decide
    up to the precision cap.  The value may be exactly 0 (or an integer,
    for a floor) without the formal expression being so.  Deliberately no
    ArithmeticError, so that a handler for division by zero does not
    swallow it."""


class TooLarge(Undecided):
    """An operation would exceed the size budget (:data:`MAX_DEGREE`,
    :data:`MAX_TERMS`, :data:`MAX_BITS`, :data:`MAX_WORK`)."""


# ----------------------------------------------------------------------
# polynomials: Fraction, or (v, (c0, c1, ..., cn)) with n >= 1, cn != 0
# and every ci a polynomial in indeterminates < v
# ----------------------------------------------------------------------

def _zero(p) -> bool:
    return type(p) is Fraction and not p


def _mk(v: int, cs) -> object:
    n = len(cs)
    while n and _zero(cs[n - 1]):
        n -= 1
    if n == 0:
        return _ZERO
    if n == 1:
        return cs[0]
    return (v, tuple(cs[:n]))


def _add(a, b):
    ta, tb = type(a) is Fraction, type(b) is Fraction
    if ta and tb:
        return a + b
    if ta:
        a, b = b, a
    elif not tb:
        va, vb = a[0], b[0]
        if va == vb:
            ca, cb = a[1], b[1]
            if len(ca) < len(cb):
                ca, cb = cb, ca
            cs = [_add(x, y) for x, y in zip(ca, cb)]
            cs.extend(ca[len(cb):])
            return _mk(va, cs)
        if va < vb:
            a, b = b, a
    # a has the larger main variable: b goes to its constant coefficient
    if _zero(b):
        return a
    cs = a[1]
    return (a[0], (_add(cs[0], b),) + cs[1:])


def _neg(p):
    if type(p) is Fraction:
        return -p
    return (p[0], tuple(_neg(c) for c in p[1]))


def _sub(a, b):
    return _add(a, _neg(b))


def _scale(p, c: Fraction):
    """``c * p`` for a nonzero Fraction ``c``."""
    if type(p) is Fraction:
        return p * c
    return (p[0], tuple(_scale(x, c) for x in p[1]))


def _mul(a, b):
    ta, tb = type(a) is Fraction, type(b) is Fraction
    if ta:
        if tb:
            return a * b
        return _ZERO if not a else (b if a == 1 else _scale(b, a))
    if tb:
        return _ZERO if not b else (a if b == 1 else _scale(a, b))
    va, vb = a[0], b[0]
    if va == vb:
        ca, cb = a[1], b[1]
        out = [_ZERO] * (len(ca) + len(cb) - 1)
        for i, x in enumerate(ca):
            if _zero(x):
                continue
            for j, y in enumerate(cb):
                if not _zero(y):
                    out[i + j] = _add(out[i + j], _mul(x, y))
        return (va, tuple(out))             # the leading product is nonzero
    if va < vb:
        a, b = b, a
    return (a[0], tuple(_mul(x, b) for x in a[1]))


def _pow(p, k: int):
    r = _ONE
    while k:
        if k & 1:
            r = _mul(r, p)
        k >>= 1
        if k:
            p = _mul(p, p)
    return r


def _too_many_bits(q: Fraction) -> bool:
    return q.denominator.bit_length() > MAX_BITS or q.numerator.bit_length() > MAX_BITS


def _add_bounded(a, b):
    """:func:`_add`, or TooLarge as soon as a coefficient of the sum has
    more than :data:`MAX_BITS` bits."""
    ta, tb = type(a) is Fraction, type(b) is Fraction
    if ta and tb:
        r = a + b
        if _too_many_bits(r):
            raise TooLarge(f"a coefficient exceeds {MAX_BITS} bits")
        return r
    if ta:
        a, b = b, a
    elif not tb:
        va, vb = a[0], b[0]
        if va == vb:
            ca, cb = a[1], b[1]
            if len(ca) < len(cb):
                ca, cb = cb, ca
            cs = [_add_bounded(x, y) for x, y in zip(ca, cb)]
            cs.extend(ca[len(cb):])
            return _mk(va, cs)
        if va < vb:
            a, b = b, a
    if _zero(b):
        return a
    cs = a[1]
    return (a[0], (_add_bounded(cs[0], b),) + cs[1:])


def _mul_bounded(a, b):
    """:func:`_mul`, or TooLarge as soon as a partial sum of a coefficient
    has more than :data:`MAX_BITS` bits.  For factors whose coefficient
    products fit the budget (see :func:`_mul_fast`): a coefficient sums
    products with different denominators, and its common denominator can
    grow with the number of summands; checked while it grows, the work
    stays bounded (at most :data:`MAX_WORK` operations on numbers of at
    most twice :data:`MAX_BITS` bits) instead of running for seconds on
    ever larger numbers and refusing the result afterwards."""
    ta, tb = type(a) is Fraction, type(b) is Fraction
    if ta or tb:
        return _mul(a, b)
    va, vb = a[0], b[0]
    if va == vb:
        ca, cb = a[1], b[1]
        out = [_ZERO] * (len(ca) + len(cb) - 1)
        for i, x in enumerate(ca):
            if _zero(x):
                continue
            for j, y in enumerate(cb):
                if not _zero(y):
                    out[i + j] = _add_bounded(out[i + j], _mul_bounded(x, y))
        return (va, tuple(out))
    if va < vb:
        a, b = b, a
    return (a[0], tuple(_mul_bounded(x, b) for x in a[1]))


def _mul_fast(sa, sb) -> bool:
    """Whether no coefficient of a product of polynomials of sizes ``sa``
    and ``sb`` (:func:`_psize`, or bounds of them) can exceed
    :data:`MAX_BITS` bits: a coefficient sums at most ``min(terms)``
    products of at most ``bits(a) + bits(b)`` bits each, and a sum of
    ``k`` fractions of ``B`` bits has at most ``k*B`` bits in the
    denominator and ``k*B + log2(k)`` in the numerator."""
    return min(sa[1], sb[1]) * (sa[2] + sb[2] + 1) <= MAX_BITS


def _mul_checked(a, b):
    """``a * b``, or TooLarge before the work of the product (terms times
    terms), while a coefficient grows too large, or after its size
    exceeds the budget."""
    if type(a) is Fraction or type(b) is Fraction:
        return _mul(a, b)
    sa, sb = _psize(a), _psize(b)
    if sa[0] + sb[0] > MAX_DEGREE or sa[2] + sb[2] > MAX_BITS or sa[1] * sb[1] > MAX_WORK:
        raise TooLarge("a product exceeds the size budget")
    r = _mul(a, b) if _mul_fast(sa, sb) else _mul_bounded(a, b)
    if _psize(r)[1] > MAX_TERMS:
        raise TooLarge("a product has more terms than the size budget")
    return r


def _pow_checked(p, k: int):
    """``p**k`` by squaring, each product checked (:func:`_mul_checked`):
    ``(pi + E + ... + 1)**64`` is refused at the first squaring that grows
    too large, not after minutes."""
    r = _ONE
    while k:
        if k & 1:
            r = _mul_checked(r, p)
        k >>= 1
        if k:
            p = _mul_checked(p, p)
    return r


def _deg(p, v: int) -> int:
    return len(p[1]) - 1 if type(p) is tuple and p[0] == v else 0


def _lc(p, v: int):
    return p[1][-1] if type(p) is tuple and p[0] == v else p


def _lcrec(p) -> Fraction:
    """The rational leading coefficient (recursively, in every variable)."""
    while type(p) is tuple:
        p = p[1][-1]
    return p


def _shift(p, v: int, k: int):
    """``t_v**k * p`` for ``p`` free of ``t_v``."""
    if k == 0:
        return p
    return (v, (_ZERO,) * k + (p,))


def _divexact(a, b):
    """``a / b`` for polynomials where ``b != 0`` divides ``a`` exactly."""
    if _zero(a):
        return _ZERO
    if type(b) is Fraction:
        return a if b == 1 else _scale(a, 1 / b)
    vb = b[0]
    if type(a) is Fraction or a[0] < vb:
        raise ArithmeticError("inexact polynomial division")
    va = a[0]
    if va > vb:
        return (va, tuple(_divexact(c, b) for c in a[1]))
    if a == b:
        return _ONE
    ca, cb = a[1], b[1]
    j = _monomial(b)
    if j:                                    # b = c * t**j: shift down
        if any(not _zero(c) for c in ca[:j]):
            raise ArithmeticError("inexact polynomial division")
        l = cb[-1]
        return _mk(va, ca[j:] if l == 1 else [_scale(c, 1 / l) for c in ca[j:]])
    if all(type(c) is Fraction for c in ca) and all(type(c) is Fraction for c in cb):
        return _mk(va, _udiv(ca, cb))        # univariate: long division over Q
    db, lb = len(b[1]) - 1, b[1][-1]
    q = [_ZERO] * (len(a[1]) - db)
    r = a
    while not _zero(r):
        dr = _deg(r, va)
        if dr < db:
            raise ArithmeticError("inexact polynomial division")
        t = _divexact(_lc(r, va), lb)
        q[dr - db] = t
        r = _sub(r, _mul(_shift(t, va, dr - db), b))
    return _mk(va, q)


def _monomial(p) -> int:
    """``k`` if ``p = c * t**k`` (``k >= 1``, ``c`` rational), else 0."""
    cs = p[1]
    if type(cs[-1]) is not Fraction:
        return 0
    for c in cs[:-1]:
        if not _zero(c):
            return 0
    return len(cs) - 1


def _order(p) -> int:
    """The largest ``j`` with ``t**j`` dividing ``p`` (main variable ``t``)."""
    for j, c in enumerate(p[1]):
        if not _zero(c):
            return j
    raise AssertionError("zero coefficient list")


def _udiv(a, b) -> list:
    """Exact quotient of univariate polynomials over Q (coefficient
    sequences, lowest degree first)."""
    r = list(a)
    db, lb = len(b) - 1, b[-1]
    if len(r) <= db:
        raise ArithmeticError("inexact polynomial division")
    q = [_ZERO] * (len(r) - db)
    for k in range(len(r) - 1 - db, -1, -1):
        f = r[k + db] / lb
        q[k] = f
        if f:
            for i in range(db):
                r[k + i] -= f * b[i]
    if any(r[:db]):
        raise ArithmeticError("inexact polynomial division")
    return q


def _monic(p):
    l = _lcrec(p)
    return p if l == 1 else _scale(p, 1 / l)


#: univariate gcds up to this degree run Euclid here, larger ones SymPy's
#: heuristic gcd over ZZ (cheaper for tiny inputs, much faster for big ones)
_EUCLID_MAX_DEG = 8


def _ugcd(a, b) -> list:
    """Monic gcd of two univariate polynomials over Q of degree >= 1
    (coefficient sequences, lowest degree first): Euclid with monic
    remainders."""
    a, b = list(a), list(b)
    if len(a) < len(b):
        a, b = b, a
    l = b[-1]
    if l != 1:
        b = [c / l for c in b]
    while True:
        db = len(b) - 1
        while len(a) > db:                   # a := a mod b (b monic)
            f = a.pop()
            s = len(a) - db
            for i in range(db):
                a[s + i] -= f * b[i]
            while a and not a[-1]:
                a.pop()
        if not a:
            return b
        if len(a) == 1:
            return [_ONE]
        l = a[-1]
        a, b = b, (a if l == 1 else [c / l for c in a])


def _inner_gcd(a, b):
    """``(g, a/g, b/g)`` for nonzero polynomials, ``g`` their monic gcd."""
    if type(a) is Fraction or type(b) is Fraction:
        return _ONE, a, b
    if a == b:
        l = _lcrec(a)
        return (a if l == 1 else _scale(a, 1 / l)), l, l
    v = a[0]
    if v == b[0]:
        ma, mb = _monomial(a), _monomial(b)
        if ma or mb:                         # gcd(p, t**k) = t**min(k, ord_t p)
            j = min(ma or _order(a), mb or _order(b))
            if j == 0:
                return _ONE, a, b
            g = (v, (_ZERO,) * j + (_ONE,))
            return g, _divexact(a, g), _divexact(b, g)
        ca, cb = a[1], b[1]
        if len(ca) <= _EUCLID_MAX_DEG + 1 and len(cb) <= _EUCLID_MAX_DEG + 1 \
                and all(type(c) is Fraction for c in ca) \
                and all(type(c) is Fraction for c in cb):
            g = _ugcd(ca, cb)
            if len(g) == 1:
                return _ONE, a, b
            return (v, tuple(g)), _mk(v, _udiv(ca, g)), _mk(v, _udiv(cb, g))
    return _sympy_inner_gcd(a, b)


def _denominators(p, acc: int) -> int:
    """The lcm of ``acc`` and the denominators of ``p``'s coefficients;
    TooLarge once it has more than :data:`MAX_BITS` bits (the gcd over ZZ
    of polynomials with a common denominator of 240000 bits, 121 terms
    with distinct 2000-bit denominators, took 5 s)."""
    if type(p) is Fraction:
        d = p.denominator
        if acc % d == 0:
            return acc
        acc = acc * d // _igcd(acc, d)
        if acc.bit_length() > MAX_BITS:
            raise TooLarge(f"a common denominator exceeds {MAX_BITS} bits")
        return acc
    for c in p[1]:
        acc = _denominators(c, acc)
    return acc


def _to_dmp(p, vs: list, i: int, den: int, K):
    """``den * p`` as a SymPy dense recursive polynomial over ``K = ZZ``
    in the variables ``vs[i:]`` (main variable first)."""
    if i == len(vs):
        return K(int(p * den))
    if type(p) is tuple and p[0] == vs[i]:
        return [_to_dmp(c, vs, i + 1, den, K) for c in reversed(p[1])]
    if _zero(p):
        from sympy.polys.densebasic import dmp_zero
        return dmp_zero(len(vs) - 1 - i)
    return [_to_dmp(p, vs, i + 1, den, K)]


def _from_dmp(f, vs: list, i: int):
    if i == len(vs):
        return Fraction(int(f))
    from sympy.polys.densebasic import dmp_zero_p
    if dmp_zero_p(f, len(vs) - 1 - i):
        return _ZERO
    return _mk(vs[i], [_from_dmp(c, vs, i + 1) for c in reversed(f)])


def _sympy_inner_gcd(a, b):
    """:func:`_inner_gcd` by SymPy's ``dmp_inner_gcd`` over ZZ (the
    heuristic gcd, with a PRS fallback inside SymPy)."""
    da, db = _denominators(a, 1), _denominators(b, 1)   # TooLarge before importing SymPy
    from sympy.polys.domains import ZZ
    from sympy.polys.euclidtools import dmp_inner_gcd
    vs = sorted(_vars(b, _vars(a, set())), reverse=True)
    h, fa, fb = dmp_inner_gcd(_to_dmp(a, vs, 0, da, ZZ), _to_dmp(b, vs, 0, db, ZZ),
                              len(vs) - 1, ZZ)
    g = _from_dmp(h, vs, 0)
    if type(g) is Fraction:
        return _ONE, a, b
    # a = (h * fa) / da and g = h / lh: a / g = fa * lh / da
    lh = _lcrec(g)
    g = _scale(g, 1 / lh)
    return g, _scale(_from_dmp(fa, vs, 0), lh / da), _scale(_from_dmp(fb, vs, 0), lh / db)


def _gcd(a, b):
    """Monic gcd (recursive leading coefficient 1) of two polynomials;
    0 for two zeros."""
    if _zero(a):
        return _ZERO if _zero(b) else _monic(b)
    if _zero(b):
        return _monic(a)
    return _inner_gcd(a, b)[0]


def _psize(p) -> tuple[int, int, int]:
    """``(total degree, number of terms, max coefficient bits)``."""
    if type(p) is Fraction:
        return 0, (1 if p else 0), max(p.numerator.bit_length(), p.denominator.bit_length())
    deg = terms = bits = 0
    cs = p[1]
    for c in cs:
        if type(c) is Fraction:
            if c:
                terms += 1
                n, d = c.numerator.bit_length(), c.denominator.bit_length()
                if n > bits:
                    bits = n
                if d > bits:
                    bits = d
        else:
            break
    else:                                    # univariate: all coefficients rational
        return len(cs) - 1, terms, bits
    deg = terms = bits = 0
    for k, c in enumerate(cs):
        if _zero(c):
            continue
        d, t, b = _psize(c)
        if d + k > deg:
            deg = d + k
        terms += t
        if b > bits:
            bits = b
    return deg, terms, bits


def _short(x, n: int = 200) -> str:
    r = repr(x)
    return r if len(r) <= n else r[:n] + "..."


def _checked(x):
    """``x``, or TooLarge when an Element exceeds the size budget."""
    if type(x) is Element:
        deg, terms, bits = x._size()
        if deg > MAX_DEGREE or terms > MAX_TERMS or bits > MAX_BITS:
            raise TooLarge(f"a number of degree {deg}, {terms} terms, "
                           f"{bits}-bit coefficients exceeds the size budget")
    return x


def _vars(p, out: set) -> set:
    if type(p) is tuple:
        out.add(p[0])
        for c in p[1]:
            _vars(c, out)
    return out


# ----------------------------------------------------------------------
# interval evaluation: integers scaled by 2**prec, outward rounded
# ----------------------------------------------------------------------

def _qenc(q: Fraction, prec: int) -> tuple[int, int]:
    """``(lo, hi)`` with ``lo <= q * 2**prec <= hi``, both tight."""
    n, d = q.numerator << prec, q.denominator
    lo = n // d
    return lo, (lo if lo * d == n else lo + 1)


def _ieval(p, prec: int, env: dict) -> tuple[int, int]:
    """``(lo, hi)`` with ``lo <= p(c) * 2**prec <= hi`` for every value
    ``c`` of the constants within ``env`` (index -> scaled enclosure)."""
    if type(p) is Fraction:
        return _qenc(p, prec)
    tl, th = env[p[0]]
    cs = p[1]
    lo, hi = _ieval(cs[-1], prec, env)
    for c in reversed(cs[:-1]):
        a, b, x, y = lo * tl, lo * th, hi * tl, hi * th
        lo = min(a, b, x, y) >> prec                  # floor
        hi = -(-max(a, b, x, y) >> prec)              # ceiling
        if not _zero(c):
            cl, ch = _ieval(c, prec, env)
            lo += cl
            hi += ch
    return lo, hi


# ----------------------------------------------------------------------
# constants
# ----------------------------------------------------------------------

class Constant:
    """An indeterminate: a real constant with rigorous enclosures.

    ``enclose(prec)`` returns integers ``(lo, hi)`` with
    ``lo <= value * 2**prec <= hi``; the width should be a few units (it
    may be wider when the constant cannot be enclosed more tightly, see
    ``max_prec``).  ``transcendental`` claims that the value is no root of
    a nonzero rational polynomial (only for proven cases: it lets a
    formally nonzero expression in this constant alone count as nonzero
    without evaluation).  ``max_prec``: the precision beyond which
    ``enclose`` does not get tighter (None: unlimited)."""

    __slots__ = ("key", "index", "name", "_enclose", "transcendental",
                 "max_prec", "_cache")

    def __init__(self, key, index, enclose, transcendental, max_prec, name):
        self.key = key
        self.index = index
        self.name = name
        self._enclose = enclose
        self.transcendental = transcendental
        self.max_prec = max_prec
        self._cache: dict = {}

    def enclose(self, prec: int) -> tuple[int, int]:
        r = self._cache.get(prec)
        if r is None:
            lo, hi = self._enclose(prec)
            if not lo <= hi:
                raise ValueError(f"bad enclosure for {self.name}")
            r = self._cache[prec] = (int(lo), int(hi))
        return r

    def __repr__(self) -> str:
        return f"Constant({self.name})"


_CONSTANTS: list[Constant] = []
_BY_KEY: dict = {}


def constant(key: Hashable, enclose: Callable[[int], tuple[int, int]], *,
             transcendental: bool = False, max_prec: int | None = None,
             name: str | None = None) -> Element:
    """The number of the constant ``key`` (registered on first use with
    the given enclosure; later calls return the same indeterminate)."""
    c = _BY_KEY.get(key)
    if c is None:
        c = Constant(key, len(_CONSTANTS), enclose, transcendental, max_prec,
                     name if name is not None else str(key))
        _CONSTANTS.append(c)
        _BY_KEY[key] = c
    return Element._new((c.index, (_ZERO, _ONE)), _ONE)


def _scaled_down(val: int, err: int, guard: int) -> tuple[int, int]:
    """Enclosure at ``prec`` from ``|value * 2**(prec+guard) - val| <= err``."""
    return (val - err) >> guard, -(-(val + err) >> guard)


def _atan_inv(x: int, w: int) -> tuple[int, int]:
    """``(s, err)`` with ``|atan(1/x) * 2**w - s| <= err`` (``x >= 2``)."""
    power = (1 << w) // x              # 2**w / x**(2k+1), each floor: error < 2
    x2 = x * x
    s = 0
    k = 0
    while power:
        term = power // (2 * k + 1)
        s = s - term if k & 1 else s + term
        power //= x2
        k += 1
    return s, 3 * (k + 2)              # 2 per term + the tail (< 2)


def _pi_enclose(prec: int) -> tuple[int, int]:
    g = 32
    w = prec + g
    a, ea = _atan_inv(5, w)
    b, eb = _atan_inv(239, w)
    return _scaled_down(16 * a - 4 * b, 16 * ea + 4 * eb, g)


def _e_enclose(prec: int) -> tuple[int, int]:
    g = 32
    w = prec + g
    term = 1 << w                      # 2**w / k!, floored: error < 2
    s = 0
    k = 0
    while term:
        s += term
        k += 1
        term //= k
    return _scaled_down(s, 2 * k + 4, g)   # tail < 2


def _iroot(n: int, b: int) -> int:
    """``floor(n ** (1/b))`` for ``n >= 0``."""
    if n < 2:
        return n
    x = 1 << -(-n.bit_length() // b)   # >= the root
    while True:
        y = ((b - 1) * x + n // x ** (b - 1)) // b
        if y >= x:
            return x
        x = y


def radical(r: Fraction, b: int) -> Element:
    """The indeterminate ``r**(1/b)`` (real ``b``-th root of ``r > 0``,
    ``b >= 2``), enclosed at any precision by integer roots.  Algebraic,
    so a plain indeterminate (see the module docstring)."""
    r = Fraction(r)
    if r <= 0 or b < 2:
        raise ValueError("radical needs r > 0 and b >= 2")
    p, q = r.numerator, r.denominator

    def enclose(prec: int) -> tuple[int, int]:
        # value * 2**prec = (p * 2**(b*prec) / q) ** (1/b)
        n = p << (b * prec)
        lo = _iroot(n // q, b)
        hi = _iroot(-(-n // q), b)
        if hi ** b < -(-n // q):
            hi += 1
        return lo, hi

    name = f"{r}**(1/{b})" if b != 2 else f"sqrt({r})"
    return constant(("root", r, b), enclose, name=name)


# ----------------------------------------------------------------------
# elements
# ----------------------------------------------------------------------

def num(x):
    """``x`` as a number of this field: the Element itself, or a
    Fraction (from anything :class:`~fractions.Fraction` accepts except
    floats); the replacement for ``Fraction(x)`` where constants may
    occur."""
    t = type(x)
    if t is Fraction or t is Element:
        return x
    if isinstance(x, float):
        raise TypeError(f"not an exact number: {x!r}")
    return Fraction(x)


def formally_zero(x) -> bool:
    """True for the rational 0; never raises.  For sparsity only (dropping
    a coefficient from a row): an Element whose value is 0 (``t**2 - 2``)
    is kept, which is exact, since the row is a formal identity."""
    return type(x) is Fraction and not x or (type(x) is int and not x)


def sign(x) -> int:
    """-1, 0 or 1 for a Fraction, int or Element (may raise Undecided)."""
    if type(x) is Element:
        return x.sign()
    return (x > 0) - (x < 0)


def _make(n, d):
    """The number ``n/d`` (``d`` a nonzero polynomial with a nonzero value)."""
    if type(d) is Fraction:
        if type(n) is Fraction:
            return n / d
        return Element._new(n if d == 1 else _scale(n, 1 / d), _ONE)
    if _zero(n):
        return _ZERO
    _, n, d = _inner_gcd(n, d)
    l = _lcrec(d)
    if l != 1:
        l = 1 / l
        n, d = _scale(n, l), _scale(d, l)
    if type(d) is Fraction:
        return n if type(n) is Fraction else Element._new(n, _ONE)
    return Element._new(n, d)


def _coerce(x):
    t = type(x)
    if t is Element or t is Fraction:
        return x
    if t is int:
        return Fraction(x)
    if isinstance(x, Fraction):
        return Fraction(x)
    if isinstance(x, int) and not isinstance(x, bool):
        return Fraction(int(x))
    return None


def _coerce_foreign(x):
    """For ``==``: a SymPy number as a Fraction or Element (``Integer(3)``,
    ``pi/2``); TypeError for any other number (``3.0``, a SymPy ``Float``,
    ``I`` or a closed expression that is not read), whose equality with an
    exact real has no single meaning; None for a non-number (never equal:
    ``None``, a string, a bool, ``Symbol('y')``, ``x + 1``, ``S.true``)."""
    import numbers
    if isinstance(x, bool):
        return None
    if type(x).__module__.startswith("sympy"):
        if getattr(x, "is_number", False) is not True:
            return None
        r = from_sympy(x)
        if r is None:
            raise TypeError(f"cannot compare an exact number with {x!r}")
        return r
    if isinstance(x, numbers.Number):
        raise TypeError(f"cannot compare an exact number with {x!r}")
    return None


class Element:
    """A number ``n/d`` of ``Q(constants)`` that is not rational formally
    (see the module docstring); operations with Fractions and ints return
    a Fraction when the result is constant-free."""

    __slots__ = ("_d", "_enc", "_hash", "_n", "_sign", "_size_", "_vars")

    @classmethod
    def _new(cls, n, d) -> Element:
        self = object.__new__(cls)
        self._n = n
        self._d = d
        self._hash = None
        self._sign = None
        self._vars = None
        self._enc = None
        self._size_ = None
        return self

    def __init__(self, *args):
        raise TypeError("build Elements with constant(), from_sympy() and arithmetic")

    # -- structure -----------------------------------------------------

    @property
    def numerator(self):
        return self._n

    @property
    def denominator(self):
        return self._d

    def constants(self) -> list[Constant]:
        """The constants this number is (formally) built from."""
        return [_CONSTANTS[i] for i in sorted(self._varset())]

    def _varset(self) -> frozenset:
        v = self._vars
        if v is None:
            v = self._vars = frozenset(_vars(self._d, _vars(self._n, set())))
        return v

    def _size(self) -> tuple[int, int, int]:
        """``(total degree, terms, coefficient bits)``, the largest of
        numerator and denominator (see :data:`MAX_DEGREE`)."""
        sz = self._size_
        if sz is None:
            a, b = _psize(self._n), _psize(self._d)
            sz = self._size_ = (max(a[0], b[0]), max(a[1], b[1]), max(a[2], b[2]))
        return sz

    def _budget_scale(self, q: Fraction) -> None:
        """Refuse a product or sum with the rational ``q`` whose
        coefficients would exceed :data:`MAX_BITS`."""
        bits = self._size()[2] + max(q.numerator.bit_length(), q.denominator.bit_length())
        if bits > MAX_BITS:
            raise TooLarge(f"{bits}-bit coefficients exceed the size budget")

    def _budget_product(self, o: Element):
        """Refuse ``self * o`` or ``self + o`` before computing it when the
        result would exceed the budget (degrees and bits add, the work is
        the product of the numbers of terms); otherwise the multiplication
        for the numerators and denominators: :func:`_mul` when no
        coefficient can outgrow the budget (:func:`_mul_fast`), else
        :func:`_mul_bounded`, which refuses a growing common denominator
        of a coefficient as soon as it is too large."""
        a, b = self._size(), o._size()
        if a[0] + b[0] > MAX_DEGREE or a[2] + b[2] > MAX_BITS or a[1] * b[1] > MAX_WORK:
            raise TooLarge(f"a result of degree {a[0] + b[0]}, {a[2] + b[2]}-bit "
                           f"coefficients, {a[1] * b[1]} term products exceeds the size budget")
        return _mul if min(a[1], b[1]) * (a[2] + b[2] + 1) <= MAX_BITS else _mul_bounded   # _mul_fast

    def _single_transcendental(self, other=None) -> bool:
        vs = self._varset()
        if other is not None:
            vs = vs | other._varset()
        if len(vs) != 1:
            return False
        (i,) = vs
        return _CONSTANTS[i].transcendental

    def __hash__(self) -> int:
        h = self._hash
        if h is None:
            h = self._hash = hash(("constfield", self._n, self._d))
        return h

    # -- arithmetic ----------------------------------------------------

    def __neg__(self):
        return Element._new(_neg(self._n), self._d)

    def __pos__(self):
        return self

    def __abs__(self):
        return -self if self.sign() < 0 else self

    def __add__(self, other):
        o = _coerce(other)
        if o is None:
            return NotImplemented
        if type(o) is Fraction:
            if not o:
                return self
            # gcd(n + o*d, d) = gcd(n, d) = 1: no normalisation needed
            self._budget_scale(o)
            d = self._d
            return Element._new(_add(self._n, o if type(d) is Fraction else _scale(d, o)), d)
        an, ad, bn, bd = self._n, self._d, o._n, o._d
        if ad == bd:
            return _checked(_make(_add(an, bn), ad))
        mul = self._budget_product(o)
        # the results below are nonzero: a = -b would have ad == bd
        if type(ad) is Fraction:             # gcd(an*bd + bn, bd) = 1
            return _checked(Element._new(_add(mul(an, bd), bn), bd))
        if type(bd) is Fraction:
            return _checked(Element._new(_add(an, mul(bn, ad)), ad))
        g, ad1, bd1 = _inner_gcd(ad, bd)
        if type(g) is Fraction:              # coprime denominators: lowest terms, monic
            return _checked(Element._new(_add(mul(an, bd), mul(bn, ad)), mul(ad, bd)))
        # cofactors can have other sizes than ad, bd: checked afresh
        return _checked(_make(_add(_mul_checked(an, bd1), _mul_checked(bn, ad1)),
                              _mul_checked(_mul_checked(ad1, bd1), g)))

    __radd__ = __add__

    def __sub__(self, other):
        o = _coerce(other)
        if o is None:
            return NotImplemented
        return self + (-o)

    def __rsub__(self, other):
        o = _coerce(other)
        if o is None:
            return NotImplemented
        return (-self) + o

    def __mul__(self, other):
        o = _coerce(other)
        if o is None:
            return NotImplemented
        if type(o) is Fraction:
            if not o:
                return _ZERO
            if o == 1:
                return self
            self._budget_scale(o)
            return Element._new(_scale(self._n, o), self._d)
        mul = self._budget_product(o)
        an, ad, bn, bd = self._n, self._d, o._n, o._d
        if type(ad) is Fraction and type(bd) is Fraction:
            return _checked(_make(mul(an, bn), _ONE))
        # cross gcds keep the result in lowest terms; cofactors of a
        # nontrivial gcd can have other sizes: checked afresh
        g1, an, bd = _inner_gcd(an, bd)
        g2, bn, ad = _inner_gcd(bn, ad)
        if type(g1) is not Fraction or type(g2) is not Fraction:
            mul = _mul_checked
        n, d = mul(an, bn), mul(ad, bd)
        if type(d) is Fraction:
            return _checked(_make(n, d))
        return _checked(Element._new(n, d))  # monic: product of monics

    __rmul__ = __mul__

    def _inverse(self):
        if not self._nonzero():
            raise ZeroDivisionError("division by zero")
        n, d = self._n, self._d
        if type(n) is Fraction:
            return Element._new(_scale(d, 1 / n), _ONE)
        l = _lcrec(n)
        if l != 1:
            l = 1 / l
            n, d = _scale(n, l), _scale(d, l)
        return Element._new(d, n)

    def __truediv__(self, other):
        o = _coerce(other)
        if o is None:
            return NotImplemented
        if type(o) is Fraction:
            if not o:
                raise ZeroDivisionError("division by zero")
            return self * (1 / o)
        if o is self or (o._n == self._n and o._d == self._d):
            o._nonzero()                     # x/x is 1 only for a nonzero x
            return _ONE
        return self * o._inverse()

    def __rtruediv__(self, other):
        o = _coerce(other)
        if o is None:
            return NotImplemented
        return self._inverse() * o

    def __pow__(self, k):
        if type(k) is not int:
            return NotImplemented
        if k < 0:
            return self._inverse() ** -k
        if k == 0:
            return _ONE
        deg, terms, bits = self._size()
        if deg * k > MAX_DEGREE or bits * k > MAX_BITS:
            raise TooLarge(f"a power of degree {deg * k} exceeds the size budget")
        # powers of coprime polynomials are coprime, monic stays monic;
        # every product of the squarings is checked against the budget
        return _checked(Element._new(_pow_checked(self._n, k), _pow_checked(self._d, k)))

    # -- signs and comparisons -----------------------------------------

    def _env(self, prec: int, vs) -> dict:
        return {i: _CONSTANTS[i].enclose(prec) for i in vs}

    def _precisions(self):
        vs = self._varset()
        cap = PREC_CAP
        limits = [_CONSTANTS[i].max_prec for i in vs]
        if limits and None not in limits:
            cap = min(cap, 2 * max(limits))
        prec = PREC_START
        while prec <= cap:
            yield prec
            prec *= 2

    def _nonzero(self) -> bool:
        """True (the value is not 0), or Undecided."""
        if self._sign is not None:
            return True
        vs = _vars(self._n, set())
        if not vs:
            return True                      # a nonzero rational numerator
        if len(vs) == 1 and _CONSTANTS[next(iter(vs))].transcendental:
            return True                      # no transcendental root
        n = self._n
        for prec in self._precisions():
            lo, hi = _ieval(n, prec, self._env(prec, vs))
            if lo > 0 or hi < 0:
                return True
        raise Undecided(f"cannot show {_short(self)} nonzero")

    def sign(self) -> int:
        """The sign (-1 or 1) of the value; Undecided if not found (the
        value may then be 0)."""
        s = self._sign
        if s is not None:
            return s
        vs = self._varset()
        sd = 1 if type(self._d) is Fraction else 0
        for prec in self._precisions():
            env = self._env(prec, vs)
            if not sd:
                dl, dh = _ieval(self._d, prec, env)
                sd = 1 if dl > 0 else -1 if dh < 0 else 0
            nl, nh = _ieval(self._n, prec, env)
            sn = 1 if nl > 0 else -1 if nh < 0 else 0
            if sn and sd:
                self._sign = sn * sd
                return self._sign
        raise Undecided(f"cannot decide the sign of {_short(self)}")

    def enclosure(self, prec: int) -> tuple[int, int] | None:
        """``(lo, hi)`` with ``lo <= value * 2**prec <= hi``, or None when
        the denominator's interval at this precision contains 0."""
        e = self._enc
        if e is not None and e[0] == prec:
            return e[1]
        env = self._env(prec, self._varset())
        nl, nh = _ieval(self._n, prec, env)
        if type(self._d) is Fraction:
            r = (nl, nh)
        else:
            dl, dh = _ieval(self._d, prec, env)
            if dl <= 0 <= dh:
                return None
            corners = [(x << prec, y) for x in (nl, nh) for y in (dl, dh)]
            lo = min(a // b for a, b in corners)
            hi = max(-(-a // b) for a, b in corners)
            r = (lo, hi)
        self._enc = (prec, r)
        return r

    def approx(self, prec: int = 64) -> tuple[Fraction, Fraction] | None:
        """Rational bounds ``lo <= value <= hi`` at ``prec`` bits, or None."""
        e = self.enclosure(prec)
        if e is None:
            return None
        return Fraction(e[0], 1 << prec), Fraction(e[1], 1 << prec)

    def _cmp(self, o) -> int:
        """sign(self - o) for a Fraction or Element ``o``."""
        if o is self or (type(o) is Element and o._n == self._n and o._d == self._d):
            return 0
        # cheap: disjoint enclosures at the first precision
        a = self.enclosure(PREC_START)
        if a is not None:
            b = _qenc(o, PREC_START) if type(o) is Fraction else o.enclosure(PREC_START)
            if b is not None:
                if a[1] < b[0]:
                    return -1
                if a[0] > b[1]:
                    return 1
        diff = self - o
        if type(diff) is Fraction:
            return (diff > 0) - (diff < 0)
        return diff.sign()

    def __eq__(self, other):
        if other is self:
            return True
        o = _coerce(other)
        if o is None:
            o = _coerce_foreign(other)
            if o is None:
                return NotImplemented            # not a number: never equal
        if type(o) is Element:
            if o._n == self._n and o._d == self._d:
                return True
            if self._single_transcendental(o):
                return False
        elif self._single_transcendental():
            return False
        return self._cmp(o) == 0

    def __ne__(self, other):
        r = self.__eq__(other)
        return r if r is NotImplemented else not r

    def __lt__(self, other):
        o = _coerce(other)
        return NotImplemented if o is None else self._cmp(o) < 0

    def __le__(self, other):
        o = _coerce(other)
        return NotImplemented if o is None else self._cmp(o) <= 0

    def __gt__(self, other):
        o = _coerce(other)
        return NotImplemented if o is None else self._cmp(o) > 0

    def __ge__(self, other):
        o = _coerce(other)
        return NotImplemented if o is None else self._cmp(o) >= 0

    def __bool__(self) -> bool:
        return self._nonzero()

    def __floor__(self) -> int:
        for prec in self._precisions():
            e = self.enclosure(prec)
            if e is not None:
                lo, hi = e[0] >> prec, e[1] >> prec
                if lo == hi:
                    return lo
        raise Undecided(f"cannot decide the floor of {_short(self)}")

    def __ceil__(self) -> int:
        return -(-self).__floor__()

    def is_integer(self) -> bool:
        """False when the value is proven not to be an integer; else
        Undecided.  An Element is never formally an integer, but its value
        can be one (``sqrt(2)**2``), so True is never answered.  In a
        single transcendental constant the value is irrational (a rational
        value ``r`` would make the nonzero polynomial ``n - r*d`` vanish
        there), so the answer is False without evaluation."""
        if self._single_transcendental():
            return False
        for prec in self._precisions():
            e = self.enclosure(prec)
            if e is not None:
                lo, hi = e
                f = lo >> prec
                if (f << prec) < lo and hi < ((f + 1) << prec):
                    return False
        raise Undecided(f"cannot show that {_short(self)} is no integer")

    # -- conversion ----------------------------------------------------

    def to_sympy(self):
        """The SymPy expression (constants registered without one become
        Symbols named after them)."""
        from sympy import Rational

        def conv(p):
            if type(p) is Fraction:
                return Rational(p.numerator, p.denominator)
            t = _sympy_constant(_CONSTANTS[p[0]])
            return sum((conv(x) * t ** k for k, x in enumerate(p[1])), Rational(0))
        return conv(self._n) / conv(self._d)

    def __repr__(self) -> str:
        def fmt(p):
            if type(p) is Fraction:
                return str(p)
            name = _CONSTANTS[p[0]].name
            parts = []
            for k, c in enumerate(p[1]):
                if _zero(c):
                    continue
                t = "" if k == 0 else name if k == 1 else f"{name}**{k}"
                cs = fmt(c)
                if not t:
                    parts.append(cs)
                elif cs == "1":
                    parts.append(t)
                else:
                    parts.append(f"({cs})*{t}" if type(c) is tuple or "/" in cs or cs.startswith("-") else f"{cs}*{t}")
            return " + ".join(reversed(parts))
        n = fmt(self._n)
        if type(self._d) is Fraction:
            return f"Element({n})"
        return f"Element(({n})/({fmt(self._d)}))"


#: pi (Lindemann 1882: transcendental)
PI = constant("pi", _pi_enclose, transcendental=True, name="pi")
#: Euler's number (Hermite 1873: transcendental)
E = constant("E", _e_enclose, transcendental=True, name="E")


# ----------------------------------------------------------------------
# SymPy
# ----------------------------------------------------------------------

def from_sympy(expr, generic: bool = True):
    """The number of a closed real SymPy expression: a Fraction, an
    Element, or None when it is not read (free symbols, Floats, non-real
    or unbounded constants, a division by a number not shown nonzero, a
    result over the size budget).  See "Constants" in the module
    docstring.  ``generic=False`` reads only rationals, ``pi``, ``E``,
    ``exp(n)`` and rational powers of rationals (with ``+ - * /`` and
    integer powers), not other constants such as ``log(2)``."""
    try:
        return _from_sympy(expr, generic)
    except (Undecided, ZeroDivisionError, _Unread):
        return None


class _Unread(Exception):
    pass


#: larger integer powers (``pi**1000``) are generic constants, not polynomials
_MAX_POW = 64


def _from_sympy(e, generic=True):
    from sympy import Float, Pow, S, exp
    from sympy.core.expr import Expr
    if not isinstance(e, Expr):
        raise _Unread(e)
    if e.is_Rational:
        return Fraction(int(e.p), int(e.q))
    if e is S.Pi:
        return PI
    if e is S.Exp1:
        return E
    if e.free_symbols or e.has(Float, S.NaN, S.Infinity, S.NegativeInfinity,
                               S.ComplexInfinity):
        raise _Unread(e)
    if e.is_Add:
        r = _ZERO
        for a in e.args:
            r = r + _from_sympy(a, generic)
        return r
    if e.is_Mul:
        r = _ONE
        for a in e.args:
            r = r * _from_sympy(a, generic)
        return r
    if isinstance(e, Pow):
        b, x = e.args
        if x.is_Integer and abs(int(x)) <= _MAX_POW:
            return _from_sympy(b, generic) ** int(x)
        if b.is_Rational and b.is_positive and x.is_Rational:
            p, q = int(x.p), int(x.q)
            if abs(p) <= _MAX_POW and q <= _MAX_POW:
                t = radical(Fraction(int(b.p), int(b.q)), q)
                return t ** p
    if isinstance(e, exp) and e.args[0].is_Integer and abs(int(e.args[0])) <= _MAX_POW:
        return E ** int(e.args[0])
    if not generic:
        raise _Unread(e)
    return _generic(e)


def _generic(e):
    """An indeterminate for a closed real constant with rigorous bounds
    (:func:`satassume.theories.lra.lra_bounds.constant_bounds`), enclosed at any
    precision by the same interval evaluation at a higher working
    precision (:func:`satassume.theories.lra.lra_bounds.constant_enclosure`)."""
    from .lra_bounds import constant_bounds, constant_enclosure
    b = constant_bounds(e)
    if b is None:
        raise _Unread(e)
    lo0, hi0 = b
    mag = max(abs(lo0), abs(hi0))
    mag = mag.numerator.bit_length() - mag.denominator.bit_length() + 1

    def enclose(prec: int) -> tuple[int, int]:
        # absolute 2**-prec: relative precision prec plus the magnitude
        r = constant_enclosure(e, prec + max(mag, 0) + 8) if prec > 64 else None
        lo, hi = r if r is not None else (lo0, hi0)
        return _qenc(lo, prec)[0], _qenc(hi, prec)[1]
    return constant(("sympy", e), enclose, name=str(e))


def _sympy_constant(c: Constant):
    """The SymPy expression of a constant (a Symbol named after it when
    it was registered by :func:`constant` with a key of its own)."""
    from sympy import Rational, S, Symbol
    k = c.key
    if k == "pi":
        return S.Pi
    if k == "E":
        return S.Exp1
    if type(k) is tuple and len(k) == 3 and k[0] == "root":
        r = k[1]
        return Rational(r.numerator, r.denominator) ** Rational(1, k[2])
    if type(k) is tuple and len(k) == 2 and k[0] == "sympy":
        return k[1]
    return Symbol(c.name)
