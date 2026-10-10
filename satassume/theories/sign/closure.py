"""CLOSURE: membership of a sum or product in Z, Q, the algebraic numbers,
R and C, from that of its arguments (issue #149, proposal T3).

A class propagator (:mod:`.lattice`) over the closure basis predicates of
``Add`` and ``Mul`` nodes and their arguments.  It decides, whatever the
arity, what the ring and field rules of the templates decide for small
arities: all arguments in a ring ``S`` put the node in ``S`` (forward);
the node and all arguments but one in ``S`` put the last one in ``S``,
for a sum always (``S`` is a group under ``+``) and for a product when
``S`` is a field and the others are nonzero (backward).  The
contrapositives are the ``irrational``/``transcendental``/``noninteger``
rules (one irrational term among rationals makes an irrational sum).  It
needs no SymPy: :mod:`.closure_adapter` tells it the terms.

**Atoms.**  The value of a term lies in one of 10 atoms, plus ``NAN``:

* ``Z0`` = {0}, ``Z1`` the nonzero integers, ``Q1`` the rationals that are
  not integers, ``AR``/``AC`` the real/non-real algebraic numbers that are
  not rational, ``TR``/``TC`` the real/non-real transcendental numbers
  (the finite complex numbers are the disjoint union of these seven);
* ``FX``: a finite value that is not complex.  The rule block allows
  ``finite & ~complex`` (SymPy's facts do), though no value in scope is
  one; the theory claims nothing about a node with such an argument
  (every operation with ``FX`` may be ``NAN``), so it never decides more
  than the rule block about it;
* ``IR`` (``oo``, ``-oo``) and ``IC`` (every other infinity: ``zoo``,
  ``oo*I``, ``oo + I``), as ``PI``/``NI`` and ``IN`` of :mod:`.sign`;
* ``NAN``: the node may be ``nan`` (``oo - oo``, ``0*oo``): no claim.

A predicate is a set of atoms (:data:`PRED_MASK`): ``integer`` = ``Z0 |
Z1``, ``rational`` adds ``Q1``, ``algebraic`` adds ``AR | AC``, ``complex``
the seven finite complex atoms, ``finite`` adds ``FX``,
``extended_real`` = the real atoms and ``IR``, ``zero`` = ``Z0``.  The
other predicates reach these through the rule block (``irrational`` is
``extended_real & finite & ~rational``, ``transcendental`` is ``complex &
~algebraic``, ``even -> integer``).

**Tables.**  Not written by hand: for finite complex atoms, ``c`` is in
``a op b`` iff the triple ``(a, b, c)`` violates none of the *axioms*
(:func:`_add_ok`, :func:`_mul_ok`), each a theorem about numbers:

* ``Z``, ``Q``, the algebraic numbers, ``R`` and ``C`` are groups under
  ``+``: of ``a``, ``b``, ``c = a + b`` never exactly two lie in one of
  them; ``0 + b = b``, and ``a + b = 0`` puts ``a = -b`` in ``b``'s atom
  (every atom is closed under negation);
* ``Z`` is closed under ``*``; ``Q``, the algebraic numbers, ``R`` and
  ``C`` without 0 are groups under ``*``: for nonzero ``a``, ``b`` (and
  so nonzero ``c``) never exactly two of them lie in one; a zero factor
  gives 0.

Every true value satisfies the axioms, so each table holds the true atom
of ``a op b`` (it over-approximates).  The infinite atoms follow SymPy's
conventions as :mod:`.sign` does (each case commented in
:func:`_add_atoms`/:func:`_mul_atoms`); ``tests/test_closure_theory.py``
checks the tables against SymPy at sample points of every atom.
"""
from __future__ import annotations

from typing import Dict, Tuple

from ...state.memos import adopt as _adopt_memo
from .lattice import ADD, MUL, ClassTheory, Lattice

__all__ = ['ADD', 'MUL', 'ALL', 'PREDS', 'PRED_MASK', 'CLOSURE', 'ClosureTheory']

#: the basis predicates the theory reads and writes, by local index
PREDS = ("integer", "rational", "algebraic", "complex", "finite", "extended_real", "zero")

Z0, Z1, Q1, AR, AC, TR, TC, FX, IR, IC = range(10)
NAN = 10
NATOMS = 10
ALL = (1 << NATOMS) - 1
NANB = 1 << NAN
#: the finite complex atoms
CPX = (Z0, Z1, Q1, AR, AC, TR, TC)
INF = (1 << IR) | (1 << IC)


def _b(*atoms) -> int:
    m = 0
    for a in atoms:
        m |= 1 << a
    return m


