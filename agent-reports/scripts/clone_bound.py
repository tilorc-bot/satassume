"""Item 2.2: the bound for a base-session clone.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy:tools python agent-reports/scripts/clone_bound.py \
        ~/.cache/satassume/stream.pkl

A cone rebuild (and a rebuild of an evicted context session) starts from
``Engine._fresh_session()`` and ``Session.assume_formula(assumptions)``:
grounding the assumption formula through SymPy, creating its nodes, their
rule blocks and templates, registering relation atoms with the theories.
That is the part a clone of a per-assumption-set base session would
replace; the query's own cone (``_literal``, ``escalate``, the search) is
per cone and stays.  The script times both parts per query (stage
tracking from ``tools/query_log.py`` tells cone from context builds),
and estimates the clone's own cost by running a prototype clone of the
solver on the base state (all solver fields copied, clauses and watches
remapped; theories are not cloned, sessions with one are counted) plus
shallow copies of every dict/list/set attribute of the ``Session``, its
``VarTable`` and its ``Relations`` and adapters, at the end of
``assume_formula``.  Bound = (time replaced - clone cost) / cold pass.
"""
import pickle, sys, time
from collections import Counter

stream = pickle.load(open(sys.argv[1], "rb"))
import query_log
from satassume.engine import Engine, Session
from satassume.solver import Solver, Clause

ctx = query_log.ctx
T = Counter(); N = Counter()
per_query = {}


def clone_solver(s):
    """Prototype of Solver.clone() at decision level 0 (no theories)."""
    c = Solver.__new__(Solver)
    d = c.__dict__
    d.update(s.__dict__)
    for name in ("_val", "_level", "_act", "_polarity", "_hpos", "_seen", "_heap",
                 "_trail", "_trail_lim", "_assumptions", "_conflict", "_tprops", "_theories"):
        d[name] = list(s.__dict__[name])
    m = {}
    new_clauses = []
    for cl in s._clauses:
        n = list(cl); m[id(cl)] = n; new_clauses.append(n)
    new_learnts = []
    for cl in s._learnts:
        n = Clause(cl); n.learnt = cl.learnt; n.act = cl.act; m[id(cl)] = n; new_learnts.append(n)
    d["_clauses"] = new_clauses; d["_learnts"] = new_learnts
    d["_watches"] = [[m.get(id(cl)) or (m.setdefault(id(cl), Clause(cl))) for cl in ws] for ws in s._watches]
    d["_reason"] = [None if r is None else m.get(id(r), r) for r in s._reason]
    d["_tmap"] = {k: list(v) for k, v in s._tmap.items()}
    d["_model"] = None; d["_witness"] = None; d["_acache"] = None; d["_held"] = None; d["_tmodels"] = None
    return c


def copy_containers(obj, seen):
    """Shallow-copy every dict/list/set/deque attribute of obj, recursing
    into attribute objects of satassume's own classes (one level of
    adapters/theories); returns the number of items copied."""
    n = 0
    if id(obj) in seen or obj is None:
        return 0
    seen.add(id(obj))
    for k, v in vars(obj).items():
        if isinstance(v, dict):
            n += len(dict(v))
        elif isinstance(v, (list, set)):
            n += len(type(v)(v))
        elif hasattr(v, "__dict__") and type(v).__module__.startswith("satassume") and k not in ("engine", "solver"):
            n += copy_containers(v, seen)
    return n


orig_fresh = Engine._fresh_session
orig_af = Session.assume_formula


def _fresh_session(self):
    t0 = time.perf_counter()
    s = orig_fresh(self)
    per_query.setdefault(ctx.i, Counter())["fresh_ms"] += 1000 * (time.perf_counter() - t0)
    return s


def assume_formula(self, f):
    t0 = time.perf_counter()
    r = orig_af(self, f)
    dt = 1000 * (time.perf_counter() - t0)
    q = per_query.setdefault(ctx.i, Counter())
    q["assume_ms"] += dt
    q["builds"] += 1
    q["kind"] = "cone" if "cone" in ctx.path else (ctx.session_new or "context_free")
    s = self.solver
    q["theory"] += bool(s._theories)
    q["nvars"] += s._nvars; q["nclauses"] += len(s._clauses)
    # clone cost estimate on this base state
    t0 = time.perf_counter()
    clone_solver(s)
    q["clone_solver_ms"] += 1000 * (time.perf_counter() - t0)
    t0 = time.perf_counter()
    q["copied_items"] += copy_containers(self, set())
    q["clone_engine_ms"] += 1000 * (time.perf_counter() - t0)
    return r


Engine._fresh_session = _fresh_session
Session.assume_formula = assume_formula
dt, bad = query_log.run(stream, "/dev/null", False)
print(f"instrumented pass {dt:.2f} s, answers differ: {len(bad)}")


COLD_MS = float(sys.argv[2]) if len(sys.argv) > 2 else 3590.0    # cold pass on this HEAD, local
agg = {}
for i, q in per_query.items():
    if not q["builds"]:
        continue
    a = agg.setdefault(q["kind"], Counter())
    for k, v in q.items():
        if k != "kind":
            a[k] += v
    a["queries"] += 1
print(f"{'kind':14} {'queries':>7} {'builds':>6} {'theory':>6} {'fresh+assume ms':>16} {'clone est ms':>13} "
      f"{'net ms':>8} {'share of cold':>13} {'vars':>6} {'clauses':>8}")
tot_net = 0.0
for kind, a in sorted(agg.items(), key=lambda kv: -kv[1]["assume_ms"]):
    replaced = a["fresh_ms"] + a["assume_ms"]
    clone = a["clone_solver_ms"] + a["clone_engine_ms"]
    net = replaced - clone
    if kind in ("cone", "evicted"):
        tot_net += net
    print(f"{kind:14} {a['queries']:7} {a['builds']:6} {a['theory']:6} {replaced:16.1f} {clone:13.1f} "
          f"{net:8.1f} {100 * net / COLD_MS:12.1f}% {a['nvars'] / a['builds']:6.0f} {a['nclauses'] / a['builds']:8.0f}")
print(f"\nbound (cone + evicted builds, base build minus clone estimate): {tot_net:.0f} ms = "
      f"{100 * tot_net / COLD_MS:.1f}% of the {COLD_MS:.0f} ms cold pass")
print("clone estimate = prototype Solver clone (no theory clone) + shallow copies of the Session/VarTable/Relations containers")
