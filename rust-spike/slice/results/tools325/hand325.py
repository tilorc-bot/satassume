"""hand325.py (sa-port-325): hand-picked points for class (i) rows the search left with one side, checked by the same
exact substitution (exact325.witness). A point here is my choice; only the substitution decides. OFFLINE ONLY."""
from sympy import Rational as R, Symbol, oo
from evalbench.fuzz import queries
import exact325 as X
x, y = Symbol("x"), Symbol("y")
pairs = queries(424242)
HAND = [  # (id, value p should take, point)
    (1056, False, {x: R(10), y: R(23)}),
    (1217, True, {x: R(13, 24), y: R(5, 12)}),
    (1840, False, {x: R(5, 4), y: R(0)}),
    (2275, True, {x: R(33, 16), y: R(5, 16)}),
    (2283, False, {x: R(-5, 2), y: R(-11, 10)}),
    (2612, True, {x: R(-1, 10), y: R(3, 2)}),
    (2687, False, {x: R(-1, 10), y: R(-4, 5)}),
    (732, False, {x: oo, y: R(0)}), (732, False, {x: -oo, y: R(0)}), (732, True, {x: oo, y: R(0)}),
]
for i, want, pt in HAND:
    p, a = pairs[i]
    print("fuzz", i, "want p", want, "at", pt, "->", X.witness(p, a, pt, want), "|", p, "|", a)
