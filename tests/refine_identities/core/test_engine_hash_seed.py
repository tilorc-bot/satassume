"""Moved from ``needs/test_baseline_hash_seed_dependence.py``.  Fixed in the engine:
the positive-sign branch of a case split was explored under ``Q.zero(x)``,
where it is inconsistent, and the backend's answer there (``True`` or a
``ValueError``) depended on the hash seed.  ``_split_branches`` now offers
no sign case when neither sign is consistent.

Found while re-baselining after the merge of ``main`` (not caused by it):
``refine`` gives different results for different ``PYTHONHASHSEED`` values.

``refine(log(1/x), Q.zero(x))`` is ``zoo`` for hash seeds 0, 1, 5, 6, 7
and ``log(1/x)`` (unchanged) for 2, 3, 4, on ``refine-identities`` both
before and after the merge.  With seed 0 the ``arg`` handler first rewrites
``arg(1/x) -> 0`` (``arg(zoo)`` is ``nan`` in SymPy, so that intermediate
step is itself questionable), and the ``log`` handler then fires; with
seed 2 neither fires.  So candidate order comes from iterating a set or a
dict keyed by hashes somewhere in the engine.  Both final results are
acceptable values, but the scoreboard and the gates must not depend on the
hash seed: the battery's ``power_exp_log`` row moved between "other form"
and "miss" from one run to the next.  Wanted: the same result for every
seed (deterministic candidate order).  Until then, baselines are recorded
with ``PYTHONHASHSEED=0``.
"""
from __future__ import annotations

import os
import subprocess
import sys

SCRIPT = """
import os
os.environ["SATREFINE_HANDLERS"] = "handlers_identities"
from sympy import Q, Symbol, log
from satrefine import refine
x = Symbol('x')
print(refine(log(1/x), Q.zero(x)))
"""


def test_result_does_not_depend_on_the_hash_seed():
    results = {}
    for seed in ("0", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = subprocess.run([sys.executable, "-c", SCRIPT], capture_output=True, text=True, env=env, check=True)
        results[seed] = out.stdout.split()[-1]
    assert len(set(results.values())) == 1, results
