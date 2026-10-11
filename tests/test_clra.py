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


# ---------------------------------------------------------------------------
# Backtracking and session restore: the split twins are switched by their
# roles and the part links hold for every value, so an engine that answered
# other queries first (same atoms under other assumptions, conflicting
# assumption sets) answers each query as a fresh engine does.
# ---------------------------------------------------------------------------

SESSION = CASES + [
    (Q.eq(re(x), 1), Q.complex(x) & Q.eq(x, 2), False),
    (Q.eq(re(x), 1), Q.eq(x, 1 + 2 * I), True),
    (Q.eq(re(x), 2), Q.eq(x, 1 + 2 * I), False),
    (Q.real(x), Q.eq(x, 1 + 2 * I), False),
    (Q.imaginary(x), Q.eq(x, 3 * I), True),
    (Q.eq(x, y), Q.eq(x + I * y, 0) & Q.real(x) & Q.real(y), True),
    # open: x - y is no relation atom (the eq/zero gap of #42)
    (Q.zero(x - y), Q.eq(x, 1 + I) & Q.eq(y, 1 + I), None),
    (Q.positive(re(x)), Q.eq(I * x, 2 * y - I) & Q.positive(im(y)), None),
    (Q.negative(im(x)), Q.eq(I * x, 2 * y - I) & Q.real(y) & Q.positive(y), True),
]


def _fresh(p, a):
    from satassume import DictCache, Engine
    return ask(p, a, Engine(cache=DictCache()))


@pytest.mark.parametrize("seed", range(4))
def test_shared_engine_matches_fresh(seed):
    from satassume import DictCache, Engine
    rnd = random.Random(seed)
    order = list(SESSION) * 2
    rnd.shuffle(order)
    eng = Engine(cache=DictCache())
    for p, a, _ in order:
        try:
            got = ask(p, a, eng)
        except ValueError:
            got = "inconsistent"
        try:
            want = _fresh(p, a)
        except ValueError:
            want = "inconsistent"
        assert got == want, (p, a)
    # an inconsistent set in the middle of a session leaves the engine usable
    with pytest.raises(ValueError):
        ask(Q.real(x), Q.eq(x, I) & Q.real(x), eng)
    for p, a, expected in SESSION:
        assert ask(p, a, eng) is _fresh(p, a) is expected, (p, a)


ZERO_ATOMS = [Eq(x + I * y, 0, evaluate=False), Eq(I * x + 2 * I * y, 0, evaluate=False),
              Eq((1 + I) * x - (2 - I) * re(y) + 3, 0, evaluate=False),
              Eq(x - I * x - Rational(1, 2) * I, 0, evaluate=False)]


@pytest.mark.parametrize("atom", ZERO_ATOMS, ids=str)
def test_zero_atom_clauses(atom):
    """The extra clauses of ``eq(e, 0)`` (``Relations._interpret_complex``):
    under the guard (every term finite) ``real(e) <-> ti`` and
    ``imaginary(e) <-> tr & ~ti``, at every finite value."""
    (rr, ri), _, _ = cinterpret(atom)
    e = atom.lhs
    syms = sorted(atom.free_symbols, key=str)
    for vals in itertools.product(VALUES, repeat=len(syms)):
        env = dict(zip(syms, vals))
        v = e.subs(env).expand()
        tr, ti = _holds(rr, env), _holds(ri, env)
        assert (v.is_real is True) == ti, (atom, env)
        assert (v.is_imaginary is True) == (tr and not ti), (atom, env)


def test_numeric_part_folds_into_the_constant():
    """A part that evaluates to a number (``re(w) = 0`` for an imaginary
    ``w``) goes to the constant: no theory variable is named by a number."""
    from sympy import Symbol
    w = Symbol("w", imaginary=True)
    for atom in (Eq(w, 2 * I, evaluate=False), Eq(x + w, 1 + 2 * I, evaluate=False),
                 Eq(I * w, 3, evaluate=False)):
        (rr, ri), terms, kinds = cinterpret(Q.eq(*atom.args))
        for r in (rr, ri):
            if r is not True and r is not False:
                assert all(t.free_symbols for t, _ in r[0][0])
        assert all(t.free_symbols for t in terms)
        for env in ({w: 2 * I, x: S(1)}, {w: -I, x: 1 + 3 * I}, {w: 3 * I, x: 1 - I}):
            want = (atom.lhs - atom.rhs).subs(env).expand() == 0
            assert (_holds(rr, env) and _holds(ri, env)) == want
    assert ask(Q.eq(im(w), 2), Q.eq(w, 2 * I)) is True
    assert ask(Q.eq(w, 2 * I), Q.eq(im(w), 2)) is True
    assert ask(Q.zero(re(x)), Q.eq(x + w, 2 * I) & Q.complex(x)) is True
