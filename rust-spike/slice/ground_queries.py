"""`live.py ground`: queries whose atoms cancel to no variables, which register in `_ground` and `_pending_ground`.

dev never had either field non-empty at a move, so their dump mutants couldn't take effect there. These go through
`ask()` like any other workload. They were picked to reach those fields, so they say nothing about how often that
happens: the group counts for this workload are not representative.
"""
from sympy import Q, Rational, symbols


def queries():
    x, y = symbols("x y")
    n = symbols("n", integer=True)
    return [
        (Q.lt(x + 1, x + 2), True),
        (Q.gt(x + 1, x + 2), True),
        (Q.le(x, x), True),
        (Q.eq(x + 1, x + 1), True),
        (Q.lt(x + y, y + x + 1), Q.gt(x, 0)),
        (Q.gt(x, y), Q.lt(x + 1, x + 2)),
        (Q.gt(x, y), Q.gt(x + 1, x + 2)),
        (Q.gt(x, y), Q.le(y + 1, y + 2)),
        (Q.ne(x + 1, x + 2), Q.gt(x, 0)),
        (Q.integer(x), Q.lt(x + 1, x + 2)),
        (Q.gt(2*x, x + x - 1), Q.gt(x, y)),
        (Q.gt(n, 0), Q.lt(n + Rational(1, 2), n + 1)),
        (Q.gt(x - y, 0), Q.gt(x, y) & Q.lt(x + 1, x + 2)),
        (Q.gt(x, 0), Q.gt(x, y) & Q.gt(y, 0) & Q.lt(y + 1, y + 2)),
        (Q.gt(x, 0), Q.gt(x, y) & Q.gt(y, 0) & Q.ge(y - 1, y - 2) & Q.lt(x + 1, x + 3)),
        (Q.ge(n, 1), Q.gt(n, 0) & Q.lt(n + 1, n + 2)),
        (Q.nonzero(x - y), Q.ne(y, x) & Q.le(x + 2, x + 2)),
        (Q.zero(x), Q.ge(x, 0) & Q.le(x, 0) & Q.ne(y + 1, y + 2)),
    ]
