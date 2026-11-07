"""identity_rule.py [OUT]: which object each backend keeps wherever equal, distinct term objects can land (planner, 7 Nov).

Every ordered pair and triple from a pool of payloads over equal, distinct objects. For each: register on real Python and on
Rust, then compare, by tag, every place a term object sits: `walk` searches all of Python's fields, so a container nobody
named shows up too. Then the model keys from check(). Then both go on with the same calls, comparing answers and state to the
end. The state transfer is gone; while it existed this ran with a move right after the registrations: 14,424 sequences,
344,304 answers, 0 differ (hook level, plain Fractions, moves at level 0). Test-only."""
import collections
import itertools
import json
import sys
from fractions import Fraction as F

import lra_backend
from satassume.theories.lra.lra import Integral, LRATheory as Py, Negated


class T:
    def __init__(self, name, tag):
        self.name, self.tag = name, tag

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return f"{self.tag}"


x1, x2, y1, y2 = T("x", "x1"), T("x", "x2"), T("y", "y1"), T("y", "y2")


def plain(pairs, k=1):
    return (tuple((t, F(c)) for t, c in pairs), F(k), False, False)


POOL = {}
for a, b, y in ((x1, x2, y1), (x2, x1, y2)):
    n = a.tag
    POOL |= {
        f"{n}": plain([(a, 1)]),
        f"{n}+y": plain([(a, 1), (y, 1)]),
        f"y+{n}": plain([(y, 1), (a, 1)]),
        f"2{n}+2y": plain([(a, 2), (y, 2)]),
        f"{n}+{b.tag}": plain([(a, 1), (b, 1)]),                  # one term twice in a payload
        f"{n}+{b.tag}+y": plain([(a, 1), (b, 1), (y, 1)]),
        f"{n}-{b.tag}": plain([(a, 1), (b, -1)]),                 # cancels: ground, but `_lin` has seen the term
        f"0{n}+y": plain([(a, 0), (y, 1)]),                       # zero coefficient
        f"Int({n}+y)": Integral(((a, F(1)), (y, F(1))), F(0)),
        f"Int({n})": Integral(((a, F(1)),), F(1, 2)),
        f"Neg({n}+y)": Negated(plain([(a, 1), (y, 1)])),
        f"dict({n}+y)": ({a: F(1), y: F(1)}, F(1), False, False),
    }


def canon(o):
    """Tags kept. Dicts and lists in their order; sets sorted, since they have none."""
    if isinstance(o, T):
        return o.tag
    if isinstance(o, dict):
        return [[canon(k), canon(v)] for k, v in o.items()]
    if isinstance(o, (list, tuple)):
        return [canon(v) for v in o]
    if isinstance(o, (set, frozenset)):
        return sorted((canon(v) for v in o), key=repr)
    return repr(o)


def holds_term(o):
    if isinstance(o, T):
        return True
    if isinstance(o, dict):
        return any(holds_term(k) or holds_term(v) for k, v in o.items())
    if isinstance(o, (list, tuple, set, frozenset)):
        return any(holds_term(v) for v in o)
    return False


def state(t):
    st = t._state() if getattr(t, "_core", None) is not None else vars(t)
    return {k: canon(st[k]) for k in lra_backend._STATE if k in st and k not in ("_py_exhausted", "_py_branched", "_py_stats")}


def run(cls, names):
    t = cls()
    for lit, n in enumerate(names, 1):
        t.register_atom(lit, POOL[n])
    return t


def calls(t, n):
    """The session after registration, every result by tag."""
    out = [canon(t.propagate())]
    for lit in range(1, n + 1):
        t.push_level()
        out.append(canon(t.assert_lit(lit)))
        out.append(canon(t.propagate()))
        out.append(canon(t.check()))
        out.append(state(t))
    out.append(canon(t.check()))
    for _ in range(n):
        t.pop_level()
        out.append(state(t))
    out.append(canon(t.check()))
    # later atoms hit `_forms` and `_var_of` with other equal objects: the only reads of those keys
    for lit, p in enumerate((plain([(x2, 1), (y1, 1)], 7), plain([(y2, 1), (x1, 1)], 8), plain([(x2, 1)], 9), plain([(x1, 2), (y1, 2)], 10)), n + 1):
        out.append(canon(t.register_atom(lit, p)))
        out.append(canon(t.propagate()))
        out.append(canon(t.check()))
        out.append(state(t))
    return out


def main(out=None):
    print("sample check:", canon(run(Py, ("x1+y",)).check()), canon(run(lra_backend.LRATheory, ("x1+y",)).check()))
    diffs = collections.Counter()
    first = {}
    extra = collections.Counter()
    nseq = session_diff = refused = answers = 0
    rows = []
    for size in (1, 2, 3):
        for names in itertools.product(POOL, repeat=size):
            nseq += 1
            try:
                p = run(Py, names)
            except Exception as e:
                p = e
            try:
                r = run(lra_backend.LRATheory, names)
            except Exception as e:
                r = e
            if isinstance(p, Exception) or isinstance(r, Exception):
                if type(p) is not type(r):
                    diffs["raise"] += 1
                    first.setdefault("raise", (names, repr(p), repr(r)))
                refused += 1
                continue
            for k, v in vars(p).items():
                if holds_term(v):
                    extra[k] += 1
            a, b = state(p), state(r)
            for k in a:
                if a[k] != b.get(k):
                    diffs[k] += 1
                    first.setdefault(k, (names, a[k], b.get(k)))
            ca, cb = canon(run(Py, names).check()), canon(run(lra_backend.LRATheory, names).check())
            if ca != cb:
                diffs["model"] += 1
                first.setdefault("model", (names, ca, cb))
            # the same calls on both, to the end of the session
            m = run(lra_backend.LRATheory, names)
            pe = run(Py, names)
            c1, c2 = calls(pe, size), calls(m, size)
            for k, v in vars(pe).items():       # any container that only fills during the session
                if holds_term(v):
                    extra["end:" + k] += 1
            hit = set()
            for j, (u, w) in enumerate(zip(c1, c2)):
                if isinstance(u, dict):
                    hit |= {k for k in u if u[k] != w.get(k)}
                    if u.get("_forms") != w.get("_forms"):
                        first.setdefault("session:_forms", (names, j, u.get("_forms"), w.get("_forms")))
                    for k in u:
                        if k != "_forms" and u[k] != w.get(k):
                            first.setdefault("session:" + k, (names, j, u[k], w.get(k)))
                elif u != w:
                    hit.add("answer")
                    first.setdefault("session:answer", (names, j, u, w))
            if len(c1) != len(c2):
                hit.add("answer")
            session_diff += bool(hit)
            for k in hit:
                diffs["session:" + k] += 1
            answers += sum(not isinstance(u, dict) for u in c1)
    res = dict(pool=len(POOL), sequences=nseq, refused_both_or_diff=refused, answers_compared=answers, session_differs=session_diff,
               differs=dict(diffs), python_fields_holding_terms=dict(extra), first={k: repr(v) for k, v in first.items()})
    print(json.dumps(res, indent=0))
    if out:
        json.dump(res, open(out, "w"), indent=0)


if __name__ == "__main__":
    main(*sys.argv[1:])
