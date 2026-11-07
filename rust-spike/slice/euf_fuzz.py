"""euf_fuzz.py [--seeds N] [--ops N] [--start N] [--sympy] [--so DIR]: the API differential for the EUF port.

The same random operations go to Python's `EUFTheory` and the crate's, with `state.diff` after every operation. An
operation matches if both return the same value, or both raise the same type with the same message. A raise leaves the
state to compare too, since a listener that raises stops a merge part way. On a difference the sequence is shrunk and
printed, and the exit code is 1.

Listeners, one per run: none; one that reads `rep`, `members` and `explain` and records them; one that re-enters `term`
and `value`; one that raises on its nth call.

Left out on purpose, each a known edge named in the report: `explain` with a negative id (Python walks raw negative ids
in `_explain`), and a literal past i32 (the crate raises OverflowError, as its solver does).
"""
import argparse
import collections
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from satassume.theories.euf.euf import EqAtom, EUFTheory as PyEUF  # noqa: E402

import state  # noqa: E402

HEADS = ["f", "g", "h", "c0", "c1", 1, 1.0, True, 2, ("f", 1), None]
OPS = ["const", "const", "app", "app", "app", "value", "atom", "atom", "assert", "assert", "assert", "assert_rep",
       "check", "propagate", "explain", "find", "equal", "rep", "members", "push", "push", "pop", "pop", "pop_empty",
       "bad_term", "bad_atom", "repr"]
LISTENERS = ["none", "read", "reenter", "raises"]


def sympy_heads():
    import sympy as S
    x, y = S.symbols("x y")
    f, g = S.Function("f"), S.Function("g")
    return [x, y, f, g, S.Integer(1), S.Integer(2), S.Rational(1, 2), S.Float(0.5), S.Float(1.0), S.Add, S.Mul, S.Pow,
            f(x), S.Dummy, 1, 0.5, S.S.One, S.S.Half]


# Past this a re-entering listener can merge without end, and Python's recursion limit stops it at a different depth on
# the two classes: 5 Python frames a merge on Python's, 1 on the crate's. That difference is real and is `--unbounded`.
REENTER_CALLS = 40


class Boom(Exception):
    pass


def attach(th, kind, nth, log):
    if kind == "none":
        return
    calls = [0]

    def f(ra, rb):
        calls[0] += 1
        log.append(("merge", ra, rb))
        if kind == "read":
            log.append(("rep", list(th.rep)))
            log.append(("members", [list(m) for m in th.members]))
            log.append(("mem", list(th.members[rb])))
            log.append(("equal", th.equal(ra, rb), th.find(ra)))
            if th.equal(ra, rb):
                try:
                    log.append(("explain", th.explain(ra, rb)))
                except Exception as e:
                    log.append(("explain-raised", type(e).__name__, str(e)))
        elif kind == "reenter" and calls[0] <= REENTER_CALLS:
            log.append(("term", th.term("listener" + str(calls[0] % 3))))
            log.append(("value", th.value(calls[0] % 2)))
            log.append(("app", th.term("lf", [ra])))
        elif kind == "raises" and calls[0] == nth:
            raise Boom(f"call {calls[0]}")
    th.on_merge = f


def gen_ops(rng, n, heads):
    """Ops as (name, picks...), with picks resolved against the run's state, so any subsequence stays meaningful."""
    out = []
    for _ in range(n):
        out.append((rng.choice(OPS), rng.randrange(len(heads)), rng.randrange(1 << 30), rng.randrange(1 << 30),
                    rng.randrange(1 << 30), rng.random() < 0.5))
    return out


def run_op(th, op, ctx, heads):
    """One op on one theory. `ctx` holds what the driver knows, which must evolve the same on both."""
    name, h, a, b, c, flag = op
    n = len(th.rep)
    head = heads[h]
    if name == "const":
        return th.term(head)
    if name == "app":
        if not n:
            return th.term(head)
        return th.term(head, [a % n] if flag else [a % n, b % n])
    if name == "value":
        return th.value(head)
    if name == "atom":
        if not n:
            return None
        v = ctx["next_var"]
        ctx["next_var"] += 1
        # a plain tuple payload is a positive atom; EqAtom carries its own polarity
        pay = EqAtom(a % n, b % n, c % 3 != 0) if flag or c % 5 else (a % n, b % n)
        r = th.register_atom(v, pay)
        ctx["vars"].append(v)
        return r
    if name == "assert":
        if not ctx["vars"]:
            return None
        v = ctx["vars"][a % len(ctx["vars"])]
        return th.assert_lit(v if flag else -v)
    if name == "assert_rep":  # a repeated assert with the same sign: Python's pop raises KeyError on it
        if not ctx["vars"]:
            return None
        v = ctx["vars"][-1]
        th.assert_lit(v)
        return th.assert_lit(v)
    if name == "check":
        r = th.check()
        return r[0], (list(r[1]) if not isinstance(r[1], dict) else sorted(r[1].items()))
    if name == "propagate":
        return th.propagate()
    if name == "explain":
        if not n:
            return None
        if flag:  # a pair known equal, when a class has two: random pairs mostly just raise
            big = [m for m in th.members if len(m) > 1]
            if big:
                m = big[a % len(big)]
                return th.explain(m[b % len(m)], m[c % len(m)])
        return th.explain(a % n, b % n)
    if name == "find":
        return th.find(a % n - (n if flag else 0)) if n else None
    if name == "equal":
        return th.equal(a % n, b % n) if n else None
    if name == "rep":
        r = th.rep
        return len(r), list(r), (r[a % n] if n else None), list(iter(r)) == list(r)
    if name == "members":
        m = th.members
        return len(m), [list(x) for x in m], (list(m[a % n]) if n else None)
    if name == "push":
        ctx["lv"] += 1
        return th.push_level()
    if name in ("pop", "pop_empty"):
        if name == "pop" and ctx["lv"] == 0:
            return None
        ctx["lv"] = max(ctx["lv"] - 1, 0)
        return th.pop_level()
    if name == "bad_term":
        if c % 4 == 0:
            return th.term(head, None)
        return th.term(head, [n + (a % 3)] if flag else [-1 - (a % 3)])
    if name == "bad_atom":
        return th.register_atom(0 if flag else -1 - (a % 3), (0, 0)) if flag else th.register_atom(1, (n, n))
    if name == "repr":
        return repr(th)
    raise AssertionError(name)


