"""The transcendence theory TRANS (issue #149, T6): its tables against
SymPy's values at sample points of every atom, the theorems they encode,
and the answers end to end (every answer of the template rows it replaced,
and the new ones)."""
from __future__ import annotations

from itertools import product

import pytest

sympy = pytest.importorskip("sympy")

from sympy import (E, I, Pow, Q, Rational, S, Symbol, oo, pi, sqrt, symbols, zoo)
from sympy import (acos, acot, asin, atan, cos, cosh, cot, exp, log, sin, sinh, tan, tanh)

from satassume.sympy_api import ask
from satassume.theories.sign import trans as T
from satassume.theories.sign.trans import (AC, ALL, AR, IC, IR, NAN, NANB, ONE, OPS, POW,
                                           PRED_MASK, PREDS, Q1, TC, TR, TRANS, Z0, ZI)
from satassume.theories.sign.trans_adapter import TransAdapter, op_args

FUNCS = {f.__name__: f for f in (exp, log, sin, cos, tan, cot, sinh, cosh, tanh, asin, acos,
                                 atan, acot)}


def atom_of(v):
    """The atom of a concrete value, None if SymPy cannot tell; NAN for
    nan and AccumBounds."""
    if v is S.NaN or v.has(sympy.AccumBounds):
        return NAN
    if v.is_finite is False:
        r = v.is_extended_real
        return None if r is None else (IR if r else IC)
    v = sympy.expand(v)
    if not v.is_finite or not v.is_complex:
        return None
    if v.is_zero:
        return Z0
    if v == 1:
        return ONE
    for pred, atom in (("integer", ZI), ("rational", Q1)):
        t = getattr(v, "is_" + pred)
        if t is None:
            return None
        if t:
            return atom
    alg, real = v.is_algebraic, v.is_extended_real
    if alg is None or real is None:
        return None
    return (AR if real else AC) if alg else (TR if real else TC)


def coarse(v):
    """The atoms a value may lie in by numeric evaluation (zero, a nonzero
    real, a non-real), None if it cannot be evaluated."""
    try:
        z = complex(v.evalf(40))
    except (TypeError, ValueError):
        return None
    if z != z or abs(z) == float("inf"):
        return None
    if abs(z) < 1e-30:
        return 1 << Z0
    if abs(z.imag) < 1e-30:
        return T._REALNZ
    return T._NONREAL


SAMPLES = {
    Z0: [S.Zero], ONE: [S.One], ZI: [S(-1), S(2), S(-3)],
    Q1: [Rational(1, 2), Rational(-3, 2)],
    AR: [sqrt(2), 1 - sqrt(2), -sqrt(3)/2], AC: [I, -I, 1 + I, sqrt(2)*I, -I/2],
    TR: [pi, E, -pi/2, 1 - pi], TC: [pi*I, pi + I, E*I],
    IR: [oo, -oo], IC: [zoo, oo*I, -oo*I, oo + I],
}
VALUES = [(a, v) for a, vs in SAMPLES.items() for v in vs]


def _check(m, r):
    """The table entry ``m`` holds the value ``r``."""
    c = atom_of(r)
    if c is None:
        cm = coarse(r)
        if cm is None:
            return False
        assert m & NANB or m & cm, r
        return True
    assert m & NANB or m >> c & 1, (r, c, m)
    if c == NAN:
        assert m & NANB, r          # an AccumBounds or nan value: no claim
    return True


def test_samples_are_in_their_atoms():
    for a, v in VALUES:
        assert atom_of(v) == a, v


def test_predicate_masks_agree_with_sympy():
    for a, v in VALUES:
        for p, pred in enumerate(PREDS):
            t = getattr(v, "is_" + pred)
            if t is not None:
                assert bool(PRED_MASK[p] >> a & 1) == t, (v, pred)
        for p, pred in enumerate(T.ONESIDED):
            if getattr(v, "is_" + pred) is True:
                assert T.ONESIDED_MASK[p] >> a & 1, (v, pred)


@pytest.mark.parametrize("name", sorted(FUNCS))
def test_unary_tables_against_sympy(name):
    f, op = FUNCS[name], OPS[name]
    table = TRANS.maps[op - TRANS.nfold][1]
    seen = 0
    for a, v in VALUES:
        seen += _check(table[(a,)], f(v))
    assert seen >= len(VALUES) - 3, seen


