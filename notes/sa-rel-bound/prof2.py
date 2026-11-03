import pickle, cProfile, pstats, sys, gc, time, collections
from satassume.sympy_api import ask
from satassume import relations as R
stream = pickle.load(open("/home/tilo/provable/data/stream.pkl", "rb"))
seen, uniq = set(), []
for p, a, r in stream:
    if (p, a) not in seen: seen.add((p, a)); uniq.append((p, a))
pr = cProfile.Profile()
orig = R.Relations.process
def process(self, *a, **k):
    pr.enable()
    try: return orig(self, *a, **k)
    finally: pr.disable()
R.Relations.process = process
for p, a in uniq:
    try: ask(p, a)
    except ValueError: pass
st = pstats.Stats(pr)
tot = collections.Counter()
for (f, l, fn), (cc, nc, tt, ct, callers) in st.stats.items():
    if "sympy/" in f: k = "sympy"
    elif "satassume" in f: k = f.split("satassume/")[-1]
    else: k = "other:" + (f if f != "~" else fn)[:60]
    tot[k] += tt
T = sum(tot.values())
print("total in process (profiled)", round(T,3))
for k, v in tot.most_common(25): print(f"{v:7.3f} {v/T:5.1%} {k}")
st.sort_stats("tottime").print_stats("sympy/", 15)
