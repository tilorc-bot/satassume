"""The sign theory (issue #149, T1 stage 1): its atom tables against
SymPy's arithmetic, and the answers it adds end to end."""
from __future__ import annotations

from itertools import product

import pytest

sympy = pytest.importorskip("sympy")

from sympy import (Add, I, Mul, Q, Rational, S, Symbol, im, nan, oo, pi, re, sqrt,
                   symbols, zoo)

from satassume.sympy_api import ask
from satassume.theories.sign import sign_adapter
from satassume.theories.sign.sign import (ADD, ALL, IN, MUL, NAN, NI, PI, PRED_MASK, PREDS, F,
                                          fold, mop, node_masks)


def _sgn(v):
    if v.is_zero:
        return 0
    if v.is_extended_positive:
        return 1
    if v.is_extended_negative:
        return -1
    return None


def atom_of(v):
    """The atom of a concrete value, None if SymPy cannot tell."""
    m = mask_of(v)
    return m.bit_length() - 1 if m and not m & (m - 1) else None


def mask_of(v):
    """The atoms a concrete value may be in, as far as SymPy tells."""
    if v is S.NaN:
        return 1 << NAN
    if v.is_finite is False:
        if v.is_extended_real:
            return 1 << (PI if v.is_extended_positive else NI)
        return 1 << IN if v.is_extended_real is False else (1 << PI | 1 << NI | 1 << IN)
    v = sympy.expand(v)
    if v.is_finite:
        r, i = _sgn(re(v)), _sgn(im(v))
        if r is not None and i is not None:
            return 1 << F(r, i)
    return ALL


_PARTS = {-1: (-3, -Rational(1, 2), -sqrt(2)), 0: (0,), 1: (1, Rational(3, 2), pi)}
SAMPLES = [r + s*I for sr, si in product((-1, 0, 1), repeat=2)
           for r in _PARTS[sr] for s in _PARTS[si]]
SAMPLES += [oo, -oo, zoo, oo*I, -oo*I, oo*(1 + I), oo + I, -oo - 2*I, oo - I]


def test_samples_cover_every_atom():
    assert {atom_of(v) for v in SAMPLES} == set(range(12))


def test_atom_of_agrees_with_the_predicate_masks():
    for v in SAMPLES:
        a = atom_of(v)
        for p, pred in enumerate(PREDS):
            t = getattr(v, 'is_' + pred)
            if t is not None:
                assert bool(PRED_MASK[p] >> a & 1) == t, (v, pred)


@pytest.mark.parametrize("op", [ADD, MUL])
def test_pairwise_tables_against_sympy(op):
    f = Add if op == ADD else Mul
    unknown = 0
    for a, b in product(SAMPLES, repeat=2):
        r = mask_of(f(a, b))
        if r == ALL:
            unknown += 1
            continue
        m = mop(op, 1 << atom_of(a), 1 << atom_of(b))
        assert m >> NAN & 1 or m & r, (a, b, f(a, b))
    assert unknown < len(SAMPLES) ** 2 // 10    # parts SymPy cannot sign


@pytest.mark.parametrize("op", [ADD, MUL])
def test_three_argument_folds_against_sympy(op):
    f = Add if op == ADD else Mul
    pool = SAMPLES[::3] + [oo, -oo, zoo, oo*I, oo + I]
    unknown = 0
    for args in product(pool, repeat=3):
        r = mask_of(f(*args))
        if r == ALL:
            unknown += 1
            continue
        m = fold(op, [1 << atom_of(a) for a in args])
        assert m >> NAN & 1 or m & r, (args, f(*args))
    assert unknown < len(pool) ** 3 // 5       # parts SymPy cannot sign


@pytest.mark.parametrize("op", [ADD, MUL])
def test_backward_keeps_the_true_atom(op):
    f = Add if op == ADD else Mul
    pool = SAMPLES[::2] + [oo, -oo, zoo, oo*I]
    for args in product(pool, repeat=3):
        v = f(*args)
        n = atom_of(v)
        if n is None or n == NAN:
            continue
        newn, out = node_masks(op, 1 << n, [ALL] * 2 + [1 << atom_of(args[2])])
        assert newn >> n & 1
        for k in range(2):
            assert out[k] >> atom_of(args[k]) & 1, (args, v)


def test_const_mask():
    for c in (S(2), S(-1), S.Zero, pi, I, oo, -oo, zoo, Rational(-1, 2)):
        assert sign_adapter.const_mask(c) >> atom_of(c) & 1


a, b, c, d, e, x, y, z, w = symbols("a b c d e x y z w")


@pytest.mark.parametrize("prop, assum, expected", [
    (Q.positive(a*b*c*d*e),
     Q.negative(a) & Q.negative(b) & Q.positive(c) & Q.positive(d) & Q.positive(e), True),
    (Q.negative(a*b*c*d*e),
     Q.negative(a) & Q.negative(b) & Q.negative(c) & Q.positive(d) & Q.positive(e), True),
    (Q.nonnegative(a*b*c*d*e),
     Q.nonpositive(a) & Q.nonpositive(b) & Q.nonnegative(c) & Q.nonnegative(d)
     & Q.nonnegative(e), True),
    (Q.infinite(a*b*c*w*x*y*z),
     Q.infinite(a) & Q.nonzero(b) & Q.nonzero(c) & Q.nonzero(w) & Q.nonzero(x)
     & Q.nonzero(y) & Q.nonzero(z), True),
    (Q.positive(a), Q.positive(a*b*c*d*e) & Q.negative(b) & Q.negative(c) & Q.positive(d)
     & Q.positive(e), True),
    (Q.zero(a*b*c*d*e*x*y),
     Q.zero(a) & Q.finite(b) & Q.finite(c) & Q.finite(d) & Q.finite(e) & Q.finite(x)
     & Q.finite(y), True),
    (Q.positive(x), Q.positive(x + y) & Q.negative(y), True),
    # 0*oo and oo - oo are nan: no claim
    (Q.zero(a*b*c*d*e), Q.zero(a) & Q.infinite(b), None),
    (Q.finite(a*b*c*d*e), Q.zero(a) & Q.infinite(b), None),
    (Q.positive(a*b*c*d*e), Q.positive(a) & Q.positive(b) & Q.positive(c) & Q.positive(d), None),
])
def test_answers(prop, assum, expected):
    assert ask(prop, assum) is expected


def test_inconsistent_wide_product_raises():
    with pytest.raises(ValueError):
        ask(Q.real(x), Q.positive(a*b*c*d*e) & Q.negative(a) & Q.positive(b) & Q.positive(c)
            & Q.positive(d) & Q.positive(e))
