"""record_lra.py WORKLOAD OUTDIR [--timers]: run dev or fuzz 424242 through the real engine and record every call into
LRATheory (register_atom, assert_lit, check, propagate, push_level, pop_level), with arguments and results.

Monkeypatches only; nothing in the package changes. Terms become per-session integer ids, in the order the session
first sees them, using the term's own hash and == (as LRATheory._var_of does). A session whose payloads have a
constfield Element (LRATheory._fields) is recorded nowhere: it isn't rational, so it stays outside the boundary, and
its time is reported separately by --timers.

--timers: no recording; outermost timers on those methods, split by rational and constant sessions and by answer,
for the core's share of a live pass.
"""
import gc
import hashlib
import inspect
import json
import os
import sys
import time
import weakref
import zlib
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from common_lra import result_str, state_str  # noqa: E402

wl, outdir = sys.argv[1], sys.argv[2]
TIMERS = "--timers" in sys.argv

from evalbench.common import workload  # noqa: E402
from satassume import sympy_api  # noqa: E402
from satassume.theories.lra.lra import Integral, LRATheory, Negated  # noqa: E402

if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)

pc = time.perf_counter


class S:
    depth = 0
    next_tid = 0
    lines = []          # (tid or -1, text, crc or -1)
    keys = {}           # tid -> {term: id}
    excluded = set()    # tids with constants
    nonfrac = 0         # int coefficients and constants in rational sessions' payloads
    dict_terms = 0
    t_by_tid = {}       # --timers
    q_lra = {}          # --timers: tid -> {query: seconds}
    q = -1
    raised = 0


def num_str(x):
    if type(x) is Fraction:
        return f"{x.numerator}/{x.denominator}"
    if type(x) is int:
        S.nonfrac += 1
        return f"{x}/1"
    raise TypeError


def terms_str(tid, terms):
    if isinstance(terms, dict):
        S.dict_terms += 1
        terms = terms.items()
    ids = S.keys[tid]
    out = []
    for t, c in terms:
        i = ids.get(t)
        if i is None:
            i = ids[t] = len(ids)
        out.append(f"{i} {num_str(c)}")
    return f"{len(out)} " + " ".join(out) if out else "0"


def payload_str(tid, p):
    if isinstance(p, Integral):
        return f"I {num_str(p.offset)} {terms_str(tid, p.terms)}"
    neg = 0
    while isinstance(p, Negated):
        neg += 1
        p = p.payload
    terms, constant, strict, equality = p
    return f"P {neg} {int(bool(strict))} {int(bool(equality))} {num_str(constant)} {terms_str(tid, terms)}"


def emit(self, tid, text, r):
    crc = zlib.crc32((result_str(r, S.keys[tid]) + state_str(self)).encode())
    S.lines.append((tid, text, crc))


def wrap_record(name, fn, enc):
    def w(self, *a):
        if S.depth:
            return fn(self, *a)
        S.depth = 1
        try:
            r = fn(self, *a)
        except Exception:
            S.raised += 1
            S.excluded.add(self._rec_tid)
            raise
        finally:
            S.depth = 0
        tid = self._rec_tid
        if self._fields:
            S.excluded.add(tid)
        if tid in S.excluded:
            return r
        try:
            text = enc(self, tid, a)
        except TypeError:           # a number that is no Fraction or int: not this boundary
            S.excluded.add(tid)
            return r
        emit(self, tid, text, r)
        return r
    return w


def wrap_timer(name, fn):
    def w(self, *a):
        if S.depth:
            return fn(self, *a)
        S.depth = 1
        t = pc()
        try:
            return fn(self, *a)
        finally:
            dt = pc() - t
            d = S.q_lra.setdefault(self._rec_tid, {})
            d[S.q] = d.get(S.q, 0.0) + dt
            S.depth = 0
    return w


ENC = {
    "register_atom": lambda s, t, a: f"R {t} {a[0]} {payload_str(t, a[1])}",
    "assert_lit": lambda s, t, a: f"A {t} {a[0]}",
    "check": lambda s, t, a: f"C {t}",
    "propagate": lambda s, t, a: f"G {t}",
    "push_level": lambda s, t, a: f"U {t}",
    "pop_level": lambda s, t, a: f"O {t}",
}
for n, e in ENC.items():
    f = getattr(LRATheory, n)
    setattr(LRATheory, n, wrap_timer(n, f) if TIMERS else wrap_record(n, f, e))

orig_init = LRATheory.__init__


def init(self, *a, **k):
    if a or k:
        raise RuntimeError("LRATheory with arguments isn't in the trace format")
    orig_init(self)
    tid = self._rec_tid = S.next_tid
    S.next_tid += 1
    S.keys[tid] = {}
    if not TIMERS:
        S.lines.append((tid, f"N {tid}", -1))
        weakref.finalize(self, lambda t=tid: S.lines.append((t, f"D {t}", -1)))


LRATheory.__init__ = init
if TIMERS:
    orig_reg = LRATheory.register_atom

    def reg(self, *a):
        r = orig_reg(self, *a)
        if self._fields:
            S.excluded.add(self._rec_tid)
        return r
    LRATheory.register_atom = reg

gc.collect()
gc.freeze()

ans = []
t_q = []
t0 = pc()
for q, (p, a) in enumerate(pairs):
    S.q = q
    if not TIMERS:
        S.lines.append((-1, f"Q {q}", -1))
    t1 = pc()
    try:
        r = sympy_api.ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:  # noqa: BLE001
        r = "raise " + type(e).__name__
    t_q.append(pc() - t1)
    ans.append(r)
T = pc() - t0
digest = hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]
cls = ["none" if x is None else "definite" if x is True or x is False else "other" for x in ans]

if TIMERS:
    out = {c: dict(T=0.0, rational=0.0, constants=0.0) for c in ("none", "definite", "other")}
    for q, x in enumerate(t_q):
        out[cls[q]]["T"] += x
    for tid, d in S.q_lra.items():
        which = "constants" if tid in S.excluded else "rational"
        for q, x in d.items():
            if q >= 0:
                out[cls[q]][which] += x
    print(json.dumps(dict(mode="timers", wl=wl, T=T, digest=digest, classes=out, sessions=S.next_tid,
                          constant_sessions=len(S.excluded))), flush=True)
    sys.exit(0)

os.makedirs(outdir, exist_ok=True)
ops = {}
crcs = []
with open(os.path.join(outdir, f"{wl}.lra"), "w") as f:
    for tid, text, crc in S.lines:
        if tid in S.excluded:
            continue
        f.write(text + "\n")
        ops[text[0]] = ops.get(text[0], 0) + 1
        crcs.append(crc)
with open(os.path.join(outdir, f"{wl}.lra.res"), "w") as f:
    f.write("\n".join(str(c) for c in crcs) + "\n")
meta = dict(wl=wl, digest=digest, cls=cls, ops=ops, sessions=S.next_tid, constant_sessions=len(S.excluded),
            nonfrac=S.nonfrac, dict_terms=S.dict_terms, raised=S.raised, record_s=T)
with open(os.path.join(outdir, f"{wl}.lra.meta.json"), "w") as f:
    json.dump(meta, f)
print(json.dumps({k: v for k, v in meta.items() if k != "cls"} | dict(
    none=cls.count("none"), definite=cls.count("definite"), other=cls.count("other"))), flush=True)
