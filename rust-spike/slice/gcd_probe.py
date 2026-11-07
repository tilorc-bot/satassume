"""High-degree probe of heu_gcd's size guard: one input, one backend, one process, so a stall is killed by the caller's
limit. gcd_probe.py KIND DEG BITS SEED rust|python. Prints the time, the gcd's hash, the counts and the largest image."""
import hashlib, os, random, sys, time
from fractions import Fraction as F
sys.path.insert(0, os.environ.get("CF_SO") or os.path.dirname(os.path.abspath(__file__)))
from satassume.theories.lra import constfield as cf
import sa_solver as S
kind, deg, bits, seed, who = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
rnd = random.Random(f"{kind} {deg} {bits} {seed}")
NV = {"uni": 1, "bi": 2, "tri": 3, "quad": 4}[kind.split("-")[0]]
TERMS = int(kind.split("-")[1]) if "-" in kind else 4
def rpoly(n):
    p = F(0)
    for _ in range(n):
        m = F(rnd.randint(-(2 ** bits), 2 ** bits) or 1)
        for v in range(NV):
            k = rnd.randint(0, deg)
            if k: m = cf._mul(m, (v, (F(0),) * k + (F(1),)))
        p = cf._add(p, m)
    return p
g, f, h = rpoly(TERMS), rpoly(TERMS), rpoly(TERMS)
a, b = cf._mul(g, f), cf._mul(g, h)
if type(a) is F or type(b) is F or cf._zero(a) or cf._zero(b): print("skip trivial"); sys.exit(0)
cf._sympy_inner_gcd((0, (F(0), F(1))), (0, (F(1), F(1))))  # SymPy's import is not the gcd's time
t0 = time.perf_counter()
r = S.cf_inner_gcd(a, b) if who == "rust" else cf._sympy_inner_gcd(a, b)
t = time.perf_counter() - t0
print(who, kind, deg, bits, seed, "t", round(t, 4), "psize", cf._psize(a), "hash", hashlib.sha1(repr(r).encode()).hexdigest()[:10],
      "counts", S.cf_gcd_counts(), "guard,maximage", S.cf_gcd_guard_count(), flush=True)
