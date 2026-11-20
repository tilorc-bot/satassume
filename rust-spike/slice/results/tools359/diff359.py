"""diff359.py WL OUT.jsonl (sa-port-359, issue 323; tools352/diff352.py's loader): one pass of a workload on the slice's
backend with the walker SLICE_CONVERT names, one line per query for cmp359.py, which compares Python's walker
(SLICE_CONVERT=py) with SLICE_CONVERT=rust.

WL: fuzzN (evalbench.fuzz, seed N), or a name live.py `load` takes (the gate's 20).
Per query: the answer; the default engine's Engine.stats and last_budget_limited after it; `cv`: every call of
`convert.convert` the query made (nested ones too), in order, as ["kept", reason, detail] or ["conv", counts, raised,
terms], where counts (key order kept) and raised are read when the outermost query ENDS, so they hold the reads the
query really asked for and no forced read. `convert.convert` is wrapped to remember its result: the entry calls it by
name and WalkEntry does not compare it (convert._ORIGINAL), so no item goes off; the last line shows cv:patched.
Last line: the walker, the .so, sa_solver.walk_counts() over the pass (740-746), term_live.counts() and RAISED, the
answers' digest, and the walkers' lifetime (ruling (1) for sa-port-359, R1/H2): `walks` = the objects behind each
conversion's `tables['reads']` (sa_solver.Walk, or Python's walker); `weakrefs` = weak references to them found when the
query ended, before this file took its own; `alive` = those still alive once the query's results were dropped (no gc
run), `alive_gc` = after one gc.collect() at the end of the pass. Environment: SLICE_DIR, SLICE_CONVERT, SLICE_TERM_FRAMES, SLICE_WITNESS as wanted."""
import gc, hashlib, json, os, sys, time, weakref
wl, out_path = sys.argv[1:3]
S = os.environ["SLICE_DIR"]
sys.path.insert(0, S)
import p_install
p_install.install()
from satassume import sympy_api
import sa_solver
import backend
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
import convert, live
so = hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest()[:16]
if wl.startswith("fuzz") and wl != "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(int(wl[4:]))
else:
    pairs = live.load(wl)
seen = []
real = convert.convert


def convert_(*a, **k):
    r = real(*a, **k)
    seen.append(r)
    return r


convert.convert = convert_


def row(r):
    if isinstance(r, convert.Kept):
        return ["kept", r.reason, str(r.detail)[:200]]
    return ["conv", [[k, v] for k, v in r.counts.items()], [list(map(str, x)) for x in r.raised], len(r.ids)]


life = dict(walks=0, weakrefs=0, alive=0, types=set())
refs = []


def lifetime():
    """Called when a query has ended, before its results are dropped."""
    for r in seen:
        w = None if isinstance(r, convert.Kept) else getattr(r.tables['reads'], '__self__', None)
        if w is not None:
            life['walks'] += 1
            life['types'].add(type(w).__module__ + '.' + type(w).__name__)
            life['weakrefs'] += weakref.getweakrefcount(w)
            refs.append(weakref.ref(w))
    del w, r


before = sa_solver.walk_counts()
ans = []
eng = sympy_api.default_engine()
ask = sympy_api.ask
t0 = time.perf_counter()
with open(out_path, "w") as f:
    for i, (p, a) in enumerate(pairs):
        try:
            r = p() if type(a) is str and a == live.CALL else ask(p, a)
            if r is not None and r is not True and r is not False:
                r = "non-bool " + repr(r)
        except ValueError:
            r = "ValueError"
        except Exception as e:
            r = "raise " + type(e).__name__
        ans.append(r)
        f.write(json.dumps(dict(q=i, a=r, stats=sorted(eng.stats.items()), bl=eng.last_budget_limited, cv=[row(x) for x in seen])) + "\n")
        if seen:
            lifetime()
        del seen[:]
        life['alive'] += sum(x() is not None for x in refs)
        del refs[:len(refs) if not any(x() is not None for x in refs) else 0]
    gc.collect()
    life.update(alive_gc=sum(x() is not None for x in refs), types=sorted(life['types']))
    w = convert.WALK[0]
    f.write(json.dumps(dict(
        total=1, wl=wl, so=so, n=len(pairs), s=round(time.perf_counter() - t0, 3), walk="py" if w is None else ",".join(w.ITEMS),
        env={k: os.environ.get(k) for k in ("SLICE_CONVERT", "SLICE_TERM_FRAMES", "SLICE_WITNESS", "SLICE_WITNESS_RUST", "SLICE_CONVERT_PLANT")},
        cv={k: v - before[k] for k, v in sa_solver.walk_counts().items()}, term=term_live.counts(), term_raised=[list(map(str, x)) for x in term_live.RAISED],
        life=life, digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16])) + "\n")
