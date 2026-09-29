"""Round 3, item B5: split of the cold pass by area after A2, by sampling.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/2026-09-perf-rounds/scripts/profile_split.py stream.pkl [INTERVAL_MS] [--json]
    python agent-reports/2026-09-perf-rounds/scripts/profile_split.py --sum run1.json run2.json ...

A CPU-time sampler (``signal.setitimer(ITIMER_PROF)``, default every 0.5
ms) records, for every sample, two things about the Python stack:

* the **phase**: where in the query the sample is, read off the outermost
  engine frames: ``sympy_api.ask`` without an engine frame (memo, formula
  translation, API), ``Engine.is_``/``_is_custom`` (context-free), the
  contextual session lookup/build (``_context_session``), and within
  ``Engine.ask`` the first attempt (``_literal``, propagation, escalation)
  or search in the reused session, or the cone (by the line ``Engine.ask``
  is executing: the cone block starts at ``s0 = s``), split the same way;
* the **area**: what the innermost frames are doing, first match from the
  innermost frame outward: the collector (a ``gc.callbacks`` flag), CDCL
  search internals, ``_propagate`` split by line into the rule-block hook
  and the watch-list loop, theories, rule-block registration, clause
  insertion, variable growth, template clause shifting (``_emit_pattern``),
  pattern bookkeeping (``_compile_patterns``), templates, variable
  blocks, writeback, formula compilation, other engine / solver code;
  time in SymPy's own code (hashing, equality, numbers, templates' SymPy
  calls) is labelled "SymPy under <the satassume area that called it>".
  The collector is under-counted by sampling (a signal is handled only
  after the collection returns): use ``gc_alloc.py`` for its share.

Sampling perturbs the pass by a few percent; shares are of the samples.
Answers are checked.  The unsampled pass time is printed first by a plain
run in the same process's absence: run ``tools/refine_replay.py`` for it.
"""
import gc, inspect, os, pickle, signal, sys, time
from collections import Counter

if sys.argv[1] == "--sum":
    import json
    A, P, PA, dts = Counter(), Counter(), Counter(), []
    for fn in sys.argv[2:]:
        d = json.loads(open(fn).read().strip().splitlines()[-1])
        A.update(d["A"]); P.update(d["P"]); PA.update(d["PA"]); dts.append(d["dt"])
        assert d["bad"] == 0
    n = sum(A.values())
    print(f"{len(dts)} sampled passes ({' '.join(f'{x:.2f}' for x in dts)} s), {n} samples")
    for title, C in (("area", A), ("phase", P)):
        print(f"-- by {title}")
        for k, v in C.most_common():
            print(f"  {k:48s} {v:6d} {100 * v / n:6.2f}%")
    print("-- phase x area (>= 0.3%)")
    for k, v in sorted(PA.items(), key=lambda kv: (kv[0].split("|")[0], -kv[1])):
        if v / n >= 0.003:
            p, a = k.split("|")
            print(f"  {p:36s} {a:44s} {100 * v / n:6.2f}%")
    sys.exit(0)
stream = pickle.load(open(sys.argv[1], "rb"))
interval = float(sys.argv[2]) / 1000 if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 0.0005
import satassume.sympy_api as api
from satassume import engine as E, solver as S
from satassume.engine import Engine, Session
from satassume.solver import Solver

api.default_engine()


def lines_of(fn, marker):
    src, start = inspect.getsourcelines(fn)
    for k, l in enumerate(src):
        if marker in l:
            return start + k
    raise SystemExit(f"marker {marker!r} not found in {fn.__name__}")


ASK_CONE = lines_of(Engine.ask, "s0 = s")
ASK_CONE_END = lines_of(Engine.ask, "return r")          # first 'return r' closes the cone block
PROP_HOOK = lines_of(Solver._propagate, "base = rb_base[p >> 1]")
PROP_WATCH = lines_of(Solver._propagate, "fl = p ^ 1")
PROP_END = lines_of(Solver._propagate, "self._qhead = qhead")
SOLVER_FILE = S.__file__
ENGINE_FILE = E.__file__
API_FILE = api.__file__
PKG = os.path.dirname(E.__file__)

SEARCH = {"_search", "_analyze", "_analyze_final", "_pick_branch", "_learn", "_backtrack",
          "_reduce_db", "_heap_pop", "_heap_down", "_heap_up", "_heap_insert", "_bump_var",
          "_bump_clause", "_rb_reason", "_witness_satisfies"}
INSERT = {"add_internal", "add_clauses", "add_clause", "_add_lits", "_attach_held", "add_pattern"}
GROW = {"_grow", "ensure_vars"}
BLOCK = {"register_block", "_rb_settle", "set_rule_block"}

in_gc = [False]
DETAIL = "--detail" in sys.argv


def gc_cb(phase, info):
    in_gc[0] = phase == "start"


def area_of(f):
    if in_gc[0]:
        return "collector"
    fr = f
    sym = ""
    while fr is not None and not fr.f_code.co_filename.startswith(PKG) and fr.f_code.co_filename != SOLVER_FILE:
        if "sympy" in fr.f_code.co_filename:
            sym = "SymPy under "
        fr = fr.f_back
    return sym + _area(fr)


