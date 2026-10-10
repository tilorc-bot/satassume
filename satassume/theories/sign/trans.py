"""TRANS: transcendence of the values of ``exp``, ``log``, the trigonometric
and hyperbolic functions and their inverses, and of powers
(Lindemann-Weierstrass, Gelfond-Schneider; issue #149, proposal T6).

A class propagator (:mod:`.lattice`) whose nodes are *map* operations
(:meth:`.lattice.Lattice.add_map`): one unary table per function and one
binary table for ``Pow(b, e)``.  It replaces the hand-written transcendence
rows of the templates (``_TRANSCENDENTAL`` and its kin in
``templates/functions.py``, ``pow.E``, ``b=algebraic.gs`` and
``e=algebraic_irrational.gs`` in ``templates/core.py``) by one procedure
that works in both directions: forward (``exp(x)`` is transcendental for
algebraic nonzero ``x``) and backward (``exp(x)`` algebraic and ``x``
nonzero put ``x`` outside the algebraic numbers; ``2**e`` algebraic and
``e`` algebraic put ``e`` in the rationals).

**Atoms.**  The value of a term lies in one of 11 atoms, plus ``NAN``:

* ``Z0`` = {0}, ``ONE`` = {1}, ``ZI`` the integers other than 0 and 1,
  ``Q1`` the rationals that are not integers, ``AR``/``AC`` the real/
  non-real algebraic numbers that are not rational, ``TR``/``TC`` the
  real/non-real transcendental numbers (these eight partition the finite
  complex numbers).  ``ONE`` is apart because Gelfond-Schneider needs a
  base outside {0, 1} and ``exp(0) = 1``, ``log(1) = 0``, ``acos(1) = 0``;
* ``FX``: finite but not complex, vacuous as in :mod:`.closure` (no value
  in scope is one; every entry with ``FX`` is "no claim");
* ``IR`` (``oo``, ``-oo``) and ``IC`` (every other infinity);
* ``NAN``: the node may be ``nan`` or SymPy leaves it unevaluated with an
  ``AccumBounds`` value (``sin(oo)``): no claim.

A predicate is a set of atoms (:data:`PRED_MASK`): ``integer``,
``rational``, ``algebraic``, ``complex``, ``finite``, ``extended_real``,
``zero``, read and written.  The rule block's basis has no predicate that
separates ``ONE`` from ``ZI``; four predicates do so one way only and are
read, never written (*one-sided*, :data:`ONESIDED`): ``prime(x)`` and
``composite(x)`` put ``x`` in ``ZI``, ``even(x)`` in ``Z0 | ZI``,
``extended_negative(x)`` in the negative reals and ``-oo``.  Their
negations say nothing (``~prime(x)`` holds of 1 and of 4).

**Tables.**  Every entry over-approximates SymPy's value at every point of
the atoms (``tests/test_trans_theory.py`` checks each against SymPy at
sample points of every atom, ``0, 1, -1, 2, 1/2, sqrt(2), I, 1 + I,
sqrt(2)*I, pi, E, pi*I, oo, -oo, zoo, oo*I``).  The comment of each entry
says why it holds.  The theorems used:

* Lindemann-Weierstrass (LW): ``exp(a)`` is transcendental for algebraic
  ``a != 0``.  Hence for algebraic ``a != 0``: ``sin``, ``cos``, ``tan``,
  ``cot``, ``sinh``, ``cosh``, ``tanh`` of ``a`` are transcendental (each
  is a rational function of ``exp(I*a)`` or ``exp(a)``, ``exp(2*I*a)``
  algebraic would make it algebraic and ``exp(2*I*a)`` is transcendental);
  ``log(a)`` is transcendental for ``a`` not 0 or 1 (``log(a) = b``
  algebraic nonzero gives ``exp(b) = a`` algebraic); ``asin``, ``acos``,
  ``atan``, ``acot`` of ``a`` are transcendental where finite and nonzero
  (``asin(a) = b`` algebraic nonzero gives ``sin(b) = a`` algebraic).
* Gelfond-Schneider (GS): ``b**e`` is transcendental for algebraic ``b``
  not 0 or 1 and algebraic irrational ``e`` (every branch, so SymPy's
  principal one).
* Algebraic closure: ``b**(p/q)`` is algebraic for algebraic ``b != 0``
  (a root of ``x**q - b**p``), and transcendental for transcendental ``b``
  and ``p != 0`` (``(b**(p/q))**q = b**p``).
* Realness and the zeros and poles of the functions, each named at its
  entry: ``exp(x + I*y)`` is real iff ``sin(y) = 0`` (``y`` in ``pi*Z``,
  never a nonzero algebraic number), and so on.

The infinite arguments follow SymPy (``exp(-oo) = 0``, ``log(-oo) = oo``,
``tanh(oo) = 1``, ``asin(oo) = -oo*I``, ``atan(oo) = pi/2``, ``acot(oo) =
0``; ``sin(oo)`` is ``AccumBounds``: no claim); ``zoo`` and the other
complex infinities give no claim (``exp(zoo) = nan``, ``tan(oo*I) = I``).
"""
from __future__ import annotations