def outcome(f):
    try:
        return "ok", f()
    except Exception as e:  # the message counts: both raise it, and a caller can read it
        return "raise", type(e).__name__, str(e)


STATS = collections.Counter()
SHRINKING = [False]


def tally(st, name, a, py):
    """What the run reached, from Python's side: zero differences say little about a path no run took."""
    if SHRINKING[0]:
        return
    if a[0] == "raise":
        st[f"raise {name} {a[1]}"] += 1
    elif name in ("assert", "assert_rep") and a[1] is not None:
        st["assert returned a conflict"] += 1
    elif name == "propagate" and a[1]:
        st["propagate with results"] += 1
    elif name == "explain" and a[1]:
        st["explain, non-empty"] += 1
    st["max terms"] = max(st["max terms"], len(py.rep))
    st["ops at depth > 0"] += bool(py._lims)
    st["ops with a pending conflict"] += py._conflict is not None
    st["trail reg_app entries seen"] += sum(1 for e in py._trail if e[0] == 4)
    st["trail reg_atom entries seen"] += sum(1 for e in py._trail if e[0] == 5)
    st["ops with congruence edges in the forest"] += any(isinstance(x, tuple) for x in py._pfl)


def run(ops, heads, kind, nth, rust_cls):
    """None if the two agree on all of `ops`, else (index, field, py, rust)."""
    py, ru = PyEUF(), rust_cls()
    lp, lr = [], []
    attach(py, kind, nth, lp)
    attach(ru, kind, nth, lr)
    cp, cr = dict(next_var=1, vars=[], lv=0), dict(next_var=1, vars=[], lv=0)
    for i, op in enumerate(ops):
        a = outcome(lambda: run_op(py, op, cp, heads))
        tally(STATS, op[0], a, py)
        b = outcome(lambda: run_op(ru, op, cr, heads))
        if a != b:
            return i, "result", repr(a), repr(b)
        if lp != lr:
            j = next((j for j, (x, y) in enumerate(zip(lp, lr)) if x != y), min(len(lp), len(lr)))
            return i, "listener", repr(lp[j:j + 1]), repr(lr[j:j + 1])
        d = state.diff(state.dump_euf_py(py), ru.dump(state.show_head))
        if d:
            return i, d[0], d[2], d[3]
        if repr(py) != repr(ru):
            return i, "repr", repr(py), repr(ru)
    return None


def shrink(ops, heads, kind, nth, rust_cls):
    """Greedy: drop chunks, largest first, while it still differs."""
    SHRINKING[0] = True
    size = len(ops) // 2 or 1
    while True:
        i = 0
        while i < len(ops):
            t = ops[:i] + ops[i + size:]
            if run(t, heads, kind, nth, rust_cls):
                ops = t
            else:
                i += size
        if size == 1:
            return ops
        size //= 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=400)
    ap.add_argument("--ops", type=int, default=120)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--sympy", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--unbounded", action="store_true", help="let the re-entering listener recurse to the limit")
    ap.add_argument("--so", default=os.environ.get("SLICE_SO") or _HERE)
    ap.add_argument("--max-report", type=int, default=5)
    a = ap.parse_args()
    sys.path.insert(0, a.so)
    import sa_solver

    global REENTER_CALLS
    if a.unbounded:
        REENTER_CALLS = 10 ** 9
    heads = sympy_heads() if a.sympy else HEADS
    bad, opsrun, seen = 0, 0, set()
    for seed in range(a.start, a.start + a.seeds):
        rng = random.Random(seed)
        kind, nth = LISTENERS[seed % len(LISTENERS)], rng.randrange(1, 6)
        ops = gen_ops(rng, a.ops, heads)
        r = run(ops, heads, kind, nth, sa_solver.EUFTheory)
        opsrun += len(ops)
        if not r:
            continue
        bad += 1
        small = shrink(ops, heads, kind, nth, sa_solver.EUFTheory)
        r = run(small, heads, kind, nth, sa_solver.EUFTheory)
        SHRINKING[0] = False
        sig = (r[1], tuple(o[0] for o in small))
        if sig in seen or len(seen) >= a.max_report:
            continue
        seen.add(sig)
        print(f"seed {seed} listener {kind} nth {nth}: {len(small)} ops, differs at op {r[0]} in {r[1]}")
        print("  ops:", [(o[0], repr(heads[o[1]]), o[2] % 97, o[3] % 97, o[4] % 15, o[5]) for o in small])
        print("  py:  ", r[2][:300])
        print("  rust:", r[3][:300])
    if a.stats:
        for k, v in sorted(STATS.items()):
            print(f"  {k}: {v}")
    print(f"euf_fuzz: seeds {a.seeds}, ops {opsrun}, heads {'sympy' if a.sympy else 'plain'}, differ {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
