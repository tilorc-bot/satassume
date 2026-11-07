"""Differential test of solver_rs/src/constfield.rs and lra_cert.rs against the Python modules: test_cf_diff.py [SEED] [OPS].
Compares structure (n, d), exception type and text, `_sign` on operands and sampled `Constant._cache` contents."""
import faulthandler, math, os, random, sys, time
if os.environ.get("CF_DUMP"): faulthandler.dump_traceback_later(int(os.environ["CF_DUMP"]), exit=True)
from collections import Counter
from fractions import Fraction as F
sys.path.insert(0, os.environ.get("CF_SO") or os.path.dirname(os.path.abspath(__file__)))
from satassume.theories.lra import constfield as cf, lra_cert as lc
import sa_solver as S
seed = int(sys.argv[1]) if len(sys.argv) > 1 else int(time.time()) % 100000
OPS = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
rnd = random.Random(seed)
print("seed", seed, "ops", OPS, "module", cf.__file__, "so", S.__file__)
stats, bad = Counter(), []
El = cf.Element
def pn(p): return ("F", p.numerator, p.denominator) if type(p) is F else ("T", type(p).__name__, p[0], tuple(pn(c) for c in p[1]))
def norm(x):
    if type(x) is F: return pn(x)
    if type(x) is El: return ("E", pn(x._n), pn(x._d))
    if type(x) is tuple: return tuple(norm(y) for y in x)
    if type(x) is list: return [norm(y) for y in x]
    return (type(x).__name__, x)
def run(f):
    try: return ("ok", norm(f()))
    except Exception as e: return ("exc", type(e).__name__, str(e))
def fresh(x):
    if type(x) is not El: return x
    y = El._new(x._n, x._d); y._sign = x._sign; return y
def sg(x): return x._sign if type(x) is El else None
def short(x): r = repr(x); return r if len(r) < 240 else r[:240] + "..."
def report(tag, args, p, r):
    bad.append(tag)
    if len(bad) <= 8: print("MISMATCH", tag, [short(a) for a in args], "\n  py", short(p), "\n  rs", short(r))
def cmp(tag, args, p, r):
    stats[tag.split(":")[0], p[0] if p[0] == "ok" else p[1]] += 1
    if p != r: report(tag, args, p, r)
PY = dict(add=lambda a, b: a + b, sub=lambda a, b: a - b, mul=lambda a, b: a * b, div=lambda a, b: a / b,
          py_eq=lambda a, b: a == b, lt=lambda a, b: a < b, le=lambda a, b: a <= b, gt=lambda a, b: a > b, ge=lambda a, b: a >= b)
PY1 = dict(neg=lambda a: -a, abs=abs, inverse=lambda a: a._inverse() if type(a) is El else 1 / a, formally_zero=cf.formally_zero,
           sign=cf.sign, nonzero=bool, floor=math.floor, ceil=math.ceil, roundtrip=lambda a: a,
           is_integer=lambda a: a.denominator == 1 if type(a) is F else a.is_integer())
log = []
def cb(name, val, fail_at=None, bad_at=None):
    def enc(prec):
        log.append((name, prec))
        if fail_at is not None and prec >= fail_at: raise RuntimeError(f"{name} fails at {prec}")
        if bad_at is not None and prec >= bad_at: return 5, 3
        s = val * (1 << prec); return math.floor(s) - 1, math.ceil(s) + 1
    return enc
PI, E = cf.PI, cf.E; s2, s3, s6 = cf.radical(F(2), 2), cf.radical(F(3), 2), cf.radical(F(6), 2)
c1 = cf.constant("cb1", cb("cb1", F(7, 5)), name="cb1")
c2 = cf.constant("cb2", cb("cb2", F(9, 7), fail_at=128), name="cb2")
c3 = cf.constant("cb3", cb("cb3", F(11, 7), fail_at=128), name="cb3")
c4 = cf.constant("bad", cb("bad", F(3, 2), bad_at=128), name="bad")
c5 = cf.constant("cap", cb("cap", F(13, 9)), max_prec=128, name="cap")
c6 = cf.constant("tr", cb("tr", F(31, 17)), transcendental=True, name="tr")
seeds = [F(0), F(1), F(-1), F(1, 2), F(3), F(-7, 3), F(2), F(6), F(2**70 + 1, 3), F(-(2**300) - 1, 7), F(1, 2**8000), F(2**8100 + 1),
         F(355, 113), PI, E, s2, s3, s6, 1 / PI, PI + 1, E * PI, c1, c2, c3, c4, c5, c6, s2 * s2 - 2, s2 * s3 - s6, s2**2, s2 * s3,
         (PI - F(355, 113))**40, (PI + 1)**8, 1 / (PI + 1), 1 / (PI * E + 1), (PI + E + 1)**4, PI / E, (E + s2) / (PI + s3),
         PI * F(1, 2**4000), E * F(2**4000 + 1), (PI + 1)**20, (PI + E + s2 + 1)**6, 1 / (s2 + 1), (c1 + 1) / c2, c6**2 + 1]
