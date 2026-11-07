"""rows_cmp.py [N] [SEED]: `_rows_runtime.py` on Rust against Python, directly, since a workload reaches few of its paths.

Compares value, class and print, or that Rust declined, on:
  every compiled row: `generator`'s attributes and `gen(R, c)` for every key and for keys it lacks
  `constant_value`: every text of the rows, and generated ones, over Integer, Rational, Float, oo, -oo, nan, huge values
  `from_text`: every text of the rows, the module's documented ones, hand-picked grammar edges, and N generated texts
Prints what Rust declined, by reason. A difference exits 1. `--plant-check` shows the compare fires on a wrong value.
"""
import collections
import random
import sys

import sa_solver
from sympy import Float, Integer, Rational, S

from satassume.knowledge.templates import _rows_runtime as RT
from satassume.knowledge.templates._compiled_rows import FAMILIES
from satassume.knowledge.templates._common import Rules
from knowledge_live import _same_objects

args = [a for a in sys.argv[1:] if not a.startswith('--')]
N = int(args[0]) if args else 20000
rng = random.Random(int(args[1]) if len(args) > 1 else 1)
stats, diffs, declined = collections.Counter(), [], collections.Counter()


def diff(kind, x, a, b):
    stats['differences'] += 1
    if len(diffs) < 30:
        diffs.append((kind, repr(x)[:120], repr(a)[:120], repr(b)[:120]))


def python(f, *a):
    try:
        return ('value', f(*a))
    except BaseException as e:      # noqa: B902  the class is the answer
        return ('raises', type(e).__name__)


def text_case(text):
    stats['from_text'] += 1
    r = sa_solver.rows_from_text(text)
    if r is None:
        stats['from_text:declined'] += 1
        declined[repr(text)] += 1
        return
    stats['from_text:read'] += 1
    p = python(RT.from_text, text)
    if p[0] != 'value' or not _same_objects(r, p[1]):
        diff('from_text', text, r, p)


def constant_case(text, c):
    stats['constant_value'] += 1
    r = sa_solver.rows_constant_value(text, c)
    if r is None:
        stats['constant_value:declined'] += 1
        declined[f'{type(c).__name__}:{text}'] += 1
        return
    stats['constant_value:read'] += 1
    p = python(RT.constant_value, text, c)
    if p[0] != 'value' or not _same_objects(r, p[1]):
        diff('constant_value', (text, c), r, p)


class Log(Rules):
    def __init__(self):
        self.seen = []

    def rule(self, prem, concl):
        self.seen.append((prem, concl))


row_texts, const_texts = set(), set()
for family, fns in FAMILIES:
    for fn_name, arity, terms, specs, *schemas in fns:
        stats['functions'] += 1
        py = RT.generator(fn_name, arity, terms, specs, 'cmp', *schemas)
        rs = sa_solver.RowsGen(terms, specs, RT.from_text, *schemas)
        for f in ('terms', 'shifts', 'specs', 'plain', 'schemas'):
            stats['attributes'] += 1
            if not _same_objects(getattr(rs, f), getattr(py, f)):
                diff('attr:' + f, fn_name, getattr(rs, f), getattr(py, f))
        keys = [n for n, _ in specs]
        for c in (*keys, *map(Integer, keys), 0, 3, 99, None, S.Half, Float(2.0), 'x'):
            a, b = Log(), Log()
            stats['gen_calls'] += 1
            pa, pb = python(rs, a, c), python(py, b, c)
            if pa[0] != pb[0] or a.seen != b.seen or (pa[0] == 'raises' and pa != pb):
                diff('gen', (fn_name, c), (pa, a.seen[:2]), (pb, b.seen[:2]))
        for v in rs.python_values:
            declined[f'row value {fn_name}: {v}'] += 1
        stats['values:read'] += len(rs.numbers())
        stats['values:python'] += len(rs.python_values)
        for _, ts in terms:
            for t in ts:
                if t[0] == 'of_constant':
                    const_texts.add(t[2])
                elif t[0] == 'times':
                    row_texts.add(t[2])
                elif t[0] != 'inner':
                    row_texts.add(t[1])
        for _, rows in specs:
            for r in rows:
                if len(r) > 2:
                    row_texts.update(s[1] for s in r[2] if s and s[0] == 'value')

