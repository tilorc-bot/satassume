"""The closure theory (issue #149, T3): its atom tables against SymPy's
arithmetic, the axioms they come from, and the answers it adds end to end."""
from __future__ import annotations

from itertools import product

import pytest

sympy = pytest.importorskip("sympy")

from sympy import (Add, And, E, I, Mul, Q, Rational, S, Symbol, nan, oo, pi, sqrt, symbols,
                   zoo)

from satassume.sympy_api import ask
from satassume.theories.sign import closure as C
from satassume.theories.sign.closure import (ADD, ALL, AC, AR, FX, IC, IR, MUL, NAN, NANB,
                                             PRED_MASK, PREDS, Q1, TC, TR, Z0, Z1, CLOSURE)
from satassume.theories.sign.closure_adapter import ClosureAdapter


def atom_of(v):
    """The atom of a concrete value, None if SymPy cannot tell."""
    if v is S.NaN:
        return NAN
    if v.is_finite is False:
        r = v.is_extended_real
        return None if r is None else (IR if r else IC)
    v = sympy.expand(v)
    if not v.is_finite or not v.is_complex:
        return None
    if v.is_zero:
        return Z0
    for pred, atom in (("integer", Z1), ("rational", Q1)):
        t = getattr(v, "is_" + pred)
        if t is None:
            return None
        if t:
            return atom
    alg, real = v.is_algebraic, v.is_extended_real
    if alg is None or real is None:
        return None
    return (AR if real else AC) if alg else (TR if real else TC)


SAMPLES = {
    Z0: [S.Zero], Z1: [S.One, S(-2), S(3)], Q1: [Rational(1, 2), Rational(-3, 2)],
    AR: [sqrt(2), 1 - sqrt(2), -sqrt(3)/2], AC: [I, 1 + I, sqrt(2)*I, -I/2],
    TR: [pi, 1 - pi, E, -pi/2], TC: [pi*I, pi + I, E*I],
    IR: [oo, -oo], IC: [zoo, oo*I, oo + I],
}
VALUES = [(a, v) for a, vs in SAMPLES.items() for v in vs]


def test_samples_are_in_their_atoms():
    for a, v in VALUES:
        assert atom_of(v) == a, v


def test_predicate_masks_agree_with_sympy():
    for a, v in VALUES:
        for p, pred in enumerate(PREDS):
            t = getattr(v, "is_" + pred)
            if t is not None:
                assert bool(PRED_MASK[p] >> a & 1) == t, (v, pred)


def test_derived_predicates():
    """The predicates the rule block defines over the basis reach the
    theory as one atom set each (``def_mask``)."""
    from satassume.knowledge.rules import DEF_LITS
    irr = ClosureAdapter.def_mask(DEF_LITS["irrational"])
    if irr is not None:
        assert irr == (1 << AR) | (1 << TR)
    tr = ClosureAdapter.def_mask(DEF_LITS["transcendental"])
    if tr is not None:
        assert tr == (1 << TR) | (1 << TC)


@pytest.mark.parametrize("op", [ADD, MUL])
def test_pairwise_tables_against_sympy(op):
    f = Add if op == ADD else Mul
    unknown = 0
    for (a, va), (b, vb) in product(VALUES, repeat=2):
        r = f(va, vb)
        c = atom_of(r)
        if c is None:
            unknown += 1
            continue
        m = CLOSURE.mop(op, 1 << a, 1 << b)
        assert m & NANB or m >> c & 1, (va, vb, r)
    assert unknown < len(VALUES) ** 2 // 6      # SymPy cannot tell (pi*E, ...)


@pytest.mark.parametrize("op", [ADD, MUL])
def test_three_argument_folds_against_sympy(op):
    f = Add if op == ADD else Mul
    pool = [v for _, v in VALUES][::2]
    unknown = 0
    for args in product(pool, repeat=3):
        c = atom_of(f(*args))
        if c is None:
            unknown += 1
            continue
        m = CLOSURE.fold(op, [1 << atom_of(v) for v in args])
        assert m & NANB or m >> c & 1, (args, f(*args))
    assert unknown < len(pool) ** 3 // 5


