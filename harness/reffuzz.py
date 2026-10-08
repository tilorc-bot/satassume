"""Differential fuzz: ``satassume.sympy_api.ask`` against ``satassume.ref.ask_ref``.

Random queries over the whole predicate vocabulary (derived predicates
included), compound expressions (Add/Mul of up to 12 terms, Pow, Abs, exp,
log, trig, re/im/conjugate), wide And/Or/Not, relations and the edge values
``oo``, ``-oo``, ``zoo``, ``I``.  Each query is answered three ways:

* ``E``: ``ask`` on a fresh engine;
* ``S``: ``ask`` on one engine reused across a stream of queries (each
  query asked twice, so the second answer comes from a warm session);
* ``R``: ``ask_ref``, the specification's answer (no state, no budget).

A *finding* is a definite answer contradicted by another column (True vs
False, a value vs an exception), or a definite ``E``/``S`` answer where
``R`` says None (the reference answers under the whole set, so it is never
less definite than the engine), or ``E`` and ``S`` disagreeing.  ``R``
definite where the engine says None is counted (``lost``), not reported:
the engine's discovery budget and relevance split allow it.

``python -m harness.reffuzz --seeds 0-3 -n 500`` runs it; ``--out F``
writes every outcome as JSON lines for a cross-version diff
(``--diff A B``).  ``tests/test_ref_fuzz.py`` is the CI slice.
"""
import argparse
import json
import random
import signal
import sys
import time

from sympy import (Abs, Add, And, E, I, Integer, Mul, Not, Or, Pow, Q, Rational, S, Symbol,
                   conjugate, cos, exp, im, log, oo, pi, re, sin, sqrt, srepr, zoo)

#: unary predicates of the vocabulary (satassume.rules.PREDICATES)
PREDS = (
    'algebraic', 'antihermitian', 'commutative', 'complex', 'composite',
    'even', 'extended_negative', 'extended_nonnegative',
    'extended_nonpositive', 'extended_nonzero', 'extended_positive',
    'extended_real', 'finite', 'hermitian', 'imaginary', 'infinite',
    'integer', 'irrational', 'negative', 'negative_infinite', 'noninteger',
    'nonnegative', 'nonpositive', 'nonzero', 'odd', 'polar', 'positive',
    'positive_infinite', 'prime', 'rational', 'real', 'transcendental',
    'zero',
)
#: predicates that are definitions over the basis on main (weighted up)
DERIVED = (
    'real', 'hermitian', 'infinite', 'positive', 'negative', 'nonnegative',
    'nonpositive', 'nonzero', 'extended_nonnegative', 'extended_nonpositive',
    'extended_nonzero', 'positive_infinite', 'negative_infinite', 'odd',
    'irrational', 'noninteger', 'transcendental', 'antihermitian',
)
RELS = ('gt', 'lt', 'ge', 'le', 'eq', 'ne')

_PLAIN = [Symbol(n) for n in 'xyzwuv']
_DECL = [Symbol('p', positive=True), Symbol('n', integer=True), Symbol('r', real=True),
         Symbol('k', nonnegative=True, integer=True), Symbol('q', negative=True)]
_CONST = [S.Zero, S.One, S.NegativeOne, Integer(2), Rational(1, 2), Rational(-3, 2), pi, E,
          sqrt(2), I, 2 * I, oo, -oo, zoo]
_EDGE = [oo, -oo, zoo, I]


