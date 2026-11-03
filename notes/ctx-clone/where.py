"""Where the copy goes: per top-level owner.attribute of a relation session,
objects copied and time to clone that attribute alone (memo seeded with the engine)."""
import pickle, sys, time, collections
from satassume import engine as E
from satassume.state.clone import clone
from satassume.sympy_api import ask
clock = time.perf_counter
fb = E.Engine._build_context
acc = collections.Counter(); cnt = collections.Counter(); n = [0]
def build(self, assumptions, proposition=None):
    r = fb(self, assumptions, proposition); s = r[0]
    if s.relations is not None:
        n[0] += 1
        owners = {"session": s, "solver": s.solver, "table": s.table, "relations": s.relations}
        for t in s.solver._theories: owners[type(t).__name__] = t
        for on, o in owners.items():
            for k, v in vars(o).items() if hasattr(o, "__dict__") else ():
                if on == "session" and k in ("solver", "table", "relations"): continue
                if on == "solver" and k == "_theories": continue
                memo = {id(self): self, **{id(x): x for x in owners.values()}}
                m0 = len(memo); t = clock(); clone(v, memo); acc[f"{on}.{k}"] += clock() - t; cnt[f"{on}.{k}"] += len(memo) - m0
    return r
E.Engine._build_context = build
stream = pickle.load(open("/home/tilo/provable/data/stream.pkl", "rb"))
seen, uniq = set(), []
for p, a, r in stream:
    if (p, a) not in seen: seen.add((p, a)); uniq.append((p, a))
for p, a in uniq:
    try: ask(p, a)
    except ValueError: pass
tot = sum(acc.values())
print(f"rel sessions {n[0]}, sum of per-attribute clones {1e3*tot/n[0]:.3f} ms/session")
for k, v in acc.most_common(25): print(f"  {k:32s} {1e3*v/n[0]:.4f} ms  {cnt[k]/n[0]:7.1f} objs")
