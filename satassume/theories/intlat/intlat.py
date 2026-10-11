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

**Representation.**  Every form is scaled by ``D``, the least common
multiple of 2 and of the denominators of the registered forms, so the
lattice is one of integer vectors (``D*M``; the constant ``1`` is ``D`` at
:data:`CONST`).  The lattice of each decision level is kept (copied on
the first change of a level) and grows by one insertion per asserted
literal.  Reasons are the asserted literals the derivation used (a
superset kept per lattice row, minimised by deletion when short).
"""
from __future__ import annotations

from fractions import Fraction
from math import gcd
from typing import Dict, FrozenSet, List, Optional, Tuple

#: the column of the constant (after every term column: echelon order puts
#: the constant row last, so it is ``M``'s intersection with the constants)
CONST = 1 << 40

Vec = Dict[int, int]

_EMPTY: FrozenSet[int] = frozenset()
_MARK: FrozenSet[int] = frozenset((0,))


def _bezout(a: int, b: int) -> Tuple[int, int, int]:
    """``(g, x, y)`` with ``a*x + b*y == g == gcd(a, b) > 0``."""
    x0, x1, y0, y1 = 1, 0, 0, 1
    while b:
        q = a // b
        a, b = b, a - q * b
        x0, x1 = x1, x0 - q * x1
        y0, y1 = y1, y0 - q * y1
    return (a, x0, y0) if a > 0 else (-a, -x0, -y0)


def _comb(a: int, u: Vec, b: int, v: Vec) -> Vec:
    """``a*u + b*v`` (a new dict, zero entries dropped)."""
    out: Vec = {k: a * x for k, x in u.items()} if a else {}
    if b:
        for k, x in v.items():
            y = out.get(k, 0) + b * x
            if y:
                out[k] = y
            else:
                del out[k]
    return out


def insert(rows: dict, v: Vec, why: FrozenSet[int]) -> None:
    """Add ``v`` (with reason ``why``) to the lattice ``rows`` (pivot
    column -> ``(row, reason)``, echelon form over Z) in place."""
    while v:
        p = min(v)
        r = rows.get(p)
        if r is None:
            rows[p] = (v, why)
            return
        rv, rwhy = r
        a, b = rv[p], v[p]
        if rwhy is not why:
            why = why | rwhy
        if b % a == 0:
            v = _comb(1, v, -(b // a), rv)
            continue
        # the Euclidean step: x*a + y*b = g, the gcd of the pivots; the
        # rows x*r + y*v (pivot g) and (b/g)*r - (a/g)*v (pivot 0) span
        # the same lattice as r and v (the 2x2 transformation is
        # unimodular)
        g, x, y = _bezout(a, b)
        rows[p] = (_comb(x, rv, y, v), why)
        v = _comb(b // g, rv, -(a // g), v)


def reduce(rows: dict, f: Vec) -> Optional[FrozenSet[int]]:
    """The reason of ``f`` in the lattice ``rows`` (the union of the rows
    used), or None if ``f`` is not in it."""
    why = _EMPTY
    while f:
        p = min(f)
        r = rows.get(p)
        if r is None:
            return None
        rv, rwhy = r
        q, m = divmod(f[p], rv[p])
        if m:
            return None
        f = _comb(1, f, -q, rv)
        if rwhy:
            why = why | rwhy
    return why


def _close(rows: dict, supp: set, negs: list, used: set, d: int,
           start: int = 0) -> Optional[FrozenSet[int]]:
    """Close the lattice ``rows`` (term columns ``supp``) under the parity
    step with the non-integral forms ``negs`` (``(form, literal,
    columns)``; ``used``: the indices already stepped) in place; the
    literals of a conflict, or None.  A form with a column outside
    ``supp`` is neither in the lattice nor twice in it.  ``start``: the
    lattice is closed for ``negs[:start]`` (only forms were appended
    since), so the first pass looks at the others only.

    A form ``h`` not stepped yet is looked at through ``2*h`` first: if
    ``2*h`` is not in the lattice, neither is ``h``.  A stepped form is not
    looked at again: ``h - 1/2`` is in the lattice, so ``h`` is iff ``1/2``
    is, which the constant row says (its reason holds the step's)."""
    while True:
        cv, cwhy = rows[CONST]
        if cv[CONST] % d:
            return cwhy
        changed = False
        for i in range(start, len(negs)):
            if i in used:
                continue
            h, lit, cols = negs[i]
            if not cols <= supp:
                continue
            w2 = reduce(rows, {k: 2 * x for k, x in h.items()})
            if w2 is None:
                continue
            w = reduce(rows, h)
            if w is not None:
                return w | {lit}
            # 2*h is an integer and h is not: h - 1/2 is one
            used.add(i)
            g = dict(h)
            y = g.get(CONST, 0) - d // 2
            if y:
                g[CONST] = y
            else:
                del g[CONST]
            insert(rows, g, w2 | {lit})
            changed = True
        if not changed:
            return None
        start = 0


class Lattice:
    """The closure of integral forms and non-integral forms (scaled by
    ``d``), with reasons.  :attr:`rows`: the module; :attr:`negs`: the
    ``(form, literal, columns)`` asserted non-integral; :attr:`conflict`:
    the literals of a conflict, or None; :attr:`supp`: the term columns of
    the rows."""

    __slots__ = ("d", "rows", "negs", "used", "conflict", "supp")

    def __init__(self, d: int):
        self.d = d
        self.rows = {CONST: ({CONST: d}, _EMPTY)}
        self.negs: list = []
        self.used: set = set()
        self.conflict: Optional[FrozenSet[int]] = None
        self.supp: set = set()

    def copy(self) -> "Lattice":
        c = Lattice.__new__(Lattice)
        c.d = self.d
        c.rows = dict(self.rows)
        c.negs = list(self.negs)
        c.used = set(self.used)
        c.conflict = self.conflict
        c.supp = set(self.supp)
        return c

    def add_pos(self, f: Vec, lit: int, cols) -> None:
        if self.conflict is not None:
            return
        insert(self.rows, f, frozenset((lit,)))
        self.supp.update(cols)
        self.conflict = _close(self.rows, self.supp, self.negs, self.used, self.d)

    def add_neg(self, h: Vec, lit: int, cols) -> None:
        if self.conflict is not None:
            return
        self.negs.append((h, lit, cols))
        if cols <= self.supp:
            self.conflict = _close(self.rows, self.supp, self.negs, self.used, self.d,
                                   len(self.negs) - 1)

    def implies(self, f: Vec) -> Optional[FrozenSet[int]]:
        """The reason of ``f`` integral, or None."""
        return reduce(self.rows, f)

    def refutes(self, f: Vec, cols) -> Optional[FrozenSet[int]]:
        """The reason of ``f`` not integral, or None: ``M + Z*f`` (closed
        again) is in conflict."""
        rows = dict(self.rows)
        insert(rows, f, _MARK)
        w = _close(rows, self.supp | cols, self.negs, set(self.used), self.d)
        if w is None or 0 not in w:
            return None
        return w - _MARK


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
    MIN_WHY = 8

    def __init__(self):
        self.frac: Dict[int, Dict[int, Fraction]] = {}   # variable -> form
        self.form: Dict[int, Vec] = {}       # variable -> form scaled by d
        self.cols: Dict[int, frozenset] = {}  # variable -> its term columns
        self.inexact: set = set()
        self.d = 2
        self.order: List[int] = []           # registered variables
        self.val: Dict[int, bool] = {}
        self.trail: List[int] = []
        self.lim: List[Tuple[int, Optional[Lattice]]] = []
        self.lat: Optional[Lattice] = None   # of the trail (None: rebuild)
        self.shared = False                  # lat is saved by a level
        self._done = False                   # propagated since the last change
        self.stats = {"props": 0, "conflicts": 0, "builds": 0}

    # -- the contract -----------------------------------------------------
    def register_atom(self, v: int, payload) -> None:
        if v in self.frac:
            return
        f, exact = payload
        self.frac[v] = f
        if not exact:
            self.inexact.add(v)
        d = self.d
        for x in f.values():
            q = x.denominator
            if d % q:
                d = d * q // gcd(d, q)
        if d != self.d:
            # a new denominator: rescale every form, rebuild the lattices
            self.d = d
            for u, g in self.frac.items():
                self.form[u] = {k: int(x * d) for k, x in g.items()}
            self.lat = None
            self.lim = [(k, None) for k, _ in self.lim]
        else:
            self.form[v] = {k: int(x * d) for k, x in f.items()}
        self.cols[v] = frozenset(k for k in f if k != CONST)
        self.order.append(v)
        self._done = False

    def assert_lit(self, lit: int):
        v = lit if lit > 0 else -lit
        if v not in self.frac or v in self.val:
            return None
        self.val[v] = lit > 0
        self.trail.append(v)
        self._done = False
        lat = self.lat
        if lat is None:
            return None
        if lit < 0 and v in self.inexact:
            return None
        if self.shared:
            lat = self.lat = lat.copy()
            self.shared = False
        if lit > 0:
            lat.add_pos(self.form[v], v, self.cols[v])
        else:
            lat.add_neg(self.form[v], lit, self.cols[v])
        return None

    def push_level(self) -> None:
        self.lim.append((len(self.trail), self.lat))
        self.shared = True

    def pop_level(self) -> None:
        k, lat = self.lim.pop()
        trail, val = self.trail, self.val
        while len(trail) > k:
            del val[trail.pop()]
        self.lat = lat
        self.shared = True
        self._done = False

    # -- reasoning ---------------------------------------------------------
    def _build(self, lits) -> Lattice:
        lat = Lattice(self.d)
        form, cols = self.form, self.cols
        for l in lits:
            if l > 0:
                lat.add_pos(form[l], l, cols[l])
            elif -l not in self.inexact:
                lat.add_neg(form[-l], l, cols[-l])
            if lat.conflict is not None:
                break
        return lat

    def lattice(self) -> Lattice:
        lat = self.lat
        if lat is None:
            val = self.val
            lat = self.lat = self._build([v if val[v] else -v for v in self.trail])
            self.shared = False
            self.stats["builds"] += 1
        return lat

    def _minimise(self, why, test):
        """Drop literals of ``why`` that ``test`` (on a literal subset:
        still derivable?) does not need."""
        if len(why) > self.MIN_WHY or len(why) <= 1:
            return list(why)
        keep = sorted(why, key=abs)
        i = 0
        while i < len(keep):
            trial = keep[:i] + keep[i + 1:]
            if test(trial):
                keep = trial
            else:
                i += 1
        return keep

    def _conflict(self, lat):
        why = self._minimise(lat.conflict, lambda ls: self._build(ls).conflict is not None)
        self.stats["conflicts"] += 1
        return [-l for l in why]

    def propagate(self):
        if self.gave_up or self._done:
            return ()
        self._done = True
        lat = self.lattice()
        if lat.conflict is not None:
            clause = self._conflict(lat)
            return [(clause[0], clause)]
        out = []
        val, form, cols, supp = self.val, self.form, self.cols, lat.supp
        # a form with columns outside the lattice's support is not in it,
        # and M + Z*f can only meet a non-integral form h with the same
        # columns outside it (h - k*f in M for some k != 0)
        outs = {}
        for h, _, hc in lat.negs:
            o = hc - supp
            if o:
                outs[o] = True
        for v in self.order:
            if v in val:
                continue
            fc = cols[v]
            out_f = fc - supp
            if out_f and out_f not in outs:
                continue
            f = form[v]
            if not out_f and v not in self.inexact:
                why = lat.implies(f)
                if why is not None:
                    why = self._minimise(why, lambda ls, f=f: self._build(ls).implies(f) is not None)
                    out.append((v, [v] + [-l for l in why]))
                    self.stats["props"] += 1
                    continue
            why = lat.refutes(f, fc)
            if why is not None:
                why = self._minimise(why, lambda ls, f=f, fc=fc: self._build(ls).refutes(f, fc) is not None)
                out.append((-v, [-v] + [-l for l in why]))
                self.stats["props"] += 1
        return out

    def check(self):
        if self.gave_up:
            return None
        lat = self.lattice()
        if lat.conflict is not None:
            return (False, self._conflict(lat))
        return None
