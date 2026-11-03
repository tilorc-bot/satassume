import pickle, cProfile, pstats, sys, collections
from satassume import engine as E
from satassume.sympy_api import ask
stream = pickle.load(open("/home/tilo/provable/data/stream.pkl", "rb"))
seen, uniq = set(), []
for p, a, r in stream:
    if (p, a) not in seen: seen.add((p, a)); uniq.append((p, a))
pr = cProfile.Profile()
fb = E.Engine._build_context
seenk = set()
def build(self, assumptions, proposition=None):
    key = (assumptions, E.theory_scope(assumptions, proposition, self._extensions))
    on = key in seenk and E.theory_scope(assumptions, proposition, self._extensions).glue
    seenk.add(key)
    if on: pr.enable()
    try: return fb(self, assumptions, proposition)
    finally:
        if on: pr.disable()
E.Engine._build_context = build
for p, a in uniq:
    try: ask(p, a)
    except ValueError: pass
st = pstats.Stats(pr)
tot = collections.Counter()
for (f, l, fn), (cc, nc, tt, ct, callers) in st.stats.items():
    k = ("sympy" if "sympy/" in f else f.split("satassume/")[-1] if "satassume" in f else "builtin")
    tot[k] += tt
T = sum(tot.values()); print("profiled", round(T, 3))
for k, v in tot.most_common(12): print(f"{v:7.3f} {v/T:5.1%} {k}")
st.sort_stats("tottime").print_stats(25)
st.sort_stats("cumulative").print_stats(40)
