"""The matcher analyses each pattern once (``_engine._shape``) and remembers it.

What it remembers must not be tied to the objects of the pattern it first saw:
SymPy's cache can be cleared (or evict an entry), so an equal pattern built
later consists of other, equal objects.  A remembered rest symbol compared by
identity then dropped every ``e*log(b)``-style binding (order-dependent suite
failures)."""
from sympy import Symbol, conjugate, exp, log, symbols
from sympy.core.cache import clear_cache

from satrefine.identities.core import match as _engine
from satrefine.identities.core.match import bindings


def _fresh(name):
    clear_cache()
    return Symbol(name)


def test_an_equal_pattern_of_other_objects_matches_the_same():
    a, b, x = symbols("a b x")
    first = _fresh("e")*log(b)
    list(bindings(exp(first), exp(a*b*log(x))))
    assert first in _engine._shapes
    again = _fresh("e")*log(b)
    assert again == first and not any(u is v for u, v in zip(again.args, first.args) if u.is_Symbol)
    found = list(bindings(exp(again), exp(a*b*log(x))))
    assert any(m[Symbol("e")] == a*b and m[b] == x for m in found)


def test_a_rest_symbol_inside_a_longer_product():
    x, y = symbols("x y")
    w, r = _fresh("w"), Symbol("r")
    list(bindings(w*conjugate(w)*r, 2*x*y*conjugate(x)))
    w2 = _fresh("w")
    found = list(bindings(w2*conjugate(w2)*Symbol("r"), 2*x*y*conjugate(x)))
    assert any(m[w2] == x and m[Symbol("r")] == 2*y for m in found)
