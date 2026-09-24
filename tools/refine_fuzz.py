#!/usr/bin/env python
"""Numeric fuzzer for the refine handlers.

Builds random expressions over the handler families, draws random consistent
assumption sets (unary predicates plus an occasional relation), refines under
the combined backend, and checks every rewrite at random numeric points that
satisfy the assumptions, evaluated at 20 digits in the complex plane.  SymPy's
own refine runs on the same inputs, so inherited upstream bugs can be told
apart from the handlers' own.  Reported categories: unsound rewrites (with the
counterexample), non-SymPy return values, crashes, and inputs where both fire
with different results.

Usage::

    PYTHONPATH=.:/path/to/sympy .venv/bin/python tools/refine_fuzz.py [seed] [cases] [--handlers handlers_v2]

A mismatch is evidence, not proof: a value that agrees to 7 digits passes, and
poles or removable singularities of the original can show up as spurious
mismatches, so read the counterexample before calling a rule wrong.
"""
from __future__ import annotations
import os, random, sys, time
if "--handlers" in sys.argv:
    i = sys.argv.index("--handlers"); os.environ["SATREFINE_HANDLERS"] = sys.argv[i + 1]; del sys.argv[i:i + 2]
from collections import Counter, defaultdict
from sympy import (Symbol, symbols, Q, I, pi, E, oo, S, nan, zoo, Rational, Integer, Float, Abs, arg, sign, re, im,
    conjugate, exp, log, sqrt, sin, cos, tan, cot, sec, csc, sinc, asin, acos, atan, atan2, sinh, cosh, tanh, coth,
    sech, csch, asinh, acosh, atanh, acoth, asech, acsch, floor, ceiling, frac, Mod, factorial, binomial,
    RisingFactorial, FallingFactorial, gamma, Min, Max, DiracDelta, KroneckerDelta, Heaviside, Pow, N)
from sympy.core.expr import Expr
from sympy.core.basic import Basic
from sympy import sympify
from sympy.functions.elementary.integers import frac as _frac
from sympy.assumptions.refine import refine as sympy_refine
from satrefine import refine as sat_refine, backend
from satrefine._upstream import handlers_dict
backend.set_backend("combined")

try:
    from sympy import Rem
except ImportError:
    Rem = None

x, y, z = symbols("x y z")
n, m, k = symbols("n m k")
i, j = symbols("i j")
SYMS = [x, y, z, n, m, k, i, j]

# --- assumption vocabulary: name -> (Q builder, numeric checker, sampler)
def c_real(v): return abs(complex(v).imag) < 1e-12
def c_pos(v): return c_real(v) and complex(v).real > 1e-9
def c_neg(v): return c_real(v) and complex(v).real < -1e-9
def c_zero(v): return abs(complex(v)) < 1e-12
def c_int(v): return c_real(v) and abs(complex(v).real - round(complex(v).real)) < 1e-9
def c_even(v): return c_int(v) and round(complex(v).real) % 2 == 0
def c_odd(v): return c_int(v) and round(complex(v).real) % 2 == 1
def c_imag(v): return abs(complex(v).real) < 1e-12 and abs(complex(v).imag) > 1e-9

PREDS = {
    "real": (Q.real, c_real),
    "positive": (Q.positive, c_pos),
    "negative": (Q.negative, c_neg),
    "nonnegative": (Q.nonnegative, lambda v: c_real(v) and complex(v).real > -1e-12),
    "nonpositive": (Q.nonpositive, lambda v: c_real(v) and complex(v).real < 1e-12),
    "nonzero": (Q.nonzero, lambda v: c_real(v) and not c_zero(v)),
    "zero": (Q.zero, c_zero),
    "integer": (Q.integer, c_int),
    "even": (Q.even, c_even),
    "odd": (Q.odd, c_odd),
    "imaginary": (Q.imaginary, c_imag),
    "complex": (Q.complex, lambda v: True),
    "rational": (Q.rational, c_int),  # sampled as integers, still rational
    "prime": (Q.prime, lambda v: c_int(v) and round(complex(v).real) in (2, 3, 5, 7, 11, 13)),
}
COMBOS = [(), ("real",), ("positive",), ("negative",), ("nonnegative",), ("nonpositive",), ("nonzero",), ("zero",),
          ("integer",), ("even",), ("odd",), ("imaginary",), ("complex",), ("prime",),
          ("positive", "integer"), ("negative", "integer"), ("odd", "positive"), ("even", "negative"),
          ("even", "positive"), ("odd", "negative"), ("real", "nonzero"), ("integer", "nonzero")]

