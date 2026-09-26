"""``floor``, ``ceiling``, ``frac``, ``Mod`` and ``Rem`` as rule tables and definitions.

**9 rows** (v3's ``handlers_v3/integer_funcs.py``: 252 lines; phase 1: 17
rule rows): 2 identity rows (``FACTS``) and 7 rule rows (``RULES``).

``FACTS`` are identity rows ``(lhs, rhs, domain)`` run by
:func:`..core.rewrite.identity_handler`: they fire when the bookkeeping in the
right side (``floor``, ``sign``) collapses, and the measure (nodes of the
row's head) must drop, so a result comes back in the user's function or not
at all.

* ``frac(x) = x - floor(x)``, the definition, replaces three rows of phase 1:
  ``frac`` of an integer (floor's integer row), ``frac(x) = x`` on ``[0, 1)``
  (the bounds rule behind ``floor``; the definition also gives ``x - k`` on
  ``[k, k + 1)``, beyond v3).  ``frac``'s integer shifts are the ``floor``
  shift rows: the shift rows are written ``F(n + x) = F(x) + F(n)`` over a
  generic head that ``floor``, ``ceiling`` and ``frac`` share (``F(n)`` is
  ``n``, ``n`` and ``0``), which replaces ``frac``'s own three.  The
  shift and integer rows take Gaussian integers (integral ``re`` and
  ``im``, which satassume proves for ``floor(y)`` and ``ceiling(y)`` of a
  finite ``y`` since ``main`` 9dfc27d), which replaces the four phase-1
  rows for ``floor(y)``/``ceiling(y)`` terms.
* ``G(a, b) = b*G(sign(a/b), 2)/2`` for ``2*a/b`` odd, shared by ``Mod``
  and ``Rem``, replaces three rows (``Mod``'s ``b/2`` and ``Rem``'s ``+-b/2``).

Rows (rules): two ``floor``/``ceiling`` rows over a generic head (integer
argument, integer shift; ``frac`` shares the shift), one ``Mod``/``Rem``
row over a generic two-argument head (multiples), ``Mod`` 3 (shift by a
multiple, inside the period, ``Mod = Rem`` for equal signs), ``Rem`` 1
(inside the period).

**Definitions tried and not used** (measured 2026-09-24):

* ``ceiling(x) = -floor(-x)``: every ``ceiling`` row is already a ``floor``
  row through the generic head, so the definition drops nothing, and its
  shifts would need a fold back from ``-floor(-u)`` to ``ceiling(u)``.
* ``Mod(a, b) = a - b*floor(a/b)`` (domain: real ``a``, real nonzero ``b``;
  SymPy's ``Mod`` of non-real arguments is not the formula, see the
  ``G`` row): with it in place of the ``Mod`` rows, 7 tests fail.  It
  derives none of them: the half-integer case needs a ``floor`` row for
  half-integers, the shift leaves ``x - b*floor(x/b)`` (a fold back to
  ``Mod`` and, since ``Mod(x + 2*n, 2) = Mod(x, 2)`` holds for complex
  ``x`` in SymPy, a complex domain would be needed), and ``floor(a/b) = 0``
  for ``0 <= a < b`` is beyond the interval reasoning (affine arguments
  with numeric coefficients only).
* ``Rem`` by truncation (``a - b*sign(a/b)*floor(Abs(a/b))``): the same
  obstacles; its one derivable case is the ``G`` row.
* ``frac``'s shifts through the definition (``frac(n + x) = x - floor(x)``,
  folded back to ``frac(x)``): the definition is false at ``x = +-oo``
  (``frac(oo)`` is ``AccumBounds(0, 1)``, ``oo - floor(oo)`` is ``nan``), so
  its domain is finite ``x`` and the shift of an unconstrained ``x`` would
  be lost; the shared shift rows hold at infinity.

``floor(x) + frac(x)`` is not rewritten to ``x``: refinement is per node and
no row sees both terms (an ``Add`` row would; none is registered).

Lost against phase 1: ``Mod(a, b) -> b/2`` for ``2*a/b`` odd when neither the
sign of ``a`` nor of ``b`` is known (the ``G`` row needs ``sign(a/b)`` decided
or a sign split on one symbol to agree; nested splits are not tried).  Not
in the battery, the tests or v3.

Pattern forms and matcher behavior this table relies on are pinned in
``tests/refine_identities/test_engine_integer_funcs.py``.
Checked (adversarial pass, 2026-09-24, on the phase-1 rows, which the rows
here restate): every row at 0, +-1, integer and half-integer boundaries,
+-oo, non-real points, relation bounds against an infinite divisor,
old-style symbols, plus ``python -m satrefine.tools.refine_differential`` seeds 2, 3, 7.
Not defects: ``Mod``/``Rem -> a`` under ``Q.lt(a, b)`` at ``b = oo`` (SymPy's
ask calls ``Q.lt(a, b) & Q.infinite(b)`` inconsistent: relations are over
the reals); the shift rows at ``oo`` (both sides ``AccumBounds(0, 1)`` for
``frac``).  Unverified: ``Rem`` for non-real arguments (SymPy leaves
``Rem`` of non-real numbers unevaluated; the ``G`` row's ``Q.nonzero(b)``
makes ``b`` real, and ``2*a/b`` odd then makes ``a`` real).
"""
from __future__ import annotations