from typing import Dict, Tuple

from ...state.memos import adopt as _adopt_memo
from .lattice import ClassTheory, Lattice

__all__ = ['ALL', 'NANB', 'PREDS', 'PRED_MASK', 'ONESIDED', 'ONESIDED_MASK', 'FUNCS',
           'OPS', 'POW', 'TRANS', 'TransTheory']

#: the basis predicates the theory reads and writes, by local index
PREDS = ("integer", "rational", "algebraic", "complex", "finite", "extended_real", "zero")
#: the basis predicates it only reads, and only when true
ONESIDED = ("prime", "composite", "even", "extended_negative")

Z0, ONE, ZI, Q1, AR, AC, TR, TC, FX, IR, IC = range(11)
NAN = 11
NATOMS = 11
ALL = (1 << NATOMS) - 1
NANB = 1 << NAN
#: the finite complex atoms
CPX = (Z0, ONE, ZI, Q1, AR, AC, TR, TC)
ATOM_NAMES = ("Z0", "ONE", "ZI", "Q1", "AR", "AC", "TR", "TC", "FX", "IR", "IC")


def _b(*atoms) -> int:
    m = 0
    for a in atoms:
        m |= 1 << a
    return m


_CPX = _b(*CPX)
_CPXNZ = _CPX & ~_b(Z0)
_REAL = _b(Z0, ONE, ZI, Q1, AR, TR)         # the finite reals
_REALNZ = _b(ONE, ZI, Q1, AR, TR)
_RAT = _b(Z0, ONE, ZI, Q1)
_ALGNZ = _b(ONE, ZI, Q1, AR, AC)
_TRN = _b(TR, TC)                           # transcendental
_NONREAL = _b(AC, TC)                       # finite, not real
_NOCLAIM = ALL | NANB
#: real nonzero algebraic arguments, where the LW entries are all ``TR``
_RALGNZ = (ONE, ZI, Q1, AR)

PRED_MASK = (
    _b(Z0, ONE, ZI),                            # integer
    _RAT,                                       # rational
    _RAT | _b(AR, AC),                          # algebraic
    _CPX,                                       # complex
    _CPX | _b(FX),                              # finite
    _REAL | _b(IR),                             # extended_real
    _b(Z0),                                     # zero
)
ONESIDED_MASK = (
    _b(ZI),                                     # prime: an integer >= 2
    _b(ZI),                                     # composite: an integer >= 4
    _b(Z0, ZI),                                 # even: never 1
    _b(ZI, Q1, AR, TR, IR),                     # extended_negative: x < 0 or -oo
)


def _unary(spec: Dict) -> Tuple[int, ...]:
    """The table of a function from ``{atom or atoms: set}``; atoms not
    named (``FX``, and mostly ``IC``) are "no claim"."""
    t = [_NOCLAIM] * NATOMS
    for k, m in spec.items():
        for a in (k if isinstance(k, tuple) else (k,)):
            t[a] = m
    t[FX] = _NOCLAIM
    return tuple(t)


