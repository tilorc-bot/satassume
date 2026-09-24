"""``floor``, ``ceiling``, ``frac``, ``Mod`` and ``Rem`` as rule tables.

Each row is ``(lhs, rhs, hypothesis)``: the handler rewrites ``lhs`` to
``rhs`` when the hypothesis is provable through ``_upstream.ask``
(:func:`._specialize.compile_table`).  The rules are the ones stated in
``handlers_v3/integer_funcs.py`` (252 lines), transcribed and minimized
into **17 rows**: four ``floor``/``ceiling`` rows shared through a generic
head, one ``Mod``/``Rem`` row shared likewise, then frac 5, Mod 4, Rem 3.

Pattern forms used beyond the current engine (requested in
``tests/refine_identities/needs/test_integer_funcs_needs.py``):

* two-argument heads (``Mod``, ``Rem``) with every argument bound;
* ``n + x`` inside a head: ``n`` binds one term of a sum, ``x`` the sum of
  the others (as ``p*r`` does for products);
* literal ``0``/``1`` values are legal bindings (``Mod(x, 1)``);
* an ``ask`` that raises ``ValueError`` (SymPy's relation ``ask`` does on
  consistent sign facts) reads as "not provable", and hypotheses are
  decided connective by connective (``ask`` returns ``None`` for a
  disjunction of a provable sign fact and a relation).

Minimizations against v3:

* ``F1``/``F2`` are one row with a disjunctive hypothesis, over a generic
  head ``F`` shared by ``floor`` and ``ceiling``.
* Merged 2026-09-24 after the row ablation
  (``agent-reports/archive/data/2026-09-24-ablation-plain.md``; no battery case,
  test or fuzz input moved): the ``F3`` shift rows are shared by ``floor``
  and ``ceiling`` through ``F`` (6 rows to 3); ``M1``/``Q1`` are one row over
  a generic two-argument head ``G`` (2 to 1); ``F4`` (``floor``/``ceiling``
  of an argument in the unit interval is 0) is dropped, since the base
  layer's ``floor_of_bounded``, the dispatcher's fallback for both keys,
  gives the same 0 (2 to 0).
* ``M1`` covers ``M2``'s even case (``a/2`` is an integer for even ``a``) and
  ``Mod(x, 1)``; ``Q1`` likewise for ``Rem``.
* ``M2``'s odd case is generalized to ``Mod(a, b) = b/2`` whenever ``2*a/b``
  is odd, exactly true for every real nonzero ``b`` (``a/b = m + 1/2`` so
  ``floor(a/b) = m``); it gives ``Mod(2*n + 1, 2) -> 1`` without ``M3``.
  ``b`` must be real: SymPy's ``Mod`` of non-real arguments does not follow
  ``a - b*floor(a/b)``.
  ``Q2`` becomes the two rows ``+-b/2`` by the sign of ``a/b``.
* Relations ``x < c`` are asked in both spellings, ``Q.lt`` and the unary
  ``Q.positive(c - x)``, as v3's ``_holds_lt`` does.

Not expressible as rows: none of the stated rules.  The "Gaussian integer"
terms of ``F3``/``R2`` (``floor(y)``, ``ceiling(y)`` of a finite ``y``) need
their own rows because ``ask`` cannot show ``Q.integer(floor(y))`` from
``Q.finite(y)``; that is a prover gap, and those rows (four since the
merge: two shared ``floor``/``ceiling`` rows and two ``frac`` rows) fold into
the plain ``n + x`` shift rows
once ``ask`` can prove that ``re`` and ``im`` of ``floor(y)`` and
``ceiling(y)`` are integers for finite ``y`` (a Gaussian-integer fact).
Checked (adversarial pass, 2026-09-24): every row at 0, +-1, integer and
half-integer boundaries, +-oo, non-real points (``I``, ``2*I``, ``3*I/2``,
``1 + I``), relation bounds against an infinite divisor, old-style symbols,
plus ``tools/refine_differential.py`` seeds 2, 3, 7 (1,500 cases each).
Found: the generalized ``M2`` fired for a non-real divisor
(``Mod(I*n, 2*I)`` under ``Q.odd(n)`` gave ``I``; ``Mod(-3*I, 2*I) = -I``);
it now needs ``Q.nonzero(b)``.  Not defects: ``Mod``/``Rem -> a`` under
``Q.lt(a, b)`` at ``b = oo`` (SymPy's ask calls ``Q.lt(a, b) &
Q.infinite(b)`` inconsistent: relations are over the reals); ``frac`` rows
at ``oo`` (both sides ``AccumBounds(0, 1)``).  Unverified: the ``Rem`` rows
for non-real arguments (SymPy leaves ``Rem`` of non-real numbers
unevaluated, so there is no value to compare; the rows follow
``a - b*trunc(a/b)``).  Unsound fuzz results through ``floor``/``Mod`` came
from the vendored ``Pow`` handler (``needs/test_checker_pow_root_of_power.py``).
"""
from __future__ import annotations

