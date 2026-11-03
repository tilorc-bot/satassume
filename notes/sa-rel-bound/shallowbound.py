"""Lower bound on a hand-written clone of a relation session: time a shallow
copy of every mutable container and object reachable from the post-build
session (SymPy objects, P atoms, the engine shared), i.e. the copies any
exact clone must make, without the Python code that would wire them up."""
import sys, collections, pickle, time, types, weakref
sys.argv = ["x", "none"]
exec(open(__file__.rsplit("/", 1)[0] + "/clonebound.py").read().split("fb = E.Engine._build_context")[0])
clock = time.perf_counter
def reach(s):
    m = {}; register_proxies(s); dup(s, m)
    return [x for x in m.values()]   # the copies; same shapes as the originals
fb = E.Engine._build_context
seenk = set(); acc = collections.Counter()
def build(self, assumptions, proposition=None):
    key = (assumptions, E.theory_scope(assumptions, proposition, self._extensions))
    rep = key in seenk; seenk.add(key)
    t = clock(); r = fb(self, assumptions, proposition); dt = clock() - t
    if r[0].relations is not None:
        objs = reach(r[0])
        lists = [o for o in objs if type(o) is list]; dicts = [o for o in objs if type(o) is dict]
        sets = [o for o in objs if type(o) is set]; other = [o for o in objs if type(o) not in (list, dict, set, tuple, frozenset)]
        t = clock()
        for o in lists: o[:]
        for o in dicts: o.copy()
        for o in sets: o.copy()
        for o in other:
            d = getattr(o, "__dict__", None)
            if d is not None: d.copy()
        c = clock() - t
        acc["n"] += 1; acc["copy"] += c; acc["build"] += dt
        acc["containers"] += len(objs); acc["elements"] += sum(map(len, lists + dicts + sets))
        if rep: acc["rep_copy"] += c; acc["rep_build"] += dt; acc["nrep"] += 1
    return r
E.Engine._build_context = build
stream = pickle.load(open("/home/tilo/provable/data/stream.pkl", "rb"))
seen, uniq = set(), []
for p, a, r in stream:
    if (p, a) not in seen: seen.add((p, a)); uniq.append((p, a))
for p, a in uniq:
    try: ask(p, a)
    except ValueError: pass
n = acc["n"]
print({k: round(v, 3) for k, v in acc.items()})
print(f"per rel build: build {1e3*acc['build']/n:.3f} ms, shallow copies {1e3*acc['copy']/n:.3f} ms, containers {acc['containers']/n:.0f}, elements {acc['elements']/n:.0f}")
print(f"per repeat rel build: build {1e3*acc['rep_build']/acc['nrep']:.3f} ms, shallow copies {1e3*acc['rep_copy']/acc['nrep']:.3f} ms")
