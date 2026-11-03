"""Builds per (set, scope) key on the unique stream, relation sessions only."""
import pickle, collections
from satassume import engine as E
from satassume.sympy_api import ask
fb = E.Engine._build_context; c = collections.Counter()
def build(self, a, p=None):
    r = fb(self, a, p)
    if r[0].relations is not None: c[(a, E.theory_scope(a, p, self._extensions))] += 1
    return r
E.Engine._build_context = build
stream = pickle.load(open("/home/tilo/provable/data/stream.pkl", "rb"))
seen, uniq = set(), []
for p, a, r in stream:
    if (p, a) not in seen: seen.add((p, a)); uniq.append((p, a))
for p, a in uniq:
    try: ask(p, a)
    except ValueError: pass
h = collections.Counter(c.values())
print("keys", len(c), "builds", sum(c.values()), "keys with >=2 builds", sum(1 for v in c.values() if v >= 2), "histogram", sorted(h.items())[:12])
