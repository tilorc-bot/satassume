"""knowledge_fresh.py WL OUT [--mode plain|atoms|shadow|discard] [--limit N] [--shuffle S]: one workload, fresh engine with memos cleared per query.

discard: run conversion, throw its result away and let Python answer, no Rust template. This is section 9's discarded run at its
widest: compared with plain on the same order, any difference is something conversion left in Python that a later answer or state read.

One line per query: index, answer, session count, digest of each session's solver at query end. Compare two modes' OUT
files by line. OUT.counts.json: knowledge_live's counts and any shadow mismatches. plain runs no Rust and no conversion.
"""
import argparse, hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('wl'); ap.add_argument('out')
ap.add_argument('--mode', default='shadow', choices=['plain', 'atoms', 'shadow', 'discard'])
ap.add_argument('--limit', type=int)
ap.add_argument('--handlers', help='handler_count rows here, `where` the query index; after the run, one planted raise at each call in the two tries, so a zero is about a counter shown to fire in this process')
ap.add_argument('--shuffle', type=int, help='run in this seeded order; the first column stays the query index, so sort before comparing')
ap.add_argument('--plant', help='a planted bug from knowledge_plants, to show a compare fires')
args = ap.parse_args()
from harness.state import reset_module_state
from satassume import sympy_api, engine as E
from evalbench.common import workload
import state as T
if args.wl == 'fuzz':
    from evalbench.fuzz import queries
    pairs = queries(424242)
elif args.wl == 'value':
    import knowledge_value_wl
    pairs = knowledge_value_wl.queries()
else:
    pairs = workload(args.wl)
pairs = pairs[:args.limit] if args.limit else pairs
order = list(enumerate(pairs))
if args.shuffle is not None:
    import random
    random.Random(args.shuffle).shuffle(order)
if args.plant:
    import knowledge_plants
K = None
if args.mode == 'discard':
    import collections, convert
    py_ask = sympy_api._ask
    done = collections.Counter()
    def _discard(p, a, eng):
        c = convert.convert(p, a, eng)
        done['kept' if isinstance(c, convert.Kept) else 'converted'] += 1
        if args.plant:
            knowledge_plants.after_convert(args.plant, p, a)
        return py_ask(p, a, eng)
    sympy_api._ask = _discard
elif args.mode != 'plain':
    import knowledge_live as K
    K.install(shadow=args.mode == 'shadow')
    if args.plant:
        knowledge_plants.wrap_templates(args.plant)
H = None
if args.handlers:
    import handler_count as H
    H.install(args.handlers)
sessions = []
_init = E.Session.__init__
def init(self, *a, **k):
    _init(self, *a, **k)
    sessions.append(self)
E.Session.__init__ = init
def dg(s):
    return hashlib.blake2b(repr(sorted(T.dump_py(s.solver).items())).encode(), digest_size=8).hexdigest()
with open(args.out, 'w') as fh:
    for i, (p, a) in order:
        reset_module_state(sympy_cache=False)
        if H:
            H.where = i
        sympy_api.set_default_engine(E.Engine())
        sessions.clear()
        try:
            r = sympy_api.ask(p, a)
        except Exception as e:
            r = 'raise:' + type(e).__name__
        ds = [dg(s) for s in sessions]
        fh.write(f"{i}\t{r}\t{len(ds)}\t{','.join(ds)}\n")
    fh.write('END\n')
if H:
    import knowledge_quiet
    print('plant check', knowledge_quiet.plant_check(H))
if args.mode == 'discard':
    print(dict(done))
if K:
    json.dump(dict(counts=K.COUNTS, mismatches=K.MISMATCHES, order_diffs=K.ORDER_DIFFS), open(args.out + '.counts.json', 'w'), indent=1)
    print(dict(K.COUNTS)); print(K.MISMATCHES[:3])
