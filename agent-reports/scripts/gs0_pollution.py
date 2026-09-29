"""Persistent-solver plan, stage 0: per-query log with sessions left polluted.

    PYTHONHASHSEED=0 PYTHONPATH=.:tools:/home/tilo/sympy python gs0_pollution.py STREAM LOG [KEY=VALUE ...]

Runs ``tools/query_log.run`` (the ``refine_replay.py --log`` format) on an
engine built with the given keyword arguments, default ``cone_search=False``
(a query that needs search is searched in the reused, polluted session
instead of a cone rebuild).  ``session_limit=N`` etc. may be added.
Prints the number of answers that differ from the recording.
"""
import pickle
import sys

import query_log
from satassume.engine import Engine
from satassume.sympy_api import set_default_engine

stream = pickle.load(open(sys.argv[1], "rb"))
kw = {"cone_search": False}
for arg in sys.argv[3:]:
    k, v = arg.split("=")
    kw[k] = eval(v)
set_default_engine(Engine(**kw))
dt, bad = query_log.run(stream, sys.argv[2])
print(f"engine {kw}: logged pass {dt:.2f}s, {len(bad)} answers differ from the recording")
for b in bad[:10]:
    print("  ", b)
