"""Bound for a recorded/cloned context build: after a (set, scope) is built
once, later builds return a generic deep copy of the pristine post-build
session (SymPy objects, P atoms, the engine shared).  Mode 'base' runs the
plain stream; 'clone' uses the copy.  Prints time, copy time, answers."""
import pickle, sys, time, types, weakref, collections, json
from fractions import Fraction
from satassume import engine as E
from satassume.sat.formula import P
from satassume.sympy_api import ask
from sympy import Basic
clock = time.perf_counter
mode = sys.argv[1]
ATOMIC = (int, float, str, bytes, bool, type(None), Fraction, Basic, P, type,
          types.FunctionType, types.BuiltinFunctionType, types.ModuleType, E.Engine, range)
stats = collections.Counter()
def dup(x, memo):
    i = id(x)
    try: return memo[i]
    except KeyError: pass
    if isinstance(x, ATOMIC): return x
    t = type(x)
    if t is list:
        y = memo[i] = []
        y.extend(dup(v, memo) for v in x); return y
    if t is tuple:
        y = tuple(dup(v, memo) for v in x); memo[i] = y; return y
    if t is dict or t is collections.OrderedDict or t is collections.defaultdict:
        if t is collections.defaultdict: y = memo[i] = t(x.default_factory)
        else: y = memo[i] = t()
        for k, v in x.items(): y[dup(k, memo)] = dup(v, memo)
        return y
    if t is set:
        y = memo[i] = set(); y.update(dup(v, memo) for v in x); return y
    if t is frozenset:
        y = frozenset(dup(v, memo) for v in x); memo[i] = y; return y
    if t is collections.deque:
        y = memo[i] = collections.deque(); y.extend(dup(v, memo) for v in x); return y
    if t is types.MethodType:
        y = memo[i] = types.MethodType(x.__func__, dup(x.__self__, memo)); return y
    if t is weakref.ProxyType:
        tgt = x.__repr__.__self__ if False else None
        y = memo[i] = weakref.proxy(memo[id(PROXY[i])]); return y
    if isinstance(x, tuple) and hasattr(t, "_make"):
        y = t._make(dup(v, memo) for v in x); memo[i] = y; return y
    if t is bytearray:
        y = memo[i] = bytearray(x); return y
    if isinstance(x, (list, dict, set)):
        y = memo[i] = t.__new__(t)
        if isinstance(x, list): y.extend(dup(v, memo) for v in x)
        else: raise TypeError(f"subclass {t}")
        for k, v in getattr(x, "__dict__", {}).items(): y.__dict__[k] = dup(v, memo)
        for c in t.__mro__:
            for k in c.__dict__.get("__slots__", ()):
                if k in ("__dict__", "__weakref__"): continue
                if hasattr(x, k): object.__setattr__(y, k, dup(getattr(x, k), memo))
        return y
    if hasattr(x, "__dict__") or hasattr(t, "__slots__"):
        y = memo[i] = t.__new__(t)
        stats[t.__name__] += 1
        d = getattr(x, "__dict__", None)
        if d is not None:
            for k, v in d.items(): y.__dict__[k] = dup(v, memo)
        for c in t.__mro__:
            for k in c.__dict__.get("__slots__", ()):
                if k in ("__dict__", "__weakref__"): continue
                if hasattr(x, k): object.__setattr__(y, k, dup(getattr(x, k), memo))
        return y
    raise TypeError(f"cannot copy {t}")
PROXY = {}
def register_proxies(s):
    r = s.relations
    if r is not None:
        PROXY[id(r.session)] = s
def clone(sl):
    s, lits = sl
    register_proxies(s)
    # copy the session first so the proxy's target is in the memo
    memo = {}
    s2 = dup(s, memo)
    return s2, dup(lits, memo)
fb = E.Engine._build_context
cache = {}
acc = collections.Counter()
def build(self, assumptions, proposition=None):
    key = (assumptions, E.theory_scope(assumptions, proposition, self._extensions))
    c = cache.get(key)
    if c is not None:
        t = clock(); r = clone(c); acc["clone_repeat"] += clock() - t; acc["n_clone"] += 1
        return r
    r = fb(self, assumptions, proposition)
    t = clock(); cache[key] = clone(r); acc["clone_store"] += clock() - t
    return r
if mode == "clone":
    E.Engine._build_context = build
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
print(mode, f"total {T:.3f}s", {k: round(v, 3) for k, v in acc.items()}, stats.most_common(12))
json.dump(out, open(f"ans-{mode}.json", "w"))
