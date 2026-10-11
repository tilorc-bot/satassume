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


class Poly:
    """A term ``u`` that is a product of powers of integral linear forms
    over *base* columns: ``u = prod_i (a_i . x + c_i)**k_i`` (integer
    ``a_i``, ``c_i``; ``k_i >= 1``).  When every base is an integer, so is
    ``u``, and ``u``'s residue modulo ``m`` is a function of the bases'
    residues modulo ``m``: :func:`_poly_step` turns that into rows of the
    lattice (stage B of T2)."""

    __slots__ = ("u", "bases", "cols", "factors")

    def __init__(self, u: int, bases: Tuple[int, ...], factors):
        self.u = u
        self.bases = bases            # the base columns, in a fixed order
        self.cols = frozenset(bases)
        self.factors = tuple(factors)  # (coefficients by base, constant, k)

    def value(self, r, m: int) -> int:
        """``u`` modulo ``m`` at base residues ``r``."""
        out = 1
        for a, c, k in self.factors:
            out = out * pow((sum(x * y for x, y in zip(a, r)) + c) % m, k, m) % m
        return out


#: the moduli :func:`_poly_step` works with: prime powers ``p**e`` of the
#: lattice's ``d`` with ``p <= MAX_P``, ``e`` lowered to ``p**e <= MAX_MOD``
#: (relations modulo a divisor of ``d`` are rows of the lattice too)
MAX_P = 13
MAX_MOD = 64
#: the base residue vectors enumerated per modulus (more: the modulus is
#: skipped, which only loses relations)
MAX_POINTS = 256


def _moduli(d: int) -> List[Tuple[int, int]]:
    """``(p, e)`` for :data:`MAX_P`-small primes ``p`` of ``d``."""
    out = []
    for p in (2, 3, 5, 7, 11, 13):
        if p > MAX_P or d % p:
            continue
        e, q = 0, d
        while q % p == 0 and p ** (e + 1) <= MAX_MOD:
            q //= p
            e += 1
        if e:
            out.append((p, e))
    return out


