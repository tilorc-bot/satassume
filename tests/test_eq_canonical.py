"""Equality atoms canonical under shared affine bijections (#53 E, H1):
``-x = -y``, ``x + 1 = y + 1`` and ``2*x = 2*y`` are the atom ``eq(x, y)``,
so ``ask`` answers them like ``x = y`` whatever the sides' domain."""

import random

import pytest
from sympy import Float, I, Q, Rational, S, oo, symbols, zoo, nan

from satassume import Engine
from satassume.formula import Not, P
from satassume.relations import relation_atom
from satassume.sympy_api import ask

x, y, z = symbols('x y z')

RESTATED = [(-x, -y), (x + 1, y + 1), (2*x, 2*y), (-3*x + Rational(1, 2),
                                                   -3*y + Rational(1, 2))]


def _same(rel, a, b):
    return ask(rel(*a), Q.eq(x, y), Engine()) == ask(rel(*b), Q.eq(x, y), Engine())


@pytest.mark.parametrize("sides", RESTATED)
def test_restated_atom_is_eq_x_y(sides):
    assert relation_atom("eq", *sides) == relation_atom("eq", x, y)
    assert relation_atom("ne", *sides) == Not(relation_atom("eq", x, y))
    assert relation_atom("eq", *sides[::-1]) == relation_atom("eq", x, y)


@pytest.mark.parametrize("sides", RESTATED)
def test_restated_answers_like_x_eq_y(sides):
    e = Engine()
    for rel in (Q.eq, Q.ne):
        assert ask(rel(*sides), Q.eq(x, y), e) == ask(rel(x, y), Q.eq(x, y), e)
        assert ask(rel(x, y), Q.eq(*sides), e) == ask(rel(x, y), Q.eq(x, y), e)
        assert ask(rel(*sides), Q.ne(x, y), e) == ask(rel(x, y), Q.ne(x, y), e)
    assert ask(Q.eq(*sides), Q.eq(x, y), Engine()) is True
    assert ask(Q.ne(*sides), Q.eq(x, y), Engine()) is False


def test_no_false_merge():
    assert relation_atom("eq", x, 2*y) == P("eq", relation_atom("eq", x, 2*y).expr)
    assert set(relation_atom("eq", x, 2*y).expr) == {x, 2*y}
    assert set(relation_atom("eq", x + 1, y + 2).expr) == {x + 1, y + 2}
    assert set(relation_atom("eq", 2*x + 1, 3*y + 1).expr) == {2*x, 3*y}
    assert ask(Q.eq(x, 2*y), Q.eq(x, y), Engine()) is not True


def test_float_coefficients_not_canonicalised():
    a = relation_atom("eq", Float(2)*x, Float(2)*y)
    assert set(a.expr) == {Float(2)*x, Float(2)*y}
    a = relation_atom("eq", x + Float(1), y + Float(1))
    assert set(a.expr) == {x + Float(1), y + Float(1)}
    a = relation_atom("eq", Float(2)*x, 2*y)
    assert set(a.expr) == {Float(2)*x, 2*y}


def test_infinite_side():
    for assum in (Q.positive_infinite(x), Q.positive_infinite(x) & Q.eq(x, y),
                  Q.negative_infinite(x) & Q.positive_infinite(y)):
        for rel in (Q.eq, Q.ne):
            assert (ask(rel(2*x, 2*y), assum, Engine())
                    == ask(rel(x, y), assum, Engine()))


def test_idempotent():
    for sides in RESTATED + [(x, y), (x, 2*y), (Float(2)*x, Float(2)*y),
                             (2*x + 2*z, 2*y + 2*z), (-x + I, -y + I)]:
        a = relation_atom("eq", *sides)
        assert relation_atom("eq", *a.expr) == a
        assert relation_atom("eq", *a.expr[::-1]) == a
    assert relation_atom("eq", x, y).expr == relation_atom("eq", y, x).expr


def _eq_value(a, b, pt):
    va, vb = a.subs(pt), b.subs(pt)
    if va is S.NaN or vb is S.NaN:
        return False                  # nan equals nothing
    return bool(va == vb)


def test_soundness_sweep():
    rng = random.Random(0)
    ks = [Rational(n, d) for n in (-3, -2, -1, 1, 2, 5) for d in (1, 2, 3)]
    cs = [S.Zero, S.One, Rational(-7, 2), Rational(1, 3)]
    vals = [S.Zero, S.One, Rational(3, 2), -2, I, 1 + 2*I, Rational(-1, 2)*I,
            oo, -oo, zoo, nan]
    for _ in range(40):
        k1 = rng.choice(ks)
        c1 = rng.choice(cs)
        k2 = k1 if rng.random() < 0.6 else rng.choice(ks)
        c2 = c1 if rng.random() < 0.6 else rng.choice(cs)
        lhs, rhs = k1*x + c1, k2*y + c2
        s, t = relation_atom("eq", lhs, rhs).expr
        for _ in range(12):
            pt = {x: rng.choice(vals), y: rng.choice(vals)}
            if rng.random() < 0.3:
                pt[y] = pt[x]
            assert _eq_value(lhs, rhs, pt) == _eq_value(s, t, pt), (lhs, rhs, pt)
        if {s, t} != {lhs, rhs}:
            assert ask(Q.eq(lhs, rhs), Q.eq(s, t), Engine()) is True
            assert ask(Q.ne(lhs, rhs), Q.eq(s, t), Engine()) is False
