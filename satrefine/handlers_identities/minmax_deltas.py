"""``Min``, ``Max``, ``KroneckerDelta`` and ``Heaviside`` as ``Piecewise``
definitions; ``DiracDelta`` as rule rows.

**8 rows**: 5 definitions (``FACTS``) and 3 ``DiracDelta`` rules.  Each
definition is an identity row whose right side states the case analysis::

    Max(a, b)                    = Piecewise((a, a >= b), (b, a < b))
    Min(a, b)                    = Piecewise((a, a <= b), (b, a > b))
    KroneckerDelta(i, j)         = Piecewise((1, i = j), (0, i != j))
    KroneckerDelta(i, j, (l, u)) = Piecewise((1, i = j & l <= i <= u), (0, True))
    Heaviside(x, h)              = Piecewise((0, x < 0), (h, x = 0), (1, x > 0))

A definition fires when the engine decides its conditions under the
assumptions (the refined right side has no ``Piecewise`` left) and the
family's heads lose an argument.  The conditions are decided by the
engine's order vocabulary (:func:`._engine.decide`), not by SymPy's
``Piecewise`` refinement: a relation holds when a proof form from signs or
infinite endpoints holds, or one from stated relations (``Q.le``, ``Q.lt``,
``Q.eq``, ``Q.ne``, the difference zero or nonzero), and the relation forms
are not used for an argument known infinite, where SymPy's ``ask`` answers
``Q.eq(x, y)`` "True" for ``x = -oo`` and ``y <= 0`` (v3 refuses relation
queries there).  No case split is tried (``splits=False``): on refusals it
cost about 5x and derived nothing the battery or the differential run needs.

The last branch of each two-way definition is ``(nan, True)``, the value
outside the domain (``Max`` of incomparable arguments, ``Heaviside`` of a
non-real argument; SymPy raises there).  The decider never refutes both
``a >= b`` and ``a < b``, so that branch is reached only for ``Heaviside``,
whose row carries the domain ``Q.extended_real(x)``.

Ties and infinities follow SymPy: ``Max(a, b)`` keeps ``a`` when ``a >= b``
(under ``Q.eq(x, y)`` the first argument survives); ``+-oo`` are ordered
like any extended real; ``Heaviside(0, h) = h`` (``Heaviside(x)`` carries
``h = 1/2``).  More than two arguments need no row: ``Max(a, b)`` matches
every ordered pair of arguments of a longer ``Max`` and keeps the others.
Derived beyond v3: the range definition gives ``1`` when ``i = j`` and the
range condition are provable, ``0`` when ``i`` is provably outside the range.
Not derived (refused as before): ``KroneckerDelta(i, j, range)`` under
``Q.eq`` alone.

``DiracDelta`` is a distribution, not a function with values: its rows are
identities between distributions and stay rules.  v3 scales out all nonzero
factors at once; the row scales out one and the dispatcher repeats it.
"""
from __future__ import annotations

from sympy import (Abs, DiracDelta, Function, Heaviside, KroneckerDelta, Max, Min, Piecewise, Q, S, Tuple,
                   count_ops, nan, symbols, true)

from .._upstream import handlers_dict
from ._engine import identity_handler, rule_handler

a, b, c, h, i, j, lo, hi, r, x = symbols('a b c h i j lo hi r x')
G = Function('G')        # generic head: KroneckerDelta(i, j), Heaviside(x, h), derivatives of DiracDelta

FACTS = [
    (Max(a, b), Piecewise((a, Q.ge(a, b)), (b, Q.lt(a, b)), (nan, True)), true),
    (Min(a, b), Piecewise((a, Q.le(a, b)), (b, Q.gt(a, b)), (nan, True)), true),
    (G(i, j), Piecewise((1, Q.eq(i, j)), (0, Q.ne(i, j)), (nan, True)), true),
    (KroneckerDelta(i, j, Tuple(lo, hi)), Piecewise((1, Q.eq(i, j) & Q.le(lo, i) & Q.le(i, hi)), (0, True)), true),
    (G(x, h), Piecewise((0, Q.extended_negative(x)), (h, Q.zero(x)), (1, Q.extended_positive(x)), (nan, True)),
     Q.extended_real(x)),
]

RULES = [
    # DiracDelta and all its derivatives vanish off the origin (x real, nonzero).
    (DiracDelta(x), S.Zero, Q.nonzero(x)),
    (G(x, r), S.Zero, Q.nonzero(x)),
    # DiracDelta(c*x) = DiracDelta(x)/|c| for nonzero real c and real x (SymPy's
    # expand(diracdelta=True) convention); derivatives pick up sign(c)**k.
    (DiracDelta(c*x), DiracDelta(x)/Abs(c), Q.nonzero(c) & Q.real(x)),
]


def _measure(e, assumptions):
    """Arguments of the family's heads, then size: a definition fires when it drops one."""
    return (sum(len(n.args) for n in e.atoms(Max, Min, KroneckerDelta, Heaviside)), count_ops(e))


def _definitions(rows):
    return identity_handler(rows, measure=_measure, opaque=(), splits=False)


handlers_dict['Max'] = _definitions(FACTS[0:1])
handlers_dict['Min'] = _definitions(FACTS[1:2])
handlers_dict['KroneckerDelta'] = _definitions(FACTS[2:4])
handlers_dict['Heaviside'] = _definitions(FACTS[4:5])
handlers_dict['DiracDelta'] = rule_handler(RULES)
