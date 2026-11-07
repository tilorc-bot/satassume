"""Ruling 6's numbers, per query on a fresh engine with every memo and SymPy's cache cleared, since a cached result hides
a construction. Run once per mode, each in its own process, since a first pass warms the input objects' own caches
(`_assumptions`, `_mhash`) and would flatter the second. Join by q with counts_summary.py.

    py:   ask alone, as pure Python does it.
    conv: conversion and Rust's table first, then the same ask. Nothing checks anything and nothing reads the table.

    term_counts.py WL py|conv OUT.jsonl [--limit N] [--no-count]

`Basic.__new__` is what's counted (constructions, by every route that reaches it). --no-count leaves it unwrapped, for
times. A row: py_new, conv_new, table_new, rest_new (the ask after conversion), keys (computed by conversion), decompose
(`decompose_power` calls), keys_used (calls in the query's own ask), and process-time seconds py_s, conv_s, table_s, rest_s.
"""
from collections import Counter
import argparse
import hashlib
import json
import os
import sys
import time

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)

ap = argparse.ArgumentParser()
ap.add_argument('wl')
ap.add_argument('mode', choices=('py', 'conv'))
ap.add_argument('out')
ap.add_argument('--limit', type=int)
ap.add_argument('--no-count', action='store_true')
ap.add_argument('--by-site', help='conv mode: write constructions during conversion by convert.py line and class to this file')
args = ap.parse_args()

from sympy.core.basic import Basic
import sa_solver
from harness.state import reset_module_state
from satassume import sympy_api
from satassume import engine as E
from satassume import relations as R
from satassume.theories.lra import lra_adapter as L
from evalbench.common import workload
import convert as C

if args.wl == 'fuzz':
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(args.wl)
if args.limit:
    pairs = pairs[:args.limit]

NEW = [0]
IN_CONV = [False]
SITES = Counter()
CONV_FILE = C.__file__
if not args.no_count:
    real_new = Basic.__new__

    def new(cls, *a, **k):
        NEW[0] += 1
        if args.by_site and IN_CONV[0]:
            f = sys._getframe(1)
            while f is not None and f.f_code.co_filename != CONV_FILE:
                f = f.f_back
            if f is not None:
                SITES[f'{f.f_code.co_name}:{f.f_lineno} {cls.__name__}'] += 1
        return real_new(cls, *a, **k)
    Basic.__new__ = staticmethod(new)

USED = [0]


def used(real):
    def key(e, *a, **k):
        USED[0] += 1
        return real(e, *a, **k)
    return key


R._key = used(R._key)
L.default_sort_key = used(L.default_sort_key)

MODE = [None]
ROW = [None]
DEPTH = [0]
real_ask = sympy_api._ask


def _ask(proposition, assumptions, eng):
    DEPTH[0] += 1
    try:
        if DEPTH[0] == 1 and MODE[0] == 'conv':
            row = ROW[0]
            n, t = NEW[0], time.process_time()
            IN_CONV[0] = True
            c = C.convert(proposition, assumptions, eng)
            IN_CONV[0] = False
            row['conv_s'] = time.process_time() - t
            row['conv_new'] = NEW[0] - n
            if isinstance(c, C.Kept):
                row['kept'] = c.reason
            else:
                row['keys'] = c.counts['keys']
                row['decompose'] = c.counts['decompose_power']
                row['pow_base_not_input'] = c.counts['pow_base_not_input']
                row['terms'] = len(c.objects)
                n, t = NEW[0], time.process_time()
                sa_solver.TermTable(c.tables)
                row['table_s'] = time.process_time() - t
                row['table_new'] = NEW[0] - n
        return real_ask(proposition, assumptions, eng)
    finally:
        DEPTH[0] -= 1


sympy_api._ask = _ask


def run(p, a, mode, row):
    reset_module_state(sympy_cache=True)
    sympy_api.set_default_engine(E.Engine())
    MODE[0] = mode
    USED[0] = 0
    n, t = NEW[0], time.process_time()
    try:
        r = repr(sympy_api.ask(p, a))
    except Exception as e:
        r = 'raised ' + type(e).__name__
    return NEW[0] - n, time.process_time() - t, r


with open(args.out, 'w') as out:
    for q, (p, a) in enumerate(pairs):
        row = {'q': q}
        ROW[0] = row
        if args.mode == 'py':
            row['py_new'], row['py_s'], ans = run(p, a, 'py', row)
            row['keys_used'] = USED[0]
        else:
            total_new, total_s, ans = run(p, a, 'conv', row)
            row['rest_new'] = total_new - row['conv_new'] - row.get('table_new', 0)
            row['rest_s'] = total_s - row['conv_s'] - row.get('table_s', 0)
        row['ans'] = hashlib.sha256(ans.encode()).hexdigest()[:12]
        out.write(json.dumps(row) + '\n')
print(args.wl, args.mode, len(pairs), 'done')
if args.by_site:
    json.dump(SITES.most_common(), open(args.by_site, 'w'), indent=0)