def draw(combo, rng):
    """Draw a value satisfying every predicate in combo (rejection sampling)."""
    for _ in range(300):
        kind = rng.random()
        if "zero" in combo: v = Integer(0)
        elif any(p in combo for p in ("integer", "even", "odd", "prime", "rational")):
            v = Integer(rng.randint(-6, 6))
            if "even" in combo: v = Integer(2 * rng.randint(-3, 3))
            if "odd" in combo: v = Integer(2 * rng.randint(-3, 3) + 1)
            if "prime" in combo: v = Integer(rng.choice([2, 3, 5, 7, 11]))
        elif "imaginary" in combo: v = I * Float(rng.uniform(-3, 3))
        elif combo == () or combo == ("complex",):
            v = Float(rng.uniform(-3, 3)) + (I * Float(rng.uniform(-3, 3)) if kind < 0.5 else 0)
            if kind > 0.85: v = Integer(rng.randint(-3, 3))
        else:
            v = Float(rng.uniform(-3, 3)) if kind < 0.8 else Integer(rng.randint(-3, 3))
        if "positive" in combo: v = Abs(v) + (Rational(1, 10) if not c_int(v) else 1) if not c_pos(v) else v
        if "negative" in combo: v = -Abs(v) - (Rational(1, 10) if not c_int(v) else 1) if not c_neg(v) else v
        if all(PREDS[p][1](v) for p in combo):
            return v
    return None

# --- expression grammar
def atom(rng):
    return rng.choice([x, y, z, n, m, k, x, n])

def inner(rng, depth=0):
    r = rng.random()
    a, b = atom(rng), atom(rng)
    choices = [
        lambda: a, lambda: -a, lambda: a + b, lambda: a - b, lambda: a * b, lambda: a ** 2, lambda: a ** 3,
        lambda: 2 * a, lambda: a * pi, lambda: pi * a / 2, lambda: a + pi, lambda: a + pi / 2, lambda: a - pi,
        lambda: I * a, lambda: a + I * b, lambda: exp(a), lambda: sqrt(a), lambda: a ** b, lambda: a ** Rational(1, 2),
        lambda: a ** Rational(-1, 2), lambda: (a ** 2) ** Rational(1, 2), lambda: (a ** 3) ** Rational(1, 3),
        lambda: Abs(a), lambda: sign(a), lambda: conjugate(a), lambda: log(a), lambda: sin(a), lambda: cos(a),
        lambda: tan(a), lambda: a * pi + b, lambda: 2 * pi * a, lambda: a ** (-1), lambda: 1 / (a + 1),
        lambda: a + 1, lambda: a - 1, lambda: a * b * pi,
    ]
    return rng.choice(choices)()

OUTER = {
    "Abs": lambda e, rng: Abs(e), "arg": lambda e, rng: arg(e), "sign": lambda e, rng: sign(e),
    "re": lambda e, rng: re(e), "im": lambda e, rng: im(e), "conjugate": lambda e, rng: conjugate(e),
    "exp": lambda e, rng: exp(e), "log": lambda e, rng: log(e), "sqrt": lambda e, rng: sqrt(e),
    "Pow": lambda e, rng: Pow(e, rng.choice([Rational(1, 2), Rational(3, 2), Rational(1, 3), 2, 3, -1, Rational(-1, 2), atom(rng)]), evaluate=False)
                        if rng.random() < 0.5 else e ** rng.choice([Rational(1, 2), Rational(3, 2), Rational(1, 3), 2, -1, atom(rng)]),
    "PowE": lambda e, rng: Pow(E, e) if rng.random() < 0.5 else (-1) ** e,
    "sin": lambda e, rng: sin(e), "cos": lambda e, rng: cos(e), "tan": lambda e, rng: tan(e), "cot": lambda e, rng: cot(e),
    "sec": lambda e, rng: sec(e), "csc": lambda e, rng: csc(e), "sinc": lambda e, rng: sinc(e),
    "asin": lambda e, rng: asin(e), "acos": lambda e, rng: acos(e), "atan": lambda e, rng: atan(e),
    "asin_sin": lambda e, rng: asin(sin(e)), "acos_cos": lambda e, rng: acos(cos(e)), "atan_tan": lambda e, rng: atan(tan(e)),
    "atan2": lambda e, rng: atan2(e, inner(rng)),
    "sinh": lambda e, rng: sinh(e), "cosh": lambda e, rng: cosh(e), "tanh": lambda e, rng: tanh(e), "coth": lambda e, rng: coth(e),
    "sech": lambda e, rng: sech(e), "csch": lambda e, rng: csch(e),
    "asinh": lambda e, rng: asinh(e), "acosh": lambda e, rng: acosh(e), "atanh": lambda e, rng: atanh(e),
    "acoth": lambda e, rng: acoth(e), "asech": lambda e, rng: asech(e), "acsch": lambda e, rng: acsch(e),
    "asinh_sinh": lambda e, rng: asinh(sinh(e)), "acosh_cosh": lambda e, rng: acosh(cosh(e)), "atanh_tanh": lambda e, rng: atanh(tanh(e)),
    "log_exp": lambda e, rng: log(exp(e)), "exp_log": lambda e, rng: exp(log(e)),
    "floor": lambda e, rng: floor(e), "ceiling": lambda e, rng: ceiling(e), "frac": lambda e, rng: frac(e),
    "Mod": lambda e, rng: Mod(e, rng.choice([2, 3, atom(rng), 2 * atom(rng)])),
    "Rem": (lambda e, rng: Rem(e, rng.choice([2, 3, atom(rng)]))) if Rem else None,
    "factorial": lambda e, rng: factorial(e), "binomial": lambda e, rng: binomial(e, rng.choice([atom(rng), 1, 2, atom(rng) - 1])),
    "rf": lambda e, rng: RisingFactorial(e, rng.choice([atom(rng), 1, 2])), "ff": lambda e, rng: FallingFactorial(e, rng.choice([atom(rng), 1, 2])),
    "gamma": lambda e, rng: gamma(e),
    "Min": lambda e, rng: Min(e, inner(rng)), "Max": lambda e, rng: Max(e, inner(rng)),
    "Min3": lambda e, rng: Min(e, atom(rng), atom(rng)), "Max3": lambda e, rng: Max(e, atom(rng), atom(rng)),
    "Heaviside": lambda e, rng: Heaviside(e), "DiracDelta": lambda e, rng: DiracDelta(e),
    "KroneckerDelta": lambda e, rng: KroneckerDelta(atom(rng), atom(rng)),
    "conj_mul": lambda e, rng: e * conjugate(e) if rng.random() < 0.5 else atom(rng) * conjugate(atom(rng)),
    "Abs_pow": lambda e, rng: Abs(e) ** rng.choice([2, 4, 3, atom(rng)]),
}
OUTER = {k_: v for k_, v in OUTER.items() if v is not None}

