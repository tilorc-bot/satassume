"""The certificate of :class:`satassume.lra.LRATheory` for payloads with
constants (``pi``): whether no search over the registered atoms can give
up, and the bound ``Y`` within which a variable may split in a branch and
bound.  The argument is "Certified constants" in the docstring of
:mod:`satassume.lra`.  Only a theory whose payloads have constants
(:attr:`LRATheory.undecidable`) reads it, so it is a module of its own:
the rational case, every query without such constants, does not load it.
"""
from __future__ import annotations

import math
from fractions import Fraction
from itertools import islice
from typing import TYPE_CHECKING

from . import constfield as _cf

if TYPE_CHECKING:  # pragma: no cover
    from .lra import LRATheory

__all__ = ["CertAtoms", "certify", "limits", "within"]

_ONE = Fraction(1)

_PI = _cf.PI.numerator[0]                   # the index of pi's indeterminate
#: with constants, a variable splits in a branch and bound only while its
#: value is at most 2**_GROWTH times what a combination of atom bounds can
#: reach (LRATheory._certify: the room certification leaves branch bounds)
_GROWTH = 16


def _laurent(x) -> dict | None:
    """``{j: c}`` with ``x = sum(c * pi**j)`` (rational ``c != 0``, integer
    ``j``, negative too) for a Fraction, or an Element in pi alone whose
    denominator is a power of pi; None for any other number."""
    if type(x) is Fraction:
        return {0: x} if x else {}
    n, d = x.numerator, x.denominator
    if type(d) is Fraction:
        j0 = 0
    else:
        cs = d[1]
        if d[0] != _PI or cs[-1] != 1 or any(type(c) is not Fraction or c for c in cs[:-1]):
            return None
        j0, d = len(cs) - 1, _ONE
    if d != 1:
        n = _cf._scale(n, 1 / d)
    if type(n) is Fraction:
        return {-j0: n}
    if n[0] != _PI or any(type(c) is not Fraction for c in n[1]):
        return None
    return {i - j0: c for i, c in enumerate(n[1]) if c}


