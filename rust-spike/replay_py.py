"""replay_py.py WORKLOAD TRACEDIR MODE: replay a recorded trace through the real Python Solver.

Modes:
  check   CRC of every public call against .res, cumulative counters per query against .meta.json perq.
  timed   no CRCs; wall time of the pass, and a timestamp per query for the None / definite split.
  nogc    timed, with the cycle collector off.
  byop    wall time per public method: rough shares, a clock pair per call.
  empty   the same loop with every call replaced by a no-op: the dispatch cost to subtract.
  tape    every theory hook in recorded order, no solver, then the same calls to a no-op method: what the tape
          body costs beyond a plain method call.

Everything is decoded before the clock starts. A tape theory raises on any hook it did not record, so a replay
that takes a different search path fails at once, in every mode.
"""
import gc
import json
import os
import sys
import time
from array import array

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from common_trace import COUNTERS, EXC, MAGIC, OPS, T_ASSERT, T_CHECK, T_DECIDE, T_PROP, crc, norm  # noqa: E402

wl, tracedir, mode = sys.argv[1], sys.argv[2], sys.argv[3]

from satassume.sat.solver import Solver  # noqa: E402

pc = time.perf_counter


class Diverged(RuntimeError):
    pass


class Tape:
    __slots__ = ("r", "i", "pushes", "pops")

    def __init__(self, recs):
        self.r = recs
        self.i = 0
        self.pushes = 0
        self.pops = 0

    def register_atom(self, var, payload):
        pass

    def push_level(self):
        pass

    def pop_level(self):
        pass

    def assert_lit(self, x):
        r = self.r[self.i]
        self.i += 1
        if r[0] != T_ASSERT or r[1] != x:
            raise Diverged(f"assert_lit({x}), tape {r[:2]} at {self.i - 1}")
        return r[2]

    def check(self):
        r = self.r[self.i]
        self.i += 1
        if r[0] != T_CHECK:
            raise Diverged(f"check, tape {r[:2]} at {self.i - 1}")
        return r[1]

    def nop(self, *a):
        return None


class TapeP(Tape):
    __slots__ = ()

    def propagate(self):
        r = self.r[self.i]
        self.i += 1
        if r[0] != T_PROP:
            raise Diverged(f"propagate, tape {r[:2]} at {self.i - 1}")
        return r[1]


class TapeD(Tape):
    __slots__ = ()

    def decide(self):
        r = self.r[self.i]
        self.i += 1
        if r[0] != T_DECIDE:
            raise Diverged(f"decide, tape {r[:2]} at {self.i - 1}")
        return r[1]


class TapePD(TapeP):
    __slots__ = ()
    decide = TapeD.decide


TAPE_CLASS = {(0, 0): Tape, (1, 0): TapeP, (0, 1): TapeD, (1, 1): TapePD}


class Counting:
    """Mixed in for check mode: push and pop counts per query."""
    __slots__ = ()

    def push_level(self):
        self.pushes += 1

    def pop_level(self):
        self.pops += 1


def load_words(path):
    a = array("i")
    with open(path, "rb") as f:
        a.frombytes(f.read())
    return a


def decode_tape(w, lo, hi):
    out = []
    i = lo
    while i < hi:
        k = w[i]
        if k == T_ASSERT:
            x, n = w[i + 1], w[i + 2]
            i += 3
            if n < 0:
                out.append((k, x, None))
            else:
                out.append((k, x, (False, w[i:i + n].tolist())))
                i += n
        elif k == T_PROP:
            np_ = w[i + 1]
            i += 2
            pairs = []
            for _ in range(np_):
                x, n = w[i], w[i + 1]
                i += 2
                pairs.append((x, w[i:i + n].tolist()))
                i += n
            out.append((k, pairs))
        elif k == T_CHECK:
            st, n = w[i + 1], w[i + 2]
            i += 3
            if st == 0:
                out.append((k, None))
            elif st == 1:
                out.append((k, (True, None)))
            else:
                out.append((k, (False, w[i:i + n].tolist())))
                i += n
        elif k == T_DECIDE:
            x = w[i + 1]
            i += 2
            out.append((k, None if x == 0 else x))
        else:
            raise ValueError(f"tape kind {k} at {i}")
    if i != hi:
        raise ValueError("tape overran its length")
    return out