from sympy import Function, Mod, Q, S, ceiling, floor, frac, im, re, sign, symbols, true
from sympy.functions.elementary.miscellaneous import Rem

from ._tables import Family, Identities, Rules, node_measure, part

a, b, c, n, x, y = symbols('a b c n x y')
F = Function('F')        # generic head: the row serves every key it is registered under
G = Function('G')        # generic two-argument head: Mod and Rem


def _lt(u, v):
    """``u < v`` in both spellings ``ask`` understands."""
    return Q.lt(u, v) | Q.positive(v - u)


def _gaussian_integer(u):
    """``u`` is an integer, or a Gaussian integer (``floor(y)`` and ``ceiling(y)`` of a
    finite ``y`` are: SymPy's floor of a complex number is taken part by part)."""
    return Q.integer(u) | (Q.integer(re(u)) & Q.integer(im(u)))


FACTS = [   # (lhs, rhs, domain): identity rows, fire when the bookkeeping collapses
    # the definition of frac: covers frac(integer) = 0 (floor's first row) and frac(x) = x - k
    # on [k, k + 1) (the bounds rule behind floor; v3's R3 is k = 0).  Not at +-oo:
    # frac(oo) is AccumBounds(0, 1).  (Q.real and a Gaussian integer imply Q.finite; they
    # are spelled out because ask does not derive finiteness from stated bounds or from
    # integral real and imaginary parts.)
    (frac(x), x - floor(x), Q.finite(x) | Q.real(x) | _gaussian_integer(x)),
    # M2/Q2 odd: a/b = m + 1/2 has floor m and truncation m or m + 1 by the sign of a/b,
    # so Mod(a, b) = b/2 and Rem(a, b) = +-b/2: both are b/2 times the function at
    # (sign(a/b), 2) (Mod(+-1, 2) = 1, Rem(+-1, 2) = +-1).  Fires when sign(a/b) is decided
    # or its sign cases agree (Mod); an odd a of unknown sign stays for Rem.  Q.nonzero(b)
    # is real and nonzero: SymPy's Mod of non-real arguments is not a - b*floor(a/b)
    # (Mod(3*I, 2*I) = 3*I, Mod(-3*I, 2*I) = -I), Rem(a, 0) is undefined (SymPy raises),
    # and the engine's sign split evaluates the left side at b = 0 unless zero is excluded
    # (needs/test_defs_case_split_zero_point_raises.py).
    (G(a, b), b*G(sign(a/b), 2)/2, Q.nonzero(b) & Q.odd(2*a/b)),
]

ROUNDING = [
    # F1, F2: floor/ceiling of a (Gaussian) integer, or of an infinity, is itself
    # (floor(oo) = oo, floor(-oo) = -oo, floor(zoo) = zoo, floor(oo*I) = oo*I).
    (F(x), x, _gaussian_integer(x) | Q.infinite(x)),
]

