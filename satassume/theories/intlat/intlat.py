"""INTLAT: the lattice of integral linear forms (issue #149, proposal T2).

An atom of this theory says that a *form* ``c_1*u_1 + ... + c_k*u_k + c``
(rational ``c_i``, ``c``; opaque terms ``u_i``) is an integer.  The adapter
(:mod:`.intlat_adapter`) reads ``integer(e)`` as the form of ``e`` and
``even(e)`` as the form of ``e/2``, so ``odd(e)`` (``integer & !even``) is
"``e`` integral and ``e/2`` not".  No SymPy import.

**What it decides.**  The forms asserted integral generate, with the
constant ``1``, a Z-module ``M`` of rational vectors; every form in ``M`` is
an integer (an integer combination of integers).  The theory keeps ``M`` in
echelon form over Z (Hermite's reduction with the Euclidean step on
rational pivots) and derives:

* a conflict when ``M`` holds a non-integer constant (``x`` and ``x + 1/2``
  both integral), or holds a form asserted non-integral;
* ``f`` integral for an atom whose form lies in ``M``;
* ``f`` not integral when ``M + Z*f`` holds a non-integer constant
  (``x/2 + 1/3`` under ``integer(x)``: ``6*(x/2 + 1/3) - 3*x = 2``) or a
  form asserted non-integral (``~even(x + y) & even(y)`` gives
  ``~even(x)``);
* the parity step: a form ``h`` asserted non-integral with ``2*h`` in
  ``M`` is a half-odd integer, so ``h - 1/2`` joins ``M`` (``odd(x)``:
  ``x`` integral, ``x/2`` not, hence ``(x - 1)/2`` integral; two odd
  terms then make an even sum).

**Soundness.**  The atoms are about values: ``integer(e)`` holds iff the
value of ``e`` is an integer, ``even(e)`` iff the value of ``e/2`` is.  The
adapter reads a form only through sums and products with a nonzero
rational coefficient, each of which is infinite or ``nan`` as soon as an
argument is, and a Float wherever an argument is a Float.  So a form
asserted integral has finite, exact terms, and its value is the
rational combination of their values; every conclusion above is an
identity between such combinations (a conclusion about ``f`` uses only
asserted forms whose terms include all of ``f``'s, or ``f``'s
integrality as a premise).  A non-integral atom says nothing about its
terms (``oo``, ``nan`` and Floats are non-integers): it is only ever used
against an ``M`` whose own literals make its terms finite and exact.

Reasons are the asserted literals the derivation used (a superset kept
per lattice row, minimised by deletion when short enough).
"""
from __future__ import annotations

from fractions import Fraction
from typing import Dict, FrozenSet, List, Optional, Tuple

#: the column of the constant (after every term column: echelon order puts
#: the constant row last, so it is ``M``'s intersection with the constants)
CONST = 1 << 40

Vec = Dict[int, Fraction]
Rows = Dict[int, Tuple[Vec, FrozenSet[int]]]

_EMPTY: FrozenSet[int] = frozenset()
_ONE = Fraction(1)
_HALF = Fraction(1, 2)


def _bezout(a: int, b: int) -> Tuple[int, int]:
    """``(x, y)`` with ``a*x + b*y == gcd(a, b)`` (``a, b`` coprime here)."""
    x0, x1, y0, y1 = 1, 0, 0, 1
    while b:
        q, a, b = a // b, b, a - (a // b) * b
        x0, x1 = x1, x0 - q * x1
        y0, y1 = y1, y0 - q * y1
    return (x0, y0) if a > 0 else (-x0, -y0)


def _comb(a: Fraction, u: Vec, b: Fraction, v: Vec) -> Vec:
    """``a*u + b*v`` (new dict, zero entries dropped)."""
    out: Vec = {}
    if a:
        for k, x in u.items():
            out[k] = a * x
    if b:
        for k, x in v.items():
            y = out.get(k, 0) + b * x
            if y:
                out[k] = y
            else:
                out.pop(k, None)
    return out


