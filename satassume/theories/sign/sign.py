"""SIGN: the class of a sum or product from the classes of its arguments.

A DPLL(T) theory (issue #149, proposal T1, stage 1) over the sign basis
variables of ``Add`` and ``Mul`` nodes and their arguments: whatever the
arity, it propagates the class of the node from the classes of the
arguments (forward), and the class of one argument from the node and the
other arguments (backward).  It needs no SymPy: :mod:`.sign_adapter`
tells it the terms, nodes and constants.

**Atoms.**  The value of a term lies in one of 12 *atoms* of the extended
complex plane, plus ``NAN``:

* a finite value by the signs of its real and imaginary parts,
  ``F(sr, si)`` with ``sr, si`` in ``{-1, 0, 1}`` (9 atoms: ``F(0, 0)`` is
  0, ``F(+-1, 0)`` the finite nonzero reals, ``F(0, +-1)`` the imaginary
  numbers, the other four the finite values off both axes);
* ``PI`` (``oo``), ``NI`` (``-oo``) and ``IN``: every other infinity
  (``zoo``, ``oo*I``, ``oo*(1 + I)``, ``oo + I``);
* ``NAN``: the sum or product is ``nan`` (``oo - oo``, ``0*oo``,
  ``zoo + zoo``).  It is "no claim": a node that may be ``nan`` gets no
  literal from this theory, as in the templates (``docs/design.md``,
  "Extended reals and nan in templates").  Arguments are never ``nan``,
  the convention of the templates' soundness oracle
  (``tests/test_templates.py``): a ``nan`` argument makes the node ``nan``
  whatever its literals say.

A literal of a basis predicate is a set of atoms (:data:`PRED_MASK`):
``extended_real`` = the reals and ``+-oo``, ``finite`` = the 9 finite
atoms, ``zero``, ``extended_positive``, ``extended_negative``,
``imaginary`` = ``F(0, +-1)``.  The other predicates reach these six
through the rule block (``prime -> extended_positive``, ``integer ->
extended_real & finite``), which writes their literals on the trail.

**Operations.**  :func:`_add_atoms` and :func:`_mul_atoms` give the set of
atoms ``a + b`` and ``a * b`` can take for ``a``, ``b`` in two atoms:
interval arithmetic on the signs of the parts (``re(a*b) = ar*br -
ai*bi``) plus SymPy's conventions for infinities (each case commented
there).  A node folds them over its arguments: both operations are
commutative and associative on values, and the set operation
over-approximates each step, so any order is sound; ``NAN`` absorbs.
``tests/test_sign_theory.py`` checks both tables against SymPy at sample
points of every atom and the folds against n-ary ``Add`` and ``Mul``.

**Propagation.**  For a node ``N = op(A1, ..., An)`` with atom sets ``S``:
``S(N) &= fold(S(A))`` unless the fold holds ``NAN``, and for each ``k``
an atom ``c`` stays in ``S(Ak)`` only if ``op(c, fold(S(Aj), j != k))``
holds ``NAN`` or meets ``S(N)``.  A literal is implied when a set lies
inside (or outside) its predicate's set; an empty set is a conflict.  The
reason of each is a subset of the node's and the arguments' literals that
suffices, minimised by deletion: one clause, the template rule it stands
for.
"""
from __future__ import annotations

from typing import Dict, Tuple

from ...state.memos import adopt as _adopt_memo
from .lattice import ADD, MUL, ClassTheory, Lattice

#: the basis predicates the theory reads and writes, by local index
PREDS = ("extended_real", "finite", "zero", "extended_positive", "extended_negative",
         "imaginary")


def F(sr: int, si: int) -> int:
    """The atom of the finite values whose real part has sign ``sr`` and
    imaginary part sign ``si``."""
    return (sr + 1) * 3 + (si + 1)


PI, NI, IN, NAN = 9, 10, 11, 12
ZERO = F(0, 0)
FIN = (1 << 9) - 1
ALL = (1 << 12) - 1            # every atom but NAN: an argument's widest set
NANB = 1 << NAN
INF = (1 << PI) | (1 << NI) | (1 << IN)


