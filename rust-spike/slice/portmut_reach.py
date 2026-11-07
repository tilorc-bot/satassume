"""portmut_reach.py WL OUT.json [live.py args]: how often each planted bug's line would change something on a workload,
with the first query that gets there. "Not caught" means something different if the line never mattered: reach 0 is
"never effective on this workload", not a gap in the comparison.
  negated: an odd count of Negated. offset: an Integral with a nonzero rational offset. touch: `_touch` with a term the
  core hasn't seen. forget: `_forget` at a move with new terms to take back. last_object: an equal term under another object."""
import collections
import json
import sys

import handler_count
import live
import lra_backend as B

C = collections.Counter()
first = {}


def hit(k):
    C[k] += 1
    first.setdefault(k, handler_count.where)


reg, pairs, forget, touch = B.LRATheory._register, B.LRATheory._pairs, B.LRATheory._forget, B.LRATheory._touch


def _register(self, core, literal, payload):
    hit("registered")
    n = 0
    p = payload
    while isinstance(p, B.Negated):
        n += 1
        p = p.payload
    if n % 2:
        hit("negated")
    if isinstance(payload, B.Integral):
        hit("integral")
        try:
            if B.num(payload[1]) != 0:
                hit("offset")
        except Exception:
            pass
    return reg(self, core, literal, payload)


def _pairs(self, terms, rebuilt):
    out, t2 = pairs(self, terms, rebuilt)
    items = t2.items() if isinstance(t2, dict) else t2
    for (t, _), (i, _) in zip(items, out):
        if self._terms[i] is not t:
            hit("last_object")
    return out, t2


def _forget(self, n0):
    if len(self._terms) > n0:
        hit("forget")
    return forget(self, n0)


def _touch(core, ids):
    if ids:
        hit("touch")
    return touch(core, ids)


B.LRATheory._register, B.LRATheory._pairs, B.LRATheory._forget, B.LRATheory._touch = _register, _pairs, _forget, staticmethod(_touch)

wl, out = sys.argv[1], sys.argv[2]
sys.argv = ["live.py", wl, "rust", out + ".rows", "--check", "plain", *sys.argv[3:]]
try:
    live.main()
finally:
    json.dump(dict(counts=C, first=first), open(out, "w"))
