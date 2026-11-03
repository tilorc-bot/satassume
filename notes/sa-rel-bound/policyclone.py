"""Estimate of a hand-written clone: per (class, attribute) a policy learnt
on the fly; an attribute whose container has only immutable members is
copied by one C-level shallow copy (what hand-written code would do), the
rest by the generic recursive copier.  Repeat builds of a (set, scope)
return a clone of the pristine post-build session; first builds store one.
Mode base|clone; --rel-only clones only relation sessions."""
import sys, collections, pickle, time, json, types, weakref
from fractions import Fraction
sys.argv, MODE, REL_ONLY = sys.argv[:1], sys.argv[1], "--rel-only" in sys.argv
from satassume import engine as E
from satassume.sat.formula import P
from satassume.sympy_api import ask
from sympy import Basic
clock = time.perf_counter
ATOMIC = (int, float, str, bytes, bool, type(None), Fraction, Basic, P, type,
          types.FunctionType, types.BuiltinFunctionType, types.ModuleType, E.Engine, range)
ATOMIC_T = set(ATOMIC)
FLAT = {}   # (class, attr) -> True if flat so far
def flat(v):
    t = type(v)
    if t is list or t is collections.deque or t is set or t is frozenset:
        return all(isinstance(x, ATOMIC) for x in v)
    if t is dict:
        return all(isinstance(k, ATOMIC) and isinstance(x, ATOMIC) for k, x in v.items())
    if t is bytearray: return True
    return False
def shallow(v):
    t = type(v)
    if t is list: return v[:]
    if t is frozenset: return v
    return v.copy()
def dup(x, memo):
    i = id(x)
    try: return memo[i]
    except KeyError: pass
    if isinstance(x, ATOMIC): return x
    t = type(x)
    if t is list:
        y = memo[i] = []; y.extend([dup(v, memo) for v in x]); return y
    if t is tuple:
        y = tuple([dup(v, memo) for v in x]); memo[i] = y; return y
    if t is dict or t is collections.OrderedDict or t is collections.defaultdict:
        y = memo[i] = t(x.default_factory) if t is collections.defaultdict else t()
        for k, v in x.items(): y[dup(k, memo)] = dup(v, memo)
        return y
    if t is set:
        y = memo[i] = set(); y.update([dup(v, memo) for v in x]); return y
    if t is frozenset:
        y = frozenset([dup(v, memo) for v in x]); memo[i] = y; return y
    if t is collections.deque:
        y = memo[i] = collections.deque(); y.extend([dup(v, memo) for v in x]); return y
    if t is types.MethodType:
        y = memo[i] = types.MethodType(x.__func__, dup(x.__self__, memo)); return y
    if t is weakref.ProxyType:
        y = memo[i] = weakref.proxy(memo[id(PROXY[i])]); return y
    if t is bytearray:
        y = memo[i] = bytearray(x); return y
    if isinstance(x, tuple) and hasattr(t, "_make"):
        y = t._make([dup(v, memo) for v in x]); memo[i] = y; return y
    y = memo[i] = t.__new__(t)
    if isinstance(x, list): y.extend([dup(v, memo) for v in x])
    d = getattr(x, "__dict__", None)
    if d is not None:
        yd = y.__dict__
        for k, v in d.items():
            key = (t, k)
            f = FLAT.get(key)
            if f is None or f:
                if type(v) in ATOMIC_T: yd[k] = v; continue
                if f is None: f = FLAT[key] = flat(v)
                if f and flat_ok(v, key):
                    yd[k] = memo[id(v)] = shallow(v); continue
            yd[k] = dup(v, memo)
    for c in t.__mro__:
        for k in c.__dict__.get("__slots__", ()):
            if k in ("__dict__", "__weakref__"): continue
            if hasattr(x, k): object.__setattr__(y, k, dup(getattr(x, k), memo))
    return y
CHECK = [True]
def flat_ok(v, key):
    # first sessions: verify the learnt policy; later trust it (as code would)
    if CHECK[0] and not flat(v):
        FLAT[key] = False; return False
    return True
PROXY = {}
def clone(sl):
    s, lits = sl
    if s.relations is not None:
        PROXY[id(s.relations.session)] = s
    memo = {}
    s2 = dup(s, memo)
    return s2, dup(lits, memo)
fb = E.Engine._build_context
cache = {}; acc = collections.Counter(); nb = [0]
def build(self, assumptions, proposition=None):
    nb[0] += 1
    if nb[0] == 600: CHECK[0] = False
    key = (assumptions, E.theory_scope(assumptions, proposition, self._extensions))
    c = cache.get(key)
    if c is not None:
        t = clock(); r = clone(c); acc["clone_repeat"] += clock() - t; acc["n_clone"] += 1
        return r
    t = clock(); r = fb(self, assumptions, proposition); acc["build"] += clock() - t
    if not REL_ONLY or r[0].relations is not None:
        t = clock(); cache[key] = clone(r); acc["store"] += clock() - t
    return r
def build_timed(self, assumptions, proposition=None):
    t = clock(); r = fb(self, assumptions, proposition); acc["build"] += clock() - t
    return r
E.Engine._build_context = build if MODE == "clone" else build_timed
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
print(MODE, "rel-only" if REL_ONLY else "", f"total {T:.3f}s", {k: round(v, 3) for k, v in acc.items()},
      "flat attrs", sum(FLAT.values()), "of", len(FLAT))
json.dump(out, open(__file__.rsplit("/", 1)[0] + f"/ans-p{MODE}.json", "w"))
