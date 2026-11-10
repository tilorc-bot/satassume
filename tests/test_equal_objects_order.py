"""Two equal queries get one answer, whichever is asked first (#96).

SymPy does not promise one object per expression: after ``clear_cache()``,
a cache eviction or with ``SYMPY_USE_CACHE=no``, the base and the exponent
of ``x**x`` can be two equal objects.  The rule of ``Pow`` about a power of
a term to itself, ``Q.extended_nonnegative(b) >> Q.extended_positive(b**b)``
(``templates/power.py``), was matched by identity (``wiring.matches``, shape
``('same', 0)``, and the key of the pattern in ``wiring.power``), so the
query built from two equal objects lost the rule and was answered ``None``.
The first of two equal queries then decided the answer of both, since the
tables behind an answer are keyed by ``==``.

Each case is asked in both orders, from emptied process memos: the
*original* (one object for base and exponent) then its *twin*, and the twin
then the original.  The twin is an equal query in which every node is a new
object.  ``default`` asks with one default engine for both; ``new`` with a
new ``Engine`` per ask (the tables shared by every engine carry the first
object too).  The answers are the definite ones: ``b**b > 0`` for a real
``b >= 0`` (``0**0`` is 1).
"""
import pytest
from sympy import Abs, Basic, Function, Pow, Q, Symbol, exp, preorder_traversal, symbols
from sympy.core.cache import clear_cache
from sympy.core.function import AppliedUndef

from satassume import Engine
from satassume import sympy_api as api
from satassume.state import memos
from satassume.sympy_api import ask

x, y = symbols('x y')
f = Function('f')


def self_power(b):
    """``b**b`` with one object for the base and the exponent."""
    return Pow(b, b)


xx, yy = self_power(x), self_power(y)

# (proposition, assumptions, answer)
CASES = {
    'x**x + 1 > 0':
        (Q.gt(xx + 1, 0), Q.ge(x, 0) & Q.ge(y, 0), True),
    'x**x <= 0':
        (Q.le(xx, 0), Q.gt(x, 0) & Q.gt(y, 0) & Q.real(f(x)), False),
    'x**x - y**y > 0, x = y':
        (Q.gt(xx - yy, 0), Q.eq(x, y) & Q.gt(x, 0), False),
    'x**x*y**y, x < y':
        (Q.extended_positive(xx*yy), Q.extended_nonnegative(x) & Q.lt(x, y), True),
    '(x*y)**(x*y) > 0, x = y':
        (Q.gt(self_power(x*y), 0), Q.eq(x, y) & Q.gt(x, 0), True),
    'Abs(x)**Abs(x)':
        (Q.extended_positive(self_power(Abs(x))),
         Q.extended_nonnegative(x) & Q.extended_nonnegative(y), True),
    '(x + 1)**(x + 1) > 0, x = y':
        (Q.gt(self_power(x + 1), 0), Q.eq(x, y) & Q.gt(x, 0), True),
    'exp(x)**exp(x) <= 0':
        (Q.le(self_power(exp(x)), 0), Q.gt(x, 0) & Q.gt(y, 0) & Q.real(f(x)), False),
    '(2*x)**(2*x) + 1 > 0':
        (Q.gt(self_power(2*x) + 1, 0), Q.ge(x, 0) & Q.ge(y, 0), True),
}


def twin(e):
    """An expression equal to ``e`` in which every node is a new object
    (each occurrence of a symbol and of an undefined function too)."""
    if not isinstance(e, Basic):
        return e
    if isinstance(e, Symbol):
        clear_cache()                  # else the cache returns the first object
        r = Symbol(e.name, **e._assumptions_orig)
    elif isinstance(e, AppliedUndef):
        args = [twin(a) for a in e.args]
        clear_cache()
        r = Function(e.func.__name__, **e.func._kwargs)(*args)
    elif not e.args or e.is_Atom:
        return e
    else:
        args = [twin(a) for a in e.args]
        clear_cache()
        r = e.func(*args)
    assert r == e and hash(r) == hash(e), (e, r)
    return r


def _self_powers(e):
    return [p for p in preorder_traversal(e) if p.is_Pow and p.base == p.exp]


def _empty():
    memos.PROCESS.clear()
    clear_cache()
    api.set_default_engine(Engine())


@pytest.fixture
def emptied():
    """Emptied process memos and SymPy cache, and a new default engine,
    so that a case starts from no earlier query; the engine is put back."""
    kept = api.default_engine()
    _empty()
    yield
    api.set_default_engine(kept)


@pytest.mark.parametrize("engine", ['default', 'new'])
@pytest.mark.parametrize("order", ['original-first', 'twin-first'])
@pytest.mark.parametrize("case", list(CASES))
def test_equal_queries_one_answer_in_both_orders(case, order, engine, emptied):
    prop, assumptions, answer = CASES[case]
    queries = {'original': (prop, assumptions), 'twin': (twin(prop), twin(assumptions))}
    # the two queries are equal, and differ in what the test is about
    assert queries['twin'] == queries['original']
    assert _self_powers(prop) and all(p.base is p.exp for p in _self_powers(prop))
    assert all(p.base is not p.exp for p in _self_powers(queries['twin'][0]))
    names = ['original', 'twin'] if order == 'original-first' else ['twin', 'original']
    got = [ask(*queries[name], Engine() if engine == 'new' else None) for name in names]
    assert got == [answer, answer]


@pytest.mark.parametrize("engine", ['default', 'new'])
def test_a_power_of_two_terms_does_not_get_the_rule(engine, emptied):
    """``x**y`` asked right after the ``x**x`` of two equal objects, and
    right before it: the pattern of a power is keyed by ``b == e``
    (``wiring.power``), so the rule of ``b**b`` reaches the second and
    never ``x**y`` (``0**1`` is not positive).  With equality in
    ``wiring.matches`` alone and the key by identity, the two powers share
    a pattern and ``x**y`` is answered ``True`` in the first order."""
    assumptions = Q.extended_nonnegative(x)

    def answers(*props):
        return [ask(p, assumptions, Engine() if engine == 'new' else None) for p in props]

    two = twin(xx)
    assert two.base is not two.exp and two == xx
    assert answers(Q.extended_positive(two), Q.extended_positive(x**y)) == [True, None]
    _empty()
    two = twin(xx)
    assert two.base is not two.exp
    assert answers(Q.extended_positive(x**y), Q.extended_positive(two)) == [None, True]
