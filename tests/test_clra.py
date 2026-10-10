"""CLRA (issue #149, T4): equalities over Q(i) split into real and imaginary
linear forms (``lra_adapter.cinterpret``, ``Relations._interpret_complex``,
``Relations._parts``)."""
import itertools
import random

import pytest
from sympy import (I, Eq, Function, Q, Rational, S, im, nan, oo, pi, re,
                   symbols, zoo)

from satassume.sympy_api import ask
from satassume.theories.lra.lra_adapter import cinterpret

x, y, z = symbols('x y z')
f = Function('f')

# finite complex values, with 0, reals and imaginaries
VALUES = [S(0), S(1), S(-2), I, -3 * I, 1 + I, Rational(1, 2) - 2 * I]


def _value(form, k, env):
    out = S(k)
    for t, c in form:
        out += S(c.p) / S(c.q) * t.subs(env) if hasattr(c, "p") else S(str(c)) * t.subs(env)
    return out


def _holds(r, env):
    """The truth of one form of :func:`cinterpret` at ``env``."""
    if r is True or r is False:
        return r
    (items, rhs, strict, equality), positive = r
    assert equality and not strict and positive
    lhs = sum((S(c.numerator) / c.denominator * t.subs(env) for t, c in items), S(0))
    return (lhs - S(rhs.numerator) / rhs.denominator).expand() == 0


ATOMS = [
    Eq(x, 1 + 2 * I, evaluate=False), Eq(x + I * y, 0, evaluate=False),
    Eq(I * x, 2 * y - I, evaluate=False), Eq((1 + I) * x, (2 - I) * y + 3, evaluate=False),
    Eq(re(x) + I * im(y), I, evaluate=False), Eq(I * x + 2 * I * y, 0, evaluate=False),
    Eq(x - I * x, Rational(1, 2) * I, evaluate=False), Eq(I * re(x), im(x) * I, evaluate=False),
]


@pytest.mark.parametrize("atom", ATOMS, ids=str)
def test_split_is_exact_on_finite_values(atom):
    """For every finite complex value of the terms, the atom holds iff both
    forms hold with each part variable at its part's value (the guard of
    the twin is the finiteness of every term)."""
    (rr, ri), terms, kinds = cinterpret(atom)
    syms = sorted(atom.free_symbols, key=str)
    for vals in itertools.product(VALUES, repeat=len(syms)):
        env = dict(zip(syms, vals))
        truth = (atom.lhs - atom.rhs).subs(env).expand() == 0
        assert truth == (_holds(rr, env) and _holds(ri, env)), (atom, env)
    for u in terms:
        assert kinds[u] == ("real" if isinstance(u, (re, im)) else "complex")


@pytest.mark.parametrize("atom", [Eq(x, y), Eq(x, 1), Eq(x * I, oo), Eq(x, zoo)], ids=str)
def test_not_split(atom):
    """No ``I``: the real path's (or nobody's); an infinity: unread."""
    assert cinterpret(atom) is None


@pytest.mark.parametrize("u", [S(0), S(2), -I, 3 + I, oo, -oo, oo * I, zoo, nan])
def test_part_links_hold_for_every_value(u):
    """The clauses of ``Relations._parts``, evaluated at special values
    (infinities and nan included; ``complex`` is SymPy's finite)."""
    real, cpx, imag = (u.is_extended_real and u.is_finite) is True, u.is_finite is True, \
        (u.is_imaginary is True)
    R, V = re(u), im(u)
    finite_real = lambda v: v.is_real is True and v.is_finite is True
    zi, zr = cpx and V == 0, cpx and R == 0
    if real:
        assert zi and R == u
    if cpx and zi:
        assert real
    if imag:
        assert zr and not zi
    if cpx and zr and not zi:
        assert imag
    if finite_real(R) and finite_real(V):
        assert cpx                         # #19: finite parts, finite number


CASES = [
    (Q.eq(re(x), 1), Q.eq(x, 1 + 2 * I), True),
    (Q.eq(im(x), 2), Q.eq(x, 1 + 2 * I), True),
    (Q.eq(im(x), 1), Q.eq(x, 1 + 2 * I), False),
    (Q.real(x), Q.eq(x, 1 + 2 * I), False),
    (Q.imaginary(I * x + 2 * I * y), Q.real(x) & Q.real(y) & Q.gt(x + 2 * y, 0), True),
    (Q.zero(x - I), Q.eq(x, I), True),
    (Q.eq(x, I), Q.zero(x - I), True),
    (Q.real(x), Q.complex(x) & Q.eq(im(x), 0), True),
    (Q.imaginary(x), Q.positive(im(x)) & Q.eq(re(x), 0), True),
    (Q.real(I * x), Q.complex(x) & Q.eq(re(x), 0), True),
    (Q.eq(f(x), f(1)), Q.complex(x) & Q.eq(re(x), 1) & Q.eq(im(x), 0), True),
    (Q.integer(re(x) / pi), Q.positive(x) & Q.lt(x, pi / 2), False),
    (Q.zero(y), Q.real(x) & Q.real(y) & Q.eq(x + I * y, 0), True),
    # stays open: x may be infinite (re(oo) = oo, im(oo) = 0)
    (Q.positive(x), Q.zero(im(x)) & Q.gt(re(x), 0), None),
    (Q.imaginary(x), Q.eq(re(x), 0), None),
    (Q.eq(x, I), Q.eq(im(x), 1), None),
]


@pytest.mark.parametrize("p, a, expected", CASES, ids=str)
def test_answers(p, a, expected):
    assert ask(p, a) is expected


def test_split_matches_random_values():
    """Random Q(i)-linear equalities in three terms against substitution."""
    rnd = random.Random(0)
    coeffs = [1, -1, 2, Rational(1, 3), I, -I, 1 + I, 2 - 3 * I]
    terms = [x, y, re(z), im(x)]
    for _ in range(200):
        lhs = sum(rnd.choice(coeffs) * rnd.choice(terms) for _ in range(rnd.randint(1, 3)))
        rhs = rnd.choice(coeffs) * rnd.choice([S(1), y]) + rnd.choice([0, I, 2])
        atom = Eq(lhs, rhs, evaluate=False)
        c = cinterpret(atom)
        if c is None:
            assert not (lhs - rhs).has(I)
            continue
        (rr, ri), _, _ = c
        env = {x: rnd.choice(VALUES), y: rnd.choice(VALUES), z: rnd.choice(VALUES)}
        truth = (lhs - rhs).subs(env).expand() == 0
        assert truth == (_holds(rr, env) and _holds(ri, env)), (atom, env)
