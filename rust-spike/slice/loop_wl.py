"""A workload for `Session._compile`'s demand path (step 5c2), as `live.py loop`. Dev and fuzz register no vocabulary
function, so no non-pattern formula there mentions another node's atom, and `drop-compile-demand` fires 0 on both: a MATCH
there says nothing about that path (gaps ruling). Built from the code reached (engine.py `_compile`, `_visit`'s
`ext.node_facts`, `_compile_pending`), not from any eval set.

`queries()` registers vocabulary functions on the default registry (satassume.knowledge.extensions) for `Add`, `Mul`, `Pow`
and `sin`. Their formulas mention atoms of the node's direct arguments and of derived nodes (`2*x` of `sin(x)`, `b**2` of
`b**e`), with predicates in PRED_INDEX, so `_compile` adds the predicates' basis to those nodes' demand. Every formula is
true of SymPy's meaning, so the extension changes no answer's truth, only how it's reached. The queries then ask about
those nodes, with and without assumptions, so some are compiled at once and some parked under a demand
(`_compile_pending`). The registrations stay for the process: run this workload in its own process, as live.py does.
"""
from sympy import Add, Mul, Pow, Q, Rational, Symbol, sin

from satassume import And, Implies, P
from satassume.knowledge.extensions import register


def _add(n):
    a = n.args
    return [Implies(And(*[P('even', t) for t in a]), P('even', n)),
            Implies(And(P('nonnegative', a[0]), P('positive', a[-1])), P('positive', n))]


def _mul(n):
    a = n.args
    return [Implies(And(*[P('positive', t) for t in a]), P('positive', n)),
            Implies(P('zero', a[0]), P('zero', n))]


def _pow(n):
    b, e = n.args
    return [Implies(And(P('positive', b), P('real', e)), P('positive', n)),
            Implies(And(P('real', b), P('nonzero', b)), P('positive', b**2))]


def _sin(n):
    x = n.args[0]
    return [Implies(P('zero', 2 * x), P('zero', n)),
            Implies(P('zero', x), P('zero', n))]


_DONE = []


def install():
    if not _DONE:
        register('even', Add)(_add)
        register('positive', Mul)(_mul)
        register('positive', Pow)(_pow)
        register('zero', sin)(_sin)
        _DONE.append(1)


def queries():
    install()
    x, y = Symbol('x', real=True), Symbol('y', real=True)
    n, m = Symbol('n', integer=True), Symbol('m', integer=True)
    u, v = Symbol('u'), Symbol('v')
    preds = (Q.positive, Q.even, Q.zero, Q.real, Q.nonzero, Q.integer, Q.nonnegative)
    nodes = [x + y, n + m, x + 1, u + v, n + 2 * m, x * y, n * m, u * v, 3 * x * y, x**y, u**v, x**Rational(1, 3), x**2 + y,
             sin(x), sin(u), sin(n * x), sin(x) + y, sin(x) * y, (x + y)**n, sin(x + y) + u * v]
    assume = [True, Q.positive(x), Q.even(n) & Q.even(m), Q.zero(x), Q.positive(x) & Q.positive(y), Q.nonnegative(x),
              Q.nonzero(x), Q.zero(u), Q.positive(u) & Q.positive(v), Q.real(v), Q.zero(2 * x)]
    out = []
    for i, e in enumerate(nodes):
        for j, p in enumerate(preds):
            out.append((p(e), True))
            out.append((p(e), assume[(i + j) % len(assume)]))
            out.append((p(e), assume[(3 * i + 2 * j + 1) % len(assume)]))
    return out
