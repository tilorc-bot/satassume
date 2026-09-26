"""Random refine inputs: the expression grammars and the per-case streams.

Scalar family (``refine_fuzz``, the differential's default): an outer head
from ``OUTER`` applied to an ``inner`` expression over the symbols ``x, y, z,
n, m, k``; each symbol gets a predicate set from ``assumptions.COMBOS``, and
now and then one relation.  :func:`generate` is case ``case`` of seed
``seed``, drawn from ``random.Random(seed * 1000003 + case)``, so every
handler package sees the same inputs whatever an earlier case consumed.

Extended family (``--ext``): the heads of ``EXT_NEW`` besides ``OUTER``
(``acot``, the inverse pairs ``acot(cot)``, ``acoth(coth)``, ``asech(sech)``,
``acsch(csch)``, ``Piecewise`` with Lt/Le/Gt/Ge/Eq/Ne conditions and bounds at
``+-oo``, ``KroneckerDelta`` of affine arguments), the ``finite``/``infinite``/
``extended_*`` predicates, and up to two relations with infinite bounds.
:func:`ext_generate` draws from its own stream (``"ext-SEED-CASE"``), so the
scalar seeds are unchanged by it.

The matrix family is :mod:`.matrices`.  All streams are pinned by digests in
``tests/refine_identities/test_fuzz_ext.py``.
"""
from __future__ import annotations

import random

from sympy import (E, I, S, Abs, And, Eq, FallingFactorial, Ge, Gt, Heaviside, KroneckerDelta, Le, Lt, Max, Min, Mod,
                   Ne, Or, Piecewise, Pow, Rational, RisingFactorial, acos, acosh, acot, acoth, acsch, arg, asech, asin,
                   asinh, atan, atan2, atanh, binomial, ceiling, conjugate, cos, cosh, cot, coth, csc, csch, exp,
                   factorial, floor, frac, gamma, im, log, oo, pi, re, sec, sech, sign, sin, sinc, sinh, sqrt, symbols, tan,
                   tanh, DiracDelta)
from sympy.core.expr import Expr

from . import assumptions as A
from .points import ext_satisfiable
from .workers import NO_SWALLOW

try:
    from sympy import Rem
except ImportError:
    Rem = None

x, y, z = symbols("x y z")
n, m, k = symbols("n m k")
i, j = symbols("i j")
SYMS = [x, y, z, n, m, k, i, j]


def atom(rng):
    return rng.choice([x, y, z, n, m, k, x, n])


def inner(rng, depth=0):
    r = rng.random()  # noqa: F841 -- part of the stream
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


def scalar_case(rng):
    """A scalar case drawn from ``rng``: (head, expr, assumptions, combos, rel) or None.

    ``combos`` maps each free symbol to its predicate names, ``rel`` is the
    relation assumption or None.  ``refine_fuzz`` goes on drawing its check
    points from the same ``rng``."""
    head = rng.choice(list(OUTER))
    try:
        e = OUTER[head](inner(rng), rng)
    except Exception:  # noqa: BLE001 -- the generator's own policy
        return None
    if not isinstance(e, Expr):
        return None
    syms = sorted(e.free_symbols, key=str)
    if not syms:
        return None
    combos = {s: rng.choice(A.COMBOS) for s in syms}
    if any(A.draw(c, rng) is None for c in combos.values()):    # a symbol whose combo has no sample
        return None
    facts = [A.PREDS[p][0](s) for s, c in combos.items() for p in c]
    rel = A.relations(rng, syms)
    if rel is not None:
        facts.append(rel)
    return head, e, A.conjunction(facts), combos, rel


def case_rng(seed, case):
    """The random stream of scalar case ``case`` of ``seed``."""
    return random.Random(seed * 1000003 + case)


def generate(seed, case):
    """Scalar case ``case`` of ``seed``: (head, expr, assumptions, combos, rel) or None."""
    return scalar_case(case_rng(seed, case))


# --- extended family

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
    combos = {s: rng.choice(A.EXT_COMBOS) for s in syms}
    rels = A.ext_relations(rng, syms)
    for s_ in sorted(A.rel_syms(rels), key=str):      # the bounds-bug shape: a relation alone on a symbol
        if s_ in combos and rng.random() < 0.5:
            combos[s_] = ()
    if not ext_satisfiable(combos, rels, random.Random(f"ext-sat-{seed}-{case}")):
        return None
    facts = [A.EXT_PREDS[p][0](s) for s, c in combos.items() for p in c] + list(rels)
    return head, e, A.conjunction(facts), combos, rels
