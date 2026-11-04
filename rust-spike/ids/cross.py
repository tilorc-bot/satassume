"""cross.py WL: under live, count SymPy calls made from satassume frames that hand over or return a hash-keyed container
built on the other side: xreplace/subs/atoms/free_symbols. A rule dict built with id hashes and read by SymPy with real
hashes silently misses, so a nonzero count means the frame-scoped live mode was not faithful there."""
import collections
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
wl = sys.argv[1]
from evalbench.common import ask_all, workload  # noqa: E402
from satassume import sympy_api  # noqa: E402
import ids_core  # noqa: E402
from sympy import Basic  # noqa: E402
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)
C = collections.Counter()
for name in ("xreplace", "subs", "atoms", "has", "replace", "rewrite", "match"):
    o = getattr(Basic, name)

    def w(self, *a, o=o, name=name, **k):
        f = sys._getframe(1)
        if ids_core.in_sa(f.f_code):
            C[f"{name} {os.path.basename(f.f_code.co_filename)}:{f.f_lineno}"] += 1
        return o(self, *a, **k)
    setattr(Basic, name, w)
ids_core.install("live")
ask_all(sympy_api.ask, pairs)
print(json.dumps(dict(wl=wl, calls=C.most_common(30))))
