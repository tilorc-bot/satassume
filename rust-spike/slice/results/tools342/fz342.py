"""fz342.py KIND SEED MODE (sa-port-342, issue 323; the planner's wider net after [151]): one pass over a seeded fuzz
stream, each query's answer or its exception's type and message recorded. Run once with SLICE_WITNESS=0 and once with
=1; fzcmp342.py compares the two row by row.

KIND  harness         harness.generators.random_stream(SEED, 300, 6), the stream of `python -m harness fuzz` at
                      campaign.sh's QUERIES=300 and --sets 6, asked one after the other on one engine of the default preset
      harness-custom  the same with custom predicates and register/unregister events (campaign.sh's fuzz-custom)
      evalbench       evalbench.fuzz.queries(SEED), the slice's fuzz workload with SEED in place of 424242, default engine
MODE  py, or rust (the slice's backend as wit328.py installs it; evalbench only)
The check's calls and certified pairs are counted by wrapping witness.witnesses here, so a row set with the switch on
shows that the check ran. Prints one JSON line."""
import hashlib, json, os, re, sys
kind, seed, mode = sys.argv[1], int(sys.argv[2]), sys.argv[3]
S = os.environ.get("SLICE_DIR")
so = None
if mode != "py":
    sys.path.insert(0, S)
    import p_install
    p_install.install()
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
ADDR = re.compile(r"0x[0-9a-f]+")
rows = []
fires = [0, 0]
real_w = witness.witnesses


def witnesses(p, a, eng=None):
    r = real_w(p, a, eng)
    fires[0] += 1
    fires[1] += r is not None
    return r


witness.witnesses = witnesses


def one(p, a, eng=None):
    try:
        r = sympy_api.ask(p, a) if eng is None else sympy_api.ask(p, a, eng)
        rows.append([repr(r), "", ""])
    except Exception as e:
        rows.append(["raise", type(e).__name__, ADDR.sub("0xX", str(e))])


if kind == "evalbench":
    from evalbench.fuzz import queries
    for p, a in queries(seed):
        one(p, a)
else:
    from harness import registry as reg
    from harness.checker import Ask, apply_event
    from harness.generators import random_stream
    from harness.state import preset
    custom = kind == "harness-custom"
    items = random_stream(seed, 300, 6, relations=True, custom=custom, events=custom, max_depth=3, profile="base",
                          lazy=0.0)
    snap = reg.snapshot()
    eng = preset("default").make()
    try:
        for it in items:
            if isinstance(it, Ask):
                one(it.prop, it.assum, eng)
            else:
                apply_event(it)
                rows.append(["event", it.kind, it.reg_id])
    finally:
        reg.restore(snap)
print(json.dumps(dict(
    kind=kind, seed=seed, mode=mode, so=so, hashseed=os.environ.get("PYTHONHASHSEED"), witness=witness.ENABLED[0],
    tree=sympy_api.__file__, n=len(rows), fires=fires[0], certified=fires[1],
    digest=hashlib.sha256(json.dumps(rows).encode()).hexdigest()[:16], rows=rows)))