def relations(rng, syms):
    """A random relational assumption over the sampled symbols, or None."""
    if len(syms) < 1 or rng.random() < 0.7:
        return None
    a = rng.choice(syms); b = rng.choice(syms + [S.Zero, S.One, pi / 2, -pi / 2])
    if a == b: return None
    return rng.choice([Q.gt, Q.ge, Q.lt, Q.le, Q.eq, Q.ne])(a, b)

def rel_holds(rel, sample):
    """Decide the relation at a numeric sample (True, False, or None if undecidable).

    Both sides are evaluated numerically; an order relation needs both real.
    (SymPy leaves ``Q.lt(-3, 0).doit()`` unevaluated, so deciding it
    symbolically never answered True and no case with a relation was checked.)
    """
    try:
        lhs, rhs = (complex(N(side.subs(sample), 20)) for side in rel.arguments)
    except (TypeError, ValueError, AttributeError):
        return None
    tol = 1e-12 * max(1.0, abs(lhs), abs(rhs))
    if rel.function == Q.eq: return abs(lhs - rhs) <= tol
    if rel.function == Q.ne: return abs(lhs - rhs) > tol
    if abs(lhs.imag) > tol or abs(rhs.imag) > tol: return False
    a, b = lhs.real, rhs.real
    return {Q.gt: a > b + tol, Q.ge: a >= b - tol, Q.lt: a < b - tol, Q.le: a <= b + tol}.get(rel.function)

def numeric(e):
    try:
        v = N(e, 20)
    except Exception:
        return "error"
    if not isinstance(v, Expr):
        return "unevaluated"
    if v.has(nan) or v is nan: return "nan"
    if v.has(zoo) or v.has(oo): return "inf"
    try:
        return complex(v)
    except Exception:
        return "unevaluated"

