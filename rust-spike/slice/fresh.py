"""fresh.py WORKLOAD py|rust OUT [--counts FILE]: per query, a fresh engine with memos cleared; the answer and a digest of
every session's solver and EUF state at query end, in creation order. One line per query, so two runs compare by `cmp`,
and a difference has its query index. Run under two PYTHONHASHSEEDs, this is the no-hash-order check; py against rust is
the held-to comparison. `seed_state.py` is the same idea on Python's solver alone, and has no EUF fields.

--counts wraps the EUF class's public methods, `on_merge` and the `rep` and `members` attributes, and writes how often
each crossed. Only the crossing is counted: a wrapper calls straight on, and the digest is the same with or without it.
The wrappers go on a Python subclass, so the solver's hooks into EUF are counted too; they reach it by attribute.
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
ap.add_argument("mode", choices=["py", "rust"])
ap.add_argument("out")
ap.add_argument("--counts")
ap.add_argument("--so")
ap.add_argument("--handlers", help="count the quiet Exception handlers here: handler_count.py")
ap.add_argument("--term", choices=["py", "table", "keys", "terms"], default="py", help="conversion on the real path: term_live.py")
ap.add_argument("--term-plant", help="term_live.PLANT, one of its test plants")
ap.add_argument("--formula-plant", help="formula.rs's plant by name (sa_solver.formula_plant), e.g. fm-hand-kept (608)")
ap.add_argument("--lra", action="store_true", help="lra_adapter's term work from Rust: lra_live.py. Needs --term")
ap.add_argument("--term-check", action="store_true", help="term_live.CHECK: run Python's own function at each answer from Rust and compare")
ap.add_argument("--term-out", help="term_live's counts, as JSON")
ap.add_argument("--discard", action="store_true", help="a planted refusal in each query's run: term_discard.py. Needs --term")
ap.add_argument("--budget", type=int, help="the engine's discovery budget for every query, as the matrix's low budgets")
ap.add_argument("--no-rollback", action="store_true", help="plant: with --discard, skip the rollback")
ap.add_argument("--full", action="store_true", help="with --term: also session_live and knowledge_live, as live.py installs them, "
                "so the engine's memos and the process memos are the Rust-native ones and --discard checks those")
ap.add_argument("--first", type=int, help="only the workload's first N queries (a kept test's short run)")
a = ap.parse_args()
if a.so:
    sys.path.insert(0, a.so)
    import sa_solver  # before backend, whose own path entry holds the unmutated build; a mutant not loaded is a void control
    if os.path.dirname(os.path.abspath(sa_solver.__file__)) != os.path.abspath(a.so):
        sys.exit(f"--so {a.so}: loaded {sa_solver.__file__} instead")
    print("so", hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest(), file=sys.stderr)

from evalbench.common import workload  # noqa: E402
from harness.state import reset_module_state  # noqa: E402
from satassume import engine as E, sympy_api  # noqa: E402
from satassume.sat.solver import Solver as PySolver  # noqa: E402
import satassume.theories.euf.euf as euf_mod  # noqa: E402
import satassume.theories.euf.euf_adapter as adapter_mod  # noqa: E402

import state as T  # noqa: E402

if a.mode == "rust":
    import backend
    backend.install()
    dump = T.with_euf(backend.RustSolver.dump, backend.RustSolver.theories)
    Base = backend.EUFTheory
else:
    dump = T.with_euf(T.dump_py, PySolver.theories)
    Base = euf_mod.EUFTheory

counts = collections.Counter()
if a.counts:
    if a.mode != "rust":
        sys.exit("--counts counts crossings into the crate: rust only")
    METHODS = ["term", "value", "find", "equal", "explain", "register_atom", "assert_lit", "check", "propagate",
               "push_level", "pop_level"]

    def wrap(name):
        inner = getattr(Base, name)

        def f(self, *args, **kw):
            counts[name] += 1
            return inner(self, *args, **kw)
        f.__name__ = name
        return f

    class Counting(Base):
        def __init__(self, *args, **kw):
            counts["theories made"] += 1
            super().__init__(*args, **kw)

        rep = property(lambda self: (counts.update(["rep read"]), Base.rep.__get__(self))[1])
        members = property(lambda self: (counts.update(["members read"]), Base.members.__get__(self))[1])

        @property
        def on_merge(self):
            return Base.on_merge.__get__(self)

        @on_merge.setter
        def on_merge(self, f):
            def g(ra, rb):
                counts["on_merge"] += 1
                return f(ra, rb)
            Base.on_merge.__set__(self, None if f is None else g)

    for m in METHODS:
        setattr(Counting, m, wrap(m))
    euf_mod.EUFTheory = adapter_mod.EUFTheory = Counting

if a.wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
elif a.wl == "lra":
    import lra_wl
    pairs = lra_wl.queries()
else:
    pairs = workload(a.wl)
if a.first is not None:
    pairs = pairs[:a.first]
if a.handlers:
    import handler_count
    handler_count.install(a.handlers)
TD = None
if a.term != "py":
    import term_live
    term_live.install(keys=a.term == "keys", terms=a.term == "terms")
    term_live.PLANT[0] = a.term_plant
    term_live.CHECK[0] = a.term_check
    term_live.PLANT_NO_ROLLBACK[0] = a.no_rollback
    if a.lra:
        import lra_live
        lra_live.install()
    if a.full:
        import session_live
        session_live.from_env()
        import knowledge_live
        knowledge_live.from_env()
    if a.discard:
        import term_discard as TD
        TD.install()
    if a.formula_plant:
        import sa_solver
        sa_solver.formula_plant(a.formula_plant)
sessions = []
#: Sessions of refused runs, dropped at the rollback: the digests are of the run that answered. Discarded + Python's was checked
#: on all 298 refused `lra` queries before this went in (port-4d.md).
discarded = [0]


def _drop_discarded():
    discarded[0] += len(sessions)
    sessions.clear()


_init = E.Session.__init__


def init(self, *args, **kw):
    _init(self, *args, **kw)
    sessions.append(self)


E.Session.__init__ = init


def digest(s):
    return hashlib.blake2b(repr(sorted(dump(s.solver).items())).encode(), digest_size=8).hexdigest()


with open(a.out, "w") as fh:
    for i, (p, q) in enumerate(pairs):
        if a.handlers:
            handler_count.where = i
        if TD:      # counts the calls at each site, then puts back everything but SymPy's caches
            n_const = len(TD.constfield._CONSTANTS), len(TD.constfield._BY_KEY)
            reset_module_state(sympy_cache=False)
            sympy_api.set_default_engine(E.Engine() if a.budget is None else E.Engine(discovery_budget=a.budget))
            TD.count_pass()
            try:
                sympy_api.ask(p, q)
            except Exception:
                pass
            del TD.constfield._CONSTANTS[n_const[0]:]
            while len(TD.constfield._BY_KEY) > n_const[1]:
                TD.constfield._BY_KEY.popitem()
            TD.arm(i)
            # A refusal of the run's own, before the plant's call, leaves it armed for the second run: that one must not refuse.
            term_live.AFTER_ROLLBACK[0] = lambda: (TD.check(), sessions.clear(), TD._arm.__setitem__(0, None))
        if a.term != "py" and not TD:
            term_live.AFTER_ROLLBACK[0] = _drop_discarded
        reset_module_state(sympy_cache=False)
        sympy_api.set_default_engine(E.Engine() if a.budget is None else E.Engine(discovery_budget=a.budget))
        sessions.clear()
        try:
            r = repr(sympy_api.ask(p, q))
        except Exception as e:  # the type and text are the answer
            r = f"{type(e).__name__}: {e}"
        fh.write(f"{i}\t{r}\t{','.join(digest(s) for s in sessions)}\n")
if a.term_out:
    import term_live
    with open(a.term_out, "w") as fh:
        out = dict(term=term_live.counts(), refusals=term_live.REFUSALS, discarded_sessions=discarded[0])
        if a.lra:
            out.update(lra=lra_live.counts(), check_bad=lra_live.CHECK_BAD[:50], scaffold_bad=lra_live.SCAFFOLD_BAD[:20])
        fh.write(TD.report() if TD else json.dumps(out, indent=0, sort_keys=True, default=repr))
if a.counts:
    json.dump(dict(counts, queries=len(pairs)), open(a.counts, "w"), indent=1, sort_keys=True)
