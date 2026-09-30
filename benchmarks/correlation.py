"""Time and counts as lines of one asv graph, to see whether they move together.

``Correlation.track_value(workload, metric)``: for ``metric == "time"`` it
returns ``{"samples": [...], "number": 1}``, which asv's result parser
(``asv/runner.py``, asv 0.6.6) treats as a timing (median, confidence
interval, quartiles) although this is a ``track_`` benchmark; every other
metric is a plain count from :mod:`.counters`.  That is how asv parses
results, not a documented feature, so a later asv may need a change here.
In the web UI tick the metrics to compare and turn on *log scale*: the same
relative change is then the same vertical step for every line.

Times:

* ``stream``: one cold pass of the refine stream per fresh subprocess,
  ``STREAM_SAMPLES`` of them (the loop of ``tools/ab.py``);
* a family: the family's queries on a fresh ``Engine``, ``FAMILY_SAMPLES``
  times in this process after one warm-up, so SymPy and the template
  registry's caches are warm and the engine's own work is what is timed.
"""
import os
import subprocess
import sys
import time

from .counters import STREAM, answer, families, load_stream, run

STREAM_SAMPLES = 3
FAMILY_SAMPLES = 15
COUNTS = ("clauses", "clauses_with_rule_block", "propagations", "nodes", "decisions")

_REPLAY = r'''
import os, pickle, sys, time
sys.path.insert(0, os.environ.get("SATASSUME_SYMPY", "/home/tilo/sympy"))
stream = pickle.load(open(sys.argv[1], "rb"))
from satassume.sympy_api import ask
t0 = time.perf_counter()
for p, a, _ in stream:
    try:
        ask(p, a)
    except ValueError:
        pass
print(time.perf_counter() - t0)
'''


def _stream_times():
    out = []
    for _ in range(STREAM_SAMPLES):
        p = subprocess.run([sys.executable, "-c", _REPLAY, STREAM],
                           capture_output=True, text=True, check=True)
        out.append(float(p.stdout.split()[-1]))
    return out


def _family_times(queries):
    answer(queries)
    out = []
    for _ in range(FAMILY_SAMPLES):
        t0 = time.perf_counter()
        answer(queries)
        out.append(time.perf_counter() - t0)
    return out


class Correlation:
    params = [["stream"] + list(families()), ("time",) + COUNTS]
    param_names = ["workload", "metric"]
    processes = 1
    timeout = 900

    def setup_cache(self):
        fams = families()
        times = {"stream": _stream_times()}
        for name, qs in fams.items():
            times[name] = _family_times(qs)
        counts = {"stream": run([(p, a) for p, a, _ in load_stream()])[1]}
        for name, qs in fams.items():
            counts[name] = run(qs)[1]
        return times, counts

    def track_value(self, cache, workload, metric):
        times, counts = cache
        if metric == "time":
            return {"samples": times[workload], "number": 1}
        return counts[workload][metric]
    track_value.unit = "value"