def agree(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return a == b or (a in ("error", "unevaluated") or b in ("error", "unevaluated"))
    try:
        return abs(a - b) <= 1e-7 * max(1.0, abs(a), abs(b))
    except OverflowError:
        return True  # both astronomically large: treat as agreeing rather than crash

def check(expr, refined, assumptions, combos, rel, rng, samples=12):
    """Return (n_checked, counterexample or None)."""
    syms = sorted(expr.free_symbols | refined.free_symbols, key=str)
    checked = 0
    for _ in range(200):
        sample = {}
        for s in syms:
            v = draw(combos.get(s, ()), rng)
            if v is None: return checked, None
            sample[s] = v
        if rel is not None and rel_holds(rel, sample) is not True:
            continue
        try:
            a, b = numeric(expr.subs(sample)), numeric(refined.subs(sample))
        except Exception:
            continue
        if a in ("error", "unevaluated", "nan", "inf") and b in ("error", "unevaluated", "nan", "inf"):
            continue
        if not agree(a, b):
            return checked, (sample, a, b)
        checked += 1
        if checked >= samples: break
    return checked, None

def main(seed=0, cases=3000):
    fired = Counter(); tried = Counter(); unsound = []; crashes = []; sympy_unsound = []; nonbasic = []
    sat_only = Counter(); sympy_only = Counter(); differ = []
    t0 = time.time()
    for case in range(cases):
        # one generator stream per case, so every handler package sees the same inputs
        # regardless of how the previous case's check consumed randomness
        rng = random.Random(seed * 1000003 + case)
        head = rng.choice(list(OUTER))
        try:
            e = OUTER[head](inner(rng), rng)
        except Exception:
            continue
        if not isinstance(e, Expr): continue
        syms = sorted(e.free_symbols, key=str)
        if not syms: continue
        combos = {s: rng.choice(COMBOS) for s in syms}
        # drop symbols whose combo has no sample
        if any(draw(c, rng) is None for c in combos.values()): continue
        facts = [PREDS[p][0](s) for s, c in combos.items() for p in c]
        rel = relations(rng, syms)
        if rel is not None: facts.append(rel)
        assumptions = S.true if not facts else facts[0] if len(facts) == 1 else facts[0] & facts[1] if len(facts) == 2 else __import__("functools").reduce(lambda a, b: a & b, facts)
        tried[head] += 1
        try:
            r = sat_refine(e, assumptions)
            if not isinstance(r, Basic):
                nonbasic.append((head, e, assumptions, repr(r)))
                r = sympify(r)
        except ValueError as ex:
            if "nconsistent" in str(ex): continue
            crashes.append((head, e, assumptions, f"{type(ex).__name__}: {ex}")); continue
        except Exception as ex:
            crashes.append((head, e, assumptions, f"{type(ex).__name__}: {str(ex)[:80]}")); continue
        try:
            rs = sympify(sympy_refine(e, assumptions))
        except Exception as ex:
            rs = None
        if r != e:
            fired[head] += 1
            n_ok, ce = check(e, r, assumptions, combos, rel, rng)
            if ce: unsound.append((head, e, assumptions, r, ce))
        if rs is not None and rs != e:
            n_ok, ce = check(e, rs, assumptions, combos, rel, rng)
            if ce: sympy_unsound.append((head, e, assumptions, rs, ce))
        if rs is not None:
            if r != e and rs == e: sat_only[head] += 1
            if r == e and rs != e: sympy_only[head] += 1
            if r != e and rs != e and r != rs: differ.append((head, e, assumptions, r, rs))
    dt = time.time() - t0
    print(f"seed={seed} cases={cases} time={dt:.0f}s tried={sum(tried.values())} fired={sum(fired.values())}")
    print("\n== fires by head (fired/tried; satrefine-only fires; sympy-only fires) ==")
    for h in sorted(tried, key=lambda h: -tried[h]):
        print(f"  {h:15} {fired[h]:4}/{tried[h]:<4} sat_only={sat_only[h]:<3} sympy_only={sympy_only[h]:<3}")
    print(f"\n== satrefine UNSOUND rewrites: {len(unsound)} ==")
    seen = set()
    for head, e, a, r, (sample, va, vb) in unsound:
        key = (head, str(e)[:40])
        if key in seen: continue
        seen.add(key)
        print(f"  [{head}] refine({e}, {a}) -> {r}\n      at {sample}: orig={va} refined={vb}")
    print(f"\n== SymPy's own refine unsound on the same inputs: {len(sympy_unsound)} ==")
    seen = set()
    for head, e, a, r, (sample, va, vb) in sympy_unsound[:15]:
        key = (head, str(e)[:40])
        if key in seen: continue
        seen.add(key)
        print(f"  [{head}] sympy.refine({e}, {a}) -> {r}\n      at {sample}: orig={va} refined={vb}")
    print(f"\n== satrefine returned a non-SymPy object: {len(nonbasic)} ==")
    for head, e, a, r in nonbasic[:5]:
        print(f"  [{head}] refine({e}, {a}) -> {r}")
    print(f"\n== crashes: {len(crashes)} ==")
    seen = Counter()
    for head, e, a, msg in crashes:
        seen[(head, msg.split(':')[0])] += 1
    for (head, msg), c in seen.most_common(20):
        ex = next(cr for cr in crashes if cr[0] == head and cr[3].startswith(msg))
        print(f"  {c:3}x [{head}] {ex[3][:100]}\n        e.g. refine({ex[1]}, {ex[2]})")
    print(f"\n== both fire, different results: {len(differ)} (first 12) ==")
    for head, e, a, r, rs in differ[:12]:
        print(f"  [{head}] {e} | {a}\n      satrefine: {r}\n      sympy:     {rs}")

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 0, int(sys.argv[2]) if len(sys.argv) > 2 else 3000)
