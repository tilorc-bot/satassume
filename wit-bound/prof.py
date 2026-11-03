import pickle, sys, cProfile, pstats
from satassume.sympy_api import ask
st = pickle.load(open(sys.argv[1], "rb"))
def run():
    for p, a, r in st:
        try: ask(p, a)
        except ValueError: pass
cProfile.run("run()", sys.argv[2])
