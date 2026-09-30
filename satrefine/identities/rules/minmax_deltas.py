"""``Min``, ``Max``, ``KroneckerDelta`` and ``Heaviside`` as ``Piecewise``
definitions; ``DiracDelta`` as rule rows.

**8 rows**: 5 definitions (``FACTS``) and 3 ``DiracDelta`` rules.  Each
definition is an identity row whose right side states the case analysis::

    Max(a, b)                    = Piecewise((a, a >= b or a = b), (b, a < b))
    Min(a, b)                    = Piecewise((a, a <= b or a = b), (b, a > b))
    KroneckerDelta(i, j)         = Piecewise((1, i = j), (0, i != j))
    KroneckerDelta(i, j, (l, u)) = Piecewise((1, i = j & l <= i <= u), (0, True))
    Heaviside(x, h)              = Piecewise((0, x < 0), (h, x = 0), (1, x > 0))

A definition fires when the engine decides its conditions under the
assumptions (the refined right side has no ``Piecewise`` left) and the
family's heads lose an argument.  The conditions are decided by the
engine (:func:`..core.prove.decide`), not by SymPy's ``Piecewise``
refinement: under satassume (the ``satassume`` and ``combined`` backends) by
one ``ask`` each, a relation saying its sides are extended reals and
holding on them, also at infinity; under SymPy's ``ask`` by the order
vocabulary, whose relation forms are not used for an argument known
infinite, where SymPy's ``ask`` answers ``Q.eq(x, y)`` "True" for ``x = -oo``
and ``y <= 0`` (v3 refuses relation queries there).  No case split is tried
(``splits=False``): on refusals it cost about 5x and derived nothing the
battery or the differential run needs.

``Max`` and ``Min`` have no default branch.  For a non-real argument both
``a >= b`` and ``a < b`` are false (a relation's sides are extended reals),
so the definition is left with no branch and does not fire: ``Max`` of
incomparable arguments is undefined, and SymPy raises there.  The two-way
definitions of ``KroneckerDelta`` and ``Heaviside`` end with ``(nan, True)``,
the value outside the domain; it is reached only for ``Heaviside`` of a
non-real argument, whose argument ``v`` is assumed extended real.

Ties and infinities follow SymPy: ``Max(a, b)`` keeps ``a`` when ``a >= b``
or ``a = b`` (under ``Q.eq(x, y)`` the first argument survives, also for a
non-real ``x``, as SymPy's ``Max(x, x)`` is ``x``); ``+-oo`` are ordered
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
                   count_ops, nan, symbols)

from ._tables import Family, Identities, Rules, add_rules

a, b, d, i, j, lo, hi, inf, ninf, r, t, u, w = symbols('a b d i j lo hi inf ninf r t u w')
G = Function('G')        # generic head: KroneckerDelta(i, j), Heaviside(u, w), derivatives of DiracDelta

# Assumed throughout: a row takes each fact whose variables are all in its left side.
# The letters follow the tables' convention (t real; u extended real; d nonzero; a, b, r, w arbitrary).
ASSUMED = {Q.extended_real(u)}   # u is an extended real (Heaviside's argument)

FACTS = (
    add_rules([
        (Max(a, b), Piecewise((a, Q.ge(a, b) | Q.eq(a, b)), (b, Q.lt(a, b)))),
        (Min(a, b), Piecewise((a, Q.le(a, b) | Q.eq(a, b)), (b, Q.gt(a, b)))),
    ])
    + add_rules([
        (G(i, j), Piecewise((1, Q.eq(i, j)), (0, Q.ne(i, j)), (nan, True))),
    ])
    + add_rules([
        (KroneckerDelta(i, j, Tuple(lo, hi)), Piecewise((1, Q.eq(i, j) & Q.le(lo, i) & Q.le(i, hi)), (0, True))),
        (G(u, w), Piecewise((0, Q.extended_negative(u)), (w, Q.zero(u)), (1, Q.extended_positive(u)), (nan, True))),
    ])
)

ASSUMED |= {Q.positive_infinite(inf), Q.negative_infinite(ninf)}   # inf is oo, ninf is -oo

INFINITE = add_rules([
    # Max(oo, b) = oo and Max(-oo, b) = b for every b Max is defined at (extended real b);
    # Min likewise.  The order vocabulary proves Q.ge(a, b) from an infinite a only for an
    # extended real b, which a plain symbol is not.  (Pairs of any arity: the other
    # arguments are kept.)
    (Max(inf, b), inf),
    (Max(ninf, b), b),
    (Min(ninf, b), ninf),
    (Min(inf, b), b),
])

ASSUMED |= {Q.nonzero(d), Q.real(t)}      # d is off the origin (nonzero: real and not 0), t is real

DIRAC = add_rules([
    # DiracDelta and all its derivatives vanish off the origin (d real, nonzero).
    (DiracDelta(d), S.Zero),
    (G(d, r), S.Zero),
    # DiracDelta(d*t) = DiracDelta(t)/|d| for nonzero real d and real t (SymPy's
    # expand(diracdelta=True) convention); derivatives pick up sign(d)**k.
    (DiracDelta(d*t), DiracDelta(t)/Abs(d)),
])

RULES = DIRAC + INFINITE


def _measure(e, assumptions):
    """Arguments of the family's heads, then size: a definition fires when it drops one."""
    return (sum(len(n.args) for n in e.atoms(Max, Min, KroneckerDelta, Heaviside)), count_ops(e))


def _definitions(rows):
    return Identities(rows, measure=_measure, opaque=(), splits=False)


SPEC = Family({'Max': (Rules(INFINITE[0:2]), _definitions(FACTS[0:1])),
               'Min': (Rules(INFINITE[2:4]), _definitions(FACTS[1:2])),
               'KroneckerDelta': _definitions(FACTS[2:4]),
               'Heaviside': _definitions(FACTS[4:5]),
               'DiracDelta': Rules(DIRAC)},
              facts=FACTS, rules=RULES, assumed=ASSUMED)
