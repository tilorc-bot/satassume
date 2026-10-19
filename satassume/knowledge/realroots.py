"""Exact real-root counts of integer polynomials (Sturm's theorem).

Plain Python over ``int`` and ``Fraction``; no SymPy.  The templates of
``ComplexRootOf`` (:mod:`satassume.knowledge.templates.rootof`) read the
facts of an indexed root from these counts.  A polynomial is a list of
coefficients, highest degree first, without leading zeros.
"""
from __future__ import annotations

from fractions import Fraction
from typing import List, Optional, Sequence

Poly = List[Fraction]

#: Largest degree and coefficient size (bits) the counts are computed for;
#: past them :func:`root_facts` gives None (no facts), so a huge
#: polynomial costs nothing.
MAX_DEGREE = 120
MAX_BITS = 512


def _strip(p: Sequence) -> Poly:
    i = 0
    while i < len(p) and p[i] == 0:
        i += 1
    return [Fraction(c) for c in p[i:]]


def _rem(a: Poly, b: Poly) -> Poly:
    """The remainder of ``a`` divided by ``b`` (``b`` nonzero)."""
    a = list(a)
    lb, db = b[0], len(b) - 1
    while len(a) - 1 >= db and a:
        q = a[0] / lb
        for i in range(len(b)):
            a[i] -= q * b[i]
        a = _strip(a)
    return a


def _monic(p: Poly) -> Poly:
    return [c / p[0] for c in p]


def _primitive(p: Poly) -> Poly:
    """``p`` times a positive rational: integer coefficients without a
    common factor.  Signs and roots stay; the Euclidean and Sturm sequences
    over ``Fraction`` otherwise grow to thousands of bits."""
    from math import gcd as igcd, lcm
    if not p:
        return p
    m = lcm(*(c.denominator for c in p))
    q = [c.numerator * (m // c.denominator) for c in p]
    g = igcd(*q)
    return [Fraction(c // g) for c in q]


def gcd(a: Sequence, b: Sequence) -> Poly:
    """The monic gcd of ``a`` and ``b`` (``[]`` if both are zero)."""
    a, b = _primitive(_strip(a)), _primitive(_strip(b))
    while b:
        a, b = b, _primitive(_rem(a, b))
    return _monic(a) if a else []


def _derivative(p: Poly) -> Poly:
    d = len(p) - 1
    return _strip([c * (d - i) for i, c in enumerate(p[:-1])])


def _div(a: Poly, b: Poly) -> Poly:
    """The exact quotient ``a / b``."""
    a, out = list(a), []
    lb = b[0]
    while len(a) >= len(b):
        q = a[0] / lb
        out.append(q)
        for i in range(len(b)):
            a[i] -= q * b[i]
        a.pop(0)
    return out


def squarefree(p: Sequence) -> bool:
    p = _strip(p)
    return len(gcd(p, _derivative(p))) <= 1


def _chain(p: Poly) -> List[Poly]:
    """The Sturm chain of the squarefree ``p``."""
    out = [_primitive(p), _primitive(_derivative(p))]
    while len(out[-1]) > 1:
        r = _primitive(_rem(out[-2], out[-1]))
        if not r:
            break
        out.append([-c for c in r])
    return out


def _changes(signs) -> int:
    s = [x for x in signs if x != 0]
    return sum(1 for u, v in zip(s, s[1:]) if (u > 0) != (v > 0))


def _at_inf(chain, neg: bool) -> int:
    return _changes([q[0] * (-1 if neg and (len(q) - 1) % 2 else 1) for q in chain])


def _at_zero(chain) -> int:
    return _changes([q[-1] for q in chain])


def real_root_counts(p: Sequence):
    """``(negative, zero, positive)``: the numbers of distinct real roots
    of the squarefree ``p`` below, at and above 0."""
    p = _strip(p)
    zero = 0
    if p[-1] == 0:
        zero = 1
        p = p[:-1]                      # squarefree: x divides p once
    if len(p) == 1:
        return 0, zero, 0
    chain = _chain(p)
    v0 = _at_zero(chain)
    return _at_inf(chain, True) - v0, zero, v0 - _at_inf(chain, False)


def _distinct_nonzero_real_roots(g: Poly) -> int:
    while g and g[-1] == 0:
        g = g[:-1]
    if len(g) <= 1:
        return 0
    h = gcd(g, _derivative(g))
    s = _div(g, h) if len(h) > 1 else g
    n, _z, pos = real_root_counts(s)
    return n + pos


def imaginary_root_count(p: Sequence) -> int:
    """The number of distinct roots ``i*y`` (``y`` real, nonzero) of ``p``:
    the nonzero real roots of the gcd of the real and imaginary parts of
    ``p(i*y)``."""
    p = _strip(p)
    d = len(p) - 1
    re: Poly = [Fraction(0)] * (d + 1)
    im: Poly = [Fraction(0)] * (d + 1)
    for i, c in enumerate(p):
        k = d - i                       # c*x**k at x = i*y: i**k * c * y**k
        part, sign = (re, 1 - (k % 4)) if k % 2 == 0 else (im, 2 - (k % 4))
        part[i] = c * sign
    return _distinct_nonzero_real_roots(gcd(re, im))


def root_facts(coeffs: Sequence[int], index: int) -> Optional[dict]:
    """The facts of root ``index`` of the squarefree integer polynomial
    ``coeffs``, in ``ComplexRootOf``'s order (the real roots ascending,
    then the non-real ones): ``{'real': bool, 'sign': -1/0/1 or None,
    'imaginary': bool or None}``.  None for a polynomial that is not
    squarefree (whose indexing counts multiplicities), of degree below 1,
    or past :data:`MAX_DEGREE` / :data:`MAX_BITS`."""
    p = _strip(coeffs)
    d = len(p) - 1
    if d < 1 or d > MAX_DEGREE or not 0 <= index < d \
            or max(abs(int(c)).bit_length() for c in p) > MAX_BITS \
            or not squarefree(p):
        return None
    neg, zero, pos = real_root_counts(p)
    nreal = neg + zero + pos
    if index < nreal:
        sign = -1 if index < neg else 0 if index < neg + zero else 1
        return {'real': True, 'sign': sign, 'imaginary': False}
    m = imaginary_root_count(p)
    imaginary = False if m == 0 else True if m == d - nreal else None
    return {'real': False, 'sign': None, 'imaginary': imaginary}