def test_pow_table_against_sympy():
    table = TRANS.maps[POW - TRANS.nfold][1]
    seen = 0
    for (a, va), (b, vb) in product(VALUES, repeat=2):
        try:
            r = Pow(va, vb)
            atom_of(r)                    # (SymPy recurses on some)
        except RecursionError:          # SymPy on oo**(oo + I)
            continue
        seen += _check(table[(a, b)], r)
    assert seen > len(VALUES) ** 2 // 2, seen


def test_the_theorems():
    """Lindemann-Weierstrass and Gelfond-Schneider, as masks."""
    algnz = T._ALGNZ
    trn = (1 << TR) | (1 << TC)
    for name in ("exp", "sin", "cos", "tan", "cot", "sinh", "cosh", "tanh", "log"):
        dom = algnz & ~(1 << ONE) if name == "log" else algnz
        newn, _ = TRANS.map_masks(OPS[name], ALL, [dom])
        assert newn & ~trn == 0, name
    for name in ("asin", "acos", "atan", "acot"):
        newn, _ = TRANS.map_masks(OPS[name], ALL, [algnz & ~(1 << ONE)])
        assert newn & T._CPX & ~trn == 0, name          # finite values transcendental
    # GS: b algebraic not 0 or 1, e algebraic irrational
    newn, _ = TRANS.map_masks(POW, ALL, [algnz & ~(1 << ONE), (1 << AR) | (1 << AC)])
    assert newn == trn
    # backward: 2**e algebraic, e algebraic: e rational
    _, (mb, me) = TRANS.map_masks(POW, PRED_MASK[2], [1 << ZI, PRED_MASK[2]])
    assert me == PRED_MASK[1]
    # exp(x) algebraic, x nonzero: x not algebraic
    _, (mx,) = TRANS.map_masks(OPS["exp"], PRED_MASK[2], [ALL & ~(1 << Z0)])
    assert mx & PRED_MASK[2] == 0
    # no claim from a base that may be 0 or 1
    newn, _ = TRANS.map_masks(POW, ALL, [PRED_MASK[2], 1 << AR])
    assert newn & PRED_MASK[2]


def test_backward_keeps_the_true_atom():
    for name, f in FUNCS.items():
        for a, v in VALUES:
            n = atom_of(f(v))
            if n is None or n == NAN:
                continue
            newn, (m,) = TRANS.map_masks(OPS[name], 1 << n, [ALL])
            assert newn >> n & 1 and m >> a & 1, (name, v)
    pool = [x for _, x in VALUES][::2]
    for vb, ve in product(pool, repeat=2):
        n = atom_of(Pow(vb, ve))
        if n is None or n == NAN:
            continue
        newn, (mb, me) = TRANS.map_masks(POW, 1 << n, [ALL, ALL])
        assert mb >> atom_of(vb) & 1 and me >> atom_of(ve) & 1, (vb, ve)


def test_const_mask_and_nodes():
    for c in (S(2), S(-1), S.Zero, S.One, pi, E, I, oo, -oo, zoo, Rational(-1, 2)):
        assert TransAdapter.const_mask(c) == 1 << atom_of(c), c
    assert TransAdapter.const_mask(sympy.Float(2.0)) & (1 << ZI) and \
        TransAdapter.const_mask(sympy.Float(2.0)) & (1 << ONE)
    x, y = symbols("x y")
    assert op_args(x**2) is None and op_args(1/x) is None and op_args(sqrt(x)) is None
    assert op_args(x**y) == (POW, (x, y)) and op_args(2**x) == (POW, (S(2), x))
    assert op_args(Pow(E, x, evaluate=False)) == (OPS["exp"], (x,))
    assert op_args(sin(x)) == (OPS["sin"], (x,))
    A = Symbol("A", commutative=False)
    assert op_args(A**x) is None and op_args(exp(A)) is None
    assert op_args(sympy.Function("exp")(x)) is None      # not SymPy's exp


def test_derived_predicates():
    from satassume.knowledge.rules import DEF_LITS
    assert TransAdapter.def_mask(DEF_LITS["transcendental"]) == (1 << TR) | (1 << TC)
    assert TransAdapter.def_mask(DEF_LITS["irrational"]) == (1 << AR) | (1 << TR)


x, y = symbols("x y")
ALG_NZ = Q.algebraic(x) & ~Q.zero(x)
GS = Q.algebraic(x) & Q.algebraic(y) & Q.irrational(y)


