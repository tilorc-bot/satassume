"""Registering clause-generating functions for predicates.

These mirror the intent of SymPy's ``test_key_extensibility``,
``test_type_extensibility``, ``test_custom_AskHandler`` and
``test_polyadic_predicate`` (``sympy/assumptions/tests/test_query.py``),
which use ``Q.<pred>.register(<classes>)``; here the registration is
``satassume.register(pred, *classes)`` and the function returns True, False,
None or formulas over ``P`` atoms.
"""
import pytest

from satassume import Engine, DictCache, Extensions, Implies, InconsistentAssumptions, Not, P
from satassume.extensions import Args


# -- engine level, no SymPy ------------------------------------------------------

def test_custom_atoms_in_the_engine():
    ext = Extensions()

    @ext.register('mine', str)
    def _(node):
        return True if node == 'x' else None

    @ext.register('twice', tuple)
    def _(node):
        kind, *args = node
        return Implies(P('mine', args[0]), P('twice', node)) if kind == 'add' else None

    @ext.register('same', str, str)
    def _(a, b):
        return a == b

    eng = Engine(templates=lambda n: [], cache=DictCache(), extensions=ext)
    assert eng.is_('x', 'mine') is True
    assert eng.is_('y', 'mine') is None
    assert eng.stats['cache_hits'] == 0
    assert eng.is_('x', 'mine') is True            # cached in the engine's own cache
    assert eng.stats['cache_hits'] == 1
    assert eng.is_(('add', 'x', 'y'), 'twice') is True
    assert eng.is_(('add', 'y', 'x'), 'twice') is None
    # custom atoms take part in contextual reasoning like any other atom
    assert eng.ask(P('mine', 'y'), P('mine', 'y')) is True
    assert eng.ask(P('twice', ('add', 'y', 'y')), P('mine', 'y')) is True
    assert eng.ask(Not(P('twice', ('add', 'y', 'y'))), P('mine', 'y')) is False
    # nothing about a custom predicate is written to the node cache
    assert eng.cache.get('x', 'mine', 'missing') == 'missing'
    # polyadic atoms are keyed by the argument tuple
    assert eng.is_(Args(('x', 'x')), 'same') is True
    assert eng.is_(Args(('x', 'y')), 'same') is False
    assert eng.ask(P('same', Args(('x', 'x'))), P('mine', 'y')) is True
    with pytest.raises(InconsistentAssumptions):
        eng.ask(P('same', Args(('x', 'y'))), P('same', Args(('x', 'y'))))


# -- the four SymPy tests ----------------------------------------------------------

sympy = pytest.importorskip("sympy")

from sympy import Basic, Integer, Predicate, Q, Symbol, log  # noqa: E402

from satassume.sympy_api import ask, out_of_scope, register, unregister  # noqa: E402

x, n = Symbol('x'), Symbol('n')


@pytest.fixture
def eng():
    return Engine(cache=DictCache())


def test_key_extensibility(eng):
    """A new key on Symbol, added at runtime."""

    class MyPredicate(Predicate):
        pass

    try:
        Q.my_key = MyPredicate()
        # not registered: out of scope, like the AttributeError in SymPy
        assert out_of_scope(Q.my_key(x)) == "custom"
        assert ask(Q.my_key(x), True, eng) is None

        @register(Q.my_key, Symbol)
        def _(expr):
            return True

        assert out_of_scope(Q.my_key(x)) is None
        assert ask(Q.my_key(x), True, eng) is True
        assert ask(Q.my_key(x + 1), True, eng) is None
        assert ask(Q.my_key(x + 1), Q.my_key(x + 1), eng) is True
        assert ask(Q.my_key(x + 1), ~Q.my_key(x + 1), eng) is False
        with pytest.raises(ValueError):
            ask(Q.my_key(x), ~Q.my_key(x), eng)
    finally:
        unregister('my_key')
        del Q.my_key
    assert out_of_scope(Q.__getattr__('my_key')(x)) == "custom" if hasattr(Q, 'my_key') else True


