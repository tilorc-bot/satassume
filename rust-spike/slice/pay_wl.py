"""A workload for the payload classes' Negated path (adapters step, part C), as `live.py pay`. The adapters build `Negated`
only for an `ne` relation (lra_adapter.py `_constraint`, positive = name != "ne"), and dev and fuzz have none: `ad:negated_new`
is 0 on both and the plant `pay-neg-twice` fires 0 there, so a MATCH there says nothing about it (gaps ruling). Built from the
code reached (lra_adapter.py `interpret`/`register`, lra_backend.py `_register`'s Negated loop), not from any eval set.

Each query has an `ne` relation between linear forms, in the proposition or the assumptions, with and without bounds that
decide it, so a lost negation moves answers. Also integer and EUF atoms beside them (`Integral`, `EqAtom`).
"""
from sympy import Function, Q, Symbol

from satassume.relations import relation_atom


def queries():
    x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
    r, s = Symbol('r', real=True), Symbol('s', real=True)
    n, m = Symbol('n', integer=True), Symbol('m', integer=True)
    f = Function('f')
    out = []
    for a, b in ((x, y), (r, s), (n, m), (x, 1), (r + s, 2), (2 * n, m + 1)):
        ne = Q.ne(a, b)
        for c in (True, Q.gt(a, b), Q.lt(a, b), Q.ge(a, b) & Q.le(a, b), Q.eq(a, b), Q.ge(a, b),
                  Q.real(a) & Q.real(b), Q.positive(a - b), Q.zero(a - b)):
            out += [(ne, c), (Q.eq(a, b), ne & c if c is not True else ne), (Q.gt(a, b), ne & Q.ge(a, b)),
                    (Q.lt(a, b), ne & Q.le(a, b)), (Q.nonzero(a - b), c), (relation_atom('ne', a, b), c)]
    out += [(Q.ne(f(x), f(y)), Q.eq(x, y)), (Q.ne(x, y), Q.ne(f(x), f(y))), (Q.eq(f(n), f(m)), Q.eq(n, m)),
            (Q.ne(n, m), Q.gt(n, m) & Q.lt(n, m + 1)), (Q.ne(2 * n, 1), Q.integer(n)), (Q.ne(n, z), Q.eq(z, n + 1)),
            (Q.positive(x - y), Q.ne(x, y) & Q.ge(x, y)), (Q.ne(x + y, z), Q.eq(x, z - y))]
    return out