pool = list(seeds)
def op_once(name, a, b):
    if name in PY: pf, rf = (lambda x, y: PY[name](x, y)), (lambda x, y: S.cf_op(name, x, y))
    else: pf, rf = (lambda x, y: PY1[name](x)), (lambda x, y: S.cf_op(name, x))
    sample = rnd.random() < 0.03
    a1, b1, a2, b2 = fresh(a), fresh(b), fresh(a), fresh(b)
    if sample:
        keep = {c.key: dict(c._cache) for c in cf._CONSTANTS}
        for c in cf._CONSTANTS: c._cache.clear()
        log.clear()
    p = run(lambda: pf(a1, b1))
    if sample:
        cp, lp = {c.key: dict(c._cache) for c in cf._CONSTANTS}, list(log)
        for c in cf._CONSTANTS: c._cache.clear()
        log.clear()
    r = run(lambda: rf(a2, b2))
    if sample:
        cr, lr = {c.key: dict(c._cache) for c in cf._CONSTANTS}, list(log)
        stats["cache-compare", "ok"] += 1
        if cp != cr: report("cache:" + name, (a, b), sorted(k for k in cp if cp[k] != cr[k]), "cache state")
        if lp != lr: report("callback-order:" + name, (a, b), lp, lr)
        for c in cf._CONSTANTS: c._cache.update(keep[c.key])
    cmp(name, (a, b), p, r)
    if (sg(a1), sg(b1)) != (sg(a2), sg(b2)): report("sign-state:" + name, (a, b), (sg(a1), sg(b1)), (sg(a2), sg(b2)))
    return pf, a1, b1, p
NAMES = list(PY) * 3 + list(PY1)
def patch(**k):
    for n, v in k.items(): setattr(cf, n, v)
    S.cf_refresh_limits()
DEF = dict(PREC_START=64, PREC_CAP=4096, MAX_DEGREE=64, MAX_TERMS=512, MAX_BITS=8192, MAX_WORK=1 << 14, _EUCLID_MAX_DEG=8)
MODES = [{}, {}, {}, dict(PREC_CAP=128), dict(PREC_CAP=64), dict(MAX_BITS=256), dict(MAX_BITS=1024), dict(MAX_DEGREE=4),
         dict(MAX_TERMS=6), dict(MAX_WORK=20), dict(_EUCLID_MAX_DEG=2), dict(PREC_START=128, PREC_CAP=256)]
t0 = time.time()
for i in range(OPS):
    if i % 200 == 0:
        patch(**{**DEF, **rnd.choice(MODES)})
    name = rnd.choice(NAMES)
    a, b = rnd.choice(pool), rnd.choice(pool)
    if rnd.random() < 0.15: b = fresh(a)
    pf, a1, b1, p = op_once(name, a, b)
    if name in ("add", "sub", "mul", "div", "inverse", "neg") and p[0] == "ok" and rnd.random() < 0.4:
        try: v = pf(fresh(a), fresh(b))
        except Exception: continue
        if type(v) is El and v._size()[1] <= 200 or type(v) is F: pool.append(v)
        if len(pool) > 150: del pool[len(seeds) + rnd.randrange(len(pool) - len(seeds))]
    if rnd.random() < 0.02 and type(a) is El:
        k = rnd.randint(-5, 9)
        cmp("pow", (a, k), run(lambda: fresh(a)**k), run(lambda: S.cf_op("pow", fresh(a), k)))
        pr = rnd.choice([64, 128, 256])
        cmp("enclosure", (a, pr), run(lambda: fresh(a).enclosure(pr)), run(lambda: S.cf_op("enclosure", fresh(a), pr)))
    if rnd.random() < 0.02:
        cmp("within", (a,), run(lambda: lc.within(fresh(a), F(rnd.randint(0, 9)))) if False else run(lambda: lc.within(fresh(a), F(5, 2))), run(lambda: S.cf_within(fresh(a), F(5, 2))))
        st, hp = (norm(a) == norm(b)), hash(a) == hash(b)
        if S.cf_op("struct_eq", a, b) is not st or (st and not S.cf_op("hash_eq", a, b)): report("struct", (a, b), st, "struct_eq")
patch(**DEF)
print("ops done", round(time.time() - t0, 1), "s")
# identities named in the brief
t = s2
for x, y in [(t**2, F(2)), (F(2), t**2), (s2 * s3, s6), (s6, s2 * s3), (t, fresh(t)), (PI, fresh(PI)), (s2 * s2 - 2, s2 * s2 - 2)]:
    for n in ("py_eq", "lt", "le", "div", "sub"): op_once(n, x, y)
