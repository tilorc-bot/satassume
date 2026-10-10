"""The sign theory (issue #149, T1 stage 1): its atom tables against
SymPy's arithmetic, and the answers it adds end to end."""
from __future__ import annotations

from itertools import product

import pytest

sympy = pytest.importorskip("sympy")

from sympy import (Add, And, I, Mul, Q, Rational, S, Symbol, im, nan, oo, pi, re, sqrt,
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
    # an infinity times a non-real or an infinity off the axis: an infinity
    (Q.finite(a*b*c*d*(1 + I)),
     Q.infinite(a) & Q.nonzero(b) & Q.nonzero(c) & Q.nonzero(d), False),
    (Q.finite(a*b*c*d*e), Q.infinite(a) & Q.infinite(b) & Q.imaginary(c) & Q.nonzero(d)
     & Q.nonzero(e), False),
    # -oo*d*(positive) is -oo: d (infinite) is +oo, not an infinity off the axis
    (Q.extended_positive(d), Q.extended_negative(e) & Q.infinite(d) & Q.negative_infinite(a)
     & Q.negative(x) & Q.negative_infinite(pi*a*d*e**2*x**2), True),
    # rows dropped over the caps (templates.core.sign_owns): the theory decides
    (Q.extended_real(Add(a, b, c, d, e, w, x)), And(*[Q.real(t) for t in (a, b, c, d, e, w, x)]),
     True),
    (Q.extended_real(Add(a, b, c, d, e, w, x)), Q.imaginary(a) & And(*[Q.real(t) for t in
                                                                      (b, c, d, e, w, x)]), False),
    (Q.zero(a*b*c*d*e*x), Q.zero(a) & Q.finite(b) & Q.finite(c) & Q.finite(d) & Q.finite(e)
     & Q.finite(x), True),
])
def test_answers(prop, assum, expected):
    assert ask(prop, assum) is expected


def test_inconsistent_wide_product_raises():
    with pytest.raises(ValueError):
        ask(Q.real(x), Q.positive(a*b*c*d*e) & Q.negative(a) & Q.positive(b) & Q.positive(c)
            & Q.positive(d) & Q.positive(e))


def test_derived_atoms_are_theory_atoms():
    """``~negative_infinite(x)`` (a disjunction of basis literals) reaches the
    theory as one literal of its derived atom (``sign_adapter.def_mask``):
    the sum is decided by propagation instead of a search over both cases of
    every term (``Session._dv``; there are enough such atoms for the set to
    share them, ``engine._NEG_SHARED``)."""
    from satassume.engine import Engine
    xs = symbols("x0:12")
    s = Add(*xs)
    a = Q.positive_infinite(xs[0]) & And(*[Q.extended_real(t) & ~Q.negative_infinite(t)
                                          for t in xs[1:]])
    eng = Engine()
    assert ask(Q.positive_infinite(s), a, engine=eng) is True
    assert eng.stats["searches"] == 0


def test_def_mask():
    from satassume.knowledge.rules import DEF_LITS
    m = sign_adapter.def_mask(DEF_LITS["negative_infinite"])
    assert m == 1 << NI
    assert sign_adapter.def_mask(DEF_LITS["positive"]) == 1 << F(1, 0)
    assert sign_adapter.def_mask(("&", (999,))) is None


def _theory_with_sum():
    from satassume.theories.sign.sign import SignTheory
    th = SignTheory()
    x, y, n = th.term(), th.term(), th.term()
    th.add_node(ADD, n, [x, y])
    pos = PRED_MASK[PREDS.index("extended_positive")]
    for v, t in ((1, x), (2, y), (3, n)):
        th.register_atom(v, (t, pos))
    return th


def test_conflict_and_budget():
    """``x, y`` extended positive and ``x + y`` not: a conflict; past the
    conflict budget the theory gives up instead (no claim), and is back at
    the root with a new budget (``satassume.sat.theory``, "Giving up")."""
    th = _theory_with_sum()
    th.push_level()
    for lit in (1, 2, -3):
        th.assert_lit(lit)
    out = th.propagate()
    assert out and sorted(out[-1][1]) == [-2, -1, 3]
    assert th.check() is not None
    th.pop_level()
    th = _theory_with_sum()
    th.budget = 0
    th.push_level()
    for lit in (1, 2, -3):
        th.assert_lit(lit)
    assert th.propagate() == [] and th.gave_up
    assert th.check() is None
    th.pop_level()
    assert not th.gave_up and th.budget == th.MAX_CONFLICTS


def test_rows_over_the_caps_are_left_to_the_theory():
    """Over the arity caps the templates leave the sign rows out
    (``templates.core.sign_owns``) and keep the others."""
    from satassume.knowledge.templates import core

    def preds(rules):
        return {lit[1] for _, concl in rules for lit in (concl if isinstance(concl, list)
                                                        else [concl])}
    assert core.sign_owns(False, 7) and not core.sign_owns(False, 6)
    assert core.sign_owns(True, 5) and not core.sign_owns(True, 4)
    assert len(core._add_rules(7, {})) < len(core._add_rules(6, {})) // 4
    assert len(core._mul_rules(5, {})) < len(core._mul_rules(4, {})) // 2
    assert 'composite' in preds(core._add_rules(7, {}))
    assert 'even' not in preds(core._add_rules(7, {}))        # INTLAT's (intlat_adapter.owns)
    assert 'integer' not in preds(core._add_rules(7, {}))     # CLOSURE's (closure_owns)
    assert 'extended_positive' not in preds(core._add_rules(7, {}))


def test_nodes_reached_through_a_registered_node_are_registered():
    # the 7-term sum is the only node over the caps the query visits; the
    # theory registering it visits its products of 5 and 6 factors, over the
    # caps too: the same sync registers them (the answer needs both)
    b, c, e, v, x, y = symbols("b c e v x y")
    s = -oo + v + x - I + 2*y + b*c*v*x**2*y**2 - I*v*e**2*x**2*y**2
    a = And(Q.even(e), Q.integer(y), Q.nonpositive(x), Q.nonzero(v), Q.odd(b), Q.prime(c))
    assert ask(Q.extended_positive(s), a) is False