@pytest.mark.parametrize("op", [ADD, MUL])
def test_backward_keeps_the_true_atom(op):
    f = Add if op == ADD else Mul
    pool = [v for _, v in VALUES][::2]
    for args in product(pool, repeat=3):
        n = atom_of(f(*args))
        if n is None or n == NAN:
            continue
        newn, out = CLOSURE.node_masks(op, 1 << n, [ALL] * 2 + [1 << atom_of(args[2])])
        assert newn >> n & 1
        for k in range(2):
            assert out[k] >> atom_of(args[k]) & 1, (args, f(*args))


def test_the_tables_decide_the_ring_and_field_rules():
    """What the templates' closure rows say for small arities, the tables
    say for any: rings forward, groups and fields backward."""
    Zm, Qm = PRED_MASK[0], PRED_MASK[1]
    Am, Cm = PRED_MASK[2], PRED_MASK[3]
    nz = ALL & ~(1 << Z0)
    for op, S_ in product((ADD, MUL), (Zm, Qm, Am, Cm)):
        assert CLOSURE.mop(op, S_, S_) & ~NANB & ~S_ == 0
    # backward: x + y in S and y in S give x in S (S a group under +)
    for S_ in (Zm, Qm, Am, Cm):
        _, out = CLOSURE.node_masks(ADD, S_, [ALL, S_])
        assert out[0] & ~S_ == 0
    # x*y in F, y in F nonzero, x finite: x in F (F a field)
    for F_ in (Qm, Am, Cm):
        _, out = CLOSURE.node_masks(MUL, F_, [Cm, F_ & nz])
        assert out[0] & ~F_ == 0
    # no such rule for Z: 2*(1/2) = 1
    _, out = CLOSURE.node_masks(MUL, Zm, [Cm, Zm & nz])
    assert out[0] >> Q1 & 1
    # finite but not complex (no value in scope): as the rows of small
    # arities say, it stays so with a complex term
    assert CLOSURE.mop(ADD, 1 << FX, 1 << Z1) == 1 << FX
    assert CLOSURE.mop(MUL, 1 << FX, 1 << Z1) == 1 << FX
    assert CLOSURE.mop(MUL, 1 << FX, 1 << Z0) == 1 << Z0
    assert CLOSURE.mop(ADD, 1 << FX, 1 << IR) & NANB


def test_const_mask():
    for c in (S(2), S(-1), S.Zero, pi, E, I, oo, -oo, zoo, Rational(-1, 2)):
        assert ClosureAdapter.const_mask(c) >> atom_of(c) & 1
    # a Float claims no ring membership (SymPy: 2.0 is not an integer)
    assert ClosureAdapter.const_mask(sympy.Float(2.0)) & (1 << Q1)


a, b, c, d, e, f, g, u, v, w, x, y, z = symbols("a b c d e f g u v w x y z")
CPX = [Q.complex(t) for t in (a, b, c, d, e, w, x, y, z)]


