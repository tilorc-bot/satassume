"""Per-query time of one cold stream pass, for a split between checkouts.

    PYTHONHASHSEED=0 PYTHONPATH=CHECKOUT:SYMPY python facts2_split.py STREAM OUT.json [REPS]

Times every query (``sympy_api.ask`` on one engine, as ``tools/ab.py``);
REPS cold passes (fresh process state is not reset between passes, so use
REPS=1 and run the script several times, or compare medians). Records per
query: seconds, whether the assumptions or the proposition contain an
equality relation, and (if the checkout has transfer) whether the
query's session had transfer engaged.
"""
import json, pickle, sys, time
from satassume.engine import Engine
from satassume.sympy_api import ask

stream = pickle.load(open(sys.argv[1], "rb"))
import os
eng = Engine(**({"transfer": False} if os.environ.get("NOXFER") else {}))


def has_eq(e):
    s = str(e)
    return "Q.eq(" in s or "Q.ne(" in s or "Eq(" in s or "Ne(" in s or "==" in s


def xfer_on(eng, a):
    hit = eng._context_sessions.get(a) if a is not True else None
    return None


out = []
perf = time.perf_counter
for p, a, r in stream:
    t = perf()
    try:
        ask(p, a, engine=eng)
    except ValueError:
        pass
    dt = perf() - t
    out.append(dt)
json.dump({"t": out, "eq": [has_eq(p) or has_eq(a) for p, a, _ in stream]}, open(sys.argv[2], "w"))
print(f"total {sum(out):.3f}s")
