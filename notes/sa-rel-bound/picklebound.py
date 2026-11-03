import pickle, sys, time, types, weakref, collections, json, io
from fractions import Fraction
from satassume import engine as E
from satassume.sat.formula import P
from satassume.sympy_api import ask
from sympy import Basic
clock = time.perf_counter
mode = sys.argv[1]
SHARED = []          # objects passed by reference (immutable or the engine)
SHARED_ID = {}
def _get(i): return SHARED[i]
def ref(x):
    i = SHARED_ID.get(id(x))
    if i is None:
        i = SHARED_ID[id(x)] = len(SHARED); SHARED.append(x)
    return _get, (i,)
class Pk(pickle.Pickler):
    def reducer_override(self, x):
        if isinstance(x, (Basic, P, E.Engine, Fraction)):
            return ref(x)
        if type(x) is weakref.ProxyType:
            return weakref.proxy, (PROXY[id(x)],)
        return NotImplemented
PROXY = {}
def dump(s, lits):
    if s.relations is not None:
        PROXY[id(s.relations.session)] = s
    b = io.BytesIO(); Pk(b, protocol=5).dump((s, lits)); return b.getvalue()
fb = E.Engine._build_context
cache = {}
acc = collections.Counter()
def build(self, assumptions, proposition=None):
    key = (assumptions, E.theory_scope(assumptions, proposition, self._extensions))
    c = cache.get(key)
    if c is not None:
        t = clock(); r = pickle.loads(c); dt = clock() - t; acc["load_repeat"] += dt; acc["n_load"] += 1
        acc["load" + ("-rel" if r[0].relations is not None else "-norel")] += dt
        return r
    t = clock(); r = fb(self, assumptions, proposition); acc["build_first"] += clock() - t
    t = clock(); cache[key] = dump(*r); acc["dump_store"] += clock() - t
    return r
seenk = set()
def build_timed(self, assumptions, proposition=None):
    key = (assumptions, E.theory_scope(assumptions, proposition, self._extensions))
    t = clock(); r = fb(self, assumptions, proposition); dt = clock() - t
    k = ("rep" if key in seenk else "first") + ("-rel" if r[0].relations is not None else "-norel")
    seenk.add(key); acc[k] += dt; acc["n" + k] += 1; acc["build"] += dt
    return r
E.Engine._build_context = build if mode == "clone" else build_timed
stream = pickle.load(open("/home/tilo/provable/data/stream.pkl", "rb"))
seen, uniq = set(), []
for p, a, r in stream:
    if (p, a) not in seen: seen.add((p, a)); uniq.append((p, a))
out = []
t0 = clock()
for p, a in uniq:
    try: out.append(repr(ask(p, a)))
    except ValueError: out.append("error")
T = clock() - t0
print(mode, f"total {T:.3f}s", {k: round(v, 3) for k, v in acc.items()}, "bytes/entry", sum(map(len, cache.values()))//max(1,len(cache)))
json.dump(out, open(f"{sys.argv[0].rsplit('/',1)[0]}/ans-{mode}.json", "w"))