def insert(rows: Rows, v: Vec, why: FrozenSet[int]) -> None:
    """Add ``v`` (with reason ``why``) to the lattice ``rows`` in place:
    echelon form over Z, one row per pivot column."""
    while v:
        p = min(v)
        r = rows.get(p)
        if r is None:
            rows[p] = (v, why)
            return
        rv, rwhy = r
        a, b = rv[p], v[p]
        q = b / a
        why = why | rwhy
        if q.denominator == 1:
            v = _comb(_ONE, v, -q, rv)
            continue
        # gcd step: q = P/Qd in lowest terms, a = Qd*g, b = P*g with g the
        # gcd; x*Qd + y*P = 1 gives a row with pivot g, and Qd*v - P*r
        # clears the column (the 2x2 transformation is unimodular)
        P, Qd = q.numerator, q.denominator
        x, y = _bezout(Qd, P)
        rows[p] = (_comb(Fraction(x), rv, Fraction(y), v), why)
        v = _comb(Fraction(Qd), v, Fraction(-P), rv)


def reduce(rows: Rows, f: Vec) -> Optional[FrozenSet[int]]:
    """The reason of ``f`` in the lattice ``rows`` (the union of the rows
    used), or None if ``f`` is not in it."""
    why = _EMPTY
    while f:
        p = min(f)
        r = rows.get(p)
        if r is None:
            return None
        rv, rwhy = r
        q = f[p] / rv[p]
        if q.denominator != 1:
            return None
        f = _comb(_ONE, f, -q, rv)
        why = why | rwhy
    return why


def const_conflict(rows: Rows) -> Optional[FrozenSet[int]]:
    """The reason of a non-integer constant in the lattice, or None."""
    r = rows.get(CONST)
    if r is None:
        return None
    c = r[0][CONST]
    if c.denominator != 1:
        return r[1]
    return None


def scale(f: Vec, c: Fraction) -> Vec:
    return {k: c * x for k, x in f.items()}


def shift(f: Vec, c: Fraction) -> Vec:
    out = dict(f)
    y = out.get(CONST, 0) + c
    if y:
        out[CONST] = y
    else:
        out.pop(CONST, None)
    return out


class Lattice:
    """The closure of a set of integral forms (``pos``: ``(form, lit)``)
    and non-integral forms (``neg``), with reasons: :attr:`rows` is the
    module, :attr:`conflict` a reason clause's negation (the literals) or
    None."""

    __slots__ = ("rows", "conflict", "neg")

    def __init__(self, pos, neg):
        rows: Rows = {CONST: ({CONST: _ONE}, _EMPTY)}
        for f, lit in pos:
            insert(rows, f, frozenset((lit,)))
        self.rows = rows
        self.neg = neg
        self.conflict = None
        self._close()

    def _close(self) -> None:
        rows = self.rows
        used = set()
        changed = True
        while changed:
            changed = False
            c = const_conflict(rows)
            if c is not None:
                self.conflict = c
                return
            for i, (h, lit) in enumerate(self.neg):
                w = reduce(rows, h)
                if w is not None:
                    self.conflict = w | {lit}
                    return
                if i in used:
                    continue
                w = reduce(rows, scale(h, Fraction(2)))
                if w is not None:
                    # 2*h is an integer and h is not: h - 1/2 is one
                    used.add(i)
                    insert(rows, shift(h, -_HALF), w | {lit})
                    changed = True

    def implies(self, f: Vec) -> Optional[FrozenSet[int]]:
        """The reason of ``f`` integral, or None."""
        return reduce(self.rows, f)

    def refutes(self, f: Vec) -> Optional[FrozenSet[int]]:
        """The reason of ``f`` not integral (``M + Z*f`` holds a non-integer
        constant or a form asserted non-integral, after the parity step),
        or None."""
        rows = dict(self.rows)
        insert(rows, f, frozenset((0,)))
        c = const_conflict(rows)
        if c is not None:
            return c - {0}
        for h, lit in self.neg:
            w = reduce(rows, h)
            if w is not None:
                return (w | {lit}) - {0}
        # the parity step under f: h non-integral with 2*h in M + Z*f
        # gives h - 1/2, which may meet the constant or another h
        extra = []
        for h, lit in self.neg:
            w = reduce(rows, scale(h, Fraction(2)))
            if w is not None:
                extra.append((shift(h, -_HALF), w | {lit}))
        if not extra:
            return None
        for g, w in extra:
            insert(rows, g, w)
        c = const_conflict(rows)
        if c is not None:
            return c - {0}
        for h, lit in self.neg:
            w = reduce(rows, h)
            if w is not None:
                return (w | {lit}) - {0}
        return None


