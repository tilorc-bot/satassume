"""Unevaluated products are not their evaluated forms (#161).

An unevaluated ``Mul(c, x, 1/x)`` or ``Mul(c, x, 0)`` is nan at ``x = 0``
or ``x = oo``; building the rest of such a product with an evaluating
``Mul`` turns it into ``c`` or ``0``.  The LRA reader (``lra_adapter._lin``),
``templates.core.ipi_split`` (the ``s`` of ``exp(I*pi*c*s)``) and the
derived ``c*t`` product of the Mul templates used to do that, and gave
definite answers that the values contradict.  The rest of a product is
now read only when the built product keeps exactly its factors
(``templates.core.kept_product``)."""
from __future__ import annotations

import pytest

sympy = pytest.importorskip("sympy")
from sympy import (E, Eq, Ge, Gt, I, Lt, Mul, Ne, Pow, Q, Rational as R, S, exp, nan,
                   oo, pi, sqrt, symbols, zoo)

from satassume.engine import Engine
from satassume.knowledge.templates.core import ipi_split, kept_product
from satassume.sympy_api import ask

x, y = symbols("x y")
A, B = symbols("A B", commutative=False)


def U(*a):
    return Mul(*a, evaluate=False)


def test_kept_product():
    assert kept_product((x, y)) == x * y
    assert kept_product((y, x)) == x * y              # commutative order is free
    assert kept_product((A, B)) == A * B
    assert kept_product((x, 1 / x)) is None           # builds to 1
    assert kept_product((x, S.Zero)) is None          # builds to 0
    assert kept_product((x, x)) is None               # builds to x**2
    assert kept_product((U(x, 1 / x), y)) is None     # flattens to y
    assert kept_product((S(2), S(3), x)) is None      # merges the numbers


def test_ipi_split():
    assert ipi_split(U(I, pi, x)) == (1, x)
    assert ipi_split(U(R(1, 2), I, pi, x, y)) == (R(1, 2), x * y)
    assert ipi_split(U(2, I, pi, x, 1 / x)) is None
    assert ipi_split(U(I, pi, x, 0)) is None
    assert ipi_split(U(I, pi, 0)) == (0, None)


m1 = U(R(1, 3), x, 3 / x)                 # nan at x = 0, oo
E1 = exp(U(2, I, pi, x, 1 / x), evaluate=False)
E2 = exp(U(I, pi, x, 1 / x), evaluate=False)

#: (proposition, assumptions): each was answered definitely before #161
#: although the proposition is nan at a point the assumptions allow
REPROS = [
    (Q.eq(m1, 1), True), (Q.eq(m1, 1), Q.real(x)), (Q.eq(m1, 1), Q.extended_real(x)),
    (Q.ge(m1, 1), Q.extended_real(x)), (Q.lt(m1, 2), Q.extended_real(x)),
    (Q.gt(m1 + y, y), Q.extended_real(x) & Q.real(y)),
    (Q.ne(m1, 1), True), (Q.ne(m1, 1), Q.extended_real(x)),
    (Q.positive(E1), True), (Q.real(E1), True), (Q.finite(E1), True),
    (Q.positive(E1), Q.real(x)), (Q.negative(E2), True), (Q.real(E2), True),
    (Q.integer(U(R(3, 2), U(x, 1 / x), x / 6)), Q.zero(x)),
]


@pytest.mark.parametrize("prop, asm", REPROS)
def test_repro_is_open(prop, asm):
    assert ask(prop, asm, engine=Engine()) is None


def test_kept_products_still_answer():
    # the guard only refuses a rest that the build changes
    assert ask(Q.ge(U(R(1, 2), x, y), 0), Q.positive(x) & Q.positive(y),
               engine=Engine()) is True
    assert ask(Q.gt(U(R(1, 3), y, x), x * y / 4), Q.positive(x) & Q.positive(y),
               engine=Engine()) is True
    assert ask(Q.positive(exp(U(2, I, pi, x, y), evaluate=False)),
               Q.integer(x) & Q.integer(y), engine=Engine()) is True


# --- brute force ------------------------------------------------------------

NODES = [m1, U(R(1, 3), x, 0), U(2, x, 1 / x), U(x, y, 1 / y), U(R(1, 2), U(x, 1 / x), y),
         U(2, x, 1 / x) + y, E1, E2, exp(U(I, pi, x, 0), evaluate=False),
         Pow(E, U(I, pi, x, 1 / x), evaluate=False),
         exp(U(R(1, 2), I, pi, x, 1 / x, y), evaluate=False), U(-1, x, 1 / x, y)]
UNARY = ["positive", "negative", "zero", "nonzero", "real", "finite", "integer", "even",
         "rational", "imaginary"]
RELS = [(Q.eq, Eq), (Q.ne, Ne), (Q.ge, Ge), (Q.gt, Gt), (Q.lt, Lt)]
ASMS = [True, Q.real(x), Q.extended_real(x), Q.integer(x) & Q.integer(y),
        Q.nonzero(x) & Q.finite(x), Q.zero(x)]
VALS = [S(0), S(1), S(-1), S(2), R(1, 2), R(-2, 3), oo, -oo, zoo, I, 1 + I, sqrt(2)]


def _value(e, g):
    def build(t):
        return t if not t.args else t.func(*[build(a) for a in t.args])
    return build(e.xreplace(g))


def _holds(asm, g):
    if asm is True:
        return True
    parts = asm.args if asm.func.__name__ == "And" else (asm,)
    return all(getattr(a.arguments[0].xreplace(g), "is_" + a.function.name) is True
               for a in parts)


def _truth(name, rel, v, c):
    """The proposition at the value ``v``; None when it is undefined (nan)."""
    if v is nan or v.has(nan):
        return None
    if rel is None:
        return getattr(v, "is_" + name)
    if v.is_extended_real is not True:
        return rel is Ne
    return bool(rel(v, c))


def test_brute_force_definite_answers_hold():
    """Every definite answer on these nodes holds at every grid point the
    assumptions allow, and none is given where the node is nan there."""
    grid = [{x: a, y: b} for a in VALS for b in VALS]
    bad = []
    for n in NODES:
        values = [_value(n, g) for g in grid]
        props = [(getattr(Q, p)(n), p, None, None) for p in UNARY]
        props += [(q(n, c), None, r, c) for q, r in RELS for c in (S(0), S(1))]
        for asm in ASMS:
            pts = [i for i, g in enumerate(grid) if _holds(asm, g)]
            for prop, name, rel, c in props:
                r = ask(prop, asm, engine=Engine())
                if r is None:
                    continue
                for i in pts:
                    t = _truth(name, rel, values[i], c)
                    if t is None or t != r:
                        bad.append((prop, asm, r, grid[i]))
                        break
    assert not bad, bad[:5]
