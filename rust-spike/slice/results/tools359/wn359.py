"""wn359.py WL MODE (sa-port-359, issue 323; tools354/wn354.py plus `cv`: sa_solver.walk_counts(), 740-746, and the walker's items): one pass of a workload as an arm of time354.sh runs it (qt342.py's
installs, kind time, nothing wrapped), then what that process read: whether witness.NATIVE holds the native entry, the
native counters 706-713 (witness_live.counts()), the default engine's witness_certified and queries, the digest of
the answers and the .so. Shows that the nat arm ran witness.rs (wn:compile is not 0) and the other arms did not.
A count, not a time."""
import hashlib, importlib, json, os, sys
wl, mode = sys.argv[1:3]
S = os.environ["SLICE_DIR"]
so = None
if mode != "py":
    sys.path.insert(0, S)
    import p_install
    p_install.install()
from evalbench.common import workload
from satassume import sympy_api, witness
if mode != "py":
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
    so = hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest()[:16]
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
elif wl in ("budget", "wiring"):
    if S not in sys.path:
        sys.path.append(S)
    pairs = importlib.import_module({"budget": "budget_wl", "wiring": "knowledge_wiring_wl"}[wl]).queries()
else:
    pairs = workload(wl)
ans = []
for p, a in pairs:
    try:
        r = sympy_api.ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:
        r = "raise " + type(e).__name__
    ans.append(r)
st = sympy_api.default_engine().stats
wn = sys.modules.get("witness_live")
native = getattr(witness, "NATIVE", [None])[0]
print(json.dumps(dict(wl=wl, mode=mode, n=len(pairs), so=so, digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16],
                      enabled=witness.ENABLED[0], cap=witness.CAP[0], work=getattr(witness, "WORK", [None])[0],
                      native=None if native is None else native.__module__ + "." + native.__name__,
                      env=os.environ.get("SLICE_WITNESS_RUST"), counts=wn.counts() if wn is not None else None,
                      cv=sa_solver.walk_counts() if mode != 'py' and hasattr(sa_solver, 'walk_counts') else None,
                      walk=None if 'convert' not in sys.modules else ('py' if sys.modules['convert'].WALK[0] is None else ','.join(sys.modules['convert'].WALK[0].ITEMS)),
                      certified=st.get("witness_certified"), queries=st.get("queries"))))
