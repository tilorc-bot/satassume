#!/usr/bin/env python
"""Numeric fuzzer for the refine handlers.

Builds random expressions over the handler families, draws random consistent
assumption sets (unary predicates plus an occasional relation), refines under
the combined backend (or ``SATREFINE_BACKEND``), and checks every rewrite at random numeric points that
satisfy the assumptions, evaluated at 20 digits in the complex plane.  SymPy's
own refine runs on the same inputs, so inherited upstream bugs can be told
apart from the handlers' own.  Reported categories: unsound rewrites (with the
counterexample), non-SymPy return values, crashes, and inputs where both fire
with different results.

Usage::

    PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satrefine.tools.refine_fuzz [seed] [cases] [--handlers handlers_v2]

A mismatch is evidence, not proof: a value that agrees to 7 digits passes, and
poles or removable singularities of the original can show up as spurious
mismatches, so read the counterexample before calling a rule wrong.
"""
from __future__ import annotations
import importlib, os, random, sys, time
if "--handlers" in sys.argv:
    i = sys.argv.index("--handlers")
    if __name__ == "__main__" and "satrefine" in sys.modules:   # python -m: satrefine is loaded already
        from satrefine.tools import rerun_with; rerun_with(handlers=sys.argv[i + 1])
    os.environ["SATREFINE_HANDLERS"] = sys.argv[i + 1]; del sys.argv[i:i + 2]
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
import satrefine
from satrefine import refine as sat_refine
from satrefine.identities.compat import backend
from satrefine._upstream import handlers_dict
backend.set_backend(os.environ.get(backend.ENV_VAR, "combined"))   # SATREFINE_BACKEND, default combined

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
    checked_cases = unchecked = 0  # fired cases checked at >= 1 point / at none
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
            elif n_ok: checked_cases += 1
            else: unchecked += 1
        if rs is not None and rs != e:
            n_ok, ce = check(e, rs, assumptions, combos, rel, rng)
            if ce: sympy_unsound.append((head, e, assumptions, rs, ce))
        if rs is not None:
            if r != e and rs == e: sat_only[head] += 1
            if r == e and rs != e: sympy_only[head] += 1
            if r != e and rs != e and r != rs: differ.append((head, e, assumptions, r, rs))
    dt = time.time() - t0
    print(f"seed={seed} cases={cases} time={dt:.0f}s tried={sum(tried.values())} fired={sum(fired.values())} "
          f"checked={checked_cases} unchecked={unchecked} unsound={len(unsound)}")
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


# ---------------------------------------------------------------------------
# Matrix expressions (``--matrices``)
# ---------------------------------------------------------------------------
# A case stream of its own: the scalar grammar above is untouched, so a scalar
# seed generates the same cases as before.  Sample points are explicit small
# matrices (0x0 to 3x3, exact rational and Gaussian-rational entries) built to
# satisfy each matrix symbol's predicates and verified against a numeric
# definition of every predicate before use (rejection sampling), together with
# values for the scalar factor, the element indices and symbolic sizes.

from sympy import (Adjoint, Determinant, HadamardProduct, Identity, ImmutableMatrix, Inverse, MatMul, MatrixSymbol,
                   OneMatrix, Trace, Transpose, ZeroMatrix, expand)
from sympy.matrices.expressions.matexpr import MatrixExpr


def _zero(e):
    return expand(e) == 0


def _same(A, B):
    return A.shape == B.shape and all(_zero(a - b) for a, b in zip(A, B))


def _eye(k):
    return ImmutableMatrix.eye(k)


def _sq(M):
    return M.rows == M.cols


def _upper(M):
    return _sq(M) and all(_zero(M[r, c]) for r in range(M.rows) for c in range(r))


def _lower(M):
    return _sq(M) and all(_zero(M[r, c]) for r in range(M.rows) for c in range(r + 1, M.cols))


def _det(M):
    return expand(M.det()) if M.rows else S.One


def _pd(M):
    if not (_sq(M) and _same(M, M.T) and all(_zero(im(e)) for e in M)):
        return False
    return all(expand(M[:r, :r].det()) > 0 for r in range(1, M.rows + 1))


MPREDS = {  # name -> (Q builder, numeric definition on an explicit matrix)
    "zero": (Q.zero, lambda M: all(_zero(e) for e in M)),
    "square": (Q.square, _sq),
    "symmetric": (Q.symmetric, lambda M: _sq(M) and _same(M, M.T)),
    "diagonal": (Q.diagonal, lambda M: _upper(M) and _lower(M)),
    "orthogonal": (Q.orthogonal, lambda M: _sq(M) and _same(M.T * M, _eye(M.rows)) and _same(M * M.T, _eye(M.rows))),
    "unitary": (Q.unitary, lambda M: _sq(M) and _same(M.H * M, _eye(M.rows)) and _same(M * M.H, _eye(M.rows))),
    "normal": (Q.normal, lambda M: _sq(M) and _same(M * M.H, M.H * M)),
    "invertible": (Q.invertible, lambda M: _sq(M) and not _zero(_det(M))),
    "singular": (Q.singular, lambda M: _sq(M) and _zero(_det(M))),
    "fullrank": (Q.fullrank, lambda M: M.rank() == min(M.shape)),
    "upper_triangular": (Q.upper_triangular, _upper),
    "lower_triangular": (Q.lower_triangular, _lower),
    "triangular": (Q.triangular, lambda M: _upper(M) or _lower(M)),
    "unit_triangular": (Q.unit_triangular, lambda M: (_upper(M) or _lower(M)) and all(_zero(M[r, r] - 1) for r in range(M.rows))),
    "positive_definite": (Q.positive_definite, _pd),
    "real_elements": (Q.real_elements, lambda M: all(_zero(im(e)) for e in M)),
    "integer_elements": (Q.integer_elements, lambda M: all(expand(e).is_Integer for e in M)),
    "complex_elements": (Q.complex_elements, lambda M: True),
}
# Per square matrix symbol; each combination is satisfiable at every size 1..3.
MCOMBOS = [(), (), ("zero",), ("symmetric",), ("diagonal",), ("orthogonal",), ("orthogonal", "real_elements"),
           ("unitary",), ("unitary", "real_elements"), ("invertible",), ("singular",), ("unit_triangular",),
           ("upper_triangular",), ("lower_triangular",), ("triangular",), ("positive_definite",), ("real_elements",),
           ("symmetric", "real_elements"), ("diagonal", "invertible"), ("diagonal", "singular"),
           ("symmetric", "singular"), ("upper_triangular", "singular"), ("normal",), ("integer_elements",),
           ("fullrank",), ("symmetric", "orthogonal"), ("diagonal", "unitary"), ("complex_elements",),
           ("orthogonal", "unitary"), ("symmetric", "unitary"), ("diagonal", "real_elements"), ("square",)]
RCOMBOS = [(), (), ("zero",), ("real_elements",), ("integer_elements",), ("fullrank",), ("complex_elements",)]
SCALAR_COMBOS = [(), ("zero",), ("zero",), ("positive",), ("real",), ("nonzero",), ("imaginary",), ("integer",), ("negative",)]
INDEX_COMBOS = [(), ("integer",), ("integer",), ("nonnegative", "integer"), ("negative", "integer"),
                ("positive", "integer"), ("nonzero", "integer"), ("zero",)]