big = (PI - F(355, 113))**400 if False else (PI - F(355, 113))**60
for x in (big, (PI - F(355, 113))**8):
    for n in ("sign", "nonzero", "floor", "ceil", "inverse", "is_integer"): op_once(n, x, x)
# gcd against the real SymPy path, and polynomial functions
def rpoly(vs, deg, terms, h=9):
    p = F(0)
    for _ in range(terms):
        m = F(rnd.randint(-h, h), rnd.choice([1, 1, 1, 2, 3, 5]))
        for v in vs:
            k = rnd.randint(0, deg)
            if k: m = cf._mul(m, (v, (F(0),) * k + (F(1),)))
        p = cf._add(p, m)
    return p
G = int(os.environ.get("CF_GCD", 1500))
tg = time.time()
for i in range(G):
    vs = rnd.sample(range(5), rnd.randint(1, int(os.environ.get("CF_GCD_VARS", 3)))); deg = rnd.randint(1, int(os.environ.get("CF_GCD_DEG", 2))); terms = rnd.randint(1, 3)
    g, f, h = rpoly(vs, deg, terms), rpoly(vs, deg, terms), rpoly(rnd.sample(vs, rnd.randint(1, len(vs))), deg, terms)
    a, b = cf._mul(g, f), cf._mul(g, h)
    if rnd.random() < 0.2: a = cf._add(a, F(1))
    if rnd.random() < 0.15: k = rnd.choice([100, 5000, 9000]); a = cf._scale(a, F(1, 2**k + 1)) if not cf._zero(a) else a
    if cf._zero(a) or cf._zero(b) or type(a) is F or type(b) is F: continue
    cmp("sympy_gcd", (a, b), run(lambda: cf._sympy_inner_gcd(a, b)), run(lambda: S.cf_inner_gcd(a, b)))
    cmp("inner_gcd", (a, b), run(lambda: cf._inner_gcd(a, b)), run(lambda: S.cf_poly_op("inner_gcd", a, b)))
    for n, pf in (("mul_checked", cf._mul_checked), ("mul_bounded", cf._mul_bounded), ("add_bounded", cf._add_bounded), ("gcd", cf._gcd)):
        cmp(n, (a, b), run(lambda: pf(a, b)), run(lambda: S.cf_poly_op(n, a, b)))
    cmp("psize", (a,), run(lambda: cf._psize(a)), run(lambda: S.cf_poly_op("psize", a)))
    m = cf._mul(a, b)
    cmp("divexact", (m, b), run(lambda: cf._divexact(m, b)), run(lambda: S.cf_poly_op("divexact", m, b)))
    cmp("divexact", (a, m), run(lambda: cf._divexact(cf._add(m, F(1)), b)), run(lambda: S.cf_poly_op("divexact", cf._add(m, F(1)), b)))
    k = rnd.randint(1, 5)
    cmp("pow_checked", (a, k), run(lambda: cf._pow_checked(a, k)), run(lambda: S.cf_poly_op("pow_checked", a, k)))
    if i % 100 == 0: patch(**{**DEF, **rnd.choice(MODES)})
patch(**DEF)
print("gcd done", round(time.time() - tg, 1), "s")
# native enclosures: the integers
for prec in [64, 96, 128, 256, 512, 1024, 2048, 4096] + [rnd.randint(1, 3000) for _ in range(20)]:
    cmp("native", (prec,), run(lambda: cf._pi_enclose(prec)), run(lambda: S.cf_native_enclose("pi", prec)))
    cmp("native", (prec,), run(lambda: cf._e_enclose(prec)), run(lambda: S.cf_native_enclose("E", prec)))
    r, b = F(rnd.randint(1, 10**6), rnd.randint(1, 10**4)), rnd.randint(2, 7)
    pyf = cf.radical(r, b).constants()[0]._enclose
    cmp("native", (r, b, prec), run(lambda: pyf(prec)), run(lambda: S.cf_native_enclose((r, b), prec)))
# a replaced _enclose is no longer native; a poisoned _cache is what Python reads
keep_e = cf.PI.constants()[0]._enclose
pc = cf.PI.constants()[0]; sv = dict(pc._cache)
pc._cache.clear(); pc._enclose = lambda prec: (1, 2)
cmp("replaced-enclose", (), run(lambda: fresh(PI + s2).enclosure(64)), run(lambda: S.cf_op("enclosure", fresh(PI + s2), 64)))
pc._cache.clear(); pc._enclose = keep_e; pc._cache[64] = (5, 6)
cmp("poisoned-cache", (), run(lambda: fresh(PI).enclosure(64)), run(lambda: S.cf_op("enclosure", fresh(PI), 64)))
pc._cache.clear(); pc._cache.update(sv)
# certify, incrementally on generated systems
def cstate(g):
    ints = [(e, mu, sorted(ek), dk, ck, nk, lkd, kc) for e, mu, ek, dk, ck, nk, lkd, kc in g.ints]
    return ((g.ok, g.na, g.ni, g.nf, sorted(g.exps)), (g.den, g.top, g.X, g.neq, g.had, ints))