class Gen:
    def __init__(self, seed: int, nsym: int = 4, decl: bool = True):
        self.r = random.Random(seed)
        self.syms = _PLAIN[:nsym] + (_DECL if decl else [])

    def leaf(self):
        r = self.r
        x = r.random()
        if x < 0.7:
            return r.choice(self.syms[:4]) if r.random() < 0.75 else r.choice(self.syms)
        return r.choice(_CONST)

    def expr(self, depth: int = 2):
        r = self.r
        if depth <= 0 or r.random() < 0.35:
            return self.leaf()
        k = r.random()
        if k < 0.25:
            n = r.choice((2, 2, 3, 3, 4, 6, 8, 12))
            return Add(*[self.term(depth - 1) for _ in range(n)])
        if k < 0.45:
            n = r.choice((2, 2, 3, 3, 4, 6, 8, 12))
            return Mul(*[self.term(depth - 1) for _ in range(n)])
        if k < 0.6:
            e = r.choice((Integer(2), Integer(3), S.NegativeOne, Rational(1, 2), Integer(-2),
                          self.leaf(), self.leaf()))
            return Pow(self.expr(depth - 1), e)
        f = r.choice((Abs, exp, log, sin, cos, re, im, conjugate, sqrt))
        return f(self.expr(depth - 1))

    def term(self, depth):
        # mostly symbols in long sums/products so they keep their width
        return self.leaf() if self.r.random() < 0.7 else self.expr(depth)

    def atom(self, derived_bias: float = 0.5):
        r = self.r
        if r.random() < 0.18:
            rel = r.choice(RELS)
            b = self.leaf() if r.random() < 0.6 else r.choice(_EDGE + [S.Zero])
            return getattr(Q, rel)(self.expr(1), b)
        name = r.choice(DERIVED) if r.random() < derived_bias else r.choice(PREDS)
        return getattr(Q, name)(self.expr(r.choice((0, 1, 1, 2))))

    def formula(self, depth: int = 2, wide: bool = False):
        r = self.r
        if depth <= 0 or r.random() < 0.45:
            a = self.atom()
            return Not(a) if r.random() < 0.25 else a
        if r.random() < 0.15:
            return Not(self.formula(depth - 1, wide))
        n = r.randint(2, 30 if wide else 4)
        op = And if r.random() < 0.5 else Or
        return op(*[self.formula(depth - 1) for _ in range(n)])

    def wide(self):
        """Wide Or/And/negation of (mostly) one derived predicate over many symbols."""
        r = self.r
        n = r.choice((8, 9, 16, 30))
        syms = [Symbol('s%d' % i) for i in range(n)]
        preds = [r.choice(DERIVED)] if r.random() < 0.6 else list(r.sample(DERIVED, 3))
        lits = [getattr(Q, r.choice(preds))(s) for s in syms]
        lits = [Not(l) if r.random() < 0.2 else l for l in lits]
        return (Or if r.random() < 0.5 else And)(*lits), syms

    def fact(self, t):
        r = self.r
        name = r.choice(DERIVED) if r.random() < 0.6 else r.choice(PREDS)
        a = getattr(Q, name)(t)
        return Not(a) if r.random() < 0.2 else a

    def compound(self, syms):
        """An expression over ``syms`` only (plus small constants)."""
        r = self.r
        k = r.random()
        ts = list(syms)
        if r.random() < 0.3:
            ts.append(r.choice((Integer(2), Integer(-1), Rational(1, 2), pi, I, oo, -oo)))
        r.shuffle(ts)
        if k < 0.3:
            return Add(*ts)
        if k < 0.6:
            return Mul(*ts)
        if k < 0.75:
            return Pow(ts[0], r.choice((Integer(2), Integer(3), S.NegativeOne, Rational(1, 2),
                                         syms[-1])))
        if k < 0.85:
            return r.choice((Abs, exp, re, im, conjugate))(Add(*ts) if r.random() < 0.5 else ts[0])
        return Add(Mul(*ts[:2]), *ts[2:]) if len(ts) > 2 else Mul(*ts)

    def chain(self):
        """Few symbols, facts about them (and about compounds of them),
        a proposition about a compound: the shape that gets definite answers."""
        r = self.r
        syms = r.sample(self.syms, r.choice((1, 2, 2, 3, 3, 4)))
        facts = [self.fact(s) for s in syms for _ in range(r.choice((1, 1, 2)))]
        if r.random() < 0.3:
            facts.append(self.fact(self.compound(syms)))
        if r.random() < 0.2 and len(syms) > 1:
            facts.append(getattr(Q, r.choice(RELS))(syms[0], syms[1]))
        if r.random() < 0.15:
            facts.append(getattr(Q, r.choice(RELS))(syms[0], r.choice((S.Zero, S.One, oo, -oo))))
        if r.random() < 0.15:
            facts = [Or(*facts[:2])] + facts[2:]
        p = self.fact(self.compound(syms) if r.random() < 0.8 else r.choice(syms))
        if r.random() < 0.15:
            p = (Or if r.random() < 0.5 else And)(p, self.fact(self.compound(syms)))
        return p, And(*facts)

    def sumprod(self):
        """Add/Mul of up to 12 symbols with one fact each."""
        r = self.r
        n = r.randint(2, 12)
        syms = [Symbol('t%d' % i) for i in range(n)]
        fam = r.sample(DERIVED + ('integer', 'even', 'rational', 'extended_real', 'zero'), 2)
        facts = [getattr(Q, r.choice(fam))(s) for s in syms]
        if r.random() < 0.2:
            facts[0] = Not(facts[0])
        e = (Add if r.random() < 0.5 else Mul)(*syms)
        if r.random() < 0.2:
            e = e * r.choice((Integer(-1), Integer(2), I))
        p = self.fact(e)
        return p, And(*facts)

    def query(self):
        r = self.r
        k = r.random()
        if k < 0.35:
            return self.chain()
        if k < 0.5:
            return self.sumprod()
        if k < 0.62:
            f, syms = self.wide()
            g = getattr(Q, r.choice(DERIVED))(r.choice(syms))
            if r.random() < 0.5:
                return g, f            # wide assumptions
            return (Not(f) if r.random() < 0.3 else f), g
        p = self.formula(r.choice((0, 0, 1, 2)), wide=r.random() < 0.1)
        if r.random() < 0.2:
            return p, True
        a = self.formula(r.choice((1, 1, 2)), wide=r.random() < 0.1)
        if r.random() < 0.6:
            a = And(*[self.atom() for _ in range(r.randint(1, 6))])
        return p, a


