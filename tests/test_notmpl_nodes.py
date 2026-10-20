"""Templates for classes that had none (#180 C-NOTMPL, part C:
``AccumBounds``, ``Idx`` and ``RandomSymbol``).

A node of these classes got no facts before: ``AccumBounds(-1, 2)`` was not
real (test_accumulationbounds::test_AccumBounds), an ``Idx`` was not an
integer (test_indexed::test_differentiation), and a random symbol was
neither real nor finite (test_rv::test_real, ``P(X < oo) == 1`` in
test_rv::test_issue_10052).
"""
import pytest
from sympy import AccumBounds, Idx, Q, Symbol, oo
from sympy.stats import Die, Exponential, Normal
from sympy.stats.rv import RandomSymbol

from satassume import DictCache, Engine

x = Symbol('x')
r = Symbol('r', real=True)
n = Symbol('n', integer=True)
p = Symbol('p', positive=True)

PREDS = ('real', 'extended_real', 'finite', 'integer', 'positive', 'negative', 'zero')


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("expr", [
    AccumBounds(-1, 2), AccumBounds(1, 2), AccumBounds(-2, -1), AccumBounds(r, oo),
    AccumBounds(-oo, oo), AccumBounds(0, oo), AccumBounds(1, 2) * r,
    Idx('i'), Idx('j', n), Idx('k', (1, n)), Idx('m', (0, 5)),
    Normal('X', 0, 1), Exponential('E', 3), Die('D', 6), RandomSymbol(p),
    RandomSymbol(Symbol('q', integer=True, positive=False)),
])
def test_agrees_with_sympy(expr):
    # every answer is SymPy's own (no new non-theorem); None where SymPy is None
    eng = fresh()
    for pred in PREDS:
        v = eng.is_(expr, pred)
        assert v is None or v is getattr(expr, 'is_' + pred), (expr, pred, v)


@pytest.mark.parametrize("expr, pred, expected", [
    # test_AccumBounds: AccumBounds(-1, 2) is real; no sign from the ends
    (AccumBounds(-1, 2), 'real', True),
    (AccumBounds(-1, 2), 'positive', None),
    (AccumBounds(1, 2), 'positive', None),
    (AccumBounds(r, oo), 'extended_real', True),
    (AccumBounds(r, oo), 'real', None),
    (AccumBounds(-oo, oo), 'real', None),
    # test_differentiation: an Idx is an integer, whatever its range
    (Idx('i'), 'integer', True),
    (Idx('k', (1, n)), 'integer', True),
    (Idx('k', (1, n)), 'positive', None),
    (Idx('i') + n, 'integer', True),
    # test_real, test_issue_10052: random symbols are finite, real on a real space
    (Normal('X', 0, 1), 'real', True),
    (Exponential('E', 3), 'finite', True),
    (Exponential('E', 3) * n, 'finite', True),
    (Die('D', 6), 'finite', True),
    (Die('D', 6), 'real', None),
    (RandomSymbol(p), 'positive', True),
    (RandomSymbol(x), 'real', None),
    (RandomSymbol(x), 'finite', True),
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


def test_with_context():
    # an assumption on the ends never gives a sign; the unit facts combine
    # with the context
    from satassume.sympy_api import ask
    a = Symbol('a', real=True)
    assert ask(Q.positive(AccumBounds(a, a + 1)), Q.positive(a)) is None
    assert ask(Q.integer(Idx('i') + x), Q.integer(x)) is True
    assert ask(Q.real(Normal('X', 0, 1) * x), Q.real(x)) is True
