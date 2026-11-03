"""out mode of rc.py: exclusive timers on what runs outside the boundary, by item. Boundary
time is excluded (B.enter / B.leave pause the current item). What no item covers (ask's
own code, the answer memo, the replay loop) is the rest."""
import time

from satassume import sympy_api

pc = time.perf_counter
GROUPS = {
    "conversion": ("_formula", "to_formula", "relation_parts", "_relation_formula"),
    "relevance": ("_relevant",),
    "consistency": ("_consistent", "_part_consistent"),
    "precheck": ("check_strict", "out_of_scope", "is_constant_proposition"),
}
NAMES = list(GROUPS)


class St:
    cur = None
    t0 = 0.0
    calls = [0] * len(NAMES)
    perq = None


def install(B, snaps, n):
    St.perq = [[0.0] * len(NAMES) for _ in range(n)]

    def charge():
        if St.cur is not None:
            St.perq[len(snaps) // 2][St.cur] += pc() - St.t0

    def make(g, orig):
        def w(*a, **k):
            if B.depth or St.cur == g:
                return orig(*a, **k)
            charge()
            prev = St.cur
            St.cur = g
            St.calls[g] += 1
            St.t0 = pc()
            try:
                return orig(*a, **k)
            finally:
                charge()
                St.cur = prev
                St.t0 = pc()
        return w

    for g, name in enumerate(NAMES):
        for fn in GROUPS[name]:
            setattr(sympy_api, fn, make(g, getattr(sympy_api, fn)))

    B.enter = lambda name, a: charge()

    def leave(name, a):
        St.t0 = pc()
    B.leave = leave


def report(ans):
    out = {"calls": dict(zip(NAMES, St.calls))}
    for g, name in enumerate(NAMES):
        out[name] = {"none": round(sum(q[g] for q, r in zip(St.perq, ans) if r is None), 5),
                     "def": round(sum(q[g] for q, r in zip(St.perq, ans) if r is not None), 5)}
    return out
