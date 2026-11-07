"""knowledge_fresh.py WL OUT [--mode plain|atoms|shadow] [--limit N]: one workload, fresh engine with memos cleared per query.

One line per query: index, answer, session count, digest of each session's solver at query end. Compare two modes' OUT
files by line. OUT.counts.json: knowledge_live's counts and any shadow mismatches. plain runs no Rust and no conversion.
"""
import argparse, hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('wl'); ap.add_argument('out')
ap.add_argument('--mode', default='shadow', choices=['plain', 'atoms', 'shadow'])
ap.add_argument('--limit', type=int)
args = ap.parse_args()
from harness.state import reset_module_state
from satassume import sympy_api, engine as E
from evalbench.common import workload
import state as T
if args.wl == 'fuzz':
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(args.wl)
pairs = pairs[:args.limit] if args.limit else pairs
K = None
if args.mode != 'plain':
    import knowledge_live as K
    K.install(shadow=args.mode == 'shadow')
sessions = []
_init = E.Session.__init__
def init(self, *a, **k):
    _init(self, *a, **k)
    sessions.append(self)
E.Session.__init__ = init
def dg(s):
    return hashlib.blake2b(repr(sorted(T.dump_py(s.solver).items())).encode(), digest_size=8).hexdigest()
with open(args.out, 'w') as fh:
    for i, (p, a) in enumerate(pairs):
        reset_module_state(sympy_cache=False)
        sympy_api.set_default_engine(E.Engine())
        sessions.clear()
        try:
            r = sympy_api.ask(p, a)
        except Exception as e:
            r = 'raise:' + type(e).__name__
        ds = [dg(s) for s in sessions]
        fh.write(f"{i}\t{r}\t{len(ds)}\t{','.join(ds)}\n")
    fh.write('END\n')
if K:
    json.dump(dict(counts=K.COUNTS, mismatches=K.MISMATCHES), open(args.out + '.counts.json', 'w'), indent=1)
    print(dict(K.COUNTS)); print(K.MISMATCHES[:3])