def _residue(rows: dict, col: int, d: int, p: int, e: int):
    """``(j, a, why)``: the largest ``j <= e`` and ``a`` (``0 <= a <
    p**j``) with ``(x - a)/p**j`` in the lattice, ``x`` the term of
    ``col``; ``why`` the reason.

    ``x/q`` is reduced by the rows down to a constant ``w/d`` (else no
    ``(x - a)/q`` is in the lattice, nor any ``(x - a)/(p*q)``); then
    ``(x - a)/q`` is in it iff ``w/d - a/q`` is an integer (the lattice's
    constants are the integers: no conflict), i.e. ``d/q`` divides ``w``
    and ``a == w/(d/q) (mod q)``."""
    j, a, why = 0, 0, _EMPTY
    while j < e:
        q = p ** (j + 1)
        s = d // q
        f = {col: s}
        w = _EMPTY
        while True:
            k = min(f)
            if k == CONST:
                break
            r = rows.get(k)
            if r is None:
                return j, a, why
            rv, rwhy = r
            t, m = divmod(f[k], rv[k])
            if m:
                return j, a, why
            f = _comb(1, f, -t, rv)
            if rwhy:
                w = w | rwhy
            if not f:
                break
        c = f.get(CONST, 0)
        if c % s:
            return j, a, why
        j, a, why = j + 1, (c // s) % q, why | w
    return j, a, why


def _kernel(points, n: int, m: int) -> List[List[int]]:
    """Vectors ``B`` with ``span(B) + m*Z^n`` the integer vectors ``v``
    with ``v . a == 0 (mod m)`` for every ``a`` of ``points``.

    Start from ``Z^n``.  For a point ``a``, a unimodular change of basis
    (Euclid on the values ``b . a``) leaves one vector with a nonzero
    value ``g`` (mod ``m``); that vector times ``m/gcd(g, m)`` and the
    others span the vectors of the old lattice that satisfy ``a``.  The
    vectors ``m*w`` satisfy every point, so the basis is kept mod ``m``."""
    basis = [[int(i == j) for j in range(n)] for i in range(n)]
    for a in points:
        s = [sum(x * y for x, y in zip(b, a)) % m for b in basis]
        nz = [i for i in range(n) if s[i]]
        if not nz:
            continue
        i0 = nz[0]
        for i in nz[1:]:
            g, x, y = _bezout(s[i0], s[i])
            u, w = basis[i0], basis[i]
            basis[i0] = [(x * p + y * q) % m for p, q in zip(u, w)]
            basis[i] = [((s[i] // g) * p - (s[i0] // g) * q) % m for p, q in zip(u, w)]
            s[i0] = g
        k = m // gcd(s[i0], m)
        basis[i0] = [(k * p) % m for p in basis[i0]]
    return basis


def _points(poly: Poly, facts, p: int, e: int):
    """The vectors ``(u, x_1, ..., x_k, 1)`` modulo ``p**e`` over the base
    residues allowed by ``facts`` (``(j, a)`` per base, then ``u``'s), or
    None if there are more than :data:`MAX_POINTS`."""
    m = p ** e
    ranges = []
    size = 1
    for j, a in facts[:-1]:
        step = p ** j
        size *= m // step
        if size > MAX_POINTS:
            return None
        ranges.append(range(a, m, step))
    ju, au = facts[-1]
    qu = p ** ju
    out = set()
    for r in _product(ranges):
        val = poly.value(r, m)
        if val % qu == au:
            out.add((val,) + r + (1,))
    return out


def _product(ranges):
    out = [()]
    for rg in ranges:
        out = [t + (x,) for t in out for x in rg]
    return out


#: (factors, residue facts, p, e) -> the kernel of :func:`_points` (a pure
#: function of the key; bounded by clearing)
_KERNELS: dict = {}


def _relations(poly: Poly, fp, p: int, e: int):
    """The kernel basis for ``poly`` at the residue facts ``fp`` modulo
    ``p**e`` (None: too many residue vectors), cached."""
    key = (poly.factors, fp, p, e)
    out = _KERNELS.get(key, _MARK)
    if out is _MARK:
        pts = _points(poly, fp, p, e)
        out = None if pts is None else _kernel(pts, len(poly.bases) + 2, p ** e)
        if len(_KERNELS) > 4096:
            _KERNELS.clear()
        _KERNELS[key] = out
    return out


def _poly_step(rows: dict, supp: set, polys, pdone: dict, d: int, focus=None) -> bool:
    """Insert the rows the products ``polys`` give (whose bases are
    integral in the lattice ``rows``); True iff the lattice grew.

    For a product ``u`` of integral forms of integer bases ``x``: ``u`` is
    an integer, and for each modulus ``m = p**e`` of :func:`_moduli` the
    relations ``(c_u*u + c . x + c_0)/m`` integral that hold at every
    residue vector of the bases modulo ``m`` that the lattice allows
    (residues of each base and of ``u`` alone, :func:`_residue`) are
    integral: ``u``'s value is the polynomial of the bases' values, and
    the residues the lattice allows contain the actual ones.  No vector
    allowed: the relation ``1/m``, a conflict.  The reason: the
    literals that make the bases integral and give those residues.
    ``pdone``: per product, the residues it was last stepped with (the
    lattice only grows, so the same residues add nothing new).  ``focus``:
    if given, only the products with a column in it are looked at."""
    grew = False
    mods = None
    for i, P in enumerate(polys):
        if not P.cols <= supp:
            continue
        if focus is not None and P.u not in focus and not (P.cols & focus):
            continue
        why = _EMPTY
        for c in P.bases:
            w = reduce(rows, {c: d})
            if w is None:
                break
            why = why | w
        else:
            if mods is None:
                mods = _moduli(d)
            cols = P.bases + (P.u,)
            facts = []
            for p, e in mods:
                fp = []
                for c in cols:
                    j, a, w = _residue(rows, c, d, p, e)
                    fp.append((j, a))
                    if w:
                        why = why | w
                facts.append(tuple(fp))
            sig = (d, tuple(facts))
            if pdone.get(i) == sig:
                continue
            pdone[i] = sig
            vecs = [{P.u: d}]
            order = (P.u,) + P.bases
            for (p, e), fp in zip(mods, facts):
                basis = _relations(P, fp, p, e)
                if basis is None:
                    continue
                s = d // p ** e
                for b in basis:
                    v = {k: s * x for k, x in zip(order, b) if x}
                    if b[-1]:
                        v[CONST] = s * b[-1]
                    if v:
                        vecs.append(v)
            for v in vecs:
                if reduce(rows, v) is None:
                    insert(rows, v, why)
                    supp.add(P.u)
                    grew = True
    return grew


def _close(rows: dict, supp: set, negs: list, used: set, d: int,
           start: int = 0, polys=(), pdone=None, focus=None) -> Optional[FrozenSet[int]]:
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
        if not changed and polys:
            changed = _poly_step(rows, supp, polys, pdone, d, focus)
        if not changed:
            return None
        start = 0


class Lattice:
    """The closure of integral forms and non-integral forms (scaled by
    ``d``), with reasons.  :attr:`rows`: the module; :attr:`negs`: the
    ``(form, literal, columns)`` asserted non-integral; :attr:`conflict`:
    the literals of a conflict, or None; :attr:`supp`: the term columns of
    the rows."""

    __slots__ = ("d", "rows", "negs", "used", "conflict", "supp", "polys", "pdone",
                 "pdirty")

    def __init__(self, d: int, polys=()):
        self.d = d
        self.polys = polys      # the products (:class:`Poly`)
        self.pdone: dict = {}   # :func:`_poly_step`'s memo
        self.pdirty = False     # rows added since the products' last step
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
        c.polys = self.polys
        c.pdone = dict(self.pdone)
        c.pdirty = self.pdirty
        return c

    def add_pos(self, f: Vec, lit: int, cols) -> None:
        if self.conflict is not None:
            return
        insert(self.rows, f, frozenset((lit,)))
        self.supp.update(cols)
        self.conflict = _close(self.rows, self.supp, self.negs, self.used, self.d)
        self.pdirty = True

    def add_neg(self, h: Vec, lit: int, cols) -> None:
        if self.conflict is not None:
            return
        self.negs.append((h, lit, cols))
        if cols <= self.supp:
            self.conflict = _close(self.rows, self.supp, self.negs, self.used, self.d,
                                   len(self.negs) - 1)
            self.pdirty = True

    def settle(self) -> None:
        """Close under the products' step too (once per batch of
        insertions: :meth:`IntLatTheory.lattice`)."""
        if self.pdirty:
            self.pdirty = False
            if self.polys and self.conflict is None:
                self.conflict = _close(self.rows, self.supp, self.negs, self.used, self.d,
                                       len(self.negs), self.polys, self.pdone)

    def implies(self, f: Vec) -> Optional[FrozenSet[int]]:
        """The reason of ``f`` integral, or None."""
        return reduce(self.rows, f)

    def refutes(self, f: Vec, cols) -> Optional[FrozenSet[int]]:
        """The reason of ``f`` not integral, or None: ``M + Z*f`` (closed
        again) is in conflict."""
        rows = dict(self.rows)
        insert(rows, f, _MARK)
        # without the products' step: what it would find here, the search
        # finds by asserting f (a conflict of the closed lattice)
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
        self.polys: List[Poly] = []          # products of integral forms
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

    def define_poly(self, poly: Poly) -> None:
        """Tell the theory that the term of column ``poly.u`` is that
        product (the lattices are rebuilt with it)."""
        self.polys.append(poly)
        self.lat = None
        self.lim = [(k, None) for k, _ in self.lim]
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
        lat = Lattice(self.d, self.polys)
        form, cols = self.form, self.cols
        for l in lits:
            if l > 0:
                lat.add_pos(form[l], l, cols[l])
            elif -l not in self.inexact:
                lat.add_neg(form[-l], l, cols[-l])
            if lat.conflict is not None:
                break
        lat.settle()
        return lat

    def lattice(self) -> Lattice:
        lat = self.lat
        if lat is None:
            val = self.val
            lat = self.lat = self._build([v if val[v] else -v for v in self.trail])
            self.shared = False
            self.stats["builds"] += 1
        elif lat.pdirty:
            if self.shared:
                lat = self.lat = lat.copy()
                self.shared = False
            lat.settle()
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