SHIFT = [
    # F3, R2: a (Gaussian) integer term shifts out: F(n + x) = F(x) + F(n) for floor,
    # ceiling and frac (F(n) is then n, n and 0 by the rows above).  Not a term floor(y)
    # of an infinite y: re(floor(oo)) is not an integer (floor(1/2 + floor(oo)) is not
    # 1/2 + oo in AccumBounds terms).
    (F(n + x), F(x) + F(n), _gaussian_integer(n)),
]


def _rounded(t):
    """``t`` is an integer multiple of a ``floor`` or ``ceiling``."""
    k, f = t.as_coeff_Mul()
    return S(bool(k.is_Integer and isinstance(f, (floor, ceiling))))


g = part('g', _rounded)

ROUNDED_SHIFT = [
    # F3 for rounded terms, which ask cannot show (Gaussian) integers: floor(y) and
    # ceiling(y) of a finite y are Gaussian integers; of an infinite y they are y,
    # which absorbs the rest as the left side does (floor(oo + x) = oo + floor(x)).
    (F(g + x), F(x) + g, true),
]

# F4 (floor(x) = 0 for 0 <= x < 1, ceiling likewise) is the base layer's
# floor_of_bounded, the dispatcher's fallback for both keys.
FLOOR = CEILING = ROUNDING + SHIFT + ROUNDED_SHIFT
FRAC = SHIFT

MULTIPLE = [
    # M1/Q1 (and M2/Q2 even): Mod(a, b) = Rem(a, b) = 0 when a is an integer multiple of a nonzero b.
    (G(a, b), S.Zero, Q.nonzero(b) & Q.integer(a/b)),
    # Mod(0, b) = Rem(0, b) = 0 whatever b is known to be (at b = 0 the left side is undefined).
    (G(a, b), S.Zero, Q.zero(a)),
]

MOD = MULTIPLE + [
    # M3: terms that are integer multiples of b drop out: Mod(c + x, b) = Mod(x, b).
    (Mod(c + x, b), Mod(x, b), Q.nonzero(b) & Q.integer(c/b)),
    # M4: Mod(a, b) = a inside the period, 0 <= a < b or b < a <= 0.
    (Mod(a, b), a, (Q.nonnegative(a) & _lt(a, b)) | (Q.nonpositive(a) & _lt(b, a))),
    # M5: Mod and Rem agree when a and b have the same sign
    # (never the reverse rewrite, so the two tables cannot loop).
    (Mod(a, b), Rem(a, b), (Q.nonnegative(a) & Q.positive(b)) | (Q.nonpositive(a) & Q.negative(b))),
]

REM = MULTIPLE + [
    # Q3: Rem(a, b) = a for -|b| < a < |b|, each branch fixing the sign of b.
    # Integer shifts are not pulled out of Rem (the shift can flip the sign of a).
    (Rem(a, b), a, (Q.nonnegative(a) & (_lt(a, b) | _lt(a, -b)))
                   | (Q.nonpositive(a) & (_lt(-b, a) | _lt(b, a)))
                   | (Q.positive(b) & _lt(-b, a) & _lt(a, b))
                   | (Q.negative(b) & _lt(b, a) & _lt(a, -b))),
]

RULES: list[tuple] = ROUNDING + SHIFT + ROUNDED_SHIFT + MOD + REM[len(MULTIPLE):]


def _instance(row: tuple, head: type) -> tuple:
    """A generic-head identity row for one head (the identity engine and the generator
    need the head: the measure counts its nodes and the catalog specializes its left side)."""
    return tuple(t.replace(G, head) for t in row)


MOD_FACTS = [_instance(FACTS[1], Mod)]
REM_FACTS = [_instance(FACTS[1], Rem)]

SPEC = Family({'floor': Rules(FLOOR), 'ceiling': Rules(CEILING),
               'frac': (Rules(FRAC), Identities(FACTS[:1], measure=node_measure((frac,)))),
               'Mod': (Rules(MOD), Identities(MOD_FACTS, measure=node_measure((Mod,)), opaque=(floor, sign))),
               'Rem': (Rules(REM), Identities(REM_FACTS, measure=node_measure((Rem,)), opaque=(floor, sign)))},
              facts=FACTS, rules=RULES)