SIZE_COMBOS = [(), ("positive",), ("positive", "integer"), ("nonnegative", "integer"), ("nonzero",)]

_msn, _msp = Symbol("n"), Symbol("p")          # symbolic sizes
_mc, _mi, _mj = Symbol("c"), Symbol("i"), Symbol("j")
SIZE_SYMS, INDEX_SYMS = (_msn, _msp), (_mi, _mj)


def _gauss(rng, real):
    re_ = Integer(rng.randint(-3, 3))
    return re_ if real or rng.random() < 0.4 else re_ + I * Integer(rng.randint(-3, 3))


def _block_diag(blocks, k):
    M = [[S.Zero] * k for _ in range(k)]
    at = 0
    for b in blocks:
        for r in range(b.rows):
            for c_ in range(b.cols):
                M[at + r][at + c_] = b[r, c_]
        at += b.rows
    return ImmutableMatrix(k, k, [e for row in M for e in row]) if k else ImmutableMatrix.zeros(0, 0)


def _perm(rng, k):
    idx = list(range(k))
    rng.shuffle(idx)
    return ImmutableMatrix(k, k, lambda r, c_: 1 if idx[r] == c_ else 0) if k else ImmutableMatrix.zeros(0, 0)


_R = Rational
ORTH2 = [ImmutableMatrix([[a, -b], [b, a]]) for a, b in ((_R(3, 5), _R(4, 5)), (0, 1), (_R(5, 13), _R(12, 13)))] + \
        [ImmutableMatrix([[a, b], [b, -a]]) for a, b in ((_R(3, 5), _R(4, 5)), (0, 1))]
# complex orthogonal (M.T*M = I), not unitary
CORTH2 = [ImmutableMatrix([[_R(5, 4), 3 * I / 4], [-3 * I / 4, _R(5, 4)]]),
          ImmutableMatrix([[_R(5, 3), 4 * I / 3], [-4 * I / 3, _R(5, 3)]]),
          ImmutableMatrix([[_R(5, 4), 3 * I / 4], [3 * I / 4, -_R(5, 4)]])]
# unitary (M.H*M = I), not orthogonal
UNIT2 = [ImmutableMatrix([[_R(3, 5), 4 * I / 5], [4 * I / 5, _R(3, 5)]]),
         ImmutableMatrix([[_R(3, 5), -4 * I / 5], [-4 * I / 5, _R(3, 5)]])]


def _blocks(rng, k, pool, ones):
    out, left = [], k
    while left:
        if left >= 2 and pool and rng.random() < 0.7:
            out.append(rng.choice(pool)); left -= 2
        else:
            out.append(ImmutableMatrix([[rng.choice(ones)]])); left -= 1
    return out


def _gen(rng, r, c_, kind):
    """A random candidate matrix of shape (r, c_) of a given construction."""
    real = rng.random() < 0.5
    generic = lambda re_=real: ImmutableMatrix(r, c_, lambda a, b: _gauss(rng, re_))  # noqa: E731
    if kind == "generic":
        return generic()
    if kind == "zero":
        return ImmutableMatrix.zeros(r, c_)
    if r != c_:
        return generic()
    k = r
    if kind == "identity":
        return _eye(k)
    if kind == "diagonal":
        return ImmutableMatrix.diag(*[_gauss(rng, real) for _ in range(k)]) if k else ImmutableMatrix.zeros(0, 0)
    if kind == "symmetric":
        G = generic()
        return G + G.T
    if kind == "rank1":
        v = ImmutableMatrix(k, 1, lambda a, b: _gauss(rng, real))
        return v * v.T if rng.random() < 0.5 else v * ImmutableMatrix(1, k, lambda a, b: _gauss(rng, real))
    if kind in ("orthogonal", "unitary"):
        if kind == "orthogonal":
            pool, ones = ORTH2 + (CORTH2 if rng.random() < 0.5 else []), [1, -1]
        else:
            pool, ones = ORTH2 + UNIT2, [1, -1, I, -I]
        B = _block_diag(_blocks(rng, k, pool, ones), k)
        P = _perm(rng, k)
        return P * B * P.T if rng.random() < 0.5 else P * B
    if kind == "singular":
        G = generic()
        if k == 0:
            return G
        rows = [list(G.row(t)) for t in range(k)]
        src, dst = rng.randrange(k), rng.randrange(k)
        f = _gauss(rng, True)
        rows[dst] = [f * e for e in rows[src]] if src != dst else [S.Zero] * k
        return ImmutableMatrix(rows)
    if kind in ("upper", "lower", "unit_upper", "unit_lower"):
        M = [[_gauss(rng, real) for _ in range(k)] for _ in range(k)]
        for a in range(k):
            for b in range(k):
                if (kind.endswith("upper") and a > b) or (kind.endswith("lower") and a < b):
                    M[a][b] = S.Zero
            if kind.startswith("unit"):
                M[a][a] = S.One
        return ImmutableMatrix(M) if k else ImmutableMatrix.zeros(0, 0)
    if kind == "pd":
        G = ImmutableMatrix(k, k, lambda a, b: Integer(rng.randint(-2, 2)))
        return G.T * G + _eye(k)
    return generic()


_KINDS = ["generic", "zero", "identity", "diagonal", "symmetric", "rank1", "orthogonal", "unitary", "singular",
          "upper", "lower", "unit_upper", "unit_lower", "pd"]


def mdraw(combo, shape, rng, tries=400):
    """An explicit matrix of ``shape`` satisfying every predicate in ``combo``, or None."""
    r, c_ = shape
    for _ in range(tries):
        M = _gen(rng, r, c_, rng.choice(_KINDS))
        if all(MPREDS[p][1](M) for p in combo):
            return M
    return None


# --- grammar: square X, Y (k x k); rectangular R, R2 (k x l) and W (l x k); scalar c; indices i, j

def _mat_inner(rng, X, Y, c):
    choices = [
        lambda: X, lambda: Y, lambda: X.T, lambda: -X, lambda: 2 * X, lambda: c * X, lambda: X * Y,
        lambda: X * Y * X, lambda: X.T * Y * X, lambda: Inverse(X), lambda: X + Y, lambda: X - X.T,
        lambda: MatMul(X, X), lambda: X.T * X, lambda: X * X.T, lambda: Adjoint(X), lambda: Adjoint(X) * X,
        lambda: X * Adjoint(X), lambda: MatMul(Inverse(X), X), lambda: MatMul(X, Inverse(X)),
        lambda: HadamardProduct(X, Y), lambda: X ** 2, lambda: X * Y.T, lambda: Inverse(X.T),
        lambda: Inverse(X * Y), lambda: c * X * Y, lambda: X + Y + X.T, lambda: X - X, lambda: Transpose(X * Y),
    ]
    return rng.choice(choices)()


def _index(rng, k):
    if rng.random() < 0.5:
        return rng.choice(INDEX_SYMS)
    return Integer(rng.choice([0, 1, -1, 2, -2]) if not isinstance(k, int) else rng.randrange(-k, k) if k else 0)


