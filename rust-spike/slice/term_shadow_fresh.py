"""One workload on a fresh engine with memos cleared per query, as the port brief requires, optionally under the shadow.

    term_shadow_fresh.py WL OUT.json [--plain] [--limit N]

WL: dev, fuzz, corpus (or any evalbench workload). --plain: no shadow, for the answers sha. OUT.json gets the shadow's
report; OUT.json.answers the per-query answers. Equal answers with and without the shadow show its reads don't move a query.
"""
import argparse
import hashlib
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)

ap = argparse.ArgumentParser()
ap.add_argument('wl')
ap.add_argument('out')
ap.add_argument('--plain', action='store_true')
ap.add_argument('--limit', type=int)
args = ap.parse_args()

from harness.state import reset_module_state
from satassume import sympy_api
from satassume import engine as E
from evalbench.common import workload

if args.wl == 'fuzz':
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(args.wl)
if args.limit:
    pairs = pairs[:args.limit]

import term_shadow
if not args.plain:
    term_shadow.install()
    term_shadow.install_algebra()

sha = hashlib.sha256()
with open(args.out + '.answers', 'w') as ans:
    for p, a in pairs:
        reset_module_state(sympy_cache=False)
        sympy_api.set_default_engine(E.Engine())
        try:
            r = repr(sympy_api.ask(p, a))
        except Exception as e:
            r = 'raised ' + type(e).__name__
        ans.write(r + '\n')
        sha.update(r.encode() + b'\n')
print(args.wl, len(pairs), 'answers', sha.hexdigest()[:16])
term_shadow.report(args.out)