def _area(fr):
    while fr is not None:
        co = fr.f_code
        fn, name = co.co_filename, co.co_name
        if fn == SOLVER_FILE:
            if name == "_propagate":
                ln = fr.f_lineno
                if PROP_HOOK <= ln < PROP_WATCH:
                    return "propagate: rule-block hook"
                if PROP_WATCH <= ln <= PROP_END:
                    return "propagate: watch lists"
                return "propagate: loop/setup"
            if name in ("_propagate_clauses",):
                return "propagate: watch lists"
            if name in ("_assume", "_assume_propagate", "implied", "propagate", "value", "root_trail"):
                return "propagate: assume/implied bookkeeping"
            if name in SEARCH:
                return "search internals (CDCL)"
            if name in ("_tpropagate", "_theory_sync", "_theory_imply", "_theory_conflict",
                        "_theory_check", "_theory_clause", "register_atom", "attach_theory"):
                return "theories (solver." + name + ")" if DETAIL else "theories"
            if name in BLOCK:
                return "rule-block registration"
            if name in INSERT:
                return "clause insertion (solver)"
            if name in GROW:
                return "variable growth (solver)"
            if name in ("_solve", "solve", "entails"):
                return "search internals (CDCL)"
            fr = fr.f_back
            continue
        if fn.startswith(PKG):
            base = os.path.basename(fn)
            if base in ("lra.py", "euf.py", "theory.py", "relations.py") or "theor" in base:
                return f"theories ({base}:{name})" if DETAIL else "theories"
            if fn == ENGINE_FILE:
                if name == "_emit_pattern":
                    return "template clauses: shift"
                if name in ("_compile_patterns", "_compile_pending", "want_of", "neighbourhood"):
                    return "template clauses: filter/slots/bookkeeping"
                if name == "writeback":
                    return "writeback"
                if name in ("_add_clauses",):
                    return "clause insertion (solver)"
                if name == "put" or name == "facts" or name == "get":
                    return "caches (DictCache, AnswerMemo)"
                return "engine: other (" + name + ")"
            if base == "compile.py":
                if name == "node_base":
                    return "variable blocks (VarTable)"
                return "formula compilation"
            if "templates" in fn:
                return "templates"
            if fn == API_FILE:
                return "API: formula/scope"
            return "satassume other (" + base + ":" + name + ")"
        fr = fr.f_back
    return "other"


def phase_of(f):
    names = []
    fr = f
    ask_line = None
    searching = False
    while fr is not None:
        co = fr.f_code
        if co.co_filename == SOLVER_FILE and co.co_name in ("entails", "_solve", "solve"):
            searching = True
        if co.co_filename == ENGINE_FILE or co.co_filename == API_FILE:
            names.append(co.co_name)
            if co.co_name == "ask" and co.co_filename == ENGINE_FILE and ask_line is None:
                ask_line = fr.f_lineno
        fr = fr.f_back
    names.reverse()         # outermost first
    if not names:
        return "outside"
    if "ask" not in names:
        return "outside"
    # outermost engine entry
    eng = [n for n in names if n in ("is_", "_is_custom")]
    if ask_line is None:
        if eng:
            return "context-free (is_)"
        return "API: memo/formula"
    # inside Engine.ask: the call directly under it
    k = len(names) - 1 - names[::-1].index("ask")
    sub = names[k + 1] if k + 1 < len(names) else "(ask itself)"
    cone = ASK_CONE <= ask_line <= ASK_CONE_END
    if sub in ("is_", "_is_custom"):
        return "context-free (is_) nested"
    if sub == "query_literal":
        sub = "query_literal/search" if searching else "query_literal/propagation"
    if cone:
        m = {"_fresh_session": "cone: session", "assume_formula": "cone: assumptions",
             "_literal": "cone: proposition nodes", "escalate": "cone: escalate",
             "query_literal/search": "cone: search", "query_literal/propagation": "cone: propagation",
             "_emit": "cone: swap"}
        return m.get(sub, "cone: " + sub)
    m = {"_context_session": "context session (lookup/build)", "_fresh_session": "session (no assumptions)",
         "_literal": "attempt: proposition nodes", "escalate": "attempt: escalate",
         "query_literal/propagation": "attempt: propagation",
         "query_literal/search": "search in the reused session"}
    return m.get(sub, "ask: " + sub)


A = Counter(); P = Counter(); PA = Counter()
qsearch = [False]


def handler(sig, frame):
    a = area_of(frame)
    p = phase_of(frame)
    A[a] += 1; P[p] += 1; PA[(p, a)] += 1


# query_literal: propagation vs search, as a phase refinement
orig_ql = Session.query_literal


def ql(self, lit, assumptions=(), search=True):
    return orig_ql(self, lit, assumptions, search)


gc.callbacks.append(gc_cb)
signal.signal(signal.SIGPROF, handler)
signal.setitimer(signal.ITIMER_PROF, interval, interval)
bad = 0
t0 = time.perf_counter()
for p, a, r in stream:
    try:
        got = api.ask(p, a)
    except ValueError:
        got = "err"
    if got is not r and got != "err":
        bad += 1
dt = time.perf_counter() - t0
signal.setitimer(signal.ITIMER_PROF, 0, 0)
n = sum(A.values())
import json
if "--json" in sys.argv:
    print(json.dumps({"dt": dt, "bad": bad, "A": A, "P": P, "PA": {"|".join(k): v for k, v in PA.items()}}))
    sys.exit(0)
print(f"sampled pass {dt:.3f}s, mismatches {bad}, {n} samples ({1000 * interval:.2f} ms)")
print("-- by area")
for k, v in A.most_common():
    print(f"  {k:48s} {v:6d} {100 * v / n:6.2f}%")
print("-- by phase")
for k, v in P.most_common():
    print(f"  {k:48s} {v:6d} {100 * v / n:6.2f}%")
print("-- phase x area (>= 0.3%)")
for (p, a), v in sorted(PA.items(), key=lambda kv: (kv[0][0], -kv[1])):
    if v / n >= 0.003:
        print(f"  {p:36s} {a:44s} {100 * v / n:6.2f}%")