# Each table: the atom set of f(x) for x in an atom.  "LW" marks the
# Lindemann-Weierstrass entries (module docstring); the realness of the
# value at a non-real algebraic argument x = u + I*v (v != 0 algebraic) is
# argued from the real and imaginary parts.
_TABLES = {
    'exp': _unary({
        Z0: _b(ONE),                            # exp(0) = 1
        _RALGNZ: _b(TR),                        # LW; exp of a real is real
        # LW; Im exp(u + I*v) = exp(u)*sin(v) != 0: v in pi*Z would make
        # v transcendental
        AC: _b(TC),
        TR: _REALNZ,                            # exp(real) > 0: exp(log(2)) = 2
        TC: _CPXNZ,                             # exp never 0; exp(I*pi) = -1
        IR: _b(Z0, IR),                         # exp(-oo) = 0, exp(oo) = oo
        # IC: exp(zoo) = exp(oo*I) = nan: no claim
    }),
    'log': _unary({
        Z0: _b(IC),                             # log(0) = zoo
        ONE: _b(Z0),                            # log(1) = 0
        # LW (a not 0 or 1); real for a > 0, log(a) = log|a| + I*pi for a < 0
        (ZI, Q1, AR): _TRN,
        AC: _b(TC),                             # LW; Im log(a) = arg(a) not in {0, pi}
        (TR, TC): _CPXNZ,                       # log(x) = 0 iff x = 1; log(E) = 1
        IR: _b(IR),                             # SymPy: log(oo) = log(-oo) = oo
        # IC: log(zoo) = zoo, log(oo*I) = oo, log(oo + I) unevaluated: no claim
    }),
    'sin': _unary({
        Z0: _b(Z0),
        _RALGNZ: _b(TR),                        # LW; real
        # LW; Im sin(u + I*v) = cos(u)*sinh(v) != 0 (cos(u) = 0 needs u in
        # pi/2 + pi*Z, transcendental)
        AC: _b(TC),
        TR: _REAL,                              # sin(pi) = 0, sin(pi/2) = 1
        TC: _CPXNZ,                             # sin(z) = 0 only at real z = k*pi
        # IR: AccumBounds(-1, 1); IC: sin(zoo) = nan: no claim
    }),
    'cos': _unary({
        Z0: _b(ONE),                            # cos(0) = 1
        _RALGNZ: _b(TR),                        # LW; real
        AC: _TRN,                               # LW; cos(I) = cosh(1) is real
        TR: _REAL,                              # cos(pi/2) = 0, cos(pi) = -1
        TC: _CPXNZ,                             # cos(z) = 0 only at real z
    }),
    'tan': _unary({
        Z0: _b(Z0),
        _RALGNZ: _b(TR),                        # LW; real (no pole: pi/2 + k*pi is transcendental)
        # LW; Im tan(u + I*v) = sinh(2*v)/(cos(2*u) + cosh(2*v)) != 0; poles real
        AC: _b(TC),
        TR: _REAL | _b(IC),                     # tan(pi/2) = zoo
        TC: _CPXNZ,                             # zeros and poles of tan are real
        # IR: AccumBounds(-oo, oo); IC: tan(oo*I) = I, tan(zoo) = nan: no claim
    }),
    'cot': _unary({
        Z0: _b(IC),                             # cot(0) = zoo
        _RALGNZ: _b(TR),                        # LW (cot = 1/tan); real
        AC: _b(TC),                             # 1/tan(a), tan(a) in TC
        TR: _REAL | _b(IC),                     # cot(pi) = zoo, cot(pi/2) = 0
        TC: _CPXNZ,                             # zeros and poles of cot are real
    }),
    'sinh': _unary({
        Z0: _b(Z0),
        _RALGNZ: _b(TR),                        # LW; real
        # LW; Im sinh(u + I*v) = cosh(u)*sin(v) != 0 (v not in pi*Z)
        AC: _b(TC),
        TR: _REALNZ,                            # sinh(x) = 0 only at x = 0 for real x
        TC: _CPX,                               # sinh(I*pi) = 0
        IR: _b(IR),                             # sinh(+-oo) = +-oo
        # IC: sinh(oo*I) = I*AccumBounds(-1, 1): no claim
    }),
    'cosh': _unary({
        Z0: _b(ONE),                            # cosh(0) = 1
        _RALGNZ: _b(TR),                        # LW; real
        AC: _TRN,                               # LW; cosh(I) = cos(1) is real
        TR: _b(ZI, Q1, AR, TR),                 # cosh(x) > 1 for real x != 0
        TC: _CPX,                               # cosh(I*pi/2) = 0, cosh(I*pi) = -1
        IR: _b(IR),                             # cosh(+-oo) = oo
    }),
    'tanh': _unary({
        Z0: _b(Z0),
        _RALGNZ: _b(TR),                        # LW; real
        # LW; Im tanh(u + I*v) = sin(2*v)/(cosh(2*u) + cos(2*v)) != 0; the
        # poles I*(pi/2 + k*pi) are transcendental
        AC: _b(TC),
        TR: _b(Q1, AR, TR),                     # 0 < |tanh(x)| < 1
        TC: _CPX | _b(IC),                      # tanh(I*pi) = 0, tanh(I*pi/2) = zoo
        IR: _b(ONE, ZI),                        # tanh(oo) = 1, tanh(-oo) = -1
    }),
    'asin': _unary({
        Z0: _b(Z0),
        ONE: _b(TR),                            # asin(1) = pi/2
        # LW (sin(asin(a)) = a); real on [-1, 1] (asin(-1) = -pi/2), else
        # pi/2 - I*log(...) (asin(2))
        (ZI, Q1, AR): _TRN,
        AC: _b(TC),                             # LW; asin(z) real makes z = sin(asin(z)) real
        TR: _CPXNZ,                             # asin(x) = 0 only at x = 0
        TC: _NONREAL,                           # as for AC: asin(sin(I)) = I
        IR: _b(IC),                             # asin(oo) = -oo*I, asin(-oo) = oo*I
    }),
    'acos': _unary({
        Z0: _b(TR),                             # acos(0) = pi/2
        ONE: _b(Z0),                            # acos(1) = 0
        # LW (cos(acos(a)) = a, acos(a) != 0); acos(-1) = pi, acos(2) = I*log(2 + sqrt(3))
        (ZI, Q1, AR): _TRN,
        AC: _b(TC),                             # LW; acos(z) real makes z = cos(acos(z)) real
        TR: _CPXNZ,                             # acos(x) = 0 only at x = 1
        TC: _NONREAL,
        IR: _b(IC),                             # acos(oo) = oo*I, acos(-oo) = -oo*I
    }),
    'atan': _unary({
        Z0: _b(Z0),
        _RALGNZ: _b(TR),                        # LW; real
        # LW; atan(+-I) = +-oo*I; atan(z) real makes z = tan(atan(z)) real
        AC: _b(TC, IC),
        TR: _REALNZ,                            # atan(tan(1)) = 1
        TC: _NONREAL,                           # atan(tan(I)) = I; atan(z) infinite only at +-I
        IR: _b(TR),                             # atan(+-oo) = +-pi/2
        # IC: atan(zoo) unevaluated: no claim
    }),
    'acot': _unary({
        Z0: _b(TR),                             # acot(0) = pi/2
        _RALGNZ: _b(TR),                        # LW; real
        AC: _b(TC, IC),                         # LW; acot(+-I) = -+oo*I
        TR: _REALNZ,
        TC: _NONREAL,                           # cot(acot(z)) = z; infinite only at +-I
        IR: _b(Z0),                             # acot(+-oo) = 0
        # IC: acot(zoo) = acot(oo*I) = 0, acot(oo + I) unevaluated: no claim
    }),
}

