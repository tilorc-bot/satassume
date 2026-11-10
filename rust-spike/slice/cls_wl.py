"""A workload for two equal class objects in one process, as `live.py cls` (issue 323, results/cbm-noid-cause.md; gaps
ruling: the path was reached only by the suite and test_cbm_noid.py, `cls:eq` 0 on every other workload).

Two `Function('f')` are one class to SymPy (`==`, one hash) and two class objects once SymPy's cache has been cleared
between them. A query whose input shows both gets one row per term from the first object it shows, and every site that
takes a row for a term of the other asks `same_class` (formula.rs, term_live.py), counted `cls:eq`. Plant 661
(`class-is`) puts the identity compare back at those sites. The queries are test_cbm_noid.py's, over three function names
and with the two objects in either order, each term also asked through the other class object after the first query has
filled the process's memos."""
from sympy import Function, Q, S, Symbol
from sympy.core.cache import clear_cache


def _two(name):
    f1 = Function(name)
    clear_cache()               # else SymPy's own cache hands the first object back
    f2 = Function(name)
    clear_cache()
    assert f1 is not f2 and f1 == f2
    return f1, f2


def queries():
    a, b = Symbol('a'), Symbol('b')
    out = []
    for name in ('f', 'g', 'h'):
        for f1, f2 in (_two(name), _two(name)[::-1]):
            t1, x1, z1 = f1(S(1)), f1(a), f1(b)
            clear_cache()       # again: SymPy's cache would hand `f1`'s `f(a)` back for `f2(a)`
            t2, x2, y2 = f2(S(1)), f2(a), f2(b)
            clear_cache()
            assert type(x1) is not type(x2) and x1 == x2 and type(t1) is not type(t2)
            out += [(Q.eq(S(1), t1), Q.ne(b, a)), (Q.eq(S(1), t2), Q.ne(b, a)),
                    (Q.eq(x1, x2), True), (Q.eq(x1, y2), Q.eq(a, b)), (Q.lt(x1, x2), True), (Q.gt(x1 + 1, x2), True),
                    (Q.le(x1, 3), Q.lt(x2, 2) & Q.real(x2)), (Q.eq(t1, 2), Q.eq(t2, 3)),
                    (Q.lt(x1, y2), Q.lt(x2, 0) & Q.gt(y2, 0)), (Q.positive(x1 - y2), Q.gt(x2, 1) & Q.lt(z1, 1)),
                    (Q.ge(2 * x2 + 1, x1), Q.positive(x1)), (Q.lt(x2, 2), Q.le(x1, 1) & Q.real(x1))]
    return out
