"""realroots_cmp.py [--random N] [--seed S]: the five public functions of `knowledge/realroots.py` against `sa_solver`'s, directly,
with no engine. Compares the value, its type and its repr, or the exception's type. Prints one summary line, the first few
differences, and how often each kind of result came up, so a MATCH can be read for what it reached. Exit 1 on any difference.
Python's module is never swapped here: `knowledge_live` isn't imported.
"""
import argparse, collections, random, sys
from fractions import Fraction

import sa_solver
from satassume.knowledge import realroots as R

ap = argparse.ArgumentParser()
ap.add_argument('--random', type=int, default=20000)
ap.add_argument('--seed', type=int, default=1)
a = ap.parse_args()
rng = random.Random(a.seed)
SEEN = collections.Counter()
DIFFS = []
N = 0


def call(f, *args):
    try:
        r = f(*args)
        return ('value', type(r).__name__, repr(r), r)
    except Exception as e:
        return ('raise', type(e).__name__, '', None)


def cmp1(name, *args):
    global N
    N += 1
    py, rs = call(getattr(R, name), *args), call(getattr(sa_solver, 'realroots_' + name), *args)
    if py[:3] != rs[:3] or (py[0] == 'value' and isinstance(py[3], list) and [type(c) for c in py[3]] != [type(c) for c in rs[3]]):
        DIFFS.append((name, repr(args)[:400], py[:3], rs[:3]))
    SEEN[f'{name}:{py[1] if py[0] == "raise" else summary(name, py[3])}'] += 1


def summary(name, r):
    if name == 'root_facts':
        return 'None' if r is None else f"real={r['real']},sign={r['sign']},imag={r['imaginary']}"
    if name == 'gcd':
        return 'deg<=0' if len(r) <= 1 else 'deg>=1'
    if name == 'real_root_counts':
        return f'zero={r[1]},any={sum(r) > 0}'
    if name == 'imaginary_root_count':
        return 'zero' if r == 0 else 'some'
    return str(r)


def mul(a, b):
    out = [0] * (len(a) + len(b) - 1)
    for i, u in enumerate(a):
        for j, v in enumerate(b):
            out[i + j] += u * v
    return out


def small(d, bits=4):
    return [rng.randint(-2**bits, 2**bits) for _ in range(d + 1)]


def poly():
    k = rng.randrange(10)
    d = rng.randint(0, 9)
    if k < 3:
        return small(d)
    if k == 3:                                              # big coefficients on both sides of MAX_BITS
        bits = rng.choice((8, 64, 65, 200, R.MAX_BITS - 1, R.MAX_BITS, R.MAX_BITS + 1, 2000))
        return [1] + [rng.randint(-2**bits, 2**bits) for _ in range(rng.randint(1, 5))]
    if k == 4:                                              # a repeated factor: not squarefree
        f = small(rng.randint(1, 3), 2)
        return mul(mul(f, f), small(rng.randint(0, 2), 2))
    if k == 5:                                              # roots on the imaginary axis, some of them
        p = [1]
        for _ in range(rng.randint(1, 4)):
            p = mul(p, [1, 0, rng.randint(1, 9)] if rng.random() < .7 else small(2, 2))
        return p
    if k == 6:                                              # a root at 0, leading zeros
        return [0] * rng.randint(0, 2) + small(d) + [0] * rng.randint(0, 2)
    if k == 7:                                              # only even powers: x**4 - 2 and the like
        return [c if i % 2 == 0 else 0 for i, c in enumerate(small(2 * rng.randint(1, 4)))]
    if k == 8:                                              # rationals, ints mixed in
        return [Fraction(rng.randint(-9, 9), rng.randint(1, 9)) if rng.random() < .7 else rng.randint(-9, 9) for _ in range(d + 1)]
    return mul(small(rng.randint(1, 4), 2), small(rng.randint(1, 4), 2))


FIXED = [[], [0], [0, 0], [5], [-5], [1, 0], [1, 0, 0], [1, 1], [1, 0, -1], [1, 0, 1], [1, 0, -3, 0], [1, 1, 3], [1, 0, 1, 3],
         [1, 0, 0, 0, -2], [1, 0, 0, 0, 1], [1, 0, -2, 0, 1], [1] + [0] * R.MAX_DEGREE + [1], [1] + [0] * (R.MAX_DEGREE - 1) + [1],
         [2**R.MAX_BITS, 1], [2**R.MAX_BITS - 1, 1], [Fraction(2**R.MAX_BITS, 3), 1], [Fraction(2**R.MAX_BITS * 2, 3), 1],
         [Fraction(1, 2), Fraction(-1, 3)], [Fraction(-1, 7), 0, 1], (1, 0, -1), [True, 0, False], [0, 0, 1, 0, -1]]
BAD = [[1.5, 1], ['1', 2], [None], 5, None, [1, 1.0]]                  # refused on Rust: reported, not compared


def one(p):
    cmp1('squarefree', p)
    cmp1('real_root_counts', p)
    cmp1('imaginary_root_count', p)
    q = poly()
    cmp1('gcd', p, q)
    n = len(p)
    for i in (-1, 0, 1, n - 2, n - 1, n, 2**80, rng.randint(0, max(n - 1, 0))):
        cmp1('root_facts', p, i)
    if rng.random() < .1:
        for i in range(n):
            cmp1('root_facts', p, i)


for p in FIXED:
    one(p)
    for q in FIXED:
        cmp1('gcd', p, q)
for _ in range(a.random):
    one(poly())

refused = 0
for p in BAD:
    if call(sa_solver.realroots_root_facts, p, 0)[:2] == ('raise', 'TypeError'):
        refused += 1
print(f'calls={N} differences={len(DIFFS)} refused_as_TypeError={refused}/{len(BAD)}')
for d in DIFFS[:10]:
    print('DIFF', *d, sep=' | ')
for k in sorted(SEEN):
    print(f'  {k}: {SEEN[k]}')
sys.exit(1 if DIFFS else 0)