#: the functions with a table, by SymPy class name
FUNCS = tuple(_TABLES)


def _pow_atoms(b: int, e: int) -> int:
    """The atom set of ``b**e`` (SymPy's principal value)."""
    if b == FX or e == FX:
        return _NOCLAIM
    if e == Z0:
        return _b(ONE)                          # x**0 = 1 (SymPy: 0**0, oo**0, zoo**0 too)
    if b in (IR, IC) or e in (IR, IC):
        # 2**oo = oo, 1**oo = nan, oo**I = nan, (-oo)**pi = oo*(-1)**pi ...
        return _NOCLAIM
    if b == Z0:
        # 0**e: 0 for e > 0, zoo for e < 0, nan for non-real e
        return _b(Z0, IC) if _REAL >> e & 1 else _NOCLAIM
    if b == ONE:
        return _b(ONE)                          # 1**e = 1 for finite e (1**I = 1)
    if e == ONE:
        return 1 << b                           # b**1 = b
    # b finite nonzero, e finite not 0 or 1: b**e = exp(e*log(b)) is
    # finite and nonzero
    if b in (ZI, Q1, AR, AC):
        if e in (ZI, Q1):
            if b in (ZI, Q1) and e == ZI:
                return _b(ONE, ZI, Q1)          # Q* is a group: (-1)**2 = 1, 2**-1 = 1/2
            return _ALGNZ                       # a root of x**q - b**p; (-1)**(1/2) = I
        if e in (AR, AC):
            return _TRN                         # Gelfond-Schneider (b not 0 or 1)
        return _CPXNZ                           # 2**(log(3)/log(2)) = 3
    # b transcendental
    if e in (ZI, Q1):
        # (b**(p/q))**q = b**p: algebraic would make b algebraic
        return _TRN
    return _CPXNZ                               # E**(I*pi) = -1


