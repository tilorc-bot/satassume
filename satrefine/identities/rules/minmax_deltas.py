"""``Max``, ``Min``, ``KroneckerDelta``, ``Heaviside`` and ``DiracDelta``."""
from __future__ import annotations

from sympy import Abs, DiracDelta, Function, Heaviside, KroneckerDelta, Max, Min, Piecewise, Q, S, Tuple, nan, symbols

from ._tables import add_rules

a, b, d, i, j, lo, hi, inf, ninf, r, t, u, w = symbols('a b d i j lo hi inf ninf r t u w')
G = Function('G')  # DiracDelta(d, r), the r-th derivative, which SymPy won't build for a symbol r

FACTS = (
    add_rules(set(), [
        (Max(a, b), Piecewise((a, Q.ge(a, b)), (b, Q.lt(a, b)))),
        (Min(a, b), Piecewise((a, Q.le(a, b)), (b, Q.gt(a, b)))),
    ])
    + add_rules(set(), [
        (KroneckerDelta(i, j), Piecewise((1, Q.eq(i, j)), (0, Q.ne(i, j)), (nan, True))),
    ])
    + add_rules({Q.extended_real(u)}, [
        (KroneckerDelta(i, j, Tuple(lo, hi)), Piecewise((1, Q.eq(i, j) & Q.le(lo, i) & Q.le(i, hi)), (0, True))),
        (Heaviside(u, w), Piecewise((0, Q.extended_negative(u)), (w, Q.zero(u)), (1, Q.extended_positive(u)),
                                    (nan, True))),
    ])
)

INFINITE = add_rules({Q.positive_infinite(inf), Q.negative_infinite(ninf)}, [
    (Max(inf, b), inf),
    (Max(ninf, b), b),
    (Min(ninf, b), ninf),
    (Min(inf, b), b),
])

DIRAC = add_rules({Q.nonzero(d), Q.real(t)}, [
    (DiracDelta(d), S.Zero),
    (G(d, r), S.Zero),
    (DiracDelta(d*t), DiracDelta(t)/Abs(d)),
])

RULES = DIRAC + INFINITE