@pytest.mark.parametrize("prop, assum, expected", [
    # backward through a sum over the caps: a group
    (Q.rational(x), Q.rational(w + x + y + z) & Q.rational(w) & Q.rational(y)
     & Q.rational(z), True),
    (Q.integer(x), Q.integer(w + x + y + z) & Q.integer(w) & Q.integer(y)
     & Q.integer(z), True),
    (Q.irrational(Add(a, b, c, d, x)), Q.irrational(x) & Q.rational(a) & Q.rational(b)
     & Q.rational(c) & Q.rational(d), True),
    (Q.transcendental(x + y + z + w), Q.transcendental(x) & Q.algebraic(y)
     & Q.algebraic(z) & Q.algebraic(w), True),
    (Q.complex(Add(a, b, c, d, e, w, x, y)), And(*CPX), True),
    (Q.algebraic(x), Q.algebraic(sqrt(2)*x + y + z + w) & Q.algebraic(y) & Q.algebraic(z)
     & Q.algebraic(w), True),
    (Q.complex(x), Q.complex(a*b*c*d*x) & Q.complex(a) & Q.complex(b) & Q.complex(c)
     & Q.complex(d) & Q.nonzero(a) & Q.nonzero(b) & Q.nonzero(c) & Q.nonzero(d), True),
    # backward through a product over the caps: a field, nonzero factors
    (Q.algebraic(x), Q.algebraic(x*y*z) & Q.algebraic(y) & Q.algebraic(z) & Q.nonzero(y)
     & Q.nonzero(z), True),
    (Q.irrational(a*b*c*d*e*x), Q.irrational(x) & Q.rational(a) & Q.rational(b)
     & Q.rational(c) & Q.rational(d) & Q.rational(e) & Q.nonzero(a) & Q.nonzero(b)
     & Q.nonzero(c) & Q.nonzero(d) & Q.nonzero(e), True),
    # Z is no field; a zero factor kills the product
    (Q.integer(x), Q.integer(x*y*z*w*a) & Q.integer(y) & Q.integer(z) & Q.integer(w)
     & Q.integer(a) & Q.nonzero(y), None),
    (Q.rational(x), Q.rational(x*y) & Q.rational(y), None),
    (Q.rational(a*b*c*d*e), Q.zero(a) & Q.finite(b) & Q.finite(c) & Q.finite(d)
     & Q.finite(e), True),
    (Q.rational(a*b*c*d*e), Q.zero(a) & Q.rational(b) & Q.rational(c) & Q.rational(d), None),
    # powers: roots and inverses
    (Q.algebraic(x), Q.algebraic(x**2), True),
    (Q.transcendental(x), Q.transcendental(x**2), True),
    (Q.rational(x), Q.rational(1/x) & Q.complex(x), True),
    (Q.algebraic(x), Q.algebraic(sqrt(x)), True),
    (Q.algebraic(x), Q.algebraic(1/sqrt(x)), None),
    (Q.algebraic(x), Q.algebraic(1/sqrt(x)) & Q.finite(x), True),
    # infinities and nan: no claim from oo - oo
    (Q.complex(Add(a, b, c, d, x)), Q.infinite(a) & Q.infinite(b), None),
    (Q.rational(Add(a, b, c, d, x)), Q.positive_infinite(a) & Q.rational(b) & Q.rational(c)
     & Q.rational(d) & Q.rational(x), False),
])
def test_answers(prop, assum, expected):
    assert ask(prop, assum) is expected


def test_wide_sum_with_compound_constant():
    """A sum over both caps has neither closure nor sign rows: the theory
    alone visits its arguments, and must visit the cone below a compound
    one (the 3**(1/3) under the product), or it sees it unconstrained."""
    k = (-2)**Rational(2, 3) * 3**Rational(1, 3) / 3
    xs = symbols("x0:5")
    s = Add(pi, k, *xs)
    assert ask(Q.complex(s), And(*[Q.complex(t) for t in xs])) is True
    g, h = symbols("g h")
    s = 2*h + sqrt(g) + g + sqrt(2) + pi + k + I
    assert ask(Q.infinite(s), Q.integer(h) & Q.rational(g)) is False


def test_inconsistent_assumptions_raise():
    q = Symbol("q", rational=True)
    with pytest.raises(ValueError):
        ask(Q.integer(q), Q.algebraic(u) & Q.integer(q**Rational(1, 3) + u + 1 + pi + I))
    with pytest.raises(ValueError):
        ask(Q.real(x), Q.integer(Add(x, y, z, w, pi)) & Q.rational(x) & Q.rational(y)
            & Q.rational(z) & Q.rational(w))


def test_rows_over_the_caps_are_left_to_the_theory():
    from satassume.knowledge.templates import core

    def preds(rules):
        return {lit[1] for _, concl in rules for lit in (concl if isinstance(concl, list)
                                                        else [concl])}
    assert core.closure_owns(False, 4) and not core.closure_owns(False, 3)
    assert core.closure_owns(True, 5) and not core.closure_owns(True, 4)
    for r in (core._add_rules(4, {}), core._mul_rules(5, {})):
        assert not preds(r) & {'integer', 'rational', 'algebraic', 'complex'}
    assert 'integer' in preds(core._add_rules(3, {}))
