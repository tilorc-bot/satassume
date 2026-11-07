"""euf_points.py WORKLOAD py|rust OUT [--plant] [--so DIR]: two open points on the EUF port, measured on one warm engine.

Every query runs on the same engine, in workload order, as a user's process does; memos stay. A row of OUT is a total.
  Lifetime: TERMS-INTERFACE.md says no id may be kept across top-level queries. This counts the EUF theories used in more
    than one top-level query, how many queries they span, and the handles handed out again in a later query than the one
    that first made them.
    `same` is a workload made for this: equality queries that repeat one assumption set, the case a kept session would serve.
  Re-entry: `transfer._merged` is said, by reading, not to re-enter. This records every listener set on a theory, and any
    call on a theory, or read of `rep` or `members`, while one of its listeners is running. The difference between
    backends (recursion limit at about 213 terms on Python and 1,011 on the crate) needs that to happen.
--plant makes each listener call `find` first, to show the detector fires: re-entry must then read above 0.
Wrappers only count and call straight on. On Python, `rep` and `members` are plain attributes and aren't watched, so a
listener reading them shows only on the crate. Errors are the workload's own if they match `live.py`'s answers.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ap = argparse.ArgumentParser()
ap.add_argument("wl")
ap.add_argument("mode", choices=["py", "rust"])
ap.add_argument("out")
ap.add_argument("--plant", action="store_true")
ap.add_argument("--so")
a = ap.parse_args()
if a.so:
    sys.path.insert(0, a.so)

from evalbench.common import workload  # noqa: E402
from harness.state import reset_module_state  # noqa: E402
from satassume import engine as E, sympy_api  # noqa: E402
import satassume.theories.euf.euf as euf_mod  # noqa: E402
import satassume.theories.euf.euf_adapter as adapter_mod  # noqa: E402

if a.mode == "rust":
    import backend
    backend.install()
    Base = backend.EUFTheory
else:
    Base = euf_mod.EUFTheory

METHODS = ["term", "value", "find", "equal", "explain", "register_atom", "assert_lit", "check", "propagate",
           "push_level", "pop_level"]
ISSUING = {"term", "value"}
query = 0
theories = []
listeners = collections.Counter()
reenter = collections.Counter()
reissued = collections.Counter()
depth = {"now": 0, "max": 0, "merges": 0}


def seen(self, name):
    self._q_last = query
    self._q_used.add(query)
    if depth["now"]:
        reenter[name] += 1


def wrap(name):
    inner = getattr(Base, name)

    def f(self, *args, **kw):
        seen(self, name)
        r = inner(self, *args, **kw)
        if name in ISSUING:
            first = self._q_ids.setdefault(r, query)
            if first != query:
                reissued[name] += 1
        return r
    f.__name__ = name
    return f


def listened(self, f):
    listeners[getattr(f, "__qualname__", repr(type(f)))] += 1

    def g(ra, rb):
        depth["merges"] += 1
        depth["now"] += 1
        depth["max"] = max(depth["max"], depth["now"])
        try:
            if a.plant:
                self.find(ra)
            return f(ra, rb)
        finally:
            depth["now"] -= 1
    return g


class Counting(Base):
    def __init__(self, *args, **kw):
        self._q_first = self._q_last = query
        self._q_used = {query}
        self._q_ids = {}
        theories.append(self)
        super().__init__(*args, **kw)

    if a.mode == "rust":
        rep = property(lambda self: (seen(self, "rep"), Base.rep.__get__(self))[1])
        members = property(lambda self: (seen(self, "members"), Base.members.__get__(self))[1])

        @property
        def on_merge(self):
            return Base.on_merge.__get__(self)

        @on_merge.setter
        def on_merge(self, f):
            Base.on_merge.__set__(self, None if f is None else listened(self, f))
    else:
        def __setattr__(self, name, value):
            if name == "on_merge" and value is not None:
                value = listened(self, value)
            object.__setattr__(self, name, value)


for m in METHODS:
    setattr(Counting, m, wrap(m))
euf_mod.EUFTheory = adapter_mod.EUFTheory = Counting

if a.wl == "same":
    from sympy import And, Eq, Function, symbols
    x, y, z = symbols("x y z")
    f, g = Function("f"), Function("g")
    ctx = And(Eq(x, y), Eq(f(y), z))
    pairs = [(Eq(f(x), z), ctx), (Eq(g(x), g(y)), ctx), (Eq(f(f(x)), f(z)), ctx), (Eq(g(z), g(f(x))), ctx), (Eq(x, z), ctx),
             (Eq(f(x), z), ctx), (Eq(g(f(y)), g(z)), Eq(f(y), z)), (Eq(g(f(y)), g(z)), Eq(f(y), z))]
elif a.wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(a.wl)

reset_module_state(sympy_cache=False)
sympy_api.set_default_engine(E.Engine())
errors = collections.Counter()
answers = []
for query, (p, q) in enumerate(pairs):
    try:
        answers.append(repr(sympy_api.ask(p, q)))
    except Exception as e:
        errors[type(e).__name__] += 1
        answers.append(type(e).__name__)

spans = [len(t._q_used) for t in theories]
across = [t for t in theories if len(t._q_used) > 1]
ids = sum(len(t._q_ids) for t in theories)
kept = sum(1 for t in across for i, first in t._q_ids.items() if t._q_last > first)
total = dict(workload=a.wl, mode=a.mode, plant=a.plant, queries=len(pairs), errors=dict(errors),
             theories=len(theories), theories_used_in_more_than_one_query=len(across),
             most_queries_on_one_theory=max(spans, default=0),
             widest_gap=max((t._q_last - t._q_first for t in theories), default=0),
             handles=ids, handles_on_a_theory_used_after_their_query=kept,
             handles_handed_out_again_in_a_later_query=dict(reissued),
             listeners=dict(listeners), calls_while_a_listener_runs=dict(reenter), deepest_listener=depth["max"], merges_heard=depth["merges"],
             spans=dict(sorted(collections.Counter(spans).items())))
if a.wl == "same":
    total["answers"] = answers
with open(a.out, "w") as fh:
    json.dump(total, fh, indent=1)
print(json.dumps(total))
