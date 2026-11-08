"""Step 6d: direct checks of Rust's `_common` rows (term/common.rs `Common`) against Python's `_common.py`.
Run from this directory: `python common_direct.py [PLANT]`. Exit 1 on any difference, so a plant (one of
knowledge_common_live.PLANTS, passed as PLANT) shows as caught by a nonzero exit. Each check prints whether it ran.

Written for the plants dev and fuzz can't catch: `MAX_CACHE`'s clear-all (dev never fills 4,096 keys), the
`TemplateKeyError` shape check (no shipped template reuses a key across shapes), and the key builders' types
(`Float(2.0) == Integer(2)`: a key without its type is still `==` on every workload whose constants differ in value).
The others are checked here too, on inputs built from the code (Rules, lits, ge2_alternatives, consts_of, facts,
units, Compiled, instantiate/wide_formulas), never from held-out data.
"""
import os
import sys

if len(sys.argv) > 1:
    os.environ['SLICE_SESSION_PLANT'] = sys.argv[1]
os.environ.pop('SESSION_REPORT', None)

from satassume.knowledge.templates import _common as C
PY = {n: getattr(C, n) for n in ('facts', 'units', 'Rules', 'lits', 'ge2_alternatives', 'consts_of', 'pattern_key',
                                 'const_key')}

import term_live
term_live.from_env()
import knowledge_live
knowledge_live.from_env()
import knowledge_common_live

from sympy import Float, I, Integer, Rational, S, Symbol, pi, oo, E as e_

R = knowledge_common_live.COMMON[0]
assert R is not None, 'Common not installed'
BAD = []
FIELDS = ('rules', 'node', 'nobjs', 'complete', 'clauses', 'used', 'child_preds', 'wide')


def same(what, a, b):
    if a != b or type(a) is not type(b):
        BAD.append(what)
        print(f'DIFF {what}:\n  rust   {a!r}\n  python {b!r}')


def pat_fields(p):
    return tuple((f, getattr(p, f, None)) for f in FIELDS)


def fresh():
    C._CACHE.clear()


x, y = Symbol('x'), Symbol('y')
CONSTS = [Integer(2), Float(2.0), Rational(1, 2), S.Half, pi, I, oo, e_, Integer(-3), S.Zero]

# 1. const_key, pattern_key, consts_of, lits, ge2_alternatives
for c in CONSTS:
    same(f'const_key {c!r}', R.const_key(c), PY['const_key'](c))
same('const_key Integer(2) vs Float(2.0) distinct', R.const_key(Integer(2)) != R.const_key(Float(2.0)), True)
for consts in ({}, {0: Integer(2)}, {0: Float(2.0), 2: pi}, {1: S.Half, 0: I}):
    same(f'pattern_key {consts!r}', R.pattern_key('t', 3, consts), PY['pattern_key']('t', 3, consts))
same('pattern_key Integer vs Float distinct',
     R.pattern_key('t', 1, {0: Integer(2)}) != R.pattern_key('t', 1, {0: Float(2.0)}), True)
for args in ((x, Integer(2), pi), (Float(2.0), y), (x, y), (S.Half, I, oo, x)):
    same(f'consts_of {args!r}', R.consts_of(args), PY['consts_of'](args))
for pos in (True, False):
    same(f'lits {pos}', R.lits([0, 2], 'positive', pos), PY['lits']([0, 2], 'positive', pos))
same('lits default', R.lits([1], 'real'), PY['lits']([1], 'real'))
same('ge2_alternatives', R.ge2_alternatives(1), PY['ge2_alternatives'](1))
print('ran: keys, consts_of, lits, ge2_alternatives')

# 2. Rules
rr, rp = R.Rules() if hasattr(R, 'Rules') else R.make_rules(), PY['Rules']()
for r in (rr, rp):
    r.rule([(0, 'positive', True), (1, 'positive', True)], (2, 'positive', True))
    r.rule([(0, 'zero', True)], [(2, 'zero', True), (1, 'zero', True)])
    r.rule([], (0, 'real', True))
    r.equiv([(0, 'real', True)], (1, 'zero', True), (2, 'zero', True))
same('Rules.rules', list(rr.rules), list(rp.rules))
print('ran: Rules')


# 3. facts: same Pattern and Compiled from the same gen, on an empty cache each time
def gen():
    r = PY['Rules']()
    r.rule([(1, 'positive', True), (2, 'positive', True)], (0, 'positive', True))
    r.rule([(1, 'real', True)], [(0, 'real', True), (2, 'zero', True)])
    r.equiv([(2, 'zero', True)], (0, 'zero', True), (1, 'zero', True))
    return r.rules


