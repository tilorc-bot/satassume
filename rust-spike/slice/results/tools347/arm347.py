"""arm347.py WL (sa-port-347, issue 323): what an arm of time347.sh sets, as satassume.witness read it, and what one
py pass of the workload under it counts: the default engine's witness_certified and budget_limited, and the plants'
fired counter. Shows that the cf and w8400 arms are not the on32 arm (a count, not a time)."""
import importlib, json, os, sys
from satassume import sympy_api, witness
wl = sys.argv[1]
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
elif wl in ("budget", "wiring"):
    sys.path.append(os.environ["SLICE_DIR"])
    pairs = importlib.import_module({"budget": "budget_wl", "wiring": "knowledge_wiring_wl"}[wl]).queries()
else:
    from evalbench.common import workload
    pairs = workload(wl)
for p, a in pairs:
    try:
        sympy_api.ask(p, a)
    except Exception:
        pass
st = sympy_api.default_engine().stats
print(json.dumps(dict(wl=wl, enabled=witness.ENABLED[0], cap=witness.CAP[0], work=getattr(witness, "WORK", [None])[0],
                      plant=str(witness.PLANT[0]), fired=witness.FIRED[0], certified=st["witness_certified"],
                      budget_limited=st["budget_limited"], queries=st["queries"], n=len(pairs))))
