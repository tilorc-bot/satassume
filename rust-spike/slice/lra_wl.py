"""A workload for slice D's sites, as `fresh.py lra` and `live.py lra`. Dev and fuzz make 0 calls to Rust's closed product and
1 to `_generic` and the bounds, so a MATCH there says nothing about them. Seeded: each query's constants and form are drawn from
what `lra_adapter` treats differently (field elements, radicals, generic constants, no enclosure, Floats, I), including
unevaluated products, where `Mul(*closed)` folds what the node kept apart.
"""
import random

from sympy import (Add, E, EulerGamma, Float, GoldenRatio, I, Integer, Mul, Pow, Q, Rational, Symbol, cos, exp, log, oo, pi, sin,
                   sqrt)

x, y, z = Symbol('x', real=True), Symbol('y', real=True), Symbol('z', real=True)
u = Symbol('u')
n, k = Symbol('n', integer=True), Symbol('k', integer=True)
SYMS = (x, y, z, u, n, k)
CONSTANTS = (pi, E, 1 / pi, pi**2, E**2, exp(3), pi + 1, sqrt(2), sqrt(3), sqrt(6), 2**Rational(1, 3), 3**Rational(2, 3), 1 / sqrt(2),
             log(2), log(3), sin(1), cos(2), EulerGamma, GoldenRatio, pi**100, 2 * pi, -pi / 2, sqrt(2) + sqrt(3), pi * sqrt(2))
ODD = (I, Float('0.5'), oo, sqrt(-1 - pi), log(-2), Integer(0), Rational(3, 2), Integer(-1))
HEADS = (Q.lt, Q.le, Q.gt, Q.ge, Q.eq, Q.ne)
UNARY = (Q.positive, Q.negative, Q.zero, Q.nonzero, Q.nonnegative, Q.nonpositive, Q.integer, Q.real, Q.finite)


def constant(r):
    return r.choice(ODD) if r.random() < 0.08 else r.choice(CONSTANTS)


def product(r):
    """A closed product times symbols. Unevaluated half the time, and in a shuffled order some of that."""
    closed = [constant(r) for _ in range(r.choice((1, 2, 2, 3)))]
    if r.random() < 0.4:
        closed.append(Rational(r.randint(-5, 5), r.randint(1, 4)))
    syms = [r.choice(SYMS) for _ in range(r.choice((1, 1, 1, 2, 3)))]
    if r.random() < 0.2:
        syms[0] = Pow(syms[0], r.choice((2, 3, -1)))
    args = closed + syms
    if r.random() < 0.5:
        return Mul(*args)
    if r.random() < 0.3:
        r.shuffle(args)
    return Mul(*args, evaluate=False)


def term(r):
    c = r.random()
    if c < 0.45:
        return product(r)
    if c < 0.6:
        return r.choice(SYMS)
    if c < 0.75:
        return constant(r)
    return Add(*[term(r) for _ in range(r.choice((2, 2, 3)))])


def atom(r):
    if r.random() < 0.3:
        return r.choice(UNARY)(term(r))
    return r.choice(HEADS)(term(r), term(r))


def queries(seed=323, n_queries=1500):
    r = random.Random(seed)
    out = []
    while len(out) < n_queries:
        p = atom(r)
        c = r.random()
        a = True if c < 0.3 else atom(r) if c < 0.7 else atom(r) & atom(r)
        out.append((p, a))
    return out
