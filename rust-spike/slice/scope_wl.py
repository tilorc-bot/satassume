"""A workload for scope.py's custom-predicate path (step scope), as `live.py scope`. Dev, fuzz and loop register no custom
predicate, so `_custom_pred` is true only for a few unregistered atoms (12 on dev, 0 on fuzz and loop), whose `facts_for` is
empty, and `extension_atoms` never takes its transitive step: `custom-never` MATCHes on dev and `ext-shallow` fires 0, so a
MATCH there says nothing about that code (gaps ruling). Built from the code
reached (scope.py `extension_atoms`, `_custom_pred`, `theory_scope`) and from test_scope_core.py's `_custom`, not from any
eval set.

`queries()` registers test_scope_core's custom predicates on the default registry (so sympy_api translates them instead of
treating them as opaque) and makes sure the default engine reads that registry: `mine(s)` implies `deep(s)`, `deep(s)` implies `s < 1`,
and `flat(z)` implies `mine(z)`. A query whose only relation comes from those facts gets the relational scope only through
`extension_atoms`' transitive step, so dropping a custom atom or the second level changes the
sessions built (their scope). On the bar's run no answer moved. The rest ask the same
predicates beside vocabulary and relation atoms, with and without assumptions. The registrations stay for the process: run
this workload in its own process, as live.py does.
"""
from sympy import Q, Symbol
from sympy.assumptions.assume import Predicate

from satassume import Implies, P
from satassume.knowledge.extensions import extensions as _default
from satassume.relations import relation_atom

_DONE = []


def install():
    if not _DONE:
        _default.register('mine', Symbol)(lambda s: Implies(P('mine', s), P('deep', s)))
        _default.register('deep', Symbol)(lambda s: Implies(P('deep', s), relation_atom('lt', s, 1)))
        _default.register('flat', Symbol)(lambda s: Implies(P('flat', s), P('mine', s)) if s.name == 'z' else True)
        from satassume import sympy_api
        sympy_api.default_engine().extensions = _default
        _DONE.append(1)


def queries():
    install()
    mine, deep, flat = Predicate('mine'), Predicate('deep'), Predicate('flat')
    x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
    r = Symbol('r', real=True)
    out = []
    for s in (x, z, r):
        for c in (mine(s), deep(s), flat(s), mine(s) & Q.positive(s), flat(s) & Q.nonnegative(s)):
            out += [(Q.positive(1 - s), c), (Q.negative(s - 1), c), (Q.positive(s - 1), c), (Q.nonzero(s - 1), c),
                    (Q.lt(s, 2), c), (Q.gt(s, 1), c), (Q.positive(2 - s), c), (Q.nonpositive(s - 1), c),
                    (Q.positive(1 - s) & Q.real(s), c), (Q.zero(s - 3), c)]
    out += [(mine(x), True), (deep(x), mine(x)), (mine(x), deep(x)), (flat(z), True), (mine(z), flat(z)), (deep(z), flat(z)),
            (Q.positive(1 - x), mine(x) | deep(x)), (Q.positive(1 - x), mine(y)), (Q.positive(1 - y), mine(x) & Q.positive(y - x)),
            (Q.positive(y - x), mine(x) & Q.gt(y, 1)), (Q.lt(x, y), deep(x) & Q.ge(y, 1)), (Q.positive(x + y), mine(x) & mine(y)),
            (Q.negative(x + y - 2), mine(x) & deep(y)), (Q.positive(1 - z), flat(z) & Q.real(z)), (Q.positive(1 - y), flat(y)),
            (deep(x), Q.lt(x, 1)), (Q.positive(1 - x), True), (Q.positive(1 - x), Q.lt(x, 0)), (Q.positive(x - y), mine(x) & Q.ge(y, 1))]
    return out