@pytest.mark.parametrize("prop, assum, expected", [
    # the answers of the removed rows (functions.py _TRANSCENDENTAL and kin)
    *[(Q.transcendental(f(x)), ALG_NZ, True)
      for f in (exp, sin, cos, tan, cot, sinh, cosh, tanh, asin)],
    (Q.transcendental(Pow(E, x, evaluate=False)), ALG_NZ, True),
    (Q.transcendental(log(x)), ALG_NZ & ~Q.zero(log(x)), True),
    (Q.transcendental(acos(x)), Q.algebraic(x) & ~Q.zero(acos(x)), True),
    (Q.transcendental(atan(x)), Q.real(x) & ALG_NZ, True),
    (Q.transcendental(acot(x)), Q.real(x) & Q.algebraic(x), True),
    (Q.algebraic(acot(x)), Q.algebraic(x), False),
    (Q.algebraic(cot(x)), Q.algebraic(x), False),
    # b=algebraic.gs (b an algebraic constant not 0 or 1)
    (Q.algebraic(2**y), Q.rational(y), True),
    (Q.algebraic(2**y), Q.algebraic(y) & ~Q.rational(y), False),
    (Q.rational(y), Q.algebraic(2**y) & Q.algebraic(y), True),
    (Q.rational(y), Q.algebraic(y) & ~Q.algebraic(Rational(1, 2)**y), False),
    (Q.algebraic(I**y), Q.algebraic(y) & ~Q.rational(y), False),
    # e=algebraic_irrational.gs (each way to say "b not in {0, 1}")
    *[(Q.algebraic(x**I), Q.algebraic(x) & p, False)
      for p in (Q.irrational(x), Q.noninteger(x), Q.negative(x), Q.prime(x), Q.composite(x))],
    (Q.algebraic(x**S.GoldenRatio), Q.algebraic(x) & Q.prime(x), False),
    # new: GS with a symbolic exponent, any way to say "b not in {0, 1}"
    (Q.transcendental(x**y), GS & Q.noninteger(x), True),
    (Q.transcendental(x**y), GS & Q.negative(x), True),
    (Q.transcendental(x**y), GS & Q.even(x) & ~Q.zero(x), True),
    (Q.algebraic(x**sqrt(2)), Q.algebraic(x) & Q.prime(x), False),
    # new: backward through the functions
    (Q.algebraic(x), Q.algebraic(exp(x)) & ~Q.zero(x), False),
    (Q.algebraic(x), Q.algebraic(sin(x)) & Q.complex(x) & ~Q.zero(x), False),
    (Q.algebraic(x), Q.rational(log(x)) & ~Q.zero(log(x)), False),
    (Q.rational(y), Q.algebraic(x**y) & Q.prime(x) & Q.algebraic(y), True),
    (Q.algebraic(Pow(S.One, x, evaluate=False)), Q.algebraic(x), True),
    # no claim where 0, 1 or an infinity is possible
    (Q.transcendental(x**y), GS, None),
    (Q.transcendental(exp(x)), Q.algebraic(x), None),
    (Q.algebraic(log(x)), Q.algebraic(x), None),
    (Q.transcendental(atan(x)), ALG_NZ, None),          # atan(I) = oo*I
    (Q.zero(exp(x)), Q.negative_infinite(x), True),
    (Q.transcendental(x**y), Q.prime(x) & Q.algebraic(y), None),
    # class facts from a zero of a compound term (an equality): engaged
    (Q.zero(sin(x)), Q.zero(x - 1), False),
    (Q.transcendental(exp(x)), Q.zero(x - 1), True),
])
def test_answers(prop, assum, expected):
    assert ask(prop, assum) is expected


def test_noncommutative_out_of_scope():
    A = Symbol("A", commutative=False)
    assert ask(Q.transcendental(exp(A)), Q.algebraic(A) & ~Q.zero(A)) is None
    assert ask(Q.algebraic(A**I), Q.algebraic(A) & Q.prime(A)) is None


def test_inconsistent_assumptions_raise():
    with pytest.raises(ValueError):
        ask(Q.real(x), Q.algebraic(exp(x)) & Q.algebraic(x) & ~Q.zero(x))
    with pytest.raises(ValueError):
        ask(Q.real(y), Q.algebraic(3**y) & Q.algebraic(y) & Q.irrational(y))
