"""`transfer:SEED:N` in transfer_fresh.py: generated queries picked to reach component 3's lemma paths.

dev has a transfer theory in 52 of 3,332 sessions and crossed `explain` 13 times. These go through `ask()` like any
other workload, and each has an `eq` atom or a reversed pair of `lt` atoms, so they say nothing about how often real
queries reach these paths: their counts are not representative. The shapes: unary facts across chains of equalities,
reversed order atoms, congruent applications, rational sides (`set_fixed`), and disjunctions, which make the search
decide, backtrack and pop levels. Deterministic in SEED, and no set of terms is iterated.
"""
import random

from sympy import Abs, And, Function, Not, Or, Q, Rational, symbols

UNARY = ["positive", "negative", "nonnegative", "nonpositive", "nonzero", "zero", "real", "integer", "rational",
         "even", "odd", "prime", "composite", "irrational", "finite", "extended_real", "extended_positive",
         "extended_negative", "complex", "imaginary", "algebraic", "transcendental"]
F, G = Function("f"), Function("g")
H = Function("h", real=True)


def _terms():
    x, y, z, w = symbols("x y z w")
    n = symbols("n", integer=True)
    r = symbols("r", real=True)
    base = [x, y, z, w, n, r]
    return base, base + [F(x), F(y), F(z), F(F(x)), F(F(y)), G(x, y), G(y, x), G(x, z), H(x), H(y), x + y, y + z,
                         x*y, y*z, x**2, y**2, Abs(x), Abs(y), 2*x, x + 1, y + 1, x - y]


NUMS = [0, 1, 2, -1, -2, 3, Rational(1, 2), Rational(-1, 3), Rational(4, 2)]


def _unary(r, ts):
    return getattr(Q, r.choice(UNARY))(r.choice(ts))


def _chain(r, ts):
    k = r.randint(2, 4)
    picks = r.sample(ts, k)
    return picks, [Q.eq(a, b) for a, b in zip(picks, picks[1:])]


def _facts(r, picks, ts, lo=1, hi=3):
    out = []
    for _ in range(r.randint(lo, hi)):
        a = _unary(r, picks if r.random() < .8 else ts)
        out.append(Not(a) if r.random() < .25 else a)
    return out


def _shape(r, base, ts):
    k = r.randrange(7)
    if k == 0:    # facts across a chain of equalities
        picks, eqs = _chain(r, ts)
        return _unary(r, picks), eqs + _facts(r, picks, ts)
    if k == 1:    # reversed order atoms
        a, b = r.sample(ts, 2)
        extra = [Q.lt(b, r.choice(ts))] if r.random() < .3 else []
        return _unary(r, [a, b]), [Q.lt(a, b), Q.lt(b, a) if r.random() < .5 else Q.gt(a, b)] + extra + _facts(r, [a, b], ts, 0, 2)
    if k == 2:    # congruent applications
        a, b = r.sample(base, 2)
        fn = r.choice([F, H, Abs, lambda t: t**2, lambda t: 2*t, lambda t: t + 1])
        p = getattr(Q, r.choice(UNARY))
        ante = [Q.eq(a, b), p(fn(a))] + ([Q.eq(fn(fn(a)), r.choice(base))] if r.random() < .2 else [])
        return p(fn(b)) if r.random() < .8 else _unary(r, [fn(a), fn(b), a]), ante
    if k == 3:    # rational sides
        a = r.choice(ts)
        ante = [Q.eq(a, r.choice(NUMS))]
        if r.random() < .5:
            b = r.choice(ts)
            ante.append(Q.eq(a, b))
            return _unary(r, [a, b]), ante + _facts(r, [a, b], ts, 0, 2)
        return _unary(r, [a]), ante
    if k == 4:    # a case split on which equality holds
        a, b, c = r.sample(ts, 3)
        p = getattr(Q, r.choice(UNARY))
        return p(a), [Or(Q.eq(a, b), Q.eq(a, c)), p(b), Not(p(c)) if r.random() < .3 else p(c)]
    if k == 5:    # a case split on the facts, with chains to backtrack over
        picks, eqs = _chain(r, ts)
        d = _facts(r, picks, ts, 2, 3)
        return _unary(r, picks), eqs + [Or(*d)] + _facts(r, picks, ts, 0, 1)
    # conflicting facts and negated equalities, with a term shared with arithmetic
    a, b = r.sample(ts, 2)
    return Q.ne(a, b) if r.random() < .3 else _unary(r, [a, b]), [Or(Q.eq(a, b), Q.lt(a, b)), Or(Q.eq(a, b), Q.gt(a, b)), *_facts(r, [a, b], ts, 1, 3)]