MAT_OUTER = {
    "Transpose": lambda e, g: Transpose(e),
    "Inverse": lambda e, g: Inverse(e),
    "Determinant": lambda e, g: Determinant(e),
    "Trace": lambda e, g: Trace(e),
    "MatAdd": lambda e, g: e + g.inner(),
    "MatAdd3": lambda e, g: e + g.inner() + g.inner(),
    "MatMul": lambda e, g: e * g.inner(),
    "MatMul3": lambda e, g: e * g.inner() * g.inner(),
    "scalar": lambda e, g: g.c * e,
    "Hadamard": lambda e, g: HadamardProduct(e, g.inner()),
    "MatrixElement": lambda e, g: e[_index(g.rng, g.k), _index(g.rng, g.k)],
    "Adjoint": lambda e, g: Adjoint(e),
    "Trace_sum": lambda e, g: Trace(e + g.inner()),
    "Det_prod": lambda e, g: Determinant(e * g.inner()),
    "Inverse_prod": lambda e, g: Inverse(g.X * g.Y),
    "rect": None,  # below
}


def _rect_expr(g):
    R, R2, W, X = g.R, g.R2, g.W, g.X
    choices = [
        lambda: Transpose(R), lambda: R.T, lambda: R + R2, lambda: HadamardProduct(R, R2), lambda: R * W,
        lambda: W * R, lambda: g.c * R, lambda: R[_index(g.rng, g.k), _index(g.rng, g.l)], lambda: Transpose(R * W),
        lambda: Trace(R * W), lambda: Determinant(R * W), lambda: R.T * X * R, lambda: Transpose(R.T * X * R),
        lambda: R * W * X, lambda: X * R * W, lambda: Transpose(R + R2), lambda: R - R, lambda: R * (W * R),
        lambda: (R * W)[_index(g.rng, g.k), _index(g.rng, g.k)], lambda: Inverse(R * W), lambda: Adjoint(R) * R,
    ]
    return g.rng.choice(choices)()


class _MatCase:
    """The symbols of one matrix case."""

    def __init__(self, rng):
        self.rng = rng
        self.k = rng.choice([1, 2, 2, 3, 3, _msn])
        self.l = rng.choice([1, 2, 3, _msp]) if rng.random() < 0.8 else self.k
        k, l = self.k, self.l
        self.X, self.Y = MatrixSymbol("X", k, k), MatrixSymbol("Y", k, k)
        self.R, self.R2 = MatrixSymbol("R", k, l), MatrixSymbol("R2", k, l)
        self.W = MatrixSymbol("W", l, k)
        self.c = _mc

    def inner(self):
        if self.rng.random() < 0.25:          # a bare symbol: what most rows are stated for
            return self.rng.choice([self.X, self.Y])
        return _mat_inner(self.rng, self.X, self.Y, self.c)


def mat_generate(seed, case):
    """Matrix case ``case`` of ``seed``: (head, expr, assumptions, combos, rel) or None.

    ``combos`` maps every free symbol of ``expr`` (matrix, scalar, index and
    size symbols) to its predicate names; ``rel`` is a relation between the
    indices or None.  The stream is separate from the scalar one.
    """
    import functools
    rng = random.Random(f"matrix-{seed}-{case}")
    g = _MatCase(rng)
    head = rng.choice(list(MAT_OUTER))
    try:
        e = _rect_expr(g) if head == "rect" else MAT_OUTER[head](g.inner(), g)
    except Exception:
        return None
    if not isinstance(e, Basic) or not e.free_symbols:
        return None
    free = set(e.free_symbols)
    free |= {d for s in e.atoms(MatrixSymbol) for d in s.shape if d in SIZE_SYMS}  # MatrixSymbol hides its size
    combos = {}
    for s in sorted(free, key=str):
        if isinstance(s, MatrixSymbol):
            combos[s] = rng.choice(MCOMBOS if s.name in ("X", "Y") else RCOMBOS)
        elif s in SIZE_SYMS:
            combos[s] = rng.choice(SIZE_COMBOS)
        elif s in INDEX_SYMS:
            combos[s] = rng.choice(INDEX_COMBOS)
        else:
            combos[s] = rng.choice(SCALAR_COMBOS)
    facts = []
    for s, combo in combos.items():
        table = MPREDS if isinstance(s, MatrixSymbol) else PREDS
        facts += [table[p][0](s) for p in combo]
    rel = None
    idx = [s for s in INDEX_SYMS if s in combos]
    if idx and rng.random() < 0.4:
        a = rng.choice(idx)
        b = rng.choice([t for t in idx if t != a] + [S.Zero, S.One])
        rel = rng.choice([Q.gt, Q.ge, Q.lt, Q.le, Q.eq, Q.ne])(a, b)
        facts.append(rel)
    assumptions = S.true if not facts else functools.reduce(lambda a, b: a & b, facts)
    return head, e, assumptions, combos, rel


def _sizes_of(combos):
    """Symbolic size symbols and the index symbols with the dimension they index."""
    return [s for s in combos if s in SIZE_SYMS]


def mat_point(combos, rel, rng):
    """One random point satisfying ``combos`` and ``rel``: {symbol: value}, or None.

    Sizes first (0 to 3), then scalars, indices (integers that are valid
    indices, negative ones wrapping, of every dimension in play) and matrices of
    the substituted shapes.
    """
    pt = {}
    for s in combos:
        if s in SIZE_SYMS:
            vals = [Integer(v) for v in range(4) if all(PREDS[p][1](Integer(v)) for p in combos[s])]
            if not vals:
                return None
            pt[s] = rng.choice(vals)
    dims = [int(d.xreplace(pt)) for s in combos if isinstance(s, MatrixSymbol) for d in s.shape]
    lim = min(dims) if dims else 3
    for s, combo in combos.items():
        if s in INDEX_SYMS:
            vals = [Integer(v) for v in range(-lim, lim) if all(PREDS[p][1](Integer(v)) for p in combo)]
            if not vals:
                return None
            pt[s] = rng.choice(vals)
        elif not isinstance(s, MatrixSymbol) and s not in SIZE_SYMS:
            v = draw(combo, rng)
            if v is None:
                return None
            pt[s] = v
    for s, combo in combos.items():
        if isinstance(s, MatrixSymbol):
            shape = tuple(int(d.xreplace(pt)) for d in s.shape)
            M = mdraw(combo, shape, rng)
            if M is None:
                return None
            pt[s] = M
    if rel is not None and rel_holds(rel, {s: v for s, v in pt.items() if not isinstance(s, MatrixSymbol)}) is not True:
        return None
    return pt


def mat_points(combos, rel, rng, count=12, tries=60):
    pts = []
    for _ in range(tries):
        if len(pts) >= count:
            break
        p = mat_point(combos, rel, rng)
        if p is not None:
            pts.append(p)
    return pts


class _Unsupported(Exception):
    pass


