"""cnt364.py WL MODE OUT.json (sa-port-364, issue 323; tools356/prof356.py's loader): per query, how often each result
of satassume/knowledge/domain.py is COMPUTED and how often it is READ (planner ruling 364 (a)). Counts, not time.

WL: dev, fuzz (seed 424242), budget, wiring. MODE: py (the package alone, the default path) or rust (the slice's
backend; the environment picks the switches, as S1's rust-nat does).

Each function of domain.py is replaced by a counting wrapper in every module that holds it (the modules import the
names; Rust looks them up at call time, and convert.py's WalkCtx is built at the first query, after the swap).
A call is charged to its caller: the calling Python frame's file:function (for a call made from Rust that is the
Python frame that entered Rust), with calls from domain.py itself (recursion, helpers) kept apart as `inner:function`.

Results and what counts as computed / read:
  level   constructed_noncommutative(t). computed: every outer call. read: the calls through engine._construction_level
          (Python's engine.py:2044/:2090 and Rust's entry.rs:579 both go through it; the value goes straight into
          `_noncommutative_answer`). The table's level column has one exposer, TermTable.row (py.rs:349); its calls
          are counted by sys.monitoring and charged to the caller, and which index a caller reads is read from its
          source (term_live.py:490 scaffold: row[0], row[1]; term_history.py: row[4], row[:5]; term_shadow.py:167: the
          level, the only reader of index 5).
  nc      _noncommutative(e). computed: a call that finds no `_NONCOMM` row (the walk). read: every call (each caller
          branches on it). Rust's entry.rs reads the memo itself; those reads are not Python calls and are not seen
          here, its misses are (they call the function).
  nfalse  noncommutative_false(). computed: the first call of the process. read: every call.
  kept    kept_product(factors). computed and read: every call (the caller uses the product or the None).
  fixed   _fixed_noncommutative(t): a helper, by caller.
Prints one JSON line (the summary); OUT.json also holds the per-query rows.
"""
import collections, hashlib, json, os, sys
wl, mode, outp = sys.argv[1:4]
S = os.environ.get("SLICE_DIR")
so = None
if mode != "py":
    sys.path.insert(0, S)
    import p_install
    p_install.install()
from evalbench.common import workload
from satassume import sympy_api, witness
from satassume import engine as E
from satassume.knowledge import domain as D
if mode != "py":
    import sa_solver
    import backend
    import convert      # holds constructed_noncommutative; term_live.from_env() builds the WalkCtx from it, so swap first
NAMES = ["constructed_noncommutative", "_noncommutative", "_fixed_noncommutative", "noncommutative_false", "kept_product",
         "_nc_product_level", "_nc_sum_level", "_fixed_level", "_plain_undefined", "_swept_unary", "_holds_matrix",
         "_matrix_to_scalar", "_is_matrix", "_label", "_nonzero_number", "_nc_symbol"]
DFILE = D.__file__
cur = collections.Counter()          # this query's counts
callers = collections.Counter()      # (function, caller) over the pass
values = collections.Counter()       # (function, caller class, returned value) for level and nc
_gf = sys._getframe


def who(f):
    c = f.f_code
    fn = c.co_filename
    if fn == DFILE:
        return "inner:" + c.co_name
    p = fn.replace("\\", "/")
    if "/satassume/" in p:
        p = "sa/" + p.split("/satassume/", 1)[1]
    elif "/rust-spike/slice/" in p:
        p = "slice/" + p.rsplit("/", 1)[1]
    else:
        p = p.rsplit("/", 1)[-1]
    return "%s:%s" % (p, c.co_name)


def wrap(name, orig):
    memo = D._NONCOMM

    def w(*a, **k):
        c = who(_gf(1))
        callers[name, c] += 1
        kind = "inner" if c.startswith("inner:") else "outer"
        cur[name, kind] += 1
        if name == "_noncommutative" and memo.get(a[0]) is None:
            cur["nc_walk", kind] += 1
        r = orig(*a, **k)
        if name in ("constructed_noncommutative", "_noncommutative") and kind == "outer":
            values[name, c, int(r)] += 1
            if r:
                cur[name, "nonzero"] += 1
        return r
    w.__name__ = name
    w.__wrapped__ = orig
    return w


swapped = collections.Counter()


def swap_all():     # in a function: at module level the loop's own variables would be holders of the original too
    for name in NAMES:
        orig = getattr(D, name)
        w = wrap(name, orig)
        for mn, m in list(sys.modules.items()):
            d = getattr(m, "__dict__", None)
            if not isinstance(d, dict):
                continue
            for k, v in list(d.items()):
                if v is orig:
                    d[k] = w
                    swapped[name, mn] += 1


