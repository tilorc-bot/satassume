"""transfer_fresh.py WORKLOAD MODE OUT: per query, a fresh engine with memos cleared; the answer and a digest of every
session's solver and transfer state at query end, in creation order. One line per query, so two runs compare by `cmp`,
and a difference has its query index. Run under two PYTHONHASHSEEDs, this is the no-hash-order check.

MODE: py, all Python. rust, the Rust solver and component 3 on Rust. solver, the Rust solver with Python's component 3,
the control. shadow, the Rust solver with `ShadowTransfer`, comparing per hook. OUT.json gets counts: quiet-handler
catches, sessions, sessions with a transfer theory, EUF crossings, and in shadow mode calls and differences.

--limit N stops early. --only I,J runs those queries, in a fresh engine as ever.
"""
import argparse
import collections
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ap = argparse.ArgumentParser()
ap.add_argument("wl")
ap.add_argument("mode", choices=["py", "rust", "solver", "shadow"])
ap.add_argument("out")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--only")
ap.add_argument("--so", help="load sa_solver from this directory (a mutant)")
a = ap.parse_args()
if a.so:
    sys.path.insert(0, a.so)

from evalbench.common import workload  # noqa: E402
from harness.state import reset_module_state  # noqa: E402
from satassume import engine as E, sympy_api  # noqa: E402
from satassume.sat.solver import Solver as PySolver  # noqa: E402

import state as T  # noqa: E402
import transfer_shadow as X  # noqa: E402

if a.mode == "py":
    dump = T.dump_py
else:
    os.environ["SLICE_TRANSFER"] = {"rust": "rust", "solver": "py", "shadow": "shadow"}[a.mode]
    import backend
    if a.so and os.path.dirname(os.path.abspath(backend.sa_solver.__file__)) != os.path.abspath(a.so):
        sys.exit(f"--so {a.so}: loaded {backend.sa_solver.__file__}")
    backend.install()
    dump = backend.RustSolver.dump

X.count_quiet_catches()
if a.mode == "shadow":
    X.log = open(a.out + ".diffs", "w")

if a.wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(a.wl)
only = set(map(int, a.only.split(","))) if a.only else None
sessions = []
_init = E.Session.__init__


def init(self, *args, **kw):
    _init(self, *args, **kw)
    sessions.append(self)


E.Session.__init__ = init
counts = collections.Counter()


def theory_of(s):
    rel = getattr(s, "xfer", None)
    return None if rel is None else rel.xfer


def digest(s):
    d = dict(dump(s.solver))
    th = theory_of(s)
    if th is not None:
        counts["sessions with transfer"] += 1
        d.update(("transfer " + k, v) for k, v in X.dump_of(th).items())
        if hasattr(th, "_crossings"):
            counts.update({"euf " + k: v for k, v in th._crossings().items()})
    counts["sessions"] += 1
    return hashlib.blake2b(repr(sorted(d.items())).encode(), digest_size=8).hexdigest()


with open(a.out, "w") as fh:
    for i, (p, q) in enumerate(pairs):
        if a.limit and i >= a.limit:
            break
        if only is not None and i not in only:
            continue
        reset_module_state(sympy_cache=False)
        sympy_api.set_default_engine(E.Engine())
        sessions.clear()
        X.where["query"] = i
        try:
            r = repr(sympy_api.ask(p, q))
        except Exception as e:  # the type and text are the answer
            counts["raised"] += 1
            r = f"{type(e).__name__}: {e}"
        fh.write(f"{i}\t{r}\t{','.join(digest(s) for s in sessions)}\n")
        counts["queries"] += 1
out = dict(counts, quiet_catches=dict(X.catches), hash_seed=os.environ.get("PYTHONHASHSEED"))
if a.mode == "shadow":
    out["shadow"] = dict(X.stats)
json.dump(out, open(a.out + ".json", "w"), indent=1, sort_keys=True)
print(json.dumps({k: out[k] for k in out if k != "shadow"}, sort_keys=True))
if a.mode == "shadow":
    print("shadow calls", X.stats["calls"], "theories", X.stats["theories"], "differences", X.stats["differences"])