EDGES = ['1/2', '-1/E', 'exp(-1)', '-I', 'I', 'E', 'pi', '-1', '- 1', '--1', '+1', '~1', '1 + 2', ' 1', '1 ', '(1)', '((2))',
         '2**3', '2**-1', '-2**2', '(-2)**2', '2**3**2', '0**0', '0**-1', '1/0', '0/0', '007', '0', '00', '1_000', '0x10', '1.5',
         '1e3', '2j', '2x', 'x', 'True', 'None', 'exp(0)', 'exp(1)', 'exp(2)', 'exp(1/2)', 'exp(E)', 'E**2', 'E**-1', 'E*E', 'E/E',
         'E-E', 'E+1-1', 'E+1', '2*E', 'E/2', '-E/2', '1/E/E', 'pi*pi', '1/pi', 'pi/2', 'pi*E', 'E/pi', 'pi-pi', 'Abs(-3)', 'Abs(-1/2)',
         'Abs(E)', 'Abs(-E)', 'Abs(E-3)', 'Abs(pi-3)', 'Abs(1,2)', 'Abs()', 'Abs(x=1)', 'sqrt(4)', 'sqrt(4/9)', 'sqrt(2)', 'sqrt(0)',
         'sqrt(-4)', 'sqrt(E)', 'sqrt(E**2)', 'I*I', '2**4096', '2**4097', '2**(1/2)', '4**(1/2)', '(1/2)**-3', 'E**(1/2)', '1//2', '1%2',
         '1,2', '', '(', ')', '1\n+2', '1 #c', '\t1', 'number', 'coefficient', 'foo(1)', 'exp(1)(2)', '1(2)', '٣', '9' * 5000,
         '(' * 80 + '1' + ')' * 80, '-' * 80 + '1']
for t in sorted(row_texts, key=repr):
    text_case(t)
for t in EDGES:
    text_case(t)
ATOMS = ['0', '1', '2', '3', '7', '12', 'E', 'pi', 'I', 'number']
OPS = ['+', '-', '*', '/', '**']


def gen_text(d):
    r = rng.random()
    if d <= 0 or r < .25:
        return rng.choice(ATOMS)
    if r < .35:
        return '-' + gen_text(d - 1)
    if r < .45:
        return '(' + gen_text(d - 1) + ')'
    if r < .55:
        return rng.choice(['Abs', 'exp', 'sqrt']) + '(' + gen_text(d - 1) + ')'
    sp = rng.choice(['', ' '])
    return gen_text(d - 1) + sp + rng.choice(OPS) + sp + gen_text(d - 1)


CS = [Integer(n) for n in (0, 1, -1, 2, -2, 3, 4, 10**30, -10**30)] + [S.Half, Rational(-1, 2), Rational(3, 4), Rational(10**30 + 1, 3),
      Float(2.0), Float(0.5), Float(-1.5), S.Infinity, S.NegativeInfinity, S.NaN]
for t in sorted(const_texts) + ['number', '-number', 'number**2', 'number**-1', '1/coefficient', 'E*number', 'Abs(number)', 'exp(number)',
                                'sqrt(number)', 'I*number']:
    for c in CS:
        constant_case(t, c)
seen = set()
for _ in range(N):
    t = gen_text(rng.randint(1, 4))
    # A huge exponent chain can stop either side for a long time, and says nothing here.
    if t.count('**') > 2 or t in seen:
        continue
    seen.add(t)
    if 'number' in t:
        constant_case(t, rng.choice(CS))
    else:
        text_case(t)

if '--plant-check' in sys.argv:
    if _same_objects(Integer(1), Integer(2)) or _same_objects(Integer(1), Float(1.0)) or _same_objects(S.Exp1, 1 / S.Exp1) \
            or not _same_objects(1 / S.Exp1, 1 / S.Exp1):
        print('compare is broken')
        sys.exit(2)
    print('compare: tells 1 from 2, Integer from Float, E from 1/E')
print(dict(sorted(stats.items())))
print('declined, most common, 40 of', len(declined))
for k, v in declined.most_common(40):
    print(f'  {v:6} {k[:90]}')
for d in diffs:
    print('DIFF', d)
sys.exit(1 if diffs else 0)
