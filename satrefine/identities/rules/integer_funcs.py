"""``floor``, ``ceiling``, ``frac``, ``Mod`` and ``Rem``."""
from __future__ import annotations

from sympy import Eq, Mod, Q, S, ceiling, floor, frac, sign, symbols
from sympy.functions.elementary.miscellaneous import Rem

from ._tables import add_rules, by_cases, gaussian_integer

a, b, c, d, f, g, h, m, n, w, x, zero = symbols('a b c d f g h m n w x zero')

ASSUMED = {Q.integer(m),
           Eq(g, floor(w)) | Eq(g, m*floor(w)) | Eq(g, ceiling(w)) | Eq(g, m*ceiling(w))}

FLOOR = add_rules({gaussian_integer(n), gaussian_integer(h) | Q.infinite(h)}, [
    (floor(h), h),
    (floor(n + x), floor(x) + n),
    (floor(g + x), floor(x) + g),
])

CEILING = add_rules({gaussian_integer(n), gaussian_integer(h) | Q.infinite(h)}, [
    (ceiling(h), h),
    (ceiling(n + x), ceiling(x) + n),
    (ceiling(g + x), ceiling(x) + g),
])

FRAC = add_rules({gaussian_integer(n)}, [
    (frac(n + x), frac(x)),
])

FRAC_DEFINITION = add_rules({by_cases(Q.finite(f), Q.real(f), gaussian_integer(f))}, [
    (frac(f), f - floor(f)),
])

MOD = (
    add_rules({Q.nonzero(d), Q.integer(a/d)}, [
        (Mod(a, d), S.Zero),
    ])
    + add_rules({Q.zero(zero)}, [
        (Mod(zero, b), S.Zero),
    ])
    + add_rules({Q.nonzero(d), Q.integer(c/d)}, [
        (Mod(c + x, d), Mod(x, d)),
    ])
    + add_rules({Q.finite(b) & ((Q.nonnegative(a) & Q.lt(a, b)) | (Q.nonpositive(a) & Q.lt(b, a)))}, [
        (Mod(a, b), a),
    ])
    + add_rules({(Q.nonnegative(a) & Q.positive(b)) | (Q.nonpositive(a) & Q.negative(b))}, [
        (Mod(a, b), Rem(a, b)),
    ])
)

REM = (
    add_rules({Q.nonzero(d), Q.integer(a/d)}, [
        (Rem(a, d), S.Zero),
    ])
    + add_rules({Q.zero(zero)}, [
        (Rem(zero, b), S.Zero),
    ])
    + add_rules({Q.finite(b) & Q.nonnegative(a) & (Q.lt(a, b) | Q.lt(a, -b))}, [
        (Rem(a, b), a),
    ])
    + add_rules({Q.finite(b) & Q.nonpositive(a) & (Q.lt(-b, a) | Q.lt(b, a))}, [
        (Rem(a, b), a),
    ])
    + add_rules({Q.positive(b) & Q.lt(-b, a) & Q.lt(a, b)}, [
        (Rem(a, b), a),
    ])
    + add_rules({Q.negative(b) & Q.lt(b, a) & Q.lt(a, -b)}, [
        (Rem(a, b), a),
    ])
)

MOD_HALF = add_rules({Q.nonzero(d), Q.odd(2*a/d)}, [
    (Mod(a, d), d*Mod(sign(a/d), 2)/2),
])
REM_HALF = add_rules({Q.nonzero(d), Q.odd(2*a/d)}, [
    (Rem(a, d), sign(a/d)*d/2),
])

FACTS = FRAC_DEFINITION + MOD_HALF + REM_HALF
RULES = FLOOR + CEILING + FRAC + MOD + REM