def queries(seed: int, n: int):
    g = Gen(seed)
    out = []
    while len(out) < n:
        try:
            p, a = g.query()
        except Exception:      # noqa: BLE001 - a SymPy constructor refused the draw
            continue
        if p in (True, False) or isinstance(p, bool) or p.is_Boolean is not True:
            continue
        out.append((p, a))
    return out


class _Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise _Timeout()


def _timed(fn, secs):
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(secs)
    try:
        return fn()
    except _Timeout:
        return "Timeout"
    finally:
        signal.alarm(0)


def answer(qs, timeout: int = 20, stream: int = 20):
    """Outcome strings ``(E, S1, S2, R)`` per query."""
    from harness.outcomes import outcome
    from satassume.engine import Engine
    from satassume.ref import ref_outcome
    res = []
    eng_s = None
    for i, (p, a) in enumerate(qs):
        if i % stream == 0:
            eng_s = Engine()
        e = _timed(lambda: outcome(p, a, Engine()), timeout)
        s1 = _timed(lambda: outcome(p, a, eng_s), timeout)
        s2 = _timed(lambda: outcome(p, a, eng_s), timeout)
        rr = _timed(lambda: ref_outcome(p, a), timeout)
        res.append((e, s1, s2, rr))
    return res


DEF = ("True", "False")


def classify(e, s1, s2, rr):
    """Finding kinds for one query's outcomes (empty: agreement)."""
    out = []
    eng = {"E": e, "S1": s1, "S2": s2}
    for k, v in eng.items():
        if v.startswith("Error") or v == "Timeout":
            out.append("%s-%s" % (k, v))
    if rr.startswith("Error") or rr == "Timeout":
        out.append("R-" + rr)
    vals = set(eng.values())
    if len(vals) > 1:
        out.append("engine-split")
    for k, v in eng.items():
        if v in DEF and rr in DEF and v != rr:
            out.append("wrong-%s" % k)
        elif v in DEF and rr == "None":
            out.append("more-%s" % k)
        elif (v == "ValueError") != (rr == "ValueError") and "None" not in (v, rr) \
                and not v.startswith("Error") and v != "Timeout" and rr != "Timeout":
            out.append("raise-%s" % k)
    return sorted(set(out))


def run(seed: int, n: int, out=None, timeout: int = 20):
    qs = queries(seed, n)
    t = time.time()
    res = answer(qs, timeout)
    stats = {"n": len(qs), "lost": 0, "definite": 0, "findings": 0}
    found = []
    for (p, a), r in zip(qs, res):
        kinds = classify(*r)
        if r[0] == "None" and r[3] in DEF:
            stats["lost"] += 1
        if r[0] in DEF:
            stats["definite"] += 1
        if kinds:
            stats["findings"] += 1
            found.append((kinds, p, a, r))
        if out is not None:
            out.write(json.dumps({"seed": seed, "p": srepr(p), "a": srepr(a), "r": r}) + "\n")
    stats["secs"] = round(time.time() - t, 1)
    return stats, found


def _seeds(s):
    a, _, b = s.partition("-")
    return range(int(a), int(b or a) + 1)


def diff(fa, fb):
    """Cross-version diff of two ``--out`` files over the same seeds."""
    A = [json.loads(l) for l in open(fa)]
    B = [json.loads(l) for l in open(fb)]
    assert len(A) == len(B), (len(A), len(B))
    cnt = {}
    for x, y in zip(A, B):
        assert x["p"] == y["p"] and x["a"] == y["a"]
        for i, col in enumerate("E S1 S2 R".split()):
            u, v = x["r"][i], y["r"][i]
            if u == v:
                continue
            kind = ("flip" if u in DEF and v in DEF else
                    "lost" if u in DEF or u == "ValueError" else
                    "gained" if v in DEF or v == "ValueError" else "other")
            key = "%s-%s" % (col, kind)
            cnt[key] = cnt.get(key, 0) + 1
            if kind != "gained":
                print(key, u, "->", v, "|", x["p"][:300], "|", x["a"][:300])
    print("diff summary", json.dumps(cnt, sort_keys=True), "of", len(A))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m harness.reffuzz")
    ap.add_argument("--seeds", default="0")
    ap.add_argument("-n", type=int, default=300)
    ap.add_argument("--out")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--diff", nargs=2)
    args = ap.parse_args(argv)
    if args.diff:
        diff(*args.diff)
        return 0
    out = open(args.out, "w") if args.out else None
    bad = 0
    for seed in _seeds(args.seeds):
        stats, found = run(seed, args.n, out, args.timeout)
        print("seed", seed, json.dumps(stats), flush=True)
        for kinds, p, a, r in found:
            print("  FINDING", kinds, r, "|", p, "|", a, flush=True)
        bad += len(found)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
