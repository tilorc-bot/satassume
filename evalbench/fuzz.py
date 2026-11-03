"""Held-out fuzz queries: random linear relations and sign facts over two
reals, the generator of reteassume's tests/test_extended_real.py
(``bench/fuzz_sweep.py``), copied here; seeds 0-39 were used there, the
held-out base seed is secret (``secret/fuzz_seed.txt``, its SHA-256 is in
BASELINE.md)."""
import random

from sympy import And, Q, Rational, S, Symbol, pi

x, y = Symbol('x'), Symbol('y')
SEEDS, PER = 20, 150


def _forms(rng):
    def lin():
        cx, cy = rng.choice([-2, -1, 0, 1, 1, 2, 3]), rng.choice([0, 0, -1, 1, 2])
        k = rng.choice([-1, 0, 0, 1, 2, Rational(1, 2), Rational(-3, 2)])
        return cx * x + cy * y + k
    return lin


def _atom(rng, lin):
    k = rng.random()
    if k < 0.7:
        rel = rng.choice([Q.lt, Q.gt, Q.le, Q.ge, Q.eq, Q.ne])
        a, b = lin(), lin()
        if a == b:
            b = b + 1
        return rel(a, b)
    pred = rng.choice([Q.positive, Q.negative, Q.zero, Q.nonzero, Q.finite,
                       Q.extended_positive, Q.nonnegative, Q.real, Q.integer, Q.integer])
    return pred(lin())


def _bound(rng):
    v = rng.choice([x, y])
    return rng.choice([Q.gt, Q.lt, Q.ge, Q.le])(v, rng.choice([-1, 0, 1, 2, Rational(1, 2), pi / 2]))


def queries(base, seeds=SEEDS, per=PER):
    out = []
    for seed in range(base, base + seeds):
        rng = random.Random(seed)
        lin = _forms(rng)
        for _ in range(per):
            assum = [_bound(rng) for _ in range(rng.choice([1, 1, 2]))]
            if rng.random() < 0.3:
                assum.append(rng.choice([Q.real, Q.extended_real, Q.finite, Q.integer])(rng.choice([x, y])))
            if rng.random() < 0.3:
                assum.append(_atom(rng, lin))
            a = And(*assum)
            p = _atom(rng, lin)
            if p in (S.true, S.false) or a in (S.true, S.false):
                continue
            out.append((p, a))
    return out
