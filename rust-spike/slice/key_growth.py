"""The lazy design's open risk: does a sort key hold a term conversion wouldn't otherwise have? A lazy key can't add a term,
since Rust's derived ids follow the input ids, so such a key refuses when it's read.

    key_growth.py WL OUT.json [--limit N]

Runs conversion alone on each top-level query, the engine skipped, on a fresh engine with memos cleared. Terms in a key are
held back rather than walked, so every other route (args, content, free symbols) has added what it adds; then each one is
looked up in the finished table. Same `enc` test as convert.py: a Basic that isn't a Rational. Has to run on a tree whose
convert.py computes keys in `term_row`, and says so if it doesn't.
"""
from collections import Counter
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('wl')
ap.add_argument('out')
ap.add_argument('--limit', type=int)
args = ap.parse_args()

from sympy.core.basic import Basic
from sympy.core.numbers import Rational
from harness.state import reset_module_state
from satassume import sympy_api
from satassume import engine as E
from evalbench.common import workload
import convert as C

if args.wl == 'fuzz':
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(args.wl)
if args.limit:
    pairs = pairs[:args.limit]

HELD = []
real_enc = C._Walk.enc


def enc(self, v, out, key=False):
    if key and isinstance(v, Basic) and not isinstance(v, Rational):
        HELD.append(v)
        out += (C.T_TERM, 0)
        return
    real_enc(self, v, out, key)


C._Walk.enc = enc
N = Counter()
MISS = Counter()
EXAMPLES = []
CUR = [None]


def _ask(proposition, assumptions, eng):
    del HELD[:]
    N['queries'] += 1
    c = C.convert(proposition, assumptions, eng)
    if isinstance(c, C.Kept):
        N['kept:' + c.reason] += 1
        return None
    N['converted'] += 1
    N['terms'] += len(c.objects)
    N['keys_computed'] += c.counts['keys']
    missed = 0
    for v in HELD:
        N['key_terms'] += 1
        N['key_term_class:' + type(v).__name__] += 1
        if v not in c.ids:
            missed += 1
            MISS[type(v).__name__] += 1
            if len(EXAMPLES) < 50:
                EXAMPLES.append((CUR[0], type(v).__name__, repr(v)[:200], repr(proposition)[:300], repr(assumptions)[:200]))
    N['key_terms_missing'] += missed
    if missed:
        N['queries_with_missing'] += 1
    return None


sympy_api._ask = _ask
for q, (p, a) in enumerate(pairs):
    CUR[0] = q
    reset_module_state(sympy_cache=False)
    sympy_api.set_default_engine(E.Engine())
    try:
        sympy_api.ask(p, a)
    except Exception as e:
        N['raised:' + type(e).__name__] += 1
if not N['keys_computed']:
    print('NOTE: no keys computed: this convert.py is lazy and this measurement is void')
json.dump({'wl': args.wl, 'n_pairs': len(pairs), 'counts': dict(sorted(N.items())), 'missing_by_class': dict(MISS),
           'examples': EXAMPLES}, open(args.out, 'w'), indent=1)
print(args.wl, len(pairs), 'key_terms', N['key_terms'], 'missing', N['key_terms_missing'], 'queries', N['queries_with_missing'])
print('done', flush=True)
