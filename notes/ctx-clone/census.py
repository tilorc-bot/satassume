"""Census of the post-build context session: walk it (immutables shared),
count mutable objects by type, and find objects that are the *same* object
in two independent builds of the same (set, scope) -- globals the copier
must share.  Usage: census.py [N unique queries]"""
import sys, pickle, collections, types, weakref
from fractions import Fraction
from satassume import engine as E
from satassume.sat.formula import P, Formula
from satassume.sympy_api import ask
from sympy import Basic
ATOMIC = (int, float, str, bytes, bool, type(None), Fraction, Basic, P, Formula, type,
          types.FunctionType, types.BuiltinFunctionType, types.ModuleType, E.Engine, range)
def children(x):
    t = type(x)
    if isinstance(x, (list, tuple, set, frozenset, collections.deque)): yield from x
    if isinstance(x, dict):
        yield from x.keys(); yield from x.values()
    if t is types.MethodType: yield x.__self__
    if t is weakref.ProxyType: return
    d = getattr(x, "__dict__", None)
    if d is not None and not isinstance(x, type): yield from d.values()
    for c in t.__mro__:
        for k in c.__dict__.get("__slots__", ()):
            if k not in ("__dict__", "__weakref__") and hasattr(x, k): yield getattr(x, k)
def walk(root):
    seen = {}; stack = [root]
    while stack:
        x = stack.pop()
        if isinstance(x, ATOMIC) or id(x) in seen: continue
        seen[id(x)] = x
        stack.extend(children(x))
    return seen
fb = E.Engine._build_context
types_c = collections.Counter(); glob = collections.Counter(); globex = {}
nrel = [0]
def build(self, assumptions, proposition=None):
    r = fb(self, assumptions, proposition)
    if r[0].relations is not None and nrel[0] < 300:
        nrel[0] += 1
        r2 = fb(self, assumptions, proposition)
        a, b = walk(r), walk(r2)
        for i, x in a.items():
            types_c[type(x).__name__] += 1
            if i in b:
                glob[type(x).__name__] += 1; globex.setdefault(type(x).__name__, x)
    return r
E.Engine._build_context = build
stream = pickle.load(open("/home/tilo/provable/data/stream.pkl", "rb"))
seen, uniq = set(), []
for p, a, r in stream:
    if (p, a) not in seen: seen.add((p, a)); uniq.append((p, a))
for p, a in uniq[: int(sys.argv[1]) if len(sys.argv) > 1 else None]:
    try: ask(p, a)
    except ValueError: pass
print("rel sessions", nrel[0]); print("per session mutable objects by type:", {k: round(v / nrel[0], 1) for k, v in types_c.most_common()})
print("shared between two builds:", {k: round(v / nrel[0], 1) for k, v in glob.most_common()})
for k, x in globex.items(): print(" ", k, repr(x)[:150])