def queries(seed, n):
    r = random.Random(seed)
    base, ts = _terms()
    out = []
    for _ in range(n):
        p, ante = _shape(r, base, ts)
        out.append((p, And(*ante)))
    return out


# `transfer2:SEED:N`: aimed at what `transfer:`, dev and fuzz leave unrun in Python's transfer.py (sa-port-25): a contradicted
# fixed fact (`_spread`'s conflict), a repeated `set_fixed`, `check`'s conflict, and more search. Separate, so that
# `transfer:`'s queries stay what its earlier runs ran.
TRUE_OF = {"positive": [1, 2, 3, Rational(1, 2)], "negative": [-1, -2, Rational(-1, 3)], "zero": [0], "even": [0, 2, -2],
           "odd": [1, 3, -1], "integer": [0, 1, 2, -1], "prime": [2, 3], "nonzero": [1, -1, 2],
           "nonnegative": [0, 1], "nonpositive": [0, -1], "rational": [Rational(1, 2), 1]}


def _shape2(r, base, ts):
    k = r.randrange(6)
    p = r.choice(sorted(TRUE_OF))
    n = r.choice(TRUE_OF[p])
    a, b, c = r.sample(ts, 3)
    fact = getattr(Q, p)
    if k == 0:    # the fact's false for the number: fact first, then the equality; and the other way
        ante = [Not(fact(a)), Q.eq(a, n)]
        return _unary(r, [a]), ante if r.random() < .5 else ante[::-1]
    if k == 1:    # the same across a chain, under a split, so it isn't settled at the root
        return _unary(r, [a, b]), [Or(Q.eq(a, b), Q.eq(a, c)), Q.eq(b, n), Q.eq(c, n), Not(fact(a))]
    if k == 2:    # two numbers in one class under a split, and one number twice
        m = r.choice(NUMS)
        return fact(a), [Or(Q.eq(a, n), Q.eq(b, n)), Or(Q.eq(a, m), Q.eq(b, m)), Q.eq(a, b), Or(fact(b), Not(fact(c)))]
    if k == 3:    # the equality is only known by congruence or by a reversed order pair, late in the search
        fn = r.choice([F, H, Abs])
        x, y = r.sample(base, 2)
        return fact(fn(y)), [Or(Q.eq(x, y), Q.lt(x, y)), Or(Q.eq(x, y), Q.gt(x, y)), Q.eq(fn(x), n), Not(fact(fn(y)))]
    if k == 4:    # the proposition carries the contradiction: the fact's atom appears only in the query
        return Not(fact(a)), [Q.eq(a, b), Or(Q.eq(b, n), Q.eq(b, c)), _unary(r, [c])]
    # many overlapping splits, for restarts and deep levels
    cl = []
    for _ in range(r.randint(3, 6)):
        u, v = r.sample(ts, 2)
        cl.append(Or(Q.eq(u, v), _unary(r, [u, v]), Not(_unary(r, [u, v]))))
    return _unary(r, ts), cl + [Q.eq(a, n)]


def queries2(seed, n):
    r = random.Random(seed)
    base, ts = _terms()
    return [(p, And(*ante)) for p, ante in (_shape2(r, base, ts) for _ in range(n))]
