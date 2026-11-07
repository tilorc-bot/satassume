"""History argument: fill the cache in a given query order, in check mode, and write each class's row digest.
Usage: row_orders.py ORDER OUT.json, ORDER one of dev, dev-rev, fuzz, fuzz-rev, fuzz-dev, dev-fuzz. Needs SLICE_CONV_CACHE=check."""
import hashlib, json, sys

sys.path.insert(0, '.')
import p_install

p_install.install()
from evalbench.common import workload
from evalbench.fuzz import queries
from harness.state import reset_module_state
from satassume import engine as E, sympy_api
import term_live, lra_live, convert as C

term_live.install(keys=False, terms=True)
lra_live.install()
order, out = sys.argv[1:3]
assert C._CACHE == 'check'
dev, fuzz = workload('dev'), queries(424242)
pairs = dict(dev=dev, fuzz=fuzz, **{'dev-rev': dev[::-1], 'fuzz-rev': fuzz[::-1], 'fuzz-dev': fuzz + dev, 'dev-fuzz': dev + fuzz})[order]
for p, q in pairs:
    reset_module_state(sympy_cache=False)
    sympy_api.set_default_engine(E.Engine())
    try:
        sympy_api.ask(p, q)
    except Exception:
        pass
rows = {f'{c.__module__}.{c.__qualname__}': hashlib.blake2b(repr(e).encode(), digest_size=8).hexdigest() for c, e in C._ROW_CACHE.items()}
json.dump(dict(order=order, n=len(pairs), counts=C.CACHE_COUNTS, differs=[d[0] for d in C.CACHE_DIFFERS[:50]], rows=rows), open(out, 'w'), indent=0, sort_keys=True)
