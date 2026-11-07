"""A workload for `_rows_runtime.py`, as `knowledge_fresh.py rows`. dev and fuzz build few of the 95 generators (fuzz makes no `gen`
call at all) and pass only rational constants to `constant_value`, so their MATCH says nothing about the others or about `Float`,
`oo`, `nan` and `zoo`. Every function of the rows, unevaluated, on symbols and on each kind of constant, then `Pow` and `Mul` on every
kind of constant with every predicate. Seeded; a node SymPy won't build is left out, the same way on every run.
"""
import random

from sympy import Float, Integer, Mul, Pow, Q, Rational, S, Symbol

from satassume.knowledge.templates import ROW_FAMILIES, wiring
from satassume.knowledge.templates._compiled_rows import FAMILIES

PREDS = (Q.real, Q.imaginary, Q.positive, Q.negative, Q.zero, Q.nonzero, Q.algebraic, Q.rational, Q.irrational, Q.integer, Q.finite,
         Q.complex, Q.even, Q.odd)
ASSUME = (Q.real, Q.positive, Q.negative, Q.integer, Q.even, Q.odd, Q.rational, Q.zero, Q.nonzero, Q.finite, Q.imaginary, Q.irrational)
x, y = Symbol('x'), Symbol('y')
CONSTANTS = (S.Zero, S.One, S.NegativeOne, Integer(2), Integer(-2), Integer(3), Integer(4), Integer(10)**30, S.Half, Rational(-1, 2),
             Rational(3, 4), Float(2.0), Float(0.5), Float(-1.5), S.Infinity, S.NegativeInfinity, S.NaN, S.ComplexInfinity, S.Exp1,
             S.ImaginaryUnit, -S.ImaginaryUnit, S.Pi, -1/S.Exp1)


def _node(fn, args):
    try:
        return fn(*args, evaluate=False)
    except Exception:
        return None


def _arities(arity):
    if arity == ():
        return (2, 3)
    return arity if isinstance(arity, tuple) else (arity,)


def queries(seed=61):
    rng = random.Random(seed)
    out = []

    def add(node, n=4):
        if node is None:
            return
        for _ in range(n):
            a = rng.choice(ASSUME)(x)
            if rng.random() < .5:
                a = a & rng.choice(ASSUME)(y)
            out.append((rng.choice(PREDS)(node), a))

    for family, fns in FAMILIES:
        declared = {f.__name__: f for f in map(wiring._declared, dict(ROW_FAMILIES)[family]) if f is not None}
        for fn_name, arity, *_ in fns:
            fn = declared.get(fn_name)
            if fn is None:
                continue
            for n in _arities(arity):
                add(_node(fn, (x, y, x, y)[:n]))
                for _ in range(6):
                    add(_node(fn, tuple(rng.choice((x, y, *CONSTANTS)) for _ in range(n))), 2)
    for c in CONSTANTS:
        for node in (_node(Pow, (c, x)), _node(Pow, (x, c)), _node(Mul, (c, x)), _node(Mul, (c, x, y)), _node(Pow, (c, c)),
                     _node(Pow, (_node(Pow, (x, c)), y)), _node(Mul, (c, _node(Pow, (x, y))))):
            add(node, 8)
    return out