#: the five sets of numbers the axioms speak of, as sets of finite atoms
_Z = frozenset((Z0, Z1))
_Q = _Z | {Q1}
_A = _Q | {AR, AC}
_R = _Q | {AR, TR}
_C = frozenset(CPX)
_RINGS = (_Z, _Q, _A, _R, _C)
_FIELDS = (_Q, _A, _R, _C)
_REAL = _R

PRED_MASK = (
    _b(*_Z),                                       # integer
    _b(*_Q),                                       # rational
    _b(*_A),                                       # algebraic
    _b(*CPX),                                      # complex
    _b(*CPX, FX),                                  # finite
    _b(*_R, IR),                                   # extended_real
    _b(Z0),                                        # zero
)


def _two_of(s, a, b, c) -> bool:
    return (a in s) + (b in s) + (c in s) == 2


def _add_ok(a: int, b: int, c: int) -> bool:
    """Whether ``c`` may be the atom of ``x + y`` for ``x`` in atom ``a``
    and ``y`` in atom ``b`` (finite complex atoms)."""
    if a == Z0 and c != b or b == Z0 and c != a:
        return False                        # 0 + y = y
    if c == Z0 and a != b:
        return False                        # x + y = 0: x = -y
    return not any(_two_of(s, a, b, c) for s in _RINGS)


def _mul_ok(a: int, b: int, c: int) -> bool:
    """Whether ``c`` may be the atom of ``x * y`` (finite complex atoms)."""
    if a == Z0 or b == Z0:
        return c == Z0                      # 0*y = 0 for finite y
    if c == Z0:
        return False                        # no zero divisors in C
    if a in _Z and b in _Z and c not in _Z:
        return False                        # Z is a ring
    return not any(_two_of(s, a, b, c) for s in _FIELDS)


def _table(ok, a: int, b: int) -> int:
    return _b(*(c for c in CPX if ok(a, b, c)))


def _add_atoms(a: int, b: int) -> int:
    if a == FX or b == FX:
        return ALL | NANB                   # no claim (see the module doc)
    if a < FX and b < FX:
        return _table(_add_ok, a, b)
    if a < FX:
        a, b = b, a
    if b < FX:
        if a == IR:
            # oo + r = oo for a finite real r; oo + (r + s*I) with s != 0
            # is an infinity off the real axis (``oo + I``)
            return 1 << (IR if b in _REAL else IC)
        # IC + r: a real r keeps the infinity off the axis (``oo + I + 1``,
        # ``zoo``); a non-real one may cancel it (``(oo + I) - I = oo``)
        return 1 << IC if b in _REAL else INF
    if a == b == IR:
        return (1 << IR) | NANB             # oo + oo = oo, oo - oo = nan
    return NANB                             # oo + zoo, zoo + zoo, ...


def _mul_atoms(a: int, b: int) -> int:
    if a == FX or b == FX:
        return ALL | NANB
    if a < FX and b < FX:
        return _table(_mul_ok, a, b)
    if a < FX:
        a, b = b, a
    if b < FX:
        if b == Z0:
            return NANB                     # 0*oo, 0*zoo
        if a == IR:
            # a nonzero real keeps oo on the real axis; a non-real factor
            # turns it off (``oo*I``, ``oo*(1 + I)``)
            return 1 << (IR if b in _REAL else IC)
        # zoo*r = zoo, (oo + I)*r for a nonzero real r stays off the axis;
        # a non-real factor may turn it onto the axis (``oo*I*I = -oo``)
        return 1 << IC if b in _REAL else INF
    if a == b == IR:
        return 1 << IR                      # oo*oo, oo*(-oo)
    if a == IR or b == IR:
        return 1 << IC                      # a real sign keeps it off the axis
    return INF                              # ``oo*I*oo*I = -oo``, ``zoo*zoo``


_ATOM_OPS = (_add_atoms, _mul_atoms)
_MEMO: Dict[tuple, int] = {}     # mop and allowed: a pure function of its key
_adopt_memo(__name__, "_MEMO")

#: the lattice (:mod:`.lattice`)
CLOSURE = Lattice(NATOMS, _ATOM_OPS, _MEMO)


class ClosureTheory(ClassTheory):
    """The theory (contract: :mod:`satassume.sat.theory`; the machinery is
    :class:`.lattice.ClassTheory`)."""
    L = CLOSURE


def atom_profile(a: int) -> Tuple[str, ...]:
    """The predicates of :data:`PREDS` that hold of atom ``a`` (for tests
    and docs)."""
    return tuple(p for p, m in zip(PREDS, PRED_MASK) if m >> a & 1)