def load():
    w = load_words(os.path.join(tracedir, f"{wl}.trace"))
    if w[0] & 0xFFFFFFFF != MAGIC:
        raise ValueError("bad magic")
    n_api, n_th = w[1], w[2]
    api_lo = 3
    i = api_lo + n_api
    tapes = []
    for _ in range(n_th):
        n = w[i]
        i += 1
        tapes.append(decode_tape(w, i, i + n))
        i += n
    if i != len(w):
        raise ValueError(f"trailing words: {len(w) - i}")
    return w, api_lo, api_lo + n_api, tapes


def decode_api(w, i, end, tape_recs):
    """The API stream as (fn, sid, args): sid < 0 is a special event, handled in the loop."""
    ops = []
    th = [None] * len(tape_recs)
    blocks = {}
    O = OPS
    S = Solver

    def mask(j):
        return sum((w[j + k] & 0xFFFFFFFF) << (32 * k) for k in range(4))

    def lits(j):
        n = w[j]
        return w[j + 1:j + 1 + n].tolist(), j + 1 + n

    def hold(x):
        return None if x < 0 else x

    while i < end:
        op = w[i]
        i += 1
        if op == O["QUERY"]:
            ops.append((None, -1, w[i]))
            i += 1
        elif op == O["NEW"]:
            ops.append((None, -2, w[i]))
            i += 1
        elif op == O["DROP"]:
            ops.append((None, -3, w[i]))
            i += 1
        elif op == O["BLOCK"]:
            bid, nc = w[i], w[i + 1]
            i += 2
            cls = []
            for _ in range(nc):
                c, i = lits(i)
                cls.append(c)
            blocks[bid] = cls
        else:
            sid = w[i]
            i += 1
            if op == O["attach_theory"]:
                tid, hp, hd = w[i], w[i + 1], w[i + 2]
                i += 3
                cls = TAPE_CLASS[(hp, hd)]
                if mode == "check":
                    cls = type(cls.__name__ + "C", (Counting, cls), {"__slots__": ()})
                th[tid] = cls(tape_recs[tid])
                ops.append((S.attach_theory, sid, (th[tid],)))
            elif op == O["register_atom"]:
                tid, var, men = w[i], w[i + 1], w[i + 2]
                i += 3
                ops.append((S.register_atom, sid, (th[tid], var, None, bool(men))))
            elif op == O["ensure_vars"]:
                ops.append((S.ensure_vars, sid, (w[i],)))
                i += 1
            elif op == O["add_clause"]:
                c, i = lits(i)
                ops.append((S.add_clause, sid, (c,)))
            elif op == O["add_internal"]:
                has, nm = w[i], w[i + 1]
                i += 2
                ms = []
                for _ in range(nm):
                    ms.append((w[i], mask(i + 1)))
                    i += 5
                nc = w[i]
                i += 1
                cls = []
                for _ in range(nc):
                    c, i = lits(i)
                    cls.append(c)
                ops.append((S.add_internal, sid, (cls, ms if has else None)))
            elif op == O["set_rule_block"]:
                nv = w[i + 1]
                ops.append((S.set_rule_block, sid, (blocks[w[i]], None if nv < 0 else nv)))
                i += 2
            elif op == O["register_block"]:
                ops.append((S.register_block, sid, (w[i], mask(i + 1))))
                i += 5
            elif op == O["mention"]:
                c, i = lits(i)
                ops.append((S.mention, sid, (c,)))
            elif op == O["propagate"]:
                ops.append((S.propagate, sid, ()))
            elif op == O["value"]:
                ops.append((S.value, sid, (w[i],)))
                i += 1
            elif op == O["implied"]:
                h = hold(w[i])
                c, i = lits(i + 1)
                ops.append((S.implied, sid, (c, h)))
            elif op == O["release"]:
                ops.append((S.release, sid, (w[i],)))
                i += 1
            elif op == O["set_inert"]:
                ops.append((S.set_inert, sid, (w[i],)))
                i += 1
            elif op == O["solve"]:
                c, i = lits(i)
                ops.append((S.solve, sid, (c,)))
            elif op == O["consistent"]:
                h = hold(w[i])
                c, i = lits(i + 1)
                ops.append((S.consistent, sid, (c, h)))
            elif op == O["entails"]:
                x, h = w[i], hold(w[i + 1])
                c, i = lits(i + 2)
                ops.append((S.entails, sid, (x, c, h)))
            elif op == O["entails_all"]:
                h = hold(w[i])
                c, i = lits(i + 1)
                a, i = lits(i)
                ops.append((S.entails_all, sid, (c, a, h)))
            elif op == O["theories"]:
                ops.append((S.theories, sid, ()))
            else:
                raise ValueError(f"op {op} at {i}")
    if i != end:
        raise ValueError("api overran its length")
    return ops, th


