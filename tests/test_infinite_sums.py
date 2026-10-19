"""Infinite sums (#187).

An infinite term that is not ``-oo``, plus other terms that are not
``-oo``, was called an infinite sum.  The other terms may be ``zoo``, nan
or an opposite infinity off the real axis: ``oo + zoo``, ``oo + nan`` and
``oo*I - oo*I`` are nan, which is not infinite.
"""
import pytest
from sympy import Add, I, Q, log, nan, oo, symbols, zoo

from satassume import DictCache, Engine
from satassume.sympy_api import ask

x, y = symbols('x y')


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("query, assumptions", [
    (Q.infinite(Add(oo, zoo, evaluate=False)), True),
    (Q.infinite(Add(oo, nan, evaluate=False)), True),
    (Q.infinite(Add(oo*I, -oo*I, evaluate=False)), True),
    # 1/0 is zoo: the value is nan
    (Q.infinite(oo + 1/x), Q.zero(x)),
    (Q.zero(1/(oo + 1/x)), Q.integer(x)),
    # log(0) is zoo: nan at x = 0
    (Q.infinite(log(x) + oo), Q.real(x)),
    (Q.infinite(x + y), Q.infinite(x) & Q.infinite(y)),
    (Q.infinite(x + y), Q.infinite(x) & ~Q.negative_infinite(y)),
])
def test_reproducers(query, assumptions):
    assert ask(query, assumptions, fresh()) is None


def test_infinite_sums_keep_their_answers():
    assert ask(Q.infinite(x + oo), Q.real(x), fresh()) is True
    assert ask(Q.infinite(x + zoo), Q.finite(x), fresh()) is True
    assert ask(Q.infinite(x + oo*I), Q.finite(x), fresh()) is True
    assert ask(Q.infinite(x + y + 1), Q.infinite(x) & Q.finite(y), fresh()) is True
    assert ask(Q.positive_infinite(x + oo), Q.extended_nonnegative(x), fresh()) is True
    assert ask(Q.infinite(x + oo), Q.extended_positive(x), fresh()) is True
    assert ask(Q.infinite(x + y), Q.positive_infinite(x) & Q.positive_infinite(y), fresh()) is True
    assert ask(Q.negative_infinite(x - oo), Q.real(x), fresh()) is True
    # contrapositive: a finite sum of finite terms and k means k is finite
    assert ask(Q.infinite(x), Q.finite(x + y) & Q.finite(y), fresh()) is False


def test_extended_real_sum_with_an_infinite_term():
    # an infinite term makes the sum infinite or nan; nan is no extended real
    assert ask(Q.finite(x + y), Q.infinite(x) & Q.extended_real(x + y), fresh()) is False
    assert ask(Q.nonzero(x + oo), True, fresh()) is False
    # an infinity or nan is no complex number (#188 review)
    assert ask(Q.complex(x*y + oo*I), True, fresh()) is False
    assert ask(Q.imaginary(x + oo*(1 + I)), True, fresh()) is False
    assert ask(Q.complex(Add(-oo, zoo, evaluate=False)), True, fresh()) is False
    assert ask(Q.complex(x + y), Q.infinite(x), fresh()) is False
    assert ask(Q.complex(x - oo), True, fresh()) is False
    with pytest.raises(ValueError):
        ask(Q.positive(x), Q.finite(x + oo) & Q.extended_real(x + oo), fresh())


def test_extended_real_sum_keeps_its_sign_undecided():
    # x - oo is -oo or nan (x = oo) for an extended real x.  "An extended-real
    # sum with a -oo term is -oo" is entailed, but SymPy's is_ge(x, oo)
    # reads is_extended_nonnegative(x - oo) and would call x >= oo False at
    # x = oo, failing 17 SymPy tests (test_inequalities): left out.
    assert ask(Q.extended_nonnegative(x - oo), Q.extended_real(x), fresh()) is None
    assert ask(Q.extended_real(x + y), Q.negative_infinite(x) & Q.positive_infinite(y),
               fresh()) is None
