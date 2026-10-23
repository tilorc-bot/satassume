"""The sign of a product in the theory (#315 step 4, relations "Products").

LRA reads a product of two symbolic factors or more as one opaque term,
so ``-x*y`` and ``x*y`` share the term ``x*y``.  The glue is on for two
sign atoms whose arguments hold the same product (twins of
``relations.bound_twins``), and a linked ``c*m + k`` gets ``real(c*m + k)
<-> real(m)``.  These replace the factor set ``(c, rest)`` of the Mul
template (``core._mul_factor_sets``).  A half product ``3*k*e/2`` is a half
sum of one term for the parity check."""
import pytest
from sympy import I, Q, Rational, S, Symbol, nan, oo, polar_lift, symbols, zoo

from satassume.engine import DictCache, Engine
from satassume.relations import bound_twins, half_terms, product_terms, relation_atom
from satassume.scope import EMPTY, theory_scope
from satassume.sat.formula import atoms_of
from satassume.sympy_api import _formula, ask

x, y, z = symbols("x y z")


def F(expr):
    return _formula(expr, True, True)


def fresh(p, a=True):
    return ask(p, a, engine=Engine(cache=DictCache()))


def test_product_terms():
    assert product_terms(-x*y) == (x*y,)
    assert product_terms(3*x*y) == (x*y,)
    assert product_terms(x*y) == (x*y,)
    assert product_terms(x*y - 1) == (x*y,)
    assert product_terms(2*x*y*z + x) == (x*y*z,)
    assert product_terms(-x) == ()
    assert product_terms(x + 1) == ()
    assert product_terms(S(3)) == ()


@pytest.mark.parametrize("p, a, expected", [
    # the refine stream's three (the factor set gave them)
    (Q.positive(-x*y), Q.negative(x*y), True),
    (Q.negative(-x*y), Q.negative(x*y), False),
    (Q.zero(-x*y), Q.negative(x*y), False),
    # the issue's table
    (Q.positive(x*y), Q.positive(3*x*y), True),
    (Q.positive(3*x*y), Q.positive(x*y), True),
    (Q.nonnegative(-2*x*y*z), Q.nonpositive(x*y*z), True),
    # a product against a sum holding it, and two sums
    (Q.positive(3*x*y), Q.positive(x*y - 1), True),
    (Q.positive(x*y - 1), Q.positive(3*x*y - 3), True),
    (Q.positive(x*y + 1), Q.positive(3*x*y), True),
    # extended: -oo < x*y < 0 gives 0 < -x*y <= oo, not a finite one
    (Q.extended_positive(-x*y), Q.extended_negative(x*y), True),
    (Q.positive(-x*y), Q.extended_negative(x*y), None),
    (Q.finite(-x*y), Q.extended_negative(x*y), None),
])
def test_signs_of_c_times_m(p, a, expected):
    assert fresh(p, a) is expected


@pytest.mark.parametrize("p, a, expected", [
    # an order atom on 2*x*y is read on the term x*y; its infinities are
    # those of x*y (_order_infinite), so extended_real(2*x*y) must reach
    # x*y: the extended_real link (the factor set gave it by the rows)
    (Q.gt(2*x*y, 0), Q.gt(2*x*y, 1), True),
    (Q.real(x*y), Q.gt(2*x*y, 1) & Q.lt(2*x*y, 3), True),
    (Q.real(2*x*y), Q.gt(2*x*y, 1) & Q.lt(2*x*y, 3), True),
    (Q.lt(-x*y, 0), Q.gt(3*x*y, 1), True),
])
def test_relations_on_c_times_m(p, a, expected):
    assert fresh(p, a) is expected


@pytest.mark.parametrize("a", [
    Q.le(2*x*y, 0) & Q.gt(2*x*y, 1),
    Q.negative_infinite(2*x*y) & Q.gt(2*x*y, z),
])
def test_inconsistent_relations_on_c_times_m(a):
    with pytest.raises(ValueError):
        fresh(Q.positive(z), a)


def test_the_pair_switches_the_glue_on():
    s = theory_scope(F(Q.negative(x*y)), F(Q.positive(-x*y)))
    assert s.glue and not s.transfer
    assert {x*y, -x*y} <= s.linked_terms
    # one product, or two over different products, or a product and a sum
    # over the same symbols that does not hold it: no pair
    assert theory_scope(None, F(Q.positive(-x*y))) is EMPTY
    assert theory_scope(F(Q.negative(x*z)), F(Q.positive(-x*y))) is EMPTY
    assert theory_scope(F(Q.negative(x + y)), F(Q.positive(-x*y))) is EMPTY
    # the same argument twice is the rows'
    assert theory_scope(F(Q.negative(x*y)), F(Q.positive(x*y))) is EMPTY
    # a non-sign atom on the product calls for nothing
    assert theory_scope(F(Q.integer(x*y)), F(Q.integer(3*x*y))) is EMPTY


def test_the_twin_is_the_formulas_own_argument():
    p, a = atoms_of(F(Q.positive(-x*y))), atoms_of(F(Q.negative(x*y)))
    assert bound_twins(p, a) == [relation_atom("lt", S.Zero, -x*y)]
    assert bound_twins(a, p) == [relation_atom("lt", S.Zero, x*y)]
    assert bound_twins(p) == []


def test_half_products():
    k = Symbol("k", integer=True)
    e = Symbol("e", even=True)
    assert half_terms(3*k*e/2) == [k*e]
    assert half_terms(k/2) is None             # one factor: the Mul rows
    assert half_terms(3*k*e) is None
    eng = Engine(cache=DictCache())
    # SymPy's test_arit::test_Mul_is_integer
    assert eng.is_(3*k*e/2, "integer") is True
    o = Symbol("o", odd=True)
    assert eng.is_(3*k*o/2, "integer") is None
    assert eng.is_(3*o*o/2, "integer") is False


def test_polar_of_a_positive_times_polars():
    # SymPy's test_arit::test_polar: a row of templates/mul.py now
    p = Symbol("p", polar=True)
    assert Engine(cache=DictCache()).is_(polar_lift(-2)*p, "polar") is True


@pytest.mark.parametrize("c", [S(-1), S(3), Rational(1, 2), Rational(-7, 3)])
@pytest.mark.parametrize("m", [S(0), S(2), S(-5), Rational(1, 3), oo, -oo, zoo, nan, I, 1 + I])
def test_real_link_on_values(c, m):
    # real(c*m + k) <-> real(m) and extended_real(c*m + k) <->
    # extended_real(m) for a Rational c != 0 and a Rational k: an infinite,
    # nan or non-real m stays one through c*m + k, +-oo stays +-oo
    for k in (S(0), S(1), Rational(-5, 2)):
        v = c*m + k
        assert bool(v.is_real) == bool(m.is_real), (c, m, k)
        assert bool(v.is_extended_real) == bool(m.is_extended_real), (c, m, k)


@pytest.mark.xfail(strict=True, reason="#315 step 4: the factor set (c, rest) is gone, and "
                   "no theory relates the non-sign facts of -m and m without a sign pair")
@pytest.mark.parametrize("p, a", [
    (Q.integer(x*y), Q.integer(-x*y)),
    (Q.infinite(x*y), Q.infinite(2*x*y)),
    (Q.real(x*y), Q.real(2*x*y)),
])
def test_non_sign_facts_of_c_times_m(p, a):
    assert fresh(p, a) is True