def test_type_extensibility(eng):
    """A vocabulary predicate on a new class."""

    class MyType(Basic):
        pass

    try:
        @register(Q.prime, MyType)
        def _(expr):
            return True

        assert out_of_scope(Q.prime(MyType())) is None
        assert ask(Q.prime(MyType()), True, eng) is True
        # the rule base applies to the new node: prime -> integer, positive
        assert ask(Q.integer(MyType()), True, eng) is True
        assert ask(Q.negative(MyType()), True, eng) is False
    finally:
        unregister(Q.prime)
    assert out_of_scope(Q.prime(MyType())) == "matrix"


def test_custom_AskHandler(eng):
    """A Mersenne predicate on Integer reasoning through ``ask``."""

    class MersennePredicate(Predicate):
        pass

    try:
        Q.mersenne = MersennePredicate()

        @register(Q.mersenne, Integer)
        def _(expr):
            if ask(Q.integer(log(expr + 1, 2)), True, eng):
                return True

        @register(Q.mersenne, Symbol)
        def _(expr):
            return None   # only what the assumptions say

        assert ask(Q.mersenne(Integer(7)), True, eng) is True
        assert ask(Q.mersenne(Integer(6)), True, eng) is None
        assert ask(Q.mersenne(n), Q.mersenne(n), eng) is True
        assert ask(Q.mersenne(n), True, eng) is None
    finally:
        unregister(Q.mersenne)
        del Q.mersenne


def test_custom_predicate_as_clauses(eng):
    """The same Mersenne predicate as a clause generator: the engine visits
    ``log(n + 1, 2)`` itself."""

    @register('mersenne', Integer)
    def _(expr):
        return Implies(P('integer', log(expr + 1, 2)), P('mersenne', expr))

    try:
        mersenne = Predicate('mersenne')
        assert ask(mersenne(Integer(31)), True, eng) is True
        assert ask(mersenne(Integer(6)), True, eng) is None
    finally:
        unregister('mersenne')


def test_polyadic_predicate(eng):
    """Sexy primes: pairs and triples of primes six apart."""

    class SexyPredicate(Predicate):
        pass

    try:
        Q.sexyprime = SexyPredicate()

        @register(Q.sexyprime, Integer, Integer)
        def _(int1, int2):
            args = sorted([int1, int2])
            if not all(ask(Q.prime(a), True, eng) for a in args):
                return False
            return args[1] - args[0] == 6

        @register(Q.sexyprime, Integer, Integer, Integer)
        def _(int1, int2, int3):
            args = sorted([int1, int2, int3])
            if not all(ask(Q.prime(a), True, eng) for a in args):
                return False
            return args[2] - args[1] == 6 and args[1] - args[0] == 6

        assert ask(Q.sexyprime(5, 11), True, eng) is True
        assert ask(Q.sexyprime(7, 13, 19), True, eng) is True
        assert ask(Q.sexyprime(5, 13), True, eng) is False
        assert ask(Q.sexyprime(4, 10), True, eng) is False
        assert out_of_scope(Q.sexyprime(5, 11)) is None
        assert out_of_scope(Q.sexyprime(5, 11, 17, 23)) == "custom"   # no 4-ary registration
        assert ask(Q.sexyprime(5, 11, 17, 23), True, eng) is None
        # the polyadic atom is an ordinary atom in assumptions
        assert ask(Q.sexyprime(x, n), Q.sexyprime(x, n), eng) is True
    finally:
        unregister(Q.sexyprime)
        del Q.sexyprime


def test_registration_version_clears_answer_memo(eng):
    """Every (un)registration bumps ``Extensions.version``; the answer memo
    of ``ask`` is keyed on it, so a memoized answer never outlives the
    registrations it was computed under."""

    class VersionPredicate(Predicate):
        pass

    from satassume.extensions import extensions
    try:
        Q.vkey = VersionPredicate()
        v0 = extensions.version
        assert ask(Q.vkey(x), True, eng) is None

        @register(Q.vkey, Symbol)
        def f(expr):
            return True

        assert extensions.version == v0 + 1
        assert ask(Q.vkey(x), True, eng) is True
        unregister(Q.vkey)
        assert extensions.version == v0 + 2
        assert ask(Q.vkey(x), True, eng) is None
        register(Q.vkey, Symbol)(f)
        assert ask(Q.vkey(x), True, eng) is True
    finally:
        unregister(Q.vkey)
        del Q.vkey