def rq(h=9): return F(rnd.randint(-h, h), rnd.randint(1, 4))
def rbound(kinds):
    k = rnd.choice(kinds)
    if k == "q": return rq()
    a, b = rq() or F(1), rq() or F(1)
    return {"pi": a * PI, "ipi": a / PI, "lin": a + b * PI, "ilin": (a + b * PI) / PI, "pi2": a * PI**2, "e": a * E, "s2": a * s2, "big": F(rnd.randint(1, 2**400)) * PI}[k]
C = int(os.environ.get("CF_CERT", 1500)); certified = 0
for sysno in range(C):
    if sysno % 25 == 0:
        patch(**{**DEF, **rnd.choice([{}, {}, {}, dict(PREC_CAP=300), dict(MAX_BITS=2000), dict(MAX_DEGREE=5), dict(MAX_TERMS=6), dict(MAX_WORK=15), dict(PREC_START=8192)])})
    kinds = rnd.choice([["q"], ["q", "pi"], ["q", "pi", "lin"], ["q", "ipi", "ilin"], ["q", "pi", "ipi"], ["q", "pi2"], ["q", "pi", "e"], ["q", "s2"], ["q", "big"]])
    g, h = lc.CertAtoms(), S.CfCertAtoms()
    atoms, ints, forms = {}, {}, {}
    for step in range(rnd.randint(1, 4)):
        for _ in range(rnd.randint(0, 3)):
            atoms[len(atoms)] = (len(atoms), rnd.choice(["<=", "<", ">=", ">", "=", "!="]), rbound(kinds))
        if rnd.random() < 0.4:
            m = rnd.choice([F(1), F(2), rq() or F(1), PI, 2 * PI, 1 / PI, PI + 1, E, PI**2])
            ints[len(ints)] = (len(ints), m, rbound(kinds))
        if rnd.random() < 0.6:
            fm = tuple((v, rq() or F(1)) for v in rnd.sample(range(6), rnd.randint(1, 3)))
            if rnd.random() < 0.05: fm += ((9, PI),)
            forms[fm] = len(forms)
        nt = rnd.randint(0, 6)
        vals = rnd.choice([None, None, (F(0), 1), (F(7, 2), 2), (rq(2**40), rnd.randint(1, 50))])
        if vals: vals = (abs(vals[0]), vals[1])
        p = run(lambda: lc.certify(g, atoms, ints, forms, nt, vals)); r = run(lambda: S.cert_check(h, atoms, ints, forms, nt, vals))
        if p[0] == "ok" and p[1][0] == ("bool", True): certified += 1
        cmp("certify", (atoms, ints, forms), p, r)
        if norm(cstate(g)) != norm(h.state()): report("cert-state", (atoms,), cstate(g), h.state())
    cmp("limits", (), ("ok", list(lc.limits())), ("ok", list(S.cf_limits())))
    vs = [rbound(kinds) for _ in range(rnd.randint(0, 4))]
    pv = None if any(type(q) is not F for q in vs) else (max([abs(q) for q in vs], default=F(0)), math.lcm(1, *[q.denominator for q in vs]))
    cmp("rational_values", (vs,), run(lambda: pv), run(lambda: S.cf_rational_values(vs)))
    for dd, hh in [(rnd.randint(1, 2**60), rnd.randint(1, 2**60))]:
        cmp("decided", (dd, hh), ("ok", ("bool", lc._decided(dd, hh))), ("ok", ("bool", S.cf_decided(dd, hh))))
patch(**DEF)
tot = sum(stats.values())
outs = Counter()
for (n, o), c in stats.items(): outs[o] += c
print("compared", tot, "by outcome", dict(outs), "certified-true", certified)
print("by op", {n: sum(c for (m, _), c in stats.items() if m == n) for n in sorted({m for m, _ in stats})})
for need in ("Undecided", "TooLarge", "ZeroDivisionError", "RuntimeError", "ValueError"):
    if not outs[need]: print("WEAK: never saw", need); bad.append("weak:" + need)
if not certified: print("WEAK: nothing certified"); bad.append("weak:cert")
print("MISMATCHES", len(bad), Counter(b.split(":")[0] + ":" + b.split(":")[-1] for b in bad).most_common(12))
sys.exit(1 if bad else 0)
