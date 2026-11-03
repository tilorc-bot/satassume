import pickle, sys, time, gc
from satassume.sympy_api import ask
st = pickle.load(open(sys.argv[1], "rb"))
gc.collect(); gc.freeze()
t = time.perf_counter()
for p, a, r in st:
    try: ask(p, a)
    except ValueError: pass
print("plain pass", round(time.perf_counter() - t, 3))
