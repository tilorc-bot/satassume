"""A workload for `root_facts`, as `knowledge_fresh.py rootof`. See `reach` in the landing report: dev and fuzz may hold no
`ComplexRootOf` at all, so a MATCH on them says nothing about this path. Fixed polys for each result kind, then seeded random ones;
every index, each predicate, and a symbol beside the node so the facts reach a theory.
"""
import random

from sympy import Poly, Q, Symbol, rootof
from sympy.polys.rootoftools import ComplexRootOf

PREDS = (Q.real, Q.imaginary, Q.positive, Q.negative, Q.zero, Q.nonzero, Q.algebraic, Q.rational, Q.irrational, Q.integer, Q.finite,
         Q.complex)
z = Symbol('z')
FIXED = (z**5 - z + 1, z**5 - z - 1, z**5 + 2*z + 1, z**7 - z**2 + 3, z**4 - 2, z**4 + 1, z**6 + z + 1, z**3 - 3*z + 1, z**8 + 3,
         z**4 + z + 1, z**5 - 4*z + 2, z**6 - 3, z**4 + 4*z**2 + 2, z**6 + 5*z**2 + 1)


def roots(p):
    """Every index that builds a `ComplexRootOf`, and not a number or a radical. `_new` keeps a poly `rootof` would factor, so
    the template meets non-irreducible and non-squarefree polys too."""
    out = []
    n = p.degree()
    for i in range(n):
        out.append(ComplexRootOf._new(p, i))
    try:
        r = rootof(p, 0, radicals=False)
        if isinstance(r, ComplexRootOf):
            out.append(r)
    except Exception:       # NotImplementedError and PolynomialError, by sympy's own limits
        pass
    return out


def queries():
    rng = random.Random(56)
    polys = [Poly(e, z) for e in FIXED]
    polys += [Poly(z**5 * c, z) + Poly(z, z) * b + Poly(a, z) for a, b, c in ((1, 1, 1), (1, -1, 2), (0, 1, 3))]
    polys += [Poly(z, z) * Poly(z**2 + 1, z), Poly(z**2 - 1, z)**2, Poly(z**2 + 1, z) * Poly(z**2 - 2, z), Poly(z**2 + 1, z)**2]
    for _ in range(40):
        d = rng.randint(3, 9)
        cs = [rng.randint(-9, 9) or 1 for _ in range(d + 1)]
        polys.append(Poly(cs, z))
    x = Symbol('x', positive=True)
    out = []
    for p in polys:
        for r in roots(p):
            out.extend((pred(r), True) for pred in PREDS)
            out.append((Q.positive(x * r), Q.positive(x)))
    return out