def _explicit(node, mats, scal):
    """``node`` evaluated with explicit matrices, operation by operation.

    Every matrix operation is done on explicit matrices (so no symbolic rule of
    SymPy's, such as ``det(ZeroMatrix(0, 0)) = 0`` or ``0*X -> ZeroMatrix``,
    decides a value).  Raises ``_Unsupported`` for a node it does not know.
    """
    from sympy import MatAdd, MatPow, Sum
    from sympy.matrices.expressions.matexpr import MatrixElement as ME
    ev = lambda a: _explicit(a, mats, scal)  # noqa: E731
    if isinstance(node, MatrixSymbol):
        M = mats.get(node.name)
        if M is None or tuple(d.xreplace(scal) for d in node.shape) != M.shape:
            raise ValueError("shape")
        return M
    if isinstance(node, (ZeroMatrix, Identity, OneMatrix)):
        node = node.xreplace(scal)
        if not all(d.is_Integer for d in node.shape):
            raise _Unsupported
        return ImmutableMatrix(node.as_explicit())
    if isinstance(node, MatAdd):
        out = ev(node.args[0])
        for a in node.args[1:]:
            out = out + ev(a)
        return out
    if isinstance(node, MatMul):
        out = S.One
        for a in node.args:
            out = out * ev(a)
        return out
    if isinstance(node, MatPow):
        return ev(node.base) ** ev(node.exp)
    if isinstance(node, Inverse):
        return ev(node.arg).inv()          # a singular matrix raises: undefined, as it should
    if isinstance(node, Transpose):
        return ev(node.arg).T
    if isinstance(node, Adjoint):
        return ev(node.arg).H
    if isinstance(node, HadamardProduct):
        out = ev(node.args[0])
        for a in node.args[1:]:
            out = out.multiply_elementwise(ev(a))
        return out
    if isinstance(node, Determinant):
        M = ev(node.arg)
        return M.det() if M.rows else S.One
    if isinstance(node, Trace):
        M = ev(node.arg)
        return M.trace() if M.rows else S.Zero
    if isinstance(node, ME):
        M, i, j = ev(node.parent), ev(node.i), ev(node.j)
        if not (i.is_Integer and j.is_Integer and -M.rows <= i < M.rows and -M.cols <= j < M.cols):
            raise ValueError("index out of range")
        return M[int(i), int(j)]
    if isinstance(node, Sum):
        raise _Unsupported
    if isinstance(node, MatrixExpr):
        raise _Unsupported
    if not node.args or not node.has(MatrixSymbol, ZeroMatrix, Identity, OneMatrix):
        return node.xreplace(scal)
    return node.func(*[ev(a) for a in node.args])


def mat_value(e, pt):
    """The numeric value of ``e`` at ``pt``: a complex, a ('M', shape, values) triple, or a failure string."""
    try:
        mats = {s.name: v for s, v in pt.items() if isinstance(s, MatrixSymbol)}
        scal = {s: v for s, v in pt.items() if not isinstance(s, MatrixSymbol)}
        try:
            v = _explicit(e, mats, scal)
        except _Unsupported:
            v = _mat_value_doit(e, pt, mats)
        if isinstance(v, str):
            return v
        if isinstance(v, MatrixExpr) or getattr(v, "is_Matrix", False):
            v = ImmutableMatrix(v.as_explicit()) if isinstance(v, MatrixExpr) else ImmutableMatrix(v)
            vals = tuple(numeric(x) for x in v)
            bad = [x for x in vals if isinstance(x, str)]
            return bad[0] if bad else ("M", v.shape, vals)
        return numeric(v)
    except Exception:
        return "error"


def _mat_value_doit(e, pt, byname):
    """Fallback for nodes ``_explicit`` does not know (``Sum``): substitute, then ``doit``."""
    # sizes first (they are part of a MatrixSymbol), then everything else in one
    # simultaneous replacement, so no symbolic cancellation happens between the steps
    e1 = e.xreplace({s: v for s, v in pt.items() if s in SIZE_SYMS})
    rep = {s: v for s, v in pt.items() if not isinstance(s, MatrixSymbol) and s not in SIZE_SYMS}
    for ms in e1.atoms(MatrixSymbol):
        M = byname.get(ms.name)
        if M is None or tuple(ms.shape) != M.shape:
            return "error"
        rep[ms] = M
    for sm in e1.atoms(ZeroMatrix, Identity, OneMatrix):
        if all(d.is_Integer for d in sm.shape):
            rep[sm] = ImmutableMatrix(sm.as_explicit())
    return e1.xreplace(rep).doit()


def mat_agree(a, b):
    if isinstance(a, tuple) and isinstance(b, tuple):
        return a[1] == b[1] and all(agree(x, y) for x, y in zip(a[2], b[2]))
    if isinstance(a, tuple) or isinstance(b, tuple):
        return False
    return agree(a, b)


def mat_compare(left, right, points, ref=None):
    """(n_checked, counterexample or None): ``left`` and ``right`` at ``points``.

    A point counts as checked only when both sides have a finite value there.
    A point where ``left`` (the input), or ``ref`` if given (the input when two
    rewrites are compared), is undefined is skipped; one where only ``right``
    is undefined is a counterexample.
    """
    bad = ("error", "unevaluated", "nan", "inf")
    checked = 0
    for pt in points:
        if ref is not None and mat_value(ref, pt) in bad:
            continue
        a, b = mat_value(left, pt), mat_value(right, pt)
        if a in bad:
            continue
        if b in bad or not mat_agree(a, b):
            return checked, (pt, a, b)
        checked += 1
    return checked, None


class MatrixRowCoverage:
    """Counts, per row of ``satrefine.identities.compat.matrices``, how often it fired.

    Inside the ``with`` block every matrix key's handler is wrapped; when it
    returns a rewrite, the first row that alone gives the same rewrite is
    credited.  (Only for the ``handlers_identities`` package.)
    """

    def __init__(self):
        self.counts = Counter()
        self.saved = {}

    def __enter__(self):
        import importlib
        from satrefine.identities.core.rewrite import rule_handler
        mod = importlib.import_module("satrefine.identities.compat.matrices")
        tables = {"Determinant": mod.DETERMINANT, "HadamardProduct": mod.HADAMARD, "Inverse": mod.INVERSE,
                  "MatAdd": mod.MATADD, "MatMul": mod.MATMUL, "MatrixElement": mod.MATRIXELEMENT,
                  "Trace": mod.TRACE, "Transpose": mod.TRANSPOSE}
        self.all_rows = [row for rows in tables.values() for row in rows]
        for key, rows in tables.items():
            original = handlers_dict[key]
            singles = [(row, rule_handler([row])) for row in rows]

            def wrapped(expr, assumptions, _original=original, _singles=singles):
                out = _original(expr, assumptions)
                if out is not None:
                    for row, h in _singles:
                        if h(expr, assumptions) == out:
                            self.counts[row] += 1
                            break
                return out
            self.saved[key] = original
            handlers_dict[key] = wrapped
        return self

    def __exit__(self, *exc):
        handlers_dict.update(self.saved)
        return False


def _short(v, width=300):
    s = str(v).replace("\n", "")
    return s if len(s) <= width else s[:width] + "..."