def _b(*atoms) -> int:
    m = 0
    for a in atoms:
        m |= 1 << a
    return m


PRED_MASK = (
    _b(F(-1, 0), ZERO, F(1, 0), PI, NI),           # extended_real
    FIN,                                           # finite
    _b(ZERO),                                      # zero
    _b(F(1, 0), PI),                               # extended_positive
    _b(F(-1, 0), NI),                              # extended_negative
    _b(F(0, -1), F(0, 1)),                         # imaginary
)


def _sadd(a: int, b: int) -> Tuple[int, ...]:
    """The signs of ``x + y`` for reals ``x``, ``y`` of signs ``a``, ``b``."""
    if a == 0:
        return (b,)
    if b == 0 or a == b:
        return (a,)
    return (-1, 0, 1)


def _fin(a: int) -> Tuple[int, int]:
    return a // 3 - 1, a % 3 - 1


def _add_atoms(a: int, b: int) -> int:
    if a < 9 and b < 9:
        (ar, ai), (br, bi) = _fin(a), _fin(b)
        return _b(*(F(r, i) for r in _sadd(ar, br) for i in _sadd(ai, bi)))
    if a < 9:
        a, b = b, a
    if b < 9:
        bi = _fin(b)[1]
        if a in (PI, NI):
            # oo + r = oo for a finite real r; oo + (r + s*I) with s != 0
            # is an infinity off the real axis (``oo + I``)
            return 1 << (a if bi == 0 else IN)
        # IN + r: a real r keeps the imaginary part (``oo + I + 1``) or
        # the undirected ``zoo``; a non-real one may cancel it
        # (``(oo + I) - I = oo``)
        return 1 << IN if bi == 0 else _b(PI, NI, IN)
    if a == b and a != IN:
        return 1 << a                       # oo + oo, -oo - oo
    return NANB                             # oo - oo, zoo + zoo, oo + zoo, ...


def _mul_atoms(a: int, b: int) -> int:
    if a < 9 and b < 9:
        (ar, ai), (br, bi) = _fin(a), _fin(b)
        m = _b(*(F(r, i) for r in _sadd(ar * br, -(ai * bi))
                 for i in _sadd(ar * bi, ai * br)))
        if a != ZERO and b != ZERO:
            m &= ~(1 << ZERO)               # the complex numbers are a field
        return m
    if a < 9:
        a, b = b, a
    if b < 9:
        if b == ZERO:
            return NANB                     # 0*oo, 0*zoo
        br, bi = _fin(b)
        if a in (PI, NI):
            if bi:
                return 1 << IN              # oo*I, oo*(1 + I)
            return 1 << (PI if (br > 0) == (a == PI) else NI)
        # zoo*r = zoo and (oo + I)*r = r*oo + r*I for a nonzero real r;
        # a non-real factor turns an infinity off the axis in any
        # direction, onto the axes too (``oo*I*I = -oo``): an infinity
        # (the templates' ``one_infinite``: an infinite factor and the
        # rest nonzero)
        return 1 << IN if bi == 0 else INF
    if a in (PI, NI) and b in (PI, NI):
        return 1 << (PI if a == b else NI)
    if a in (PI, NI) or b in (PI, NI):
        return 1 << IN                      # a real sign keeps it off the axis
    return INF                              # IN*IN: ``oo*I*oo*I = -oo``, ``zoo*zoo``


_ATOM_OPS = (_add_atoms, _mul_atoms)
_MEMO: Dict[tuple, int] = {}     # mop and allowed: a pure function of its key
_adopt_memo(__name__, "_MEMO")

#: the lattice (:mod:`.lattice`): its folds are this module's functions
SIGN = Lattice(12, _ATOM_OPS, _MEMO)
mop = SIGN.mop
allowed = SIGN.allowed
fold = SIGN.fold
node_masks = SIGN.node_masks


class SignTheory(ClassTheory):
    """The theory (contract: :mod:`satassume.sat.theory`; the machinery is
    :class:`.lattice.ClassTheory`)."""
    L = SIGN