class IntLatTheory:
    """The theory (contract: :mod:`satassume.sat.theory`).  Registered
    atoms: ``payload`` is ``(form, exact)``, the form a dict column ->
    Fraction (the constant at :data:`CONST`); ``v`` says the node's value
    is an integer.  ``exact`` is False for a node some of whose terms
    cancel in its form: its value may be infinite or ``nan`` while the
    form is an integer, so only its positive literal is read (it makes
    every term finite), and only its negation is derived."""

    gave_up = False
    #: reasons with at most this many literals are minimised by deletion
    MIN_WHY = 12

    def __init__(self):
        self.form: Dict[int, Vec] = {}
        self.inexact: set = set()
        self.order: List[int] = []           # registered variables
        self.val: Dict[int, bool] = {}
        self.trail: List[int] = []
        self.lim: List[int] = []
        self._lat: Optional[Lattice] = None  # of the current trail (None: stale)
        self._done = 0                       # trail length propagated
        self.stats = {"props": 0, "conflicts": 0, "builds": 0}

    # -- the contract -----------------------------------------------------
    def register_atom(self, v: int, payload) -> None:
        if v in self.form:
            return
        f, exact = payload
        self.form[v] = f
        if not exact:
            self.inexact.add(v)
        self.order.append(v)
        self._done = -1                     # a new atom may be implied

    def assert_lit(self, lit: int):
        v = lit if lit > 0 else -lit
        if v not in self.form or v in self.val:
            return None
        self.val[v] = lit > 0
        self.trail.append(v)
        self._lat = None
        return None

    def push_level(self) -> None:
        self.lim.append(len(self.trail))

    def pop_level(self) -> None:
        k = self.lim.pop()
        trail, val = self.trail, self.val
        if len(trail) > k:
            while len(trail) > k:
                del val[trail.pop()]
            self._lat = None
            self._done = -1

    # -- reasoning ---------------------------------------------------------
    def _lits(self):
        pos, neg = [], []
        form, val = self.form, self.val
        for v in self.trail:
            if val[v]:
                pos.append((form[v], v))
            elif v not in self.inexact:
                neg.append((form[v], -v))
        return pos, neg

    def lattice(self) -> Lattice:
        lat = self._lat
        if lat is None:
            pos, neg = self._lits()
            lat = self._lat = Lattice(pos, neg)
            self.stats["builds"] += 1
        return lat

    def _minimise(self, why, test):
        """Drop literals of ``why`` (a set of asserted literals) that
        ``test`` (a function of a literal subset: still derivable?) does
        not need."""
        if len(why) > self.MIN_WHY or len(why) <= 1:
            return why
        keep = sorted(why, key=abs)
        i = 0
        while i < len(keep):
            trial = keep[:i] + keep[i + 1:]
            if test(trial):
                keep = trial
            else:
                i += 1
        return keep

    def _sub(self, lits) -> Lattice:
        form = self.form
        pos = [(form[l], l) for l in lits if l > 0]
        neg = [(form[-l], l) for l in lits if l < 0]
        return Lattice(pos, neg)

    def propagate(self):
        if self.gave_up or self._done == len(self.trail):
            return ()
        lat = self.lattice()
        self._done = len(self.trail)
        if lat.conflict is not None:
            why = self._minimise(lat.conflict, lambda ls: self._sub(ls).conflict is not None)
            self.stats["conflicts"] += 1
            clause = [-l for l in why]
            return [(clause[0], clause)]
        out = []
        val, form = self.val, self.form
        for v in self.order:
            if v in val:
                continue
            f = form[v]
            why = lat.implies(f) if v not in self.inexact else None
            if why is not None:
                why = self._minimise(why, lambda ls, f=f: self._sub(ls).implies(f) is not None)
                out.append((v, [v] + [-l for l in why]))
                self.stats["props"] += 1
                continue
            why = lat.refutes(f)
            if why is not None:
                why = self._minimise(why, lambda ls, f=f: self._sub(ls).refutes(f) is not None)
                out.append((-v, [-v] + [-l for l in why]))
                self.stats["props"] += 1
        return out

    def check(self):
        if self.gave_up:
            return None
        lat = self.lattice()
        if lat.conflict is not None:
            why = self._minimise(lat.conflict, lambda ls: self._sub(ls).conflict is not None)
            self.stats["conflicts"] += 1
            return (False, [-l for l in why])
        return None