w, lo, hi, tape_recs = load()
ops, th = decode_api(w, lo, hi, tape_recs)
with open(os.path.join(tracedir, f"{wl}.meta.json")) as f:
    meta = json.load(f)
ans = meta["answers"]
nsolvers = meta["solvers"]
del w


def new_solver():
    s = Solver()
    s.track_owners = False
    return s


def run_check():
    res = array("I")
    with open(os.path.join(tracedir, f"{wl}.res"), "rb") as f:
        res.frombytes(f.read())
    perq = meta["perq"]
    solvers = [None] * nsolvers
    last = [[0] * len(COUNTERS) for _ in range(nsolvers)]
    total = [0] * len(COUNTERS)
    calls = 0
    q = -1
    out = []

    def snap():
        pushes = sum(t.pushes for t in th if t is not None)
        pops = sum(t.pops for t in th if t is not None)
        return [*total, pushes, pops, calls]

    def close_query():
        cur = snap()
        out.append(cur)
        if cur != perq[q]:
            d = {n: (a, b) for n, a, b in zip([*COUNTERS, "pushes", "pops", "calls"], cur, perq[q]) if a != b}
            raise Diverged(f"query {q}: counters differ (replay, recorded): {d}")

    for f, s, a in ops:
        if s == -1:
            if q >= 0:
                close_query()
            q = a
        elif s == -2:
            solvers[a] = new_solver()
        elif s == -3:
            solvers[a] = None
        else:
            so = solvers[s]
            try:
                h = crc(norm(f(so, *a)))
            except ValueError:
                h = crc(EXC)
            if h != res[calls]:
                raise Diverged(f"call {calls}, query {q}: {f.__name__}{a!r}: result crc differs")
            calls += 1
            prev = last[s]
            for i, name in enumerate(COUNTERS):
                x = getattr(so, name)
                total[i] += x - prev[i]
                prev[i] = x
    close_query()
    if calls != len(res) or q != len(perq) - 1:
        raise Diverged(f"short replay: {calls}/{len(res)} calls, {q + 1}/{len(perq)} queries")
    for i, t in enumerate(th):
        if t is not None and t.i != len(t.r):
            raise Diverged(f"theory {i}: {t.i}/{len(t.r)} tape records used")
    return dict(zip([*COUNTERS, "pushes", "pops", "calls"], out[-1])), out


