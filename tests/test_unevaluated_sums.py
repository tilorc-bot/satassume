"""Unevaluated sums whose rebuilt parts differ from the node (#184).

``_half_split`` (deleted in #315 step 3; ``relations.half_terms`` now) read the parity of a sum ``c0 + sum(c_k*t_k)`` from its
last Rational term only, and built ``t_k`` with an evaluating ``Mul``
(``Mul(1/2, x, 1/x)`` read as ``1/2``); the ``x - 1`` slot of log, asin
and acos rebuilt an unevaluated sum (``Add(y, -y, 1) - 1`` is ``0``).
"""
import pytest
from sympy import Add, Mul, Q, S, acos, asin, log, symbols

from satassume import DictCache, Engine
from satassume.sympy_api import ask

x, y = symbols('x y')
half = S(1)/2


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("query, assumptions, expected", [
    # x + 1/2 + 1/2 is x + 1: an integer, not a half-integer
    (Q.integer(Add(x, half, half, evaluate=False)), Q.integer(x), True),
    (Q.integer(Add(x, half, half, evaluate=False)), Q.even(x), True),
    (Q.integer(Add(x, half, half, half, evaluate=False)), Q.integer(x), False),
    (Q.integer(Add(x, half, S(3)/2, evaluate=False)), Q.odd(x), True),
    # x*(1/x) is nan at x = 0: neither an integer nor a rational
    (Q.integer(Add(Mul(half, x, 1/x, evaluate=False), half, evaluate=False)), Q.real(x), None),
    (Q.rational(Add(Mul(half, x, 1/x, evaluate=False), half, evaluate=False)), True, None),
    # the argument is nan at y = oo
    (Q.zero(log(Add(y, -y, 1, evaluate=False), evaluate=False)), Q.extended_real(y), None),
    # (asin's one rule over the slot needs the argument nonnegative, which
    # excludes nan already: this case passes on main too)
    (Q.zero(asin(Add(y, -y, 1, evaluate=False), evaluate=False)), Q.extended_real(y), None),
    (Q.zero(acos(Add(y, -y, 1, evaluate=False), evaluate=False)), Q.extended_real(y), None),
])
def test_reproducers(query, assumptions, expected):
    assert ask(query, assumptions, fresh()) is expected


def test_evaluated_sums_keep_their_answers():
    assert ask(Q.integer((x + 1)/2), Q.odd(x), fresh()) is True
    assert ask(Q.integer(x/2 + half), Q.odd(x), fresh()) is True
    assert ask(Q.integer(x*y/2 + half), Q.odd(x) & Q.odd(y), fresh()) is True
    assert ask(Q.zero(log(y + 1)), Q.zero(y), fresh()) is True
    assert ask(Q.zero(log(y + 1)), Q.positive(y), fresh()) is False
    assert ask(Q.zero(acos(y + 1)), Q.zero(y), fresh()) is True
    # unevaluated, but its terms rebuild to the same terms
    assert ask(Q.zero(log(Add(y, 1, evaluate=False))), Q.zero(y), fresh()) is True
    assert ask(Q.zero(acos(Add(y, 1, evaluate=False))), Q.zero(y), fresh()) is True
    assert ask(Q.positive(log(Add(y, 2, evaluate=False))), Q.positive(y), fresh()) is True