for consts, objs in (({}, (x + y, x, y)), ({2: Integer(2)}, (x * 2, x, Integer(2))),
                     ({1: pi}, (pi + y, pi, y))):
    fresh()
    a = R.facts(('direct', len(consts)), gen, consts, objs, 0)
    fresh()
    b = PY['facts'](('direct', len(consts)), gen, consts, objs, 0)
    same(f'facts pattern {consts!r}', pat_fields(a.pattern), pat_fields(b.pattern))
    same(f'facts objs {consts!r}', a.objs, b.objs)
    same(f'facts type {consts!r}', type(a), type(b))
    same(f'wide_formulas {consts!r}', R.wide_formulas(a) if hasattr(R, 'wide_formulas') else a.wide_formulas(),
         b.wide_formulas())
    same(f'formulas {consts!r}', a.formulas(), b.formulas())
print('ran: facts, Compiled')

# 3b. instantiate through the dispatch's path (Rust wide_formulas on a Compiled whose pattern has wide rules)
D = knowledge_live.DISPATCH[0]
ran_wide = 0
WIDE = [[(k, 'positive_infinite', False) for k in range(1, 5)] + [(1, 'real', True)],   # a wide Add's 2**n
        [(k, 'negative_infinite', False) for k in range(1, 5)] + [(2, 'positive_infinite', False)],
        [(k, 'nonpositive', True) for k in range(1, 5)] + [(k, 'noninteger', True) for k in range(1, 5)]]
for k, prem in enumerate(WIDE):
    def wgen(prem=prem):
        return [(prem, [(0, 'nonnegative', True), (0, 'extended_nonzero', False)]), ([(1, 'zero', True)], [(0, 'zero', True)])]
    objs = (x + y, x, y, x * y, x - y)
    fresh()
    a = R.facts(('direct-wide', k), wgen, {}, objs, 0)
    fresh()
    b = PY['facts'](('direct-wide', k), wgen, {}, objs, 0)
    if b.pattern.wide:
        ran_wide += 1
    same(f'wide pattern {k}', pat_fields(a.pattern), pat_fields(b.pattern))
    same(f'wide wide_formulas {k}', R.wide_formulas(a), b.wide_formulas())
print('ran: wide patterns', ran_wide)

# 4. TemplateKeyError on a key reused with another shape, both sides
for f, name in ((R.facts, 'rust'), (PY['facts'], 'python')):
    fresh()
    f(('shape',), gen, {}, (x + y, x, y), 0)
    try:
        f(('shape',), gen, {}, (x + y, x, y, x), 0)
        got = None
    except C.TemplateKeyError as e:
        got = 'TemplateKeyError'
    if name == 'rust':
        rust_got = got
same('TemplateKeyError shape', rust_got, got)
print('ran: TemplateKeyError')

# 5. MAX_CACHE: a full cache is cleared before the next new key, both sides
sizes = []
for f in (R.facts, PY['facts']):
    fresh()
    for k in range(C.MAX_CACHE):
        C._CACHE[('filler', k)] = None
    f(('max', 0), gen, {}, (x + y, x, y), 0)
    sizes.append(len(C._CACHE))
same('MAX_CACHE clear-all size', sizes[0], sizes[1])
fresh()
print('ran: MAX_CACHE')


# 6. units: the same closed pattern
def ugen(pairs):
    return lambda: list(pairs)


for pairs in ([('positive', True)], [('integer', True), ('even', False)], [('zero', False), ('real', True)],
              [('antihermitian', True)], [('rational', True), ('positive', False), ('zero', False)]):
    fresh()
    a = R.units(('u', tuple(pairs)), ugen(pairs), x)
    fresh()
    b = PY['units'](('u', tuple(pairs)), ugen(pairs), x)
    same(f'units {pairs!r}', pat_fields(a.pattern), pat_fields(b.pattern))
    same(f'units objs {pairs!r}', a.objs, b.objs)
print('ran: units')

# 7. make_compiled (knowledge_live's rust_compiled) and the swap plant on two objects
fresh()
p = PY['facts'](('mc',), gen, {}, (x + y, x, y), 0).pattern
same('make_compiled 3 objs', R.make_compiled((x + y, x, y), p).objs, C.Compiled((x + y, x, y), p).objs)
fresh()

print('plant fired:', R.counts().get('plant:fired', 0))
print('DIFFERENCES:', len(BAD))
sys.exit(1 if BAD else 0)
