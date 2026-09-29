"""``floor``, ``ceiling``, ``frac``, ``Mod`` and ``Rem``.

Rounding: ``floor`` and ``ceiling`` leave an integer (and an infinity) as it is,
and an integer term moves out of them.  ``frac`` is defined as ``x - floor(x)``,
so it is 0 at an integer and drops an integer term.  Bounds (``floor(x) = 0`` for
``0 <= x < 1``) are interval arithmetic, not rows: ``floor_of_bounded`` in
:mod:`._simple`.

Remainders: ``Mod(a, b)`` has the sign of ``b`` (Python's ``%``), ``Rem(a, b)``
the sign of ``a`` (truncating division).  Both are 0 at a multiple of ``b`` and
``a`` itself inside the period, and they agree when ``a`` and ``b`` have the same
sign.  ``Q.nonzero(b)`` in their conditions also makes ``b`` real: SymPy's ``Mod``
of non-real arguments is not ``a - b*floor(a/b)`` (``Mod(3*I, 2*I) = 3*I``).

Two things the conditions spell out because ``ask`` does not derive them:
"integer" includes Gaussian integers (SymPy takes the floor of a complex number
part by part, so ``floor(y)`` of a finite ``y`` is one), and ``u < v`` is asked
both as ``Q.lt(u, v)`` and as ``Q.positive(v - u)``.

Not stated as definitions, because they derive nothing the rows below do not
(measured 2026-09-24): ``ceiling(x) = -floor(-x)``, ``Mod(a, b) = a -
b*floor(a/b)``, ``Rem`` by truncation.  Pattern forms these rows rely on are
pinned in ``tests/refine_identities/core/test_engine_integer_funcs.py``.
"""
from __future__ import annotations

from sympy import Mod, Q, S, ceiling, floor, frac, im, re, sign, symbols
from sympy.functions.elementary.miscellaneous import Rem

from ._tables import Family, Identities, Rules, given, node_measure, part


def integer(u):
    """``u`` is an integer or a Gaussian integer (integral real and imaginary parts)."""
    return Q.integer(u) | (Q.integer(re(u)) & Q.integer(im(u)))


def less(u, v):
    """``u < v``, in both spellings ``ask`` understands."""
    return Q.lt(u, v) | Q.positive(v - u)


def _is_rounded(t):
    """``t`` is an integer times a ``floor`` or ``ceiling``: a Gaussian integer ``ask`` cannot see."""
    k, f = t.as_coeff_Mul()
    return S(bool(k.is_Integer and isinstance(f, (floor, ceiling))))


# Throughout: n is an integer and b is nonzero (real).  a, c, d and x are arbitrary.
a, b, c, d, n, x = symbols('a b c d n x')
rounded = part('rounded', _is_rounded)   # a term floor(y) or ceiling(y) of a sum
rows = given({n: integer, b: Q.nonzero})


# ---- floor, ceiling, frac ------------------------------------------------------

def rounding(f):
    return rows([
        (f(x), x, integer(x) | Q.infinite(x)),   # floor(3) = 3, floor(oo) = oo
        (f(n + x), f(x) + n),                    # floor(x + 3) = floor(x) + 3
        # the same for a term floor(y), whether y is finite or not (floor(oo + x) = oo + floor(x))
        (f(rounded + x), f(x) + rounded),
    ])


FLOOR = rounding(floor)
CEILING = rounding(ceiling)

FRAC = rows([
    (frac(n + x), frac(x)),                      # frac(x + 3) = frac(x)
])

FRAC_DEFINITION = rows([
    # gives frac(3) = 0 and frac(x) = x - k on [k, k + 1).  Not at +-oo, where frac is
    # AccumBounds(0, 1); Q.real and integer imply Q.finite, but ask does not see it.
    (frac(x), x - floor(x), Q.finite(x) | Q.real(x) | integer(x)),
])


# ---- Mod, Rem ------------------------------------------------------------------

def multiple(f):
    return rows([
        (f(a, b), S.Zero, Q.integer(a/b)),       # Mod(6, 3) = 0
        (f(a, d), S.Zero, Q.zero(a)),            # Mod(0, d) = 0, whatever d is
    ])


MOD = multiple(Mod) + rows([
    (Mod(c + x, b), Mod(x, b), Q.integer(c/b)),                                          # Mod(x + 6, 3) = Mod(x, 3)
    (Mod(a, d), a, (Q.nonnegative(a) & less(a, d)) | (Q.nonpositive(a) & less(d, a))),   # 0 <= a < d, d < a <= 0
    # same signs; never the reverse rewrite, so Mod and Rem cannot loop
    (Mod(a, d), Rem(a, d), (Q.nonnegative(a) & Q.positive(d)) | (Q.nonpositive(a) & Q.negative(d))),
])

REM = multiple(Rem) + rows([   # Rem(a, d) = a for |a| < |d|, one row per way the signs can be known
    (Rem(a, d), a, Q.nonnegative(a) & (less(a, d) | less(a, -d))),   # 0 <= a < |d|
    (Rem(a, d), a, Q.nonpositive(a) & (less(-d, a) | less(d, a))),   # -|d| < a <= 0
    (Rem(a, d), a, Q.positive(d) & less(-d, a) & less(a, d)),        # -d < a < d
    (Rem(a, d), a, Q.negative(d) & less(d, a) & less(a, -d)),        # d < a < -d
])

# At a half period (a/b = k + 1/2): Mod(a, b) = b/2, and Rem(a, b) = b/2 or -b/2 by the
# sign of a/b.  Identity rows: they fire once the assumptions decide sign(a/b).
MOD_HALF = rows([(Mod(a, b), b*Mod(sign(a/b), 2)/2, Q.odd(2*a/b))])   # Mod(+-1, 2) = 1
REM_HALF = rows([(Rem(a, b), sign(a/b)*b/2, Q.odd(2*a/b))])


FACTS = FRAC_DEFINITION + MOD_HALF + REM_HALF
RULES = FLOOR + CEILING + FRAC + MOD + REM


def _half(rows, f):
    return Identities(rows, measure=node_measure((f,)), opaque=(floor, sign))


SPEC = Family({'floor': Rules(FLOOR),
               'ceiling': Rules(CEILING),
               'frac': (Rules(FRAC), Identities(FRAC_DEFINITION, measure=node_measure((frac,)))),
               'Mod': (Rules(MOD), _half(MOD_HALF, Mod)),
               'Rem': (Rules(REM), _half(REM_HALF, Rem))},
              facts=FACTS, rules=RULES)