def mat_main(seed=0, cases=1000):
    """The matrix fuzz: refine every case, check each rewrite at sampled explicit matrices."""
    fired, tried, checked_cases, unchecked, unsound, crashes, nopoint, sympy_unsound = (
        Counter(), Counter(), Counter(), [], [], [], 0, [])
    t0 = time.time()
    coverage = MatrixRowCoverage() if satrefine.HANDLERS_PACKAGE == "handlers_identities" else None
    if coverage:
        coverage.__enter__()
    for case in range(cases):
        g = mat_generate(seed, case)
        if g is None:
            continue
        head, e, assumptions, combos, rel = g
        tried[head] += 1
        try:
            r = sat_refine(e, assumptions)
        except ValueError as ex:
            if "nconsistent" in str(ex):
                continue
            crashes.append((f"{head} #{case}", e, assumptions, f"{type(ex).__name__}: {ex}"))
            continue
        except Exception as ex:
            crashes.append((f"{head} #{case}", e, assumptions, f"{type(ex).__name__}: {str(ex)[:80]}"))
            continue
        rng = random.Random(f"matrix-points-{seed}-{case}")
        points = mat_points(combos, rel, rng)
        if not points:
            nopoint += 1
        if r != e:
            fired[head] += 1
            n_ok, ce = mat_compare(e, r, points)
            if ce:
                unsound.append((f"{head} #{case}", e, assumptions, r, ce))
            elif n_ok:
                checked_cases[head] += 1
            else:
                unchecked.append((f"{head} #{case}", e, assumptions, r))
        try:
            rs = sympy_refine(e, assumptions)
        except Exception:
            rs = e
        if rs != e:
            n_ok, ce = mat_compare(e, rs, points)
            if ce:
                sympy_unsound.append((head, e, assumptions, rs, ce))
    print(f"matrices seed={seed} cases={cases} time={time.time() - t0:.0f}s tried={sum(tried.values())} "
          f"fired={sum(fired.values())} checked={sum(checked_cases.values())} unchecked={len(unchecked)} "
          f"unsound={len(unsound)} crash={len(crashes)} (no satisfying point: {nopoint} cases)")
    for h in sorted(tried, key=lambda h: -tried[h]):
        print(f"  {h:14} fired {fired[h]:4}/{tried[h]:<4} checked {checked_cases[h]}")
    if coverage:
        coverage.__exit__(None, None, None)
        unfired = [row for row in coverage.all_rows if not coverage.counts[row]]
        print(f"\n== matrices rows fired: {len(coverage.all_rows) - len(unfired)} of {len(coverage.all_rows)} ==")
        for row in coverage.all_rows:
            print(f"  {coverage.counts[row]:4}  {_short(row[0], 40):40} -> {_short(row[1], 30):30} if {_short(row[2], 80)}"
                  + (f" unless {row[3]}" if len(row) > 3 else ""))
    print(f"\n== satrefine UNSOUND matrix rewrites: {len(unsound)} ==")
    for head, e, a, r, (pt, va, vb) in unsound[:20]:
        print(f"  [{head}] refine({_short(e)}, {a}) -> {_short(r)}\n      at {_short(pt)}: orig={_short(va)} refined={_short(vb)}")
    print(f"\n== fired but unchecked (no point with a finite input value): {len(unchecked)} ==")
    for head, e, a, r in unchecked[:20]:
        print(f"  [{head}] refine({_short(e)}, {a}) -> {_short(r)}")
    print(f"\n== SymPy's own refine unsound on the same inputs: {len(sympy_unsound)} ==")
    for head, e, a, r, (pt, va, vb) in sympy_unsound[:10]:
        print(f"  [{head}] sympy.refine({_short(e)}, {a}) -> {_short(r)}\n      at {_short(pt)}: orig={_short(va)} refined={_short(vb)}")
    print(f"\n== crashes: {len(crashes)} ==")
    for head, e, a, msg in crashes[:10]:
        print(f"  [{head}] refine({_short(e)}, {a}): {msg}")

# ---------------------------------------------------------------------------
# Extended family (``--ext``): infinities, Piecewise, the inverse pairs
# ---------------------------------------------------------------------------
# A case stream of its own (``ext_generate``, seeded with the string
# "ext-SEED-CASE"): the default scalar and matrix streams above are unchanged,
# so the default differential seeds still compare 1:1 with earlier runs.
#
# What it adds to the default grammar:
# * the predicates ``finite``, ``infinite`` and ``extended_*`` (real, positive,
#   negative, nonnegative, nonpositive, nonzero), alone and combined;
# * relations with infinite bounds (``Q.ge(x, oo)``, ``Q.lt(x, oo)``,
#   ``Q.le(x, -oo)``, ...), sometimes two per case (two-sided bounds);
# * ``Piecewise`` with Lt/Le/Gt/Ge/Eq/Ne conditions (bounds at +-oo too, And/Or),
#   ``KroneckerDelta`` of affine arguments, ``acot`` and the inverse pairs
#   ``acot(cot)``, ``acoth(coth)``, ``asech(sech)``, ``acsch(csch)``.
#
# Sample points.  A symbol may take the values oo, -oo, zoo, oo*I, -oo*I when
# its predicates allow them (checked against ``EXT_PREDS``) and either it has a
# predicate or it occurs in a relation (a relation makes it extended real, so
# only +-oo pass the relation there).  A symbol with no fact at all is sampled
# finite, as in the default family.  Relations are decided numerically at
# finite points and with SymPy's Gt/Ge/Lt/Le/Eq/Ne at infinite ones.
#
# Values (``ext_value``, KroneckerDelta decided by Eq): a finite complex; ("inf", direction) for a signed or
# directed infinity; "zoo"; "nan" (nan or an AccumBounds: no value); or
# "unevaluated"/"error".  A point where the input has no value ("nan") is
# skipped and counted; so is one where a side cannot be evaluated.  A
# mismatch is excused, and counted per label, when it comes from a SymPy
# convention (``ext_convention``):
# * "zoo vs signed infinity (1/0 = zoo | log(0) = zoo)": one side is zoo, the
#   other a signed infinity, and an exact 1/0 or log(0) produced the zoo (zoo
#   from a function's own pole, such as acsch(0), is reported);
# * "log of a non-positive infinity": a side takes log at -oo or oo*I (SymPy
#   gives oo and drops the imaginary part);
# * "atan2 of two infinities": atan2(oo, oo) = 0 etc. are arbitrary;
# Every other mismatch is a counterexample: at a finite point, at an infinite
# point, or "undefined output" (the input has a value, the output is nan).

from sympy import Piecewise, acot, Eq, Ne, Lt, Le, Gt, Ge, And, Or, Add, Mul
from sympy.calculus.accumulationbounds import AccumBounds

INF_VALUES = (oo, -oo, zoo, I * oo, -I * oo)
# Exceptions the checker must never swallow: the differential's worker puts its
# per-case timeout here, so a slow SymPy evaluation ends the case instead of
# being skipped as one unevaluable point after another.
NO_SWALLOW = ()


def is_inf(v):
    return isinstance(v, Basic) and v.has(oo, -oo, zoo)


def _fin(check):
    return lambda v: not is_inf(v) and check(v)


