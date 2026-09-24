"""``Min``, ``Max``, ``DiracDelta``, ``KroneckerDelta`` and ``Heaviside`` as
rule tables.

A row is ``(lhs, rhs, hypothesis)`` or ``(lhs, rhs, hypothesis, unless)``:
it fires when the hypothesis is provable through ``_upstream.ask`` and the
``unless`` condition is not.  The rules are those stated in
``handlers_v3/minmax_deltas.py`` (305 lines), in **13 rows**: Max 2, Min 2,
DiracDelta 3, KroneckerDelta 3, Heaviside 3.

Pattern forms used beyond the current engine (requested in
``tests/refine_identities/needs/test_minmax_deltas_needs.py``):

* ``Max(a, b)`` / ``Min(a, b)`` against a ``Max``/``Min`` of any arity binds
  ``a``, ``b`` to two distinct arguments (every ordered pair) and keeps the
  other arguments: ``Max(x, y, z) -> Max(rhs, z)``;
* heads of two and three arguments with every argument bound; literal
  ``0``/``1`` bindings (``Max(x, 0)``, ``Heaviside(x, 1)``);
* the ``unless`` element: SymPy's relation ``ask`` is unsound for infinite
  arguments (``Q.eq(y, x)`` is "True" for ``x = -oo`` and ``y``
  extended-nonpositive), and v3 refuses relation queries when an argument
  is *known* infinite.  "Not known" is not a hypothesis ``ask`` can prove,
  so it is the ``unless`` condition ``Q.infinite(a) | Q.infinite(b)``;
* hypotheses decided structurally (``Or``: some disjunct provable) and an
  ``ask`` that raises ``ValueError`` read as "not provable": SymPy's
  relation ``ask`` raises on sign facts such as ``Q.positive(x) &
  Q.negative(y)`` and returns ``None`` for a disjunction mixing a provable
  sign fact with a relation.

Minimizations against v3:

* ``Min`` and ``Max`` are each one sign row and one relation row, with the
  kept argument first: "``Max(a, b) -> a`` if ``b <= a``" also gives
  ``Max(x, y) -> x`` under ``Q.eq(x, y)`` (the first argument survives, as
  in v3), so equality needs no row of its own.
* ``DiracDelta``: v3 scales out all nonzero factors at once; the row scales
  out one factor, and the dispatcher's re-refinement repeats it.

Not expressible as rows: v3's query budget and caching (one ``ask`` per
argument and per ordered pair) are procedure, not rules; the rows ask more.
Checked (adversarial pass, 2026-09-24): ``Max``/``Min`` of two and three
arguments with ``+-oo`` known or merely possible, extended signs, relation
chains and equalities, compound infinite arguments (``x - 1``, ``2*x``,
``x*z``, ``x + z`` with ``x = -oo``) against both rows and the ``unless``
guard; ``DiracDelta`` off the origin with real, extended-real and non-real
arguments and scaled derivatives; ``KroneckerDelta`` with ranges, infinite
and imaginary indices; ``Heaviside`` at 0 and ``+-oo`` with and without
``H0``; plus ``tools/refine_differential.py`` seeds 2, 3, 7.  Found
nothing: SymPy's wrong ``Q.eq(y, x)`` for ``x = -oo`` is only reached with
a bare symbol (compound ``-oo`` arguments give ``None``), where the guard
holds.  ``DiracDelta(0)`` is not compared (a distribution has no value
there).
"""
from __future__ import annotations

from sympy import Abs, DiracDelta, Function, Max, Min, Q, S, symbols

from .._upstream import handlers_dict
from ._specialize import compile_table

a, b, c, h, i, j, r, x = symbols('a b c h i j r x')
G = Function('G')        # generic two-argument head
H = Function('H')        # generic three-argument head


def _le_by_signs(u, v):
    """``u <= v`` from unary facts: signs, or an infinite endpoint."""
    return ((Q.extended_nonpositive(u) & Q.extended_nonnegative(v))
            | (Q.infinite(v) & Q.extended_nonnegative(v) & Q.extended_real(u))
            | (Q.infinite(u) & Q.extended_nonpositive(u) & Q.extended_real(v)))


def _le_by_relation(u, v):
    """``u <= v`` as a relation (SymPy derives ``le`` neither from ``lt`` nor ``eq``)."""
    return Q.le(u, v) | Q.lt(u, v) | Q.eq(u, v)


_INFINITE = Q.infinite(a) | Q.infinite(b)

MAX = [
    # Max(a, b, ...) = Max(a, ...) when b <= a, by signs or an infinite endpoint.
    (Max(a, b), a, _le_by_signs(b, a)),
    # ... or by a relation among the assumptions, never for a known infinite argument.
    (Max(a, b), a, _le_by_relation(b, a), _INFINITE),
]

MIN = [
    # Min(a, b, ...) = Min(a, ...) when a <= b.
    (Min(a, b), a, _le_by_signs(a, b)),
    (Min(a, b), a, _le_by_relation(a, b), _INFINITE),
]

DIRAC = [
    # The distribution and all its derivatives vanish off the origin (x real, nonzero).
    (DiracDelta(x), S.Zero, Q.nonzero(x)),
    (G(x, r), S.Zero, Q.nonzero(x)),
    # DiracDelta(c*x) = DiracDelta(x)/|c| for a nonzero real c and real x
    # (SymPy's expand(diracdelta=True) convention); derivatives are not rescaled
    # (they pick up sign(c)**k), so the row is for DiracDelta(x) of order 0 only.
    (DiracDelta(c*x), DiracDelta(x)/Abs(c), Q.nonzero(c) & Q.real(x)),
]

_DIFFERENT = Q.nonzero(i - j) | Q.ne(i, j) | Q.ne(j, i) | Q.lt(i, j) | Q.lt(j, i)
_INFINITE_INDEX = Q.infinite(i) | Q.infinite(j)

KRONECKER = [
    # delta(i, j) = 0 for indices known different (with or without a range).
    (G(i, j), S.Zero, _DIFFERENT, _INFINITE_INDEX),
    (H(i, j, r), S.Zero, _DIFFERENT, _INFINITE_INDEX),
    # delta(i, j) = 1 for indices known equal; only without a range (with one,
    # equal indices outside the range give 0).
    (G(i, j), S.One, Q.zero(i - j) | Q.eq(i, j) | Q.eq(j, i), _INFINITE_INDEX),
]

HEAVISIDE = [
    # Heaviside(x, H0) is 1 right of the origin (+oo included), 0 left of it,
    # and H0 at it (SymPy's convention; Heaviside(x) carries H0 = 1/2).
    (G(x, h), S.One, Q.extended_positive(x)),
    (G(x, h), S.Zero, Q.extended_negative(x)),
    (G(x, h), h, Q.zero(x)),
]

RULES: list[tuple] = MAX + MIN + DIRAC + KRONECKER + HEAVISIDE

handlers_dict['Min'] = compile_table(MIN)
handlers_dict['Max'] = compile_table(MAX)
handlers_dict['DiracDelta'] = compile_table(DIRAC)
handlers_dict['KroneckerDelta'] = compile_table(KRONECKER)
handlers_dict['Heaviside'] = compile_table(HEAVISIDE)
