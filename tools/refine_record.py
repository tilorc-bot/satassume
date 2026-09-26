"""Record the ``ask`` query stream that satrefine issues over its battery.

    PYTHONHASHSEED=0 SATREFINE_HANDLERS=handlers_identities SATREFINE_IDENTITIES=generated \
      PYTHONPATH=.:/path/to/sympy python tools/refine_record.py stream.pkl

Needs a checkout that has ``satrefine`` and ``tests/refine_identities``
(the ``refine-identities`` branch); the pickle it writes is replayed by
``tools/refine_replay.py`` against any satassume checkout.
"""
import pickle, sys, time
import satrefine, satrefine.identities.compat.backend as B
from tests.refine_identities.battery_v3 import BATTERY
B.set_backend("satassume")
orig = B._satassume_ask
stream = []
def rec(p, a=True):
    r = orig(p, a); stream.append((p, a, r)); return r
B._IMPLEMENTATIONS["satassume"] = rec
t0 = time.perf_counter()
for expr, assum, exp, src in BATTERY:
    try: satrefine.refine(expr, assum)
    except Exception: pass
print(f"refine loop {time.perf_counter()-t0:.1f}s, {len(stream)} queries")
with open(sys.argv[1], "wb") as f: pickle.dump(stream, f)
