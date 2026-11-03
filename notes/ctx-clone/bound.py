"""Copy vs build per context session on the unique stream.
mode 'build': plain, times every build (first/repeat, rel/norel).
mode 'clone': first build of a (set, scope) stores a pristine copy, repeats get a copy of it.
Writes answers to ans-<mode>.json next to this file."""
import pickle, sys, time, collections, json
from satassume import engine as E
from satassume.state.clone import clone
from satassume.sympy_api import ask
sys.path.insert(0, __file__.rsplit('/',1)[0]); import pk
clock = time.perf_counter
mode = sys.argv[1]
fb = E.Engine._build_context
store = {}; acc = collections.Counter()
def build(self, assumptions, proposition=None):
    key = (assumptions, E.theory_scope(assumptions, proposition, self._extensions))
    c = store.get(key)

    if c is not None and mode != "build":
        k = "rel" if c[0].relations is not None else "norel"
        t = clock(); r = clone(c, {id(self): self}) if mode == 'clone' else pk.loads(*c[2]); dt = clock() - t
        acc["copy-" + k] += dt; acc["ncopy-" + k] += 1
        return r
    t = clock(); r = fb(self, assumptions, proposition); dt = clock() - t
    k = ("rep-" if key in store else "first-") + ("rel" if r[0].relations is not None else "norel")
    acc[k] += dt; acc["n" + k] += 1
    if key not in store:
        t = clock(); store[key] = clone(r, {id(self): self}) if mode == "clone" else (r[0], None, pk.dumps(r, [self])) if mode == "pickle" else (None,); acc["store"] += clock() - t
    return r
E.Engine._build_context = build
stream = pickle.load(open("/home/tilo/provable/data/stream.pkl", "rb"))
seen, uniq = set(), []
for p, a, r in stream:
    if (p, a) not in seen: seen.add((p, a)); uniq.append((p, a))
out = []; t0 = clock()
for p, a in uniq:
    try: out.append(repr(ask(p, a)))
    except ValueError: out.append("error")
T = clock() - t0
print(mode, f"total {T:.3f}s")
for k in sorted(acc):
    if not k.startswith("n"): n = acc.get("n" + k, 0); print(f"  {k:12s} {acc[k]:.3f}s" + (f"  n={n} {1e3*acc[k]/n:.3f} ms each" if n else ""))
json.dump(out, open(f"{__file__.rsplit('/',1)[0]}/ans-{mode}.json", "w"))