_MEMO: Dict[tuple, int] = {}     # map_masks: a pure function of its key
_adopt_memo(__name__, "_MEMO")

#: the lattice (:mod:`.lattice`): no folds, one map op per function
TRANS = Lattice(NATOMS, (), _MEMO)
#: function name -> map op id
OPS = {name: TRANS.add_map(lambda a, t=t: t[a], 1) for name, t in _TABLES.items()}
#: the map op id of ``Pow(b, e)``
POW = TRANS.add_map(_pow_atoms, 2)


class TransTheory(ClassTheory):
    """The theory (contract: :mod:`satassume.sat.theory`; the machinery is
    :class:`.lattice.ClassTheory`).  Besides the atoms of :data:`PREDS` it
    takes *one-sided* atoms (payload ``(t, m, True)``): ``v`` true puts
    term ``t`` in ``m``, ``v`` false says nothing.  They are kept out of
    ``tvars`` (so never propagated) and enter the reasons only when true."""
    L = TRANS

    def __init__(self):
        super().__init__()
        self.ovars = []          # term -> its one-sided (variable, atom set)
        self.oneside = set()     # the one-sided variables

    def term(self, fixed: int = -1) -> int:
        self.ovars.append([])
        return super().term(fixed)

    def register_atom(self, v: int, payload) -> None:
        if len(payload) == 2:
            return super().register_atom(v, payload)
        t, m, _ = payload
        if v in self.atom:
            return
        self.ovars[t].append((v, m))
        self.oneside.add(v)
        self.atom[v] = (t, m)
        self.dirty.update(self.tnodes[t])

    def assert_lit(self, lit: int):
        if lit < 0 and -lit in self.oneside:
            # says nothing: recorded (for the trail) but no narrowing
            v = -lit
            if v not in self.val:
                self.val[v] = False
                self.trail.append(v)
            return None
        return super().assert_lit(lit)

    def _lits(self, t: int):
        val = self.val
        out = [v if val[v] else -v for v, _ in self.tvars[t] if v in val]
        for v, _ in self.ovars[t]:
            if val.get(v):
                out.append(v)
        return out


def atom_profile(a: int) -> Tuple[str, ...]:
    """The predicates of :data:`PREDS` that hold of atom ``a`` (tests, docs)."""
    return tuple(p for p, m in zip(PREDS, PRED_MASK) if m >> a & 1)
