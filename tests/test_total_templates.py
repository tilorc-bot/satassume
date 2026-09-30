"""Regression tests for the template gaps the totality gate found
(``tools/totality.py``, ``tests/test_totality.py``; #53 stage 1).

A non-total block that is not unsound is a gap: the node's block decides
facts about its children that their own blocks cannot, so the answer
about the children depends on whether the parent is in the session.  The
three found on ``main``: a real value of floor/ceiling is an integer, a
transcendental times nonzero algebraics is transcendental, and a Mul must
derive the products other templates split off its factors.  (The unsound
``commutative`` rules of #47 and #59 are fixed and tested by #54 and #61,
``tests/test_noncommutative.py``.)

Every ``fresh`` query runs on its own engine: these are statements about
the templates, not about a session's history.
"""
from sympy import I, Q, Rational, exp, floor, ceiling, pi, symbols

from satassume import DictCache, Engine
from satassume.sympy_api import ask

x, y = symbols('x y')


def fresh(p, a=True):
    return ask(p, a, Engine(cache=DictCache()))


def test_real_rounding_is_an_integer():
    # floor(1 + I/2) == 1 is real and an integer; floor(oo) == oo is not real
    assert fresh(Q.integer(floor(x)), Q.real(floor(x))) is True
    assert fresh(Q.integer(ceiling(y)), Q.real(ceiling(y))) is True
    assert fresh(Q.irrational(ceiling(y))) is False
    assert fresh(Q.integer(floor(x)), Q.extended_real(floor(x))) is None


def test_transcendental_times_nonzero_algebraic():
    assert fresh(Q.transcendental(pi * x), Q.algebraic(x) & Q.nonzero(x)) is True
    assert fresh(Q.transcendental(pi * x), Q.algebraic(x)) is None      # x = 0
    assert fresh(Q.algebraic(3 * I + pi * I)) is False
    assert fresh(Q.transcendental(3 * I + pi * I)) is True


def test_rational_coefficient_product_derives_the_coefficient_free_product():
    # 2*x*y is related to x*y by the binary c*x rules
    assert fresh(Q.positive(2 * x * y), Q.positive(x * y)) is True
    assert fresh(Q.positive(x * y), Q.positive(2 * x * y)) is True
    assert fresh(Q.even(2 * x * y), Q.integer(x * y)) is True
    assert fresh(Q.rational(x * y), Q.rational(Rational(1, 2) * x * y)) is True


def test_i_pi_product_derives_the_product_of_the_other_factors():
    # exp(I*pi*x*y) reasons about x*y; its argument now derives x*y too
    # (the block over (I, pi, x*y) -> I*pi*x*y), so facts about x*y reach
    # the argument and through it the exp
    assert fresh(Q.finite(x * y), Q.finite(I * pi * x * y)) is True
    assert fresh(Q.transcendental(3 * I * pi * x * y), Q.algebraic(x * y) & Q.nonzero(x * y)) is True
    assert fresh(Q.zero(exp(I * pi * x * y)), Q.finite(x * y)) is False
    assert fresh(Q.finite(exp(I * pi * x * y)), Q.finite(x * y)) is True
