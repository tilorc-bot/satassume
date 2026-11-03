"""Time spent in LRA checks that exhaust the branch budget (one cold pass).

    python cost_child.py SPEC [MODE]
MODE "" = timed pass with the _check wrapper; "plain" = untimed-wrapper pass
(total only, to see the wrapper's overhead).
Prints one JSON line: total pass s, s in all _check, s in exhausting _check,
s of queries with >=1 exhausting check, counts, branches in exhausting checks.
"""
import json
import os
import sys
import time

sys.setrecursionlimit(100000)
spec = sys.argv[1]
mode = sys.argv[2] if len(sys.argv) > 2 else ""
from evalbench.common import workload  # noqa: E402

if spec.startswith("fuzz:"):
    from evalbench.fuzz import queries
    pairs = queries(int(spec.split(":")[1]))
else:
    pairs = workload(spec)

from satassume import sympy_api  # noqa: E402
from satassume.theories.lra import lra  # noqa: E402

pc = time.perf_counter
acc = {"check_s": 0.0, "exh_s": 0.0, "checks": 0, "exh": 0, "exh_branches": 0,
       "nonexh_branches": 0}
qflag = [False]
ocheck = lra.LRATheory._check


def check(self):
    e0 = self.stats["exhausted"]
    b0 = self.stats["branches"]
    t0 = pc()
    r = ocheck(self)
    dt = pc() - t0
    acc["check_s"] += dt
    acc["checks"] += 1
    if self.stats["exhausted"] != e0:
        acc["exh_s"] += dt
        acc["exh"] += 1
        acc["exh_branches"] += self.stats["branches"] - b0
        qflag[0] = True
    else:
        acc["nonexh_branches"] += self.stats["branches"] - b0
    return r


if mode == "latds":                     # sa-bb-1's c2 prototype under the timer
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "bb-tools"))
    from proto_hook import install
    ocheck = install(lra)
if mode != "plain":
    lra.LRATheory._check = check
ask = sympy_api.ask
total = 0.0
exhq_s = 0.0
exhq_none_s = 0.0
none_s = 0.0
exhq = 0
perq, flags, answers = [], [], []
for p, a in pairs:
    qflag[0] = False
    t0 = pc()
    try:
        r = ask(p, a)
    except Exception:
        r = "err"
    dt = pc() - t0
    perq.append(round(dt * 1e6))
    flags.append(int(qflag[0]))
    answers.append(str(r))
    total += dt
    if r is None:
        none_s += dt
    if qflag[0]:
        exhq += 1
        exhq_s += dt
        if r is None:
            exhq_none_s += dt
acc.update(spec=spec, mode=mode, queries=len(pairs), total_s=round(total, 4),
           none_s=round(none_s, 4), exh_queries=exhq, exhq_s=round(exhq_s, 4),
           exhq_none_s=round(exhq_none_s, 4))
for k in ("check_s", "exh_s"):
    acc[k] = round(acc[k], 4)
import hashlib
acc['answers_sha'] = hashlib.sha1('|'.join(answers).encode()).hexdigest()[:12]
acc['perq_us'] = perq
acc['exh_flags'] = flags
print(json.dumps(acc))
