"""The fuzzers' assumption vocabulary: predicates with numeric definitions, samplers, relations.

Scalar family: ``PREDS`` maps a predicate name to ``(Q builder, numeric check)``;
``COMBOS`` are the per-symbol predicate sets a case draws from; :func:`draw`
samples a value satisfying a set (rejection sampling); :func:`relations`
draws a relation assumption and :func:`rel_holds` decides one at a point.

Extended family: ``EXT_PREDS`` adds ``finite``, ``infinite`` and the
``extended_*`` predicates, with checks that also accept the infinities
``INF_VALUES`` where the predicate allows them; :func:`draw_ext` may return
one; :func:`ext_relations` draws up to two relations whose bounds include
``+-oo``, and :func:`rel_holds_ext` decides a relation at an infinite value
with SymPy's own ``Gt``/``Ge``/... .

The random calls are part of the case streams (pinned by
``tests/refine_identities/test_fuzz_ext.py``): change the order of any of
them and every seed generates different cases.
"""
from __future__ import annotations

import functools

from sympy import Abs, Eq, Float, Ge, Gt, I, Integer, Le, Lt, N, Ne, Q, Rational, S, nan, oo, pi, sympify, zoo
from sympy.core.basic import Basic

from .workers import NO_SWALLOW


# --- scalar vocabulary: name -> (Q builder, numeric checker)
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


def conjunction(facts):
    """``facts`` joined with ``&`` (``S.true`` for none)."""
    return S.true if not facts else functools.reduce(lambda a, b: a & b, facts)


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


# --- extended vocabulary: infinities, finite/infinite, extended_*

INF_VALUES = (oo, -oo, zoo, I * oo, -I * oo)


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


def rel_syms(rels):
    """The symbols the relations ``rels`` mention."""
    return set().union(*(sympify(side).free_symbols for r in rels for side in r.arguments)) if rels else set()


def holds_all(rels, pt):
    return all(rel_holds_ext(r, pt) is True for r in rels)