def run_timed():
    solvers = [None] * nsolvers
    stamps = []
    add = stamps.append
    t0 = pc()
    for f, s, a in ops:
        if s >= 0:
            try:
                f(solvers[s], *a)
            except ValueError:
                pass
        elif s == -1:
            add(pc())
        elif s == -2:
            so = Solver()
            so.track_owners = False
            solvers[a] = so
        else:
            solvers[a] = None
    t1 = pc()
    return t1 - t0, stamps, t1


def run_byop():
    """Wall time per public method, a clock pair per call: rough shares only."""
    solvers = [None] * nsolvers
    by = {}
    t0 = pc()
    for f, s, a in ops:
        if s == -1:
            continue
        t = pc()
        if s >= 0:
            name = f.__name__
            try:
                f(solvers[s], *a)
            except ValueError:
                pass
        elif s == -2:
            name = "new"
            so = Solver()
            so.track_owners = False
            solvers[a] = so
        else:
            name = "drop"
            solvers[a] = None
        d = pc() - t
        e = by.get(name)
        if e is None:
            by[name] = [d, 1]
        else:
            e[0] += d
            e[1] += 1
    return pc() - t0, by


def nop(self, *a):
    return None


class Dummy:
    track_owners = True


def run_empty():
    """run_timed's loop, every call a no-op (the plain cost of the call stays in, as in run_timed)."""
    fast = [(nop, s, a) if s >= 0 else (f, s, a) for f, s, a in ops]
    gc.collect()
    gc.freeze()
    solvers = [None] * nsolvers
    stamps = []
    add = stamps.append
    t0 = pc()
    for f, s, a in fast:
        if s >= 0:
            try:
                f(solvers[s], *a)
            except ValueError:
                pass
        elif s == -1:
            add(pc())
        elif s == -2:
            so = Dummy()
            so.track_owners = False
            solvers[a] = so
        else:
            solvers[a] = None
    return pc() - t0


def run_tape():
    """Every hook call in tape order, then the same number of calls to a no-op method."""
    calls = []
    plain = []
    for t in th:
        if t is None:
            continue
        for r in t.r:
            k = r[0]
            if k == T_ASSERT:
                calls.append((t.assert_lit, (r[1],)))
            elif k == T_PROP:
                calls.append((t.propagate, ()))
            elif k == T_CHECK:
                calls.append((t.check, ()))
            else:
                calls.append((t.decide, ()))
            plain.append((t.nop, calls[-1][1]))
    gc.collect()
    gc.freeze()
    t0 = pc()
    for f, a in calls:
        f(*a)
    t1 = pc()
    for f, a in plain:
        f(*a)
    t2 = pc()
    return len(calls), t1 - t0, t2 - t1


gc.collect()
gc.freeze()
if mode == "check":
    tot, per = run_check()
    print(json.dumps(dict(impl="py", mode="check", wl=wl, ok=True, **tot)), flush=True)
    with open(os.path.join(tracedir, f"{wl}.perq-py.json"), "w") as f:
        json.dump(per, f)
elif mode in ("timed", "nogc"):
    if mode == "nogc":
        gc.disable()      # how much of T is the cycle collector, on the solver's objects alone
    T, stamps, t1 = run_timed()
    tn = td = 0.0
    for q, st in enumerate(stamps):
        d = (stamps[q + 1] if q + 1 < len(stamps) else t1) - st
        if ans[q] is None:
            tn += d
        else:
            td += d
    print(json.dumps(dict(impl="py", mode=mode, wl=wl, T=T, T_none=tn, T_def=td)), flush=True)
elif mode == "byop":
    T, by = run_byop()
    print(json.dumps(dict(impl="py", mode="byop", wl=wl, T=T, by=by)), flush=True)
elif mode == "empty":
    print(json.dumps(dict(impl="py", mode="empty", wl=wl, T=run_empty())), flush=True)
elif mode == "tape":
    n, tt, tp = run_tape()
    print(json.dumps(dict(impl="py", mode="tape", wl=wl, calls=n, T_tape=tt, T_plain=tp)), flush=True)
else:
    raise SystemExit(f"mode {mode}")