EXT_PREDS = {name: (q, _fin(chk)) for name, (q, chk) in PREDS.items()}
EXT_PREDS.update({
    "finite": (Q.finite, lambda v: not is_inf(v)),
    "infinite": (Q.infinite, is_inf),
    "extended_real": (Q.extended_real, lambda v: v in (oo, -oo) or (not is_inf(v) and c_real(v))),
    "extended_positive": (Q.extended_positive, lambda v: v == oo or (not is_inf(v) and c_pos(v))),
    "extended_negative": (Q.extended_negative, lambda v: v == -oo or (not is_inf(v) and c_neg(v))),
    "extended_nonnegative": (Q.extended_nonnegative, lambda v: v == oo or (not is_inf(v) and PREDS["nonnegative"][1](v))),
    "extended_nonpositive": (Q.extended_nonpositive, lambda v: v == -oo or (not is_inf(v) and PREDS["nonpositive"][1](v))),
    "extended_nonzero": (Q.extended_nonzero, lambda v: v in (oo, -oo) or (not is_inf(v) and PREDS["nonzero"][1](v))),
})
_FINITE_OF = {"finite": None, "extended_real": "real", "extended_positive": "positive", "extended_negative": "negative",
              "extended_nonnegative": "nonnegative", "extended_nonpositive": "nonpositive", "extended_nonzero": "nonzero"}
EXT_COMBOS = [(), (), ("real",), ("positive",), ("negative",), ("nonzero",), ("integer",), ("complex",), ("zero",),
              ("imaginary",), ("positive", "integer"),
              ("finite",), ("infinite",), ("extended_real",), ("extended_real",), ("extended_positive",),
              ("extended_positive",), ("extended_negative",), ("extended_nonnegative",), ("extended_nonpositive",),
              ("extended_nonzero",), ("infinite", "extended_positive"), ("infinite", "extended_negative"),
              ("infinite", "extended_real"), ("finite", "extended_positive"), ("finite", "extended_real"),
              ("finite", "extended_nonnegative"), ("extended_real", "extended_nonzero")]
EXT_BOUNDS = [S.Zero, S.One, S.NegativeOne, pi / 2, -pi / 2, oo, -oo, oo, -oo]


def draw_ext(combo, rng, inf_ok=True, p_inf=0.3):
    """A value satisfying every predicate in ``combo`` (``EXT_PREDS``), possibly infinite if ``inf_ok``."""
    infs = [v for v in INF_VALUES if all(EXT_PREDS[p][1](v) for p in combo)] if inf_ok else []
    if "infinite" in combo:
        return rng.choice(infs) if infs else None
    if infs and rng.random() < p_inf:
        return rng.choice(infs)
    fin = tuple(_FINITE_OF.get(p, p) for p in combo if _FINITE_OF.get(p, p))
    for _ in range(20):
        v = draw(fin, rng)
        if v is None:
            return None
        if all(EXT_PREDS[p][1](v) for p in combo):
            # the same binary value at 40 digits: SymPy evaluates a Float argument at the
            # Float's own precision, and 15 digits lose atanh(tanh(-13.19)) (tanh is -1 + 7e-12)
            return v.xreplace({f: Float(f, 40) for f in v.atoms(Float)}) if v.has(Float) else v
    return None


def ext_relations(rng, syms):
    """Zero, one or two relations over ``syms``, bounds including +-oo."""
    if rng.random() < 0.4:
        return ()
    out = []
    for _ in range(2 if rng.random() < 0.3 else 1):
        a = rng.choice(syms)
        b = rng.choice(syms + EXT_BOUNDS)
        if a == b:
            continue
        out.append(rng.choice([Q.gt, Q.ge, Q.lt, Q.le, Q.gt, Q.lt, Q.eq, Q.ne])(a, b))
    return tuple(out)


_SYMREL = {Q.gt: Gt, Q.ge: Ge, Q.lt: Lt, Q.le: Le, Q.eq: Eq, Q.ne: Ne}


def rel_holds_ext(rel, pt):
    """``rel_holds``, and SymPy's own relation at infinite values (None if undefined there)."""
    try:
        lhs, rhs = (sympify(side).xreplace(pt) for side in rel.arguments)
    except NO_SWALLOW:
        raise
    except Exception:  # noqa: BLE001
        return None
    if not (is_inf(lhs) or is_inf(rhs)):
        return rel_holds(rel, pt)
    if lhs.has(nan, zoo) or rhs.has(nan, zoo) or not (lhs.is_extended_real and rhs.is_extended_real):
        return None
    try:
        v = _SYMREL[rel.function](lhs, rhs)
    except NO_SWALLOW:
        raise
    except Exception:  # noqa: BLE001
        return None
    return True if v is S.true else False if v is S.false else None


def _rel_syms(rels):
    return set().union(*(sympify(side).free_symbols for r in rels for side in r.arguments)) if rels else set()


def _holds_all(rels, pt):
    return all(rel_holds_ext(r, pt) is True for r in rels)


def _draw_point(syms, combos, rels, rng, inf_ok, p_inf=0.3):
    pt = {s: draw_ext(combos.get(s, ()), rng, inf_ok[s], p_inf) for s in syms}
    if any(v is None for v in pt.values()):
        return None
    for r in rels:                     # make an equation hold now and then
        if r.function == Q.eq and rng.random() < 0.7:
            a, b = (sympify(t) for t in r.arguments)
            if a in pt:
                v = b.xreplace(pt)
                if v.is_number and all(EXT_PREDS[p][1](v) for p in combos.get(a, ())):
                    pt[a] = v
    return pt


def ext_satisfiable(combos, rels, rng, tries=80):
    """Whether a random point satisfies ``combos`` and ``rels`` (a cheap filter, not a proof)."""
    syms = sorted(combos, key=str)
    inf_ok = {s: bool(combos[s]) or s in _rel_syms(rels) for s in syms}
    for t in range(tries):
        pt = _draw_point(syms, combos, rels, rng, inf_ok, p_inf=0.5)
        if pt is None:
            return False
        if _holds_all(rels, pt):
            return True
    return False