from sympy import Function, Mod, Q, S, ceiling, floor, frac, symbols
from sympy.functions.elementary.miscellaneous import Rem

from .._upstream import handlers_dict
from ._specialize import compile_table

a, b, c, n, x, y = symbols('a b c n x y')
F = Function('F')        # generic head: the row serves every key it is registered under
G = Function('G')        # generic two-argument head: Mod and Rem


def _lt(u, v):
    """``u < v`` in both spellings ``ask`` understands."""
    return Q.lt(u, v) | Q.positive(v - u)


ROUNDING = [
    # F1, F2: floor/ceiling of an integer, or of +-oo, is itself.
    (F(x), x, Q.integer(x) | (Q.infinite(x) & Q.extended_real(x))),
]

SHIFT = [
    # F3: an integer term shifts out: floor(n + x) = n + floor(x), same for ceiling.
    (F(n + x), n + F(x), Q.integer(n)),
    # F3: floor/ceiling of a finite y is a (Gaussian) integer and shifts out too
    # (not for y = oo: floor(1/2 + floor(oo)) is not 1/2 + oo in AccumBounds terms).
    (F(floor(y) + x), floor(y) + F(x), Q.finite(y)),
    (F(ceiling(y) + x), ceiling(y) + F(x), Q.finite(y)),
]

# F4 (floor(x) = 0 for 0 <= x < 1, ceiling likewise) is the base layer's
# floor_of_bounded, the dispatcher's fallback for both keys.
FLOOR = CEILING = ROUNDING + SHIFT

FRAC = [
    # R1: frac of an integer is 0.
    (frac(x), S.Zero, Q.integer(x)),
    # R2: integer terms drop out: frac(n + x) = frac(x).
    (frac(n + x), frac(x), Q.integer(n)),
    (frac(floor(y) + x), frac(x), Q.finite(y)),
    (frac(ceiling(y) + x), frac(x), Q.finite(y)),
    # R3: frac(x) = x for 0 <= x < 1 (a merely real x is left alone).
    (frac(x), x, Q.nonnegative(x) & _lt(x, 1)),
]

MULTIPLE = [
    # M1/Q1 (and M2/Q2 even): Mod(a, b) = Rem(a, b) = 0 when a is an integer multiple of a nonzero b.
    (G(a, b), S.Zero, Q.nonzero(b) & Q.integer(a/b)),
]

MOD = MULTIPLE + [
    # M2 odd, generalized: a/b = m + 1/2 gives Mod(a, b) = b/2; exact for every real
    # b != 0.  Not for non-real b: SymPy's Mod of non-real arguments is not
    # a - b*floor(a/b) (Mod(3*I, 2*I) = 3*I, Mod(-3*I, 2*I) = -I).
    (Mod(a, b), b/2, Q.nonzero(b) & Q.odd(2*a/b)),
    # M3: terms that are integer multiples of b drop out: Mod(c + x, b) = Mod(x, b).
    (Mod(c + x, b), Mod(x, b), Q.nonzero(b) & Q.integer(c/b)),
    # M4: Mod(a, b) = a inside the period, 0 <= a < b or b < a <= 0.
    (Mod(a, b), a, (Q.nonnegative(a) & _lt(a, b)) | (Q.nonpositive(a) & _lt(b, a))),
    # M5: Mod and Rem agree when a and b have the same sign
    # (never the reverse rewrite, so the two tables cannot loop).
    (Mod(a, b), Rem(a, b), (Q.nonnegative(a) & Q.positive(b)) | (Q.nonpositive(a) & Q.negative(b))),
]

REM = MULTIPLE + [
    # Q2 odd, generalized: a/b = m + 1/2 truncates towards zero, so Rem(a, b) is
    # b/2 for a/b > 0 and -b/2 for a/b < 0 (an odd a of unknown sign stays).
    (Rem(a, b), b/2, Q.odd(2*a/b) & Q.positive(a/b)),
    (Rem(a, b), -b/2, Q.odd(2*a/b) & Q.negative(a/b)),
    # Q3: Rem(a, b) = a for -|b| < a < |b|, each branch fixing the sign of b.
    # Integer shifts are not pulled out of Rem (the shift can flip the sign of a).
    (Rem(a, b), a, (Q.nonnegative(a) & (_lt(a, b) | _lt(a, -b)))
                   | (Q.nonpositive(a) & (_lt(-b, a) | _lt(b, a)))
                   | (Q.positive(b) & _lt(-b, a) & _lt(a, b))
                   | (Q.negative(b) & _lt(b, a) & _lt(a, -b))),
]

RULES: list[tuple] = FLOOR + FRAC + MOD + REM[len(MULTIPLE):]

handlers_dict['floor'] = compile_table(FLOOR)
handlers_dict['ceiling'] = compile_table(CEILING)
handlers_dict['frac'] = compile_table(FRAC)
handlers_dict['Mod'] = compile_table(MOD)
handlers_dict['Rem'] = compile_table(REM)
