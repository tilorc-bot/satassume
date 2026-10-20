"""A log with a base, ``log(x, b, evaluate=False)``, is one ``log`` node with
two args whose value is ``log(x)/log(b)``: the unary templates must not
read it as ``log(x)`` (#191)."""
import pytest
from sympy import Q, Rational, Symbol, genocchi, log, symbols

from satassume import DictCache, Engine
from satassume.sympy_api import ask

p = Symbol('p', positive=True)
x = symbols('x')


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("expr, pred", [
    (log(2, Rational(1, 3), evaluate=False), 'positive'),     # ~ -0.63
    (log(Rational(1, 2), Rational(1, 3), evaluate=False), 'negative'),  # ~ 0.63
    (log(8, 3, evaluate=False) - 2, 'positive'),              # ~ -0.107
    (log(1, 3, evaluate=False), 'nonzero'),                   # 0
    (log(3, 3, evaluate=False), 'zero'),                      # 1
])
def test_no_wrong_answer(expr, pred):
    assert fresh().is_(expr, pred) is not True
    assert ask(getattr(Q, pred)(expr), True, fresh()) is not True


def test_base_is_not_read_as_log():
    e = log(p + 1, Rational(1, 2), evaluate=False)            # negative
    assert fresh().is_(e, 'positive') is None
    assert ask(Q.positive(e), Q.positive(p), fresh()) is None


def test_one_arg_log_keeps_its_facts():
    assert fresh().is_(log(p + 1), 'positive') is True


def test_genocchi_polynomial_gets_no_facts():
    assert fresh().is_(genocchi(2, x, evaluate=False), 'integer') is None