def ext_points(exprs, combos, rels, rng, random_points=12, cap=200):
    """Points satisfying ``combos`` and ``rels``: random draws, edge values, infinities and relation bounds."""
    import itertools
    rd = importlib.import_module("satrefine.tools.refine_differential")
    syms = sorted(set().union(*(e.free_symbols for e in exprs)), key=str)
    relsyms = _rel_syms(rels)
    inf_ok = {s: bool(combos.get(s)) or s in relsyms for s in syms}
    points = []
    for _ in range(random_points * 8):
        if len(points) >= random_points:
            break
        pt = _draw_point(syms, combos, rels, rng, inf_ok)
        if pt is None:
            break
        if _holds_all(rels, pt):
            points.append(pt)
    cand = {s: list(rd.edge_values()) + ([v for v in INF_VALUES] if inf_ok[s] else []) for s in syms}
    for arg, pts in rd._cut_arguments(exprs):
        free = arg.free_symbols
        if len(free) != 1:
            continue
        (s,) = free
        if s not in cand:
            continue
        slope = arg.diff(s)
        if slope.free_symbols or slope == 0 or arg.subs(s, 0).free_symbols:
            continue
        for p in pts:
            v = (p - arg.subs(s, 0)) / slope
            if v not in cand[s]:
                cand[s].append(v)
    for r in rels:                     # the finite bounds themselves
        for side in r.arguments:
            side = sympify(side)
            if side.is_number and not is_inf(side):
                for s in _rel_syms((r,)):
                    if s in cand and side not in cand[s]:
                        cand[s].append(side)

    def ok(s, v):
        try:
            return all(EXT_PREDS[p][1](v) for p in combos.get(s, ()))
        except (TypeError, ValueError):
            return False
    cand = {s: [v for v in vs if ok(s, v)] for s, vs in cand.items()}
    total = 1
    for s in syms:
        total *= max(1, len(cand[s]))
    edge = []
    if syms and total <= cap:
        for combo in itertools.product(*[cand[s] or [None] for s in syms]):
            edge.append({s: (v if v is not None else draw_ext(combos.get(s, ()), rng, inf_ok[s])) for s, v in zip(syms, combo)})
    else:
        for s in syms:
            for v in cand[s]:
                edge.append({t: (v if t == s else draw_ext(combos.get(t, ()), rng, inf_ok[t])) for t in syms})
    points += [p for p in edge if all(w is not None for w in p.values()) and _holds_all(rels, p)]
    return points


def _inf_class(v):
    """("inf", unit direction) for a signed or directed infinity, "zoo", or "unevaluated"."""
    if v is zoo:
        return "zoo"
    if v.has(zoo):
        return "unevaluated"
    terms = [t for t in Add.make_args(v) if t.has(oo, -oo)]
    if len(terms) != 1 or any(not t.is_number for t in Add.make_args(v)):
        return "unevaluated"
    t = terms[0]
    if t in (oo, -oo):
        d = S.One if t == oo else S.NegativeOne
    elif isinstance(t, Mul):
        infs = [f for f in t.args if f in (oo, -oo)]
        rest = [f for f in t.args if f not in (oo, -oo)]
        if len(infs) != 1 or any(f.has(oo, -oo, zoo) for f in rest):
            return "unevaluated"
        d = Mul(*rest) * (1 if infs[0] == oo else -1)
    else:
        return "unevaluated"
    try:
        dc = complex(N(d, 20))
    except (TypeError, ValueError):
        return "unevaluated"
    if dc == 0:
        return "unevaluated"
    return ("inf", dc / abs(dc))


class _NoBranch(Exception):
    pass


def _pw_resolve(e, pt):
    """``e`` with every Piecewise replaced by its branch at ``pt``.

    Substituting into a Piecewise rebuilds it through SymPy's argument
    collapse, which can recurse without end (``Ne(2, z**2)`` with a complex
    Float ``z``); here each condition is decided on its own instead.  Raises
    ``_NoBranch`` if no condition holds (the Piecewise has no value).
    """
    if not isinstance(e, Basic) or not e.has(Piecewise):
        return e
    if isinstance(e, Piecewise):
        for expr_, cond in e.args:
            c = S.true if cond is S.true else _pw_resolve(cond, pt).xreplace(pt)
            if c is S.true:
                return _pw_resolve(expr_, pt)
            if c is not S.false:
                raise TypeError("undecided Piecewise condition")
        raise _NoBranch
    return e.func(*[_pw_resolve(a, pt) for a in e.args])


def ext_value(e, pt):
    """The value of ``e`` at ``pt`` (see the section comment)."""
    try:
        v = _pw_resolve(e, pt).xreplace(pt)
    except _NoBranch:
        return "nan"
    except NO_SWALLOW:
        raise
    except NO_SWALLOW:
        raise
    except Exception:  # noqa: BLE001 -- e.g. a Piecewise condition on a non-real value
        return "error"
    if not isinstance(v, Expr):
        return "unevaluated"
    if v.has(KroneckerDelta):          # SymPy leaves KroneckerDelta(oo, oo) unevaluated; decide it by Eq
        v = v.replace(KroneckerDelta, lambda p, q: {S.true: S.One, S.false: S.Zero}.get(Eq(p, q), KroneckerDelta(p, q)))
    if v.has(nan) or v.has(AccumBounds):
        return "nan"
    if is_inf(v):
        return _inf_class(v)
    try:
        w = N(v, 20)
    except NO_SWALLOW:
        raise
    except Exception:  # noqa: BLE001
        return "error"
    return numeric(w)


def ext_agree(a, b):
    if isinstance(a, tuple) or isinstance(b, tuple):
        return isinstance(a, tuple) and isinstance(b, tuple) and abs(a[1] - b[1]) < 1e-9
    if a == "zoo" or b == "zoo":
        return a == b
    return agree(a, b)


def _zero_division(sides, pt):
    """The label of an exact 1/0 or log(0) met while evaluating ``sides`` at ``pt``, or None."""
    for e in sides:
        for sub in e.atoms(log, Pow):
            try:
                if isinstance(sub, log):
                    if sub.args[0].xreplace(pt) == 0:
                        return "log(0) = zoo"
                elif sub.base.xreplace(pt) == 0:
                    ev = ext_value(sub.exp, pt)
                    if isinstance(ev, complex) and ev.real < 0:
                        return "1/0 = zoo"
            except NO_SWALLOW:
                raise
            except Exception:  # noqa: BLE001, S112
                continue
    return None


def ext_convention(sides, pt, a, b):
    """The SymPy convention that explains the mismatch ``a != b`` at ``pt``, or None.

    zoo against a signed infinity is excused only when an exact 1/0 or log(0)
    produced it; zoo from a function's own pole (``acsch(0)``) is reported.
    """
    if (a == "zoo" and isinstance(b, tuple)) or (b == "zoo" and isinstance(a, tuple)):
        lab = _zero_division(sides, pt)
        return f"zoo vs signed infinity ({lab})" if lab else None
    for e in sides:
        for sub in e.atoms(log, atan2, Pow):
            try:
                if isinstance(sub, log):
                    u = ext_value(sub.args[0], pt)
                    if isinstance(u, tuple) and abs(u[1] - 1) > 1e-9:
                        return "log of a non-positive infinity"
                elif isinstance(sub, atan2):
                    if all(is_inf(t.xreplace(pt)) for t in sub.args):
                        return "atan2 of two infinities"
            except NO_SWALLOW:
                raise
            except Exception:  # noqa: BLE001, S112
                continue
    return None


def ext_compare(left, right, points, ref=None):
    """(n_checked, counterexample or None, stats) for ``left`` (the input) against ``right``.

    The counterexample is (point, left value, right value, kind), kind one of
    "finite point", "infinite point", "undefined output".  ``stats`` counts the
    points skipped (input undefined, unevaluable), excused per convention label
    and checked at an infinity.  With ``ref`` (the input, when two rewrites are
    compared) a point where ``ref`` has no value is skipped.
    """
    stats = Counter()
    checked = 0
    for pt in points:
        inf_pt = any(is_inf(v) for v in pt.values())
        if ref is not None and ext_value(ref, pt) in ("nan", "error", "unevaluated"):
            stats["input undefined"] += 1
            continue
        a, b = ext_value(left, pt), ext_value(right, pt)
        if a == "nan":
            stats["input undefined"] += 1
            continue
        if a in ("error", "unevaluated") or b in ("error", "unevaluated"):
            stats["unevaluable"] += 1
            continue
        if b != "nan" and ext_agree(a, b):
            checked += 1
            if inf_pt:
                stats["checked at an infinity"] += 1
            continue
        conv = ext_convention((left, right), pt, a, b)
        if conv:
            stats["convention: " + conv] += 1
            continue
        kind = "undefined output" if b == "nan" else "infinite point" if inf_pt else "finite point"
        return checked, (pt, a, b, kind), stats
    return checked, None, stats


