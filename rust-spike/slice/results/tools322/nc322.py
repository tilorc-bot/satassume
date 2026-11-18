"""nc322.py WL OUT.jsonl [BRANCH_BUDGET] (sa-port-322, issue 323): one cold pass of a workload in recorded order, installs as
sa-port-317's s1/tools/qt195.py does in rust mode (same order), per-query seconds, answer and, on the count build
(mkpatch322.py), the query's event tokens (sa_solver.nc322_take). Line 1 of OUT is the header (digest as qt195's), then one
line per query. With BRANCH_BUDGET the pass runs with satassume.theories.lra.lra.BRANCH_BUDGET set to it (lra_backend.py
reads the module global at every check): answers recorded, not adopted. After the pass, outside the timer: for each None
answer sympy_api.out_of_scope's category, and for every query the index of the first equal (p, A) (the answer memo).
Lives outside the package: no satassume or crate source changes."""
import gc, hashlib, json, os, sys, time
wl, out = sys.argv[1:3]
bb = int(sys.argv[3]) if len(sys.argv) > 3 else None
sys.path.insert(0, os.environ["SLICE_DIR"])
import p_install
p_install.install()
from evalbench.common import workload
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
import satassume.theories.lra.lra as L
import lra_backend
assert lra_backend._lra is L
base_bb = L.BRANCH_BUDGET
if bb is not None:
    L.BRANCH_BUDGET = bb
so = hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest()[:16]
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
elif wl == "plant":
    pairs = None
else:
    pairs = workload(wl)
take = getattr(sa_solver, "nc322_take", None)
ask = sympy_api.ask
pc = time.perf_counter


def run(pairs):
    per = [0.0] * len(pairs); ans = [None] * len(pairs); evs = [""] * len(pairs)
    gc.collect(); gc.freeze()
    if take:
        take()
    t0 = pc()
    for i, (p, a) in enumerate(pairs):
        t = pc()
        try:
            r = ask(p, a)
            if r is not None and r is not True and r is not False:
                r = "non-bool " + repr(r)
        except ValueError:
            r = "ValueError"
        except Exception as e:
            r = "raise " + type(e).__name__
        per[i] = pc() - t
        ans[i] = r
        if take:
            evs[i] = take()
    return per, ans, evs, pc() - t0


if __name__ == "__main__" and pairs is not None:
    per, ans, evs, total = run(pairs)
    head = dict(wl=wl, digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16], s=total, so=so, n=len(pairs),
                bb=L.BRANCH_BUDGET, base_bb=base_bb, events=bool(take), convert=os.environ.get("SLICE_CONVERT"),
                frames=os.environ.get("SLICE_TERM_FRAMES"), lra=lra_live.counts(), refusals=len(term_live.REFUSALS),
                session={k: v for k, v in session_live.counts().items() if k.startswith(("ctx:", "th:")) and v})
    first = {}
    with open(out, "w") as fh:
        fh.write(json.dumps(head) + "\n")
        for i, (p, a) in enumerate(pairs):
            row = dict(i=i, ans=ans[i], t=per[i], ev=evs[i])
            try:
                row["dup"] = first.setdefault((p, a), i)
            except TypeError:
                row["dup"] = -1
            if ans[i] is None:
                try:
                    row["oos"] = sympy_api.out_of_scope(p, a)
                except Exception as e:
                    row["oos"] = "raise " + type(e).__name__
                row["q"] = str(p)[:300]; row["a"] = str(a)[:300]
            fh.write(json.dumps(row) + "\n")
    print(json.dumps({k: head[k] for k in ("wl", "digest", "s", "so", "n", "bb", "events")}))