def _ceil_abs(c: Fraction) -> int:
    return -(-abs(c.numerator) // c.denominator)


def _magnitude(lx: dict) -> int:
    """An integer upper bound of ``|sum(c * pi**j)|`` (``pi**j <= 4**j``,
    and ``<= 1`` for ``j <= 0``)."""
    return sum(_ceil_abs(c) << (2 * j if j > 0 else 0) for j, c in lx.items())


def within(q, bound: Fraction) -> bool:
    """``|q| <= bound`` shown by an enclosure at constfield's first
    precision (never raises; False when it does not show it)."""
    if type(q) is Fraction:
        return abs(q) <= bound
    e = q.enclosure(_cf.PREC_START)
    if e is None:
        return False
    s = bound * (1 << _cf.PREC_START)
    return -s <= e[0] and e[1] <= s


def _window(exps: set) -> bool:
    """Every number with these exponents is ``pi**j0 * (a + b*pi)``,
    ``j0`` in {-1, 0}: its numerator in constfield has degree <= 1 and its
    denominator is 1 or pi."""
    return exps <= {0, 1} or exps <= {-1, 0}


def _decided(den: int, height: int) -> bool:
    """Whether constfield decides, by ``PREC_CAP``, the sign of every
    ``pi**j0 * (A + B*pi) / den`` (``j0`` in {-1, 0}, integers ``A, B``
    with ``|A|, |B| <= height``, not both 0) and the floor of every such
    number with an irrational value.  Mahler (1953): ``|pi - p/q| >
    q**-42`` for integers ``q >= 2``, so ``|A + B*pi| >= 1/(8*|B|**41)``
    (for ``B != 0``, and ``>= 1/den`` otherwise); constfield's interval
    evaluation errs by at most ``(3*|B| + 8) * 2**-prec`` (a pi enclosure
    a few units wide).  For a floor ``B`` is replaced by ``B - N*den`` for
    the integers ``N`` within 1 of the value, and an extra factor 4 covers
    the division by pi: ``3*height + 2*den`` and 8 bits cover both."""
    return (den.bit_length() + 41 * (3 * height + 2 * den).bit_length()
            + (3 * height + 8).bit_length() + 8 <= _cf.PREC_CAP)


#: what the certificate's size argument assumes of constfield's budget:
#: every number a certified search computes has a numerator and a
#: denominator of degree at most _CERT_DEGREE in pi (so at most
#: _CERT_DEGREE + 1 terms), and constfield multiplies two of them on the
#: way (degrees add, the work is terms times terms)
_CERT_DEGREE = 3


def limits() -> tuple:
    """constfield's current precision and size limits (read at every
    certification: a test or a user may change them)."""
    return (_cf.PREC_START, _cf.PREC_CAP, _cf.MAX_DEGREE, _cf.MAX_TERMS, _cf.MAX_BITS,
            _cf.MAX_WORK)


def _limits_suffice() -> bool:
    """Whether constfield's current size budget admits what the
    certificate's argument assumes (degrees below ``_CERT_DEGREE + 1``,
    their products, the term counts and the work of those products);
    below it a certified search could raise TooLarge, so nothing is
    certified.  The coefficient bits are checked against ``MAX_BITS`` in
    :meth:`LRATheory._certify` and the precision in :func:`_decided`."""
    t = _CERT_DEGREE + 1
    return (_cf.MAX_DEGREE >= 2 * _CERT_DEGREE and _cf.MAX_TERMS >= 2 * t - 1
            and _cf.MAX_WORK >= t * t and _cf.PREC_START <= _cf.PREC_CAP)


class CertAtoms:
    """The registered atoms' part of :meth:`LRATheory._certify`, gathered
    incrementally (atoms, integrality atoms and forms are only ever
    added, and dicts keep their order)."""

    __slots__ = ("ok", "na", "ni", "nf", "exps", "den", "top", "X", "neq", "had", "ints")

    def __init__(self) -> None:
        self.ok = True
        self.na = self.ni = self.nf = 0
        self.exps: set = set()              # exponents of pi in atom bounds
        self.den = 1                        # lcm of their denominators
        self.top = 0                        # an integer >= every |coefficient|
        self.X = 0                          # an integer >= every |bound|
        self.neq = 0                        # = and != atoms
        self.had = 1                        # Hadamard bound of the rows
        #: per integrality atom m*v + k, m = mu*pi**e: (e, mu, Laurent
        #: exponents of k, lcm of the denominators its branch bounds can
        #: have, their largest |coefficient| beside n/mu, and the part of
        #: |n/mu - k_0/mu| beyond the value bound: (|k| + 1 + |k_0|)/|mu|,
        #: the lcm of k's denominators and the largest |numerator| over it)
        self.ints: list = []

    def update(self, t: LRATheory) -> bool:
        """Take in the atoms registered since (the newest, from the end of
        each dict); False when one is outside the certified kind of
        payload."""
        atoms, ints, forms = t._atoms, t._ints, t._slack_of
        if len(atoms) > self.na:
            for _, kind, b in islice(reversed(atoms.values()), len(atoms) - self.na):
                if kind == "=" or kind == "!=":
                    self.neq += 1
                if type(b) is Fraction:             # the common case, in ints
                    n, d = b.numerator, b.denominator
                    if n:
                        self.exps.add(0)
                        if d != 1:
                            self.den = math.lcm(self.den, d)
                        n = -(-abs(n) // d)
                        if n > self.top:
                            self.top = n
                        if n > self.X:
                            self.X = n
                    continue
                lb = _laurent(b)
                if lb is None:
                    return False
                for j, c in lb.items():
                    self.exps.add(j)
                    self.den = math.lcm(self.den, c.denominator)
                    self.top = max(self.top, _ceil_abs(c))
                self.X = max(self.X, _magnitude(lb))
            self.na = len(atoms)
        if len(ints) > self.ni:
            for _, m, k in islice(reversed(ints.values()), len(ints) - self.ni):
                lm, lk = _laurent(m), _laurent(k)
                if lm is None or lk is None or len(lm) != 1:
                    return False
                ((e, mu),) = lm.items()
                nm, dm = abs(mu.numerator), mu.denominator
                lkd = math.lcm(1, *(c.denominator for c in lk.values()))
                kc = max((abs(c.numerator) * (lkd // c.denominator) for c in lk.values()),
                         default=0)
                k0 = lk.get(0)
                big = _magnitude(lk) + 1 + (_ceil_abs(k0) if k0 is not None else 0)
                self.ints.append((
                    e, mu, frozenset(lk), math.lcm(nm, lkd * nm),
                    -(-kc * dm // (nm * lkd)),       # >= |c/mu| for c in k
                    -(-big * dm // nm), lkd, kc))
            self.ni = len(ints)
        if len(forms) > self.nf:
            # Hadamard: every minor of the integer rows (each form scaled by
            # the lcm of its denominators) is at most the product of their
            # norms; tableau entries are ratios of minors over det(basis)
            for form in islice(reversed(forms), len(forms) - self.nf):
                dl = 1
                for _, a in form:
                    if type(a) is not Fraction:
                        return False
                    dl = math.lcm(dl, a.denominator)
                n2 = dl * dl + sum((a.numerator * (dl // a.denominator)) ** 2 for _, a in form)
                r = math.isqrt(n2)
                self.had *= r + (r * r < n2)
            self.nf = len(forms)
        return True


def certify(t: LRATheory, values) -> tuple:
    """``(certified, Y)`` for the theory ``t`` (memoized by
    :meth:`satassume.lra.LRATheory._certificate`); the argument is
    "Certified constants" in the docstring of :mod:`satassume.lra`."""
    # The numbers a search can meet.  Values are rational combinations
    # (the tableau is rational) of the bounds ever set (a nonbasic
    # variable sits at 0 or at a bound it was given): the atom bounds,
    # and branch bounds (n - k)/m with |n| <= |m|*Y + |k| + 1, as a
    # variable splits only within Y (_branch).  Everything below is an
    # upper bound, monotone in the atoms.
    no = (False, None)
    if not _limits_suffice():
        return no
    g = t._cagg
    if g is None:
        g = t._cagg = CertAtoms()
    if not g.ok or not g.update(t):
        g.ok = False
        return no
    exps, den, top, X = set(g.exps), g.den, g.top, g.X
    had, neq, ints = g.had, g.neq, g.ints
    if values is not None:
        if values[0]:
            exps.add(0)
        vt = math.ceil(values[0])
        top, X = max(top, vt), max(X, vt)
        den = math.lcm(den, values[1])
    nt = len(t._key) - len(t._rows)   # nonbasic variables
    # a combination of atom bounds, with room for branch bounds to grow
    Y = (nt + 1) * had * (X + 1) << _GROWTH
    for e, mu, ek, dk, ck, nk, _, _ in ints:
        # (n - k)/m, |n| <= |m|*Y + |k| + 1, |m| <= |mu|*4**max(e, 0)
        exps.add(-e)
        exps.update(j - e for j in ek)
        den = math.lcm(den, dk)
        top = max(top, ck, ((4 ** e if e > 0 else 1) * Y) + nk)
    if not _window(exps):
        return no
    if any(not _window({j + e for j in exps} | ek | {0}) for e, _, ek, *_ in ints):
        return no
    hb = top * den
    # value minus bound, over det * den (det <= had)
    h1, d1 = (nt + 1) * had * hb, had * den
    # _concrete's delta candidates (value - bound)/(eps/det), and the
    # differences of two of them
    dc = den * (nt + 1) * had
    h3, d3 = 2 * h1 * dc, dc * dc
    checks = [(d1, h1), (d3, h3)]
    for _, mu, _, _, _, _, lkd, kc in ints:
        # floors of m*x + k, x a value
        dm, nm = mu.denominator, abs(mu.numerator)
        checks.append((had * den * dm * lkd,
                       nm * (nt + 1) * had * hb * lkd + kc * had * den * dm))
    if not all(_decided(d, h) for d, h in checks):
        return no
    # coefficients: a compared number's are fractions of at most
    # bits(h) + bits(d) bits; products of two such, and their sums,
    # stay within 8 times that (see _limits_suffice)
    if 8 * max(d.bit_length() + h.bit_length() for d, h in checks) + 64 > _cf.MAX_BITS:
        return no
    # sizes far below constfield's budget (degrees stay below 4, which
    # _limits_suffice checked against the current limits): the
    # weights t**i of _check's generic combination, t <= neq**2 + 1
    if neq * (neq * neq + 2).bit_length() > _cf.MAX_BITS // 8:
        return no
    return True, Y
