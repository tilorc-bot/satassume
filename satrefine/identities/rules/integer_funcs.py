"""``floor``, ``ceiling``, ``frac``, ``Mod`` and ``Rem``.

Rounding: ``floor`` and ``ceiling`` leave an integer (and an infinity) as it is,
and an integer term moves out of them.  ``frac`` is defined as ``x - floor(x)``,
so it is 0 at an integer and drops an integer term.  Bounds (``floor(x) = 0`` for
``0 <= x < 1``) are interval arithmetic, not rows: ``floor_of_bounded`` in
:mod:`._simple`.

Remainders: ``Mod(a, b)`` has the sign of ``b`` (Python's ``%``), ``Rem(a, b)``
the sign of ``a`` (truncating division).  Both are 0 at a multiple of ``b`` and
``a`` itself inside the period, and they agree when ``a`` and ``b`` have the same
sign.  ``b`` is assumed nonzero, which also makes it real: SymPy's ``Mod``
of non-real arguments is not ``a - b*floor(a/b)`` (``Mod(3*I, 2*I) = 3*I``).

Two things the assumptions spell out because ``ask`` does not derive them:
"integer" includes Gaussian integers (SymPy takes the floor of a complex number
part by part, so ``floor(y)`` of a finite ``y`` is one), and ``u < v`` is asked
both as ``Q.lt(u, v)`` and as ``Q.positive(v - u)``.

Not stated as definitions, because they derive nothing the rows below do not
(measured 2026-09-24): ``ceiling(x) = -floor(-x)``, ``Mod(a, b) = a -
b*floor(a/b)``, ``Rem`` by truncation.  Pattern forms these rows rely on are
pinned in ``tests/refine_identities/core/test_engine_integer_funcs.py``.
"""
from __future__ import annotations

from sympy import Eq, Mod, Q, S, ceiling, floor, frac, im, re, sign, symbols
from sympy.functions.elementary.miscellaneous import Rem

from ._tables import Family, Identities, Rules, node_measure


def integer(u):
    """``u`` is an integer or a Gaussian integer (integral real and imaginary parts)."""
    return Q.integer(u) | (Q.integer(re(u)) & Q.integer(im(u)))


def less(u, v):
    """``u < v``, in both spellings ``ask`` understands."""
    return Q.lt(u, v) | Q.positive(v - u)


a, b, c, d, k, m, n, r, t, x, y, z = symbols('a b c d k m n r t x y z')

# Assumed throughout: a row takes each fact whose variables are all in its left side.
ASSUMED = {integer(n), Q.nonzero(b)}   # n is an integer, b is nonzero


# ---- floor, ceiling, frac ------------------------------------------------------

ASSUMED |= {integer(k) | Q.infinite(k)}   # k is an integer or an infinity

# r is a floor or ceiling term: floor(t) or ceiling(t), times an integer m.  (The m-less
# forms are listed because a pattern m*floor(t) does not match floor(t) itself.)
ASSUMED |= {Q.integer(m),
            Eq(r, floor(t)) | Eq(r, m*floor(t)) | Eq(r, ceiling(t)) | Eq(r, m*ceiling(t))}

FLOOR = [
    (floor(k), k),                       # floor(3) = 3, floor(oo) = oo
    (floor(n + x), floor(x) + n),        # floor(x + 3) = floor(x) + 3
    # r moves out as n does, for any t: floor(t) is an integer or, for an infinite t, t
    # itself, which absorbs the rest.  SymPy's floor returns an infinite argument unchanged
    # (floor(1/2 + I*oo) = 1/2 + I*oo, where flooring each part gives I*oo), so its
    # expressions can keep a finite part there that these rows drop: the same value.
    (floor(r + x), floor(x) + r),
]

CEILING = [
    (ceiling(k), k),
    (ceiling(n + x), ceiling(x) + n),
    (ceiling(r + x), ceiling(x) + r),
]

FRAC = [
    (frac(n + x), frac(x)),              # frac(x + 3) = frac(x)
]

# y is finite.  (A Gaussian integer y is too, but ask does not see it: issue #19.)  Not
# at +-oo, where frac is AccumBounds(0, 1).
ASSUMED |= {Q.finite(y) | Q.real(y) | integer(y)}

FRAC_DEFINITION = [
    (frac(y), y - floor(y)),             # gives frac(3) = 0 and frac(y) = y - k on [k, k + 1)
]


# ---- Mod, Rem ------------------------------------------------------------------
# b is nonzero; d is any divisor.

ASSUMED |= {Q.zero(z)}   # z is 0

MOD = [
    (Mod(a, b), S.Zero, Q.integer(a/b)),                                                 # Mod(6, 3) = 0
    (Mod(z, d), S.Zero),                                                                 # Mod(0, d) = 0
    (Mod(c + x, b), Mod(x, b), Q.integer(c/b)),                                          # Mod(x + 6, 3) = Mod(x, 3)
    (Mod(a, d), a, (Q.nonnegative(a) & less(a, d)) | (Q.nonpositive(a) & less(d, a))),   # 0 <= a < d, d < a <= 0
    # same signs; never the reverse rewrite, so Mod and Rem cannot loop
    (Mod(a, d), Rem(a, d), (Q.nonnegative(a) & Q.positive(d)) | (Q.nonpositive(a) & Q.negative(d))),
]

REM = [
    (Rem(a, b), S.Zero, Q.integer(a/b)),                                 # Rem(6, 3) = 0
    (Rem(z, d), S.Zero),                                                 # Rem(0, d) = 0
    # Rem(a, d) = a for |a| < |d|, one row per way the signs can be known
    (Rem(a, d), a, Q.nonnegative(a) & (less(a, d) | less(a, -d))),      # 0 <= a < |d|
    (Rem(a, d), a, Q.nonpositive(a) & (less(-d, a) | less(d, a))),      # -|d| < a <= 0
    (Rem(a, d), a, Q.positive(d) & less(-d, a) & less(a, d)),           # -d < a < d
    (Rem(a, d), a, Q.negative(d) & less(d, a) & less(a, -d)),           # d < a < -d
]

# At a half period (a/b = k + 1/2): Mod(a, b) = b/2, and Rem(a, b) = b/2 or -b/2 by the
# sign of a/b.  Identity rows: they fire once the assumptions decide sign(a/b).
MOD_HALF = [(Mod(a, b), b*Mod(sign(a/b), 2)/2, Q.odd(2*a/b))]   # Mod(+-1, 2) = 1
REM_HALF = [(Rem(a, b), sign(a/b)*b/2, Q.odd(2*a/b))]


FACTS = FRAC_DEFINITION + MOD_HALF + REM_HALF
RULES = FLOOR + CEILING + FRAC + MOD + REM

SPEC = Family({'floor': Rules(FLOOR),
               'ceiling': Rules(CEILING),
               'frac': (Rules(FRAC), Identities(FRAC_DEFINITION, measure=node_measure((frac,)))),
               'Mod': (Rules(MOD), Identities(MOD_HALF, measure=node_measure((Mod,)), opaque=(floor, sign))),
               'Rem': (Rules(REM), Identities(REM_HALF, measure=node_measure((Rem,)), opaque=(floor, sign)))},
              facts=FACTS, rules=RULES, assumed=ASSUMED)