swap_all()
if mode != "py":
    backend.install_euf()
    import term_live
    term_live.from_env()
    import lra_live
    lra_live.from_env()
    import session_live
    session_live.from_env()
    import knowledge_live
    knowledge_live.from_env()
    backend.install()
    so = hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest()[:16]
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
elif wl in ("budget", "wiring"):
    import importlib
    if S not in sys.path:
        sys.path.append(S)
    pairs = importlib.import_module({"budget": "budget_wl", "wiring": "knowledge_wiring_wl"}[wl]).queries()
else:
    pairs = workload(wl)

_cl = E._construction_level


def construction_level(term):
    cur["level_read", who(_gf(1))] += 1
    return _cl(term)


E._construction_level = construction_level
_na = E._noncommutative_answer


def noncommutative_answer(level, pred):
    cur["answer", "py"] += 1
    return _na(level, pred)


E._noncommutative_answer = noncommutative_answer

# TermTable.row: the one reader of the table's level column (py.rs:349). A C-level method, so sys.monitoring's CALL.
mon = sys.monitoring
TOOL = 4
mon.use_tool_id(TOOL, "cnt364")


TT = sa_solver.TermTable if mode != "py" else None


def on_call(code, off, callable_, arg0):
    # a method call reaches here as the unbound descriptor with the instance as arg0; a bound one carries __self__
    if getattr(callable_, "__name__", None) == "row" and TT is not None and (
            getattr(callable_, "__objclass__", None) is TT or type(getattr(callable_, "__self__", None)) is TT):
        cur["row_call", who(_gf(1))] += 1


mon.register_callback(TOOL, mon.events.CALL, on_call)
mon.set_events(TOOL, mon.events.CALL)

ans = [None] * len(pairs)
rows = []
ask = sympy_api.ask
for i, (p, a) in enumerate(pairs):
    cur.clear()
    try:
        r = ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:
        r = "raise " + type(e).__name__
    ans[i] = r
    rows.append({"%s|%s" % k: v for k, v in cur.items()})
# FALSE ZEROS: each read counter is shown to fire on a planted read, after the pass (not in the rows): a query on a
# non-commutative symbol straight at the engine (past sympy_api's scope check) reads the level through
# `_construction_level`, and one `TermTable.row` call on a table converted here reads the table's level column.
cur.clear()
pass_callers, pass_values = collections.Counter(callers), collections.Counter(values)   # the pass's own, before the self-check
selfcheck = {}
try:
    from sympy import Symbol, Q
    from satassume.engine import Engine
    eng = Engine()
    selfcheck["is_(A, commutative)"] = repr(eng.is_(Symbol("A", commutative=False), "commutative"))
    selfcheck["level_read"] = sum(v for k, v in cur.items() if k[0] == "level_read")
    if mode != "py":
        c = convert.convert(Q.positive(Symbol("x")), Q.real(Symbol("x")), eng)
        if isinstance(c, convert.Kept):
            selfcheck["kept"] = c.reason
        else:
            selfcheck["row"] = repr(sa_solver.TermTable(c.tables).row(0))[:80]
        selfcheck["row_call"] = sum(v for k, v in cur.items() if k[0] == "row_call")
except Exception as e:
    selfcheck["raise"] = "%s: %s" % (type(e).__name__, e)
mon.set_events(TOOL, 0)
mon.free_tool_id(TOOL)

keys = sorted({k for r in rows for k in r})
tot = {k: sum(r.get(k, 0) for r in rows) for k in keys}
nq = {k: sum(1 for r in rows if r.get(k, 0)) for k in keys}
out = dict(
    wl=wl, mode=mode, so=so, n=len(pairs), digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16],
    convert=os.environ.get("SLICE_CONVERT", "py"), frames=os.environ.get("SLICE_TERM_FRAMES", "py"),
    witness=witness.ENABLED[0], term_shadow="term_shadow" in sys.modules, swapped=sorted("%s in %s" % k for k in swapped),
    total=tot, queries_with=nq, selfcheck=selfcheck,
    callers={"%s <- %s" % k: v for k, v in sorted(pass_callers.items(), key=lambda x: -x[1])},
    values={"%s <- %s = %d" % k: v for k, v in sorted(pass_values.items(), key=lambda x: -x[1])},
    walk_counts=(sa_solver.walk_counts() if so and hasattr(sa_solver, "walk_counts") else None))
json.dump(dict(out, rows=rows), open(outp, "w"))
print(json.dumps(out))
