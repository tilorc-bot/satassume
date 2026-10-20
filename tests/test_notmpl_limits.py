"""Templates for ``Sum``, ``Product`` and ``Integral`` (#180 C-NOTMPL,
part C).

These nodes got no facts before: ``Sum(0, (x, 1, n))`` was not zero
(test_sums_products::test_is_zero), an integral of a finite function over
``(x, a, a)`` was not zero (test_integrals::test_doit_integrals), and the
sums of test_sumproducts_assumptions had no sign.  The function is no slot
(its variable is bound): its facts come from a context-free query, so an
assumption on a free symbol of the same name never reaches it.
"""
import pytest
from sympy import Add, Integral, Product, Q, Rational, Sum, Symbol, oo

from satassume import DictCache, Engine
from satassume.sympy_api import ask

x = Symbol('x')
y = Symbol('y')
n = Symbol('n', integer=True)
k = Symbol('k', integer=True, positive=True)
M = Symbol('M', integer=True, positive=True)
r = Symbol('r', real=True)

PREDS = ('zero', 'finite', 'positive', 'negative', 'nonnegative', 'nonpositive', 'integer')


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("expr", [
    Sum(0, (x, 1, n)), Sum(k, (k, 1, M)), Sum(k, (k, 1, 3), (n, 1, k)), Sum(1, (x, 0, Rational(1, 2))),
    Sum(1 / x, (x, 1, n)), Product(k, (k, 1, M)), Product(2, (x, 0, oo)),
    Integral(x, (x, 1, 1)), Integral(0, (x, y)), Integral(1 / x, (x, -1, 1)), Integral(r, (x, 0)),
])
def test_agrees_with_sympy(expr):
    # no new non-theorem: every answer is SymPy's own, None where SymPy is None
    eng = fresh()
    for pred in PREDS:
        v = eng.is_(expr, pred)
        assert v is None or v is getattr(expr, 'is_' + pred), (expr, pred, v)


@pytest.mark.parametrize("expr, pred, expected", [
    # test_is_zero, test_literal_evalf...: a sum of zeros, an empty range
    (Sum(0, (x, 1, n)), 'zero', True),
    (Sum(x, (x, 1, 0)), 'zero', True),
    (Sum(x, (x, 3, 1)), 'zero', None),
    # test_sumproducts_assumptions: the sign of the function over a range
    # that is not empty (strict) or not reversed
    (Sum(k, (k, 1, M)), 'positive', True),
    (Sum(k, (k, 1, M)), 'finite', True),
    (Product(k, (k, 1, M)), 'positive', True),
    (Sum(Symbol('m', integer=True, nonnegative=True), (Symbol('m', integer=True, nonnegative=True), 0, M)),
     'nonnegative', True),
    (Sum(Symbol('m', integer=True, nonnegative=True), (Symbol('m', integer=True, nonnegative=True), 0, M)),
     'positive', None),
    (Sum(Symbol('m', integer=True), (Symbol('m', integer=True), -M, M)), 'finite', True),
    (Sum(2, (x, 0, oo)), 'finite', None),
    (Sum(2, (x, 0, oo)), 'positive', None),
    # Karr: a product over a reversed range is 1/Product over the gap, so a
    # product of zeros is zero only over a range that is not empty, and not
    # positive over one of unknown sign
    (Product(0, (x, 2, 1)), 'zero', False),
    (Product(0, (x, 2, 1)), 'positive', True),
    (Product(x, (x, 2, 1)), 'integer', True),  # 1, where SymPy is None
    (Product(0, (x, 1, M)), 'zero', True),
    (Product(0, (x, 3, 1)), 'zero', None),
    (Product(k, (k, 1, n)), 'positive', None),
    (Product(k, (k, 1, n)), 'finite', None),
    # test_doit_integrals: equal ends, a zero function
    (Integral(x, (x, 1, 1)), 'zero', True),
    (Integral(1 / x, (x, y, y)), 'zero', True),
    (Integral(0, (x, y)), 'zero', True),
    (Integral(r, (x, 0)), 'zero', True),
    (Integral(y, (x, 0)), 'zero', None),     # y*0 is nan at y = oo
    (Integral(x, (x, 0, 1)), 'zero', None),
    (Integral(1, (x, 1, 2)), 'zero', None),  # not SymPy's False for a nonzero function
    # the ends of a sum that rebuilds to other terms are no slots (#184)
    (Sum(1, (x, 1, Add(y, -y, 1, evaluate=False))), 'finite', None),
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


def test_bound_variable_context():
    # an assumption on the free x is no fact about the bound x
    assert ask(Q.zero(Sum(x, (x, 1, 2))), Q.zero(x)) is None
    assert ask(Q.finite(Sum(1 / x, (x, -1, 1))), Q.nonzero(x)) is None
    assert ask(Q.positive(Sum(x, (x, 1, y))), Q.positive(x) & Q.integer(y) & Q.positive(y)) is None
    assert ask(Q.zero(Integral(x, (x, 0, 1))), Q.zero(x)) is None
    assert ask(Q.positive(Product(x, (x, 1, 3))), Q.positive(x)) is None


def test_ends_in_context():
    # the ends are in the scope of the node: their facts come from the context
    m = Symbol('m', integer=True, positive=True)
    assert ask(Q.positive(Sum(m, (m, 1, y))), Q.integer(y) & Q.positive(y)) is True
    assert ask(Q.positive(Sum(m, (m, 1, y))), Q.integer(y)) is None
    assert ask(Q.zero(Sum(x, (x, y, y - 1))), Q.finite(y)) is True
    assert ask(Q.zero(Integral(x, (x, 0, y))), Q.zero(y)) is True
    assert ask(Q.zero(Integral(x, (x, 0, y))), Q.nonzero(y)) is None