def _acot_cot(e, rng): return acot(cot(e))
def _acoth_coth(e, rng): return acoth(coth(e))
def _asech_sech(e, rng): return asech(sech(e))
def _acsch_csch(e, rng): return acsch(csch(e))


_RELS = (Lt, Le, Gt, Ge, Eq, Ne, Eq, Ne)


def _cond(rng):
    a = atom(rng)
    b = rng.choice([atom(rng), S.Zero, S.One, pi / 2, oo, -oo, 2 * atom(rng), atom(rng) + 1, 3 * atom(rng) + 1, inner(rng)])
    c = rng.choice(_RELS)(a, b)
    if rng.random() < 0.2:
        c = rng.choice([And, Or])(c, rng.choice(_RELS)(atom(rng), rng.choice([S.Zero, S.One, atom(rng)])))
    return c


def _piecewise(e, rng):
    pieces = [(e, _cond(rng))]
    if rng.random() < 0.4:
        pieces.append((inner(rng), _cond(rng)))
    pieces.append((rng.choice([S.Zero, S.One, inner(rng), -e]), True))
    return Piecewise(*pieces)


EXT_NEW = {
    "acot": lambda e, rng: acot(e), "acot_cot": _acot_cot, "acoth_coth": _acoth_coth,
    "asech_sech": _asech_sech, "acsch_csch": _acsch_csch,
    "Piecewise": _piecewise,
    "Piecewise_outer": lambda e, rng: _piecewise(OUTER[rng.choice(list(OUTER))](e, rng), rng),
    "KroneckerDelta_affine": lambda e, rng: KroneckerDelta(e, rng.choice(
        [2 * atom(rng), atom(rng) + 1, 3 * atom(rng) + 1, atom(rng), inner(rng)])),
}
EXT_OUTER = {**OUTER, **EXT_NEW}


def ext_generate(seed, case):
    """Case ``case`` of the extended family: (head, expr, assumptions, combos, rels) or None.

    ``rels`` is a tuple of relations (possibly empty).  A case with no
    satisfying point found by ``ext_satisfiable`` is dropped (None).
    """
    import functools
    rng = random.Random(f"ext-{seed}-{case}")
    head = rng.choice(list(EXT_NEW)) if rng.random() < 0.4 else rng.choice(list(OUTER))
    try:
        e = EXT_OUTER[head](inner(rng), rng)
    except NO_SWALLOW:
        raise
    except Exception:  # noqa: BLE001 -- the generator's own policy
        return None
    if not isinstance(e, Expr) or not e.free_symbols:
        return None
    syms = sorted(e.free_symbols, key=str)
    combos = {s: rng.choice(EXT_COMBOS) for s in syms}
    rels = ext_relations(rng, syms)
    for s_ in sorted(_rel_syms(rels), key=str):      # the bounds-bug shape: a relation alone on a symbol
        if s_ in combos and rng.random() < 0.5:
            combos[s_] = ()
    if not ext_satisfiable(combos, rels, random.Random(f"ext-sat-{seed}-{case}")):
        return None
    facts = [EXT_PREDS[p][0](s) for s, c in combos.items() for p in c] + list(rels)
    assumptions = S.true if not facts else functools.reduce(lambda a, b: a & b, facts)
    return head, e, assumptions, combos, rels


def ext_main(seed=0, cases=1000):
    """The extended fuzz for the selected package: refine, check at finite and infinite points."""
    tried, fired = Counter(), Counter()
    unsound, crashes, unchecked, conv_cases = [], [], 0, Counter()
    stats = Counter()
    dropped = checked_cases = 0
    t0 = time.time()
    for case in range(cases):
        g = ext_generate(seed, case)
        if g is None:
            dropped += 1
            continue
        head, e, assumptions, combos, rels = g
        tried[head] += 1
        try:
            r = sat_refine(e, assumptions)
            if not isinstance(r, Basic):
                r = sympify(r)
        except ValueError as ex:
            if "nconsistent" in str(ex):
                continue
            crashes.append((head, e, assumptions, f"{type(ex).__name__}: {ex}"))
            continue
        except Exception as ex:  # noqa: BLE001
            crashes.append((head, e, assumptions, f"{type(ex).__name__}: {str(ex)[:80]}"))
            continue
        if r == e:
            continue
        fired[head] += 1
        n_ok, ce, st = ext_compare(e, r, ext_points([e, r], combos, rels, random.Random(f"ext-pts-{seed}-{case}")))
        stats.update(st)
        for lab in st:
            if lab.startswith("convention"):
                conv_cases[lab] += 1
        if ce:
            unsound.append((head, case, e, assumptions, r, ce))
        elif n_ok:
            checked_cases += 1
        else:
            unchecked += 1
    kinds = Counter(u[5][3] for u in unsound)
    print(f"ext seed={seed} cases={cases} time={time.time() - t0:.0f}s dropped={dropped} tried={sum(tried.values())} "
          f"fired={sum(fired.values())} checked={checked_cases} unchecked={unchecked} unsound={len(unsound)} "
          f"({', '.join(f'{k} {v}' for k, v in sorted(kinds.items())) or 'none'}) crash={len(crashes)}")
    print("  points: " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())))
    print("  cases with a convention-excused point: " + (", ".join(f"{k[12:]} {v}" for k, v in sorted(conv_cases.items())) or "0"))
    print("\n== fires by head (fired/tried) ==")
    for h in sorted(tried, key=lambda h: -tried[h]):
        print(f"  {h:22} {fired[h]:4}/{tried[h]}")
    print(f"\n== UNSOUND: {len(unsound)} ==")
    for head, case, e, a, r, (pt, va, vb, kind) in unsound[:40]:
        print(f"  [{head} #{case}] refine({e}, {a}) -> {r}\n      {kind} {pt}: orig={va} refined={vb}")
    print(f"\n== crashes: {len(crashes)} ==")
    for head, e, a, msg in crashes[:20]:
        print(f"  [{head}] refine({e}, {a}): {msg}")

if __name__ == "__main__":
    if "--ext" in sys.argv:
        sys.argv.remove("--ext")
        ext_main(int(sys.argv[1]) if len(sys.argv) > 1 else 0, int(sys.argv[2]) if len(sys.argv) > 2 else 1000)
    elif "--matrices" in sys.argv:
        sys.argv.remove("--matrices")
        mat_main(int(sys.argv[1]) if len(sys.argv) > 1 else 0, int(sys.argv[2]) if len(sys.argv) > 2 else 1000)
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else 0, int(sys.argv[2]) if len(sys.argv) > 2 else 3000)
