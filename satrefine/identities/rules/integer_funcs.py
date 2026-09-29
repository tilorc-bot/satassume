"""``floor``, ``ceiling``, ``frac``, ``Mod`` and ``Rem``.

Rounding: ``floor`` and ``ceiling`` leave an integer (and an infinity) as it is,
and an integer term moves out of them.  ``frac`` is defined as ``x - floor(x)``,
so it is 0 at an integer and drops an integer term.  Bounds (``floor(x) = 0`` for
``0 <= x < 1``) are interval arithmetic, not rows: ``floor_of_bounded`` in
:mod:`._simple`.

Remainders: ``Mod(a, d)`` has the sign of ``d`` (Python's ``%``), ``Rem(a, d)``
the sign of ``a`` (truncating division).  Both are 0 at a multiple of ``d`` and
``a`` itself inside the period, and they agree when ``a`` and ``d`` have the same
sign.  ``d`` is assumed nonzero, which also makes it real: SymPy's ``Mod``
of non-real arguments is not ``a - d*floor(a/d)`` (``Mod(3*I, 2*I) = 3*I``).

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


a, b, c, d, f, g, h, m, n, w, x, zero = symbols('a b c d f g h m n w x zero')

# Assumed throughout: a row takes each fact whose variables are all in its left side.
# The letters follow the tables' convention (n, m integers; d nonzero; a, b, c, w, x arbitrary).
ASSUMED = {integer(n), Q.nonzero(d)}   # n is an integer (Gaussian included), d is nonzero


# ---- floor, ceiling, frac ------------------------------------------------------

ASSUMED |= {integer(h) | Q.infinite(h)}   # h is an integer or an infinity

# g is a floor or ceiling term: floor(w) or ceiling(w), times an integer m.  (The m-less
# forms are listed because a pattern m*floor(w) does not match floor(w) itself.)
ASSUMED |= {Q.integer(m),
            Eq(g, floor(w)) | Eq(g, m*floor(w)) | Eq(g, ceiling(w)) | Eq(g, m*ceiling(w))}

FLOOR = [
    (floor(h), h),                       # floor(3) = 3, floor(oo) = oo
    (floor(n + x), floor(x) + n),        # floor(x + 3) = floor(x) + 3
    # g moves out as n does, for any w: floor(w) is an integer or, for an infinite w, w
    # itself, which absorbs the rest.  SymPy's floor returns an infinite argument unchanged
    # (floor(1/2 + I*oo) = 1/2 + I*oo, where flooring each part gives I*oo), so its
    # expressions can keep a finite part there that these rows drop: the same value.
    (floor(g + x), floor(x) + g),
]

CEILING = [
    (ceiling(h), h),
    (ceiling(n + x), ceiling(x) + n),
    (ceiling(g + x), ceiling(x) + g),
]

FRAC = [
    (frac(n + x), frac(x)),              # frac(x + 3) = frac(x)
]

# f is finite.  (A Gaussian integer f is too, but ask does not see it: issue #19.)  Not
# at +-oo, where frac is AccumBounds(0, 1).
ASSUMED |= {Q.finite(f) | Q.real(f) | integer(f)}

FRAC_DEFINITION = [
    (frac(f), f - floor(f)),             # gives frac(3) = 0 and frac(f) = f - n on [n, n + 1)
]


# ---- Mod, Rem ------------------------------------------------------------------
# d is nonzero; b is any divisor.

ASSUMED |= {Q.zero(zero)}

MOD = [
    (Mod(a, d), S.Zero, Q.integer(a/d)),                                                 # Mod(6, 3) = 0
    (Mod(zero, b), S.Zero),                                                              # Mod(0, b) = 0
    (Mod(c + x, d), Mod(x, d), Q.integer(c/d)),                                          # Mod(x + 6, 3) = Mod(x, 3)
    (Mod(a, b), a, (Q.nonnegative(a) & less(a, b)) | (Q.nonpositive(a) & less(b, a))),   # 0 <= a < b, b < a <= 0
    # same signs; never the reverse rewrite, so Mod and Rem cannot loop
    (Mod(a, b), Rem(a, b), (Q.nonnegative(a) & Q.positive(b)) | (Q.nonpositive(a) & Q.negative(b))),
]

REM = [
    (Rem(a, d), S.Zero, Q.integer(a/d)),                                 # Rem(6, 3) = 0
    (Rem(zero, b), S.Zero),                                              # Rem(0, b) = 0
    # Rem(a, b) = a for |a| < |b|, one row per way the signs can be known
    (Rem(a, b), a, Q.nonnegative(a) & (less(a, b) | less(a, -b))),      # 0 <= a < |b|
    (Rem(a, b), a, Q.nonpositive(a) & (less(-b, a) | less(b, a))),      # -|b| < a <= 0
    (Rem(a, b), a, Q.positive(b) & less(-b, a) & less(a, b)),           # -b < a < b
    (Rem(a, b), a, Q.negative(b) & less(b, a) & less(a, -b)),           # b < a < -b
]

# At a half period (a/d = n + 1/2): Mod(a, d) = d/2, and Rem(a, d) = d/2 or -d/2 by the
# sign of a/d.  Identity rows: they fire once the assumptions decide sign(a/d).
MOD_HALF = [(Mod(a, d), d*Mod(sign(a/d), 2)/2, Q.odd(2*a/d))]   # Mod(+-1, 2) = 1
REM_HALF = [(Rem(a, d), sign(a/d)*d/2, Q.odd(2*a/d))]


FACTS = FRAC_DEFINITION + MOD_HALF + REM_HALF
RULES = FLOOR + CEILING + FRAC + MOD + REM

SPEC = Family({'floor': Rules(FLOOR),
               'ceiling': Rules(CEILING),
               'frac': (Rules(FRAC), Identities(FRAC_DEFINITION, measure=node_measure((frac,)))),
               'Mod': (Rules(MOD), Identities(MOD_HALF, measure=node_measure((Mod,)), opaque=(floor, sign))),
               'Rem': (Rules(REM), Identities(REM_HALF, measure=node_measure((Rem,)), opaque=(floor, sign)))},
              facts=FACTS, rules=RULES, assumed=ASSUMED)
