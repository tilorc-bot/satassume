"""Component 6's atom reads are lazy (planner's ruling on lazy reads, issue 323): nothing in conversion, one read per term
when the template visits, and a read that raises is loud. Every count here is shown firing, or its zero proves nothing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
import sa_solver
from sympy import Q, S, Symbol, pi
from sympy.core.expr import Expr
from sympy.polys.rootoftools import CRootOf

from harness.state import reset_module_state
from satassume import engine as E
from satassume import sympy_api

import convert as C
import knowledge_live as K

X, Y = Symbol('x'), Symbol('y')
SYM, CONST = C.READS.index('symbol'), C.READS.index('constant')


def fresh():
    reset_module_state(sympy_cache=True)
    sympy_api.set_default_engine(E.Engine())


@pytest.fixture
def live():
    undo = K.install()
    K.COUNTS.clear()
    del K.RAISED[:]
    fresh()     # an engine's memo holds what a template returned, so a new one for each test, or it won't read
    yield
    undo()
    fresh()


@pytest.fixture
def complex_calls(monkeypatch):
    calls = []
    real = Expr.__complex__

    def counted(self):
        calls.append(self)
        return real(self)
    monkeypatch.setattr(Expr, '__complex__', counted)
    return calls


def converted(prop):
    return C.convert(prop, True, E.Engine())


def atom_reads(c):
    return c.counts['read:symbol'], c.counts['read:constant']


def test_conversion_reads_no_atom():
    c = converted(Q.positive(Symbol('p', positive=True) + pi))
    assert not isinstance(c, C.Kept)
    assert atom_reads(c) == (0, 0)


def test_the_plant_restoring_an_eager_read_is_seen():
    """What `test_conversion_reads_no_atom` would see if conversion read atoms up front, as it did before lazy reads."""
    p = Symbol('p', positive=True)
    c = converted(Q.positive(p + pi))
    c.tables['reads'](SYM, c.ids[p])
    c.tables['reads'](CONST, c.ids[pi])
    assert atom_reads(c) == (1, 1)


def test_the_template_reads_once_per_table(live):
    p = Symbol('p', positive=True)
    c = converted(Q.positive(p))
    t = sa_solver.TermTable(c.tables)
    kn = sa_solver.Knowledge(sa_solver.OfflineData(os.path.join(os.path.dirname(K.__file__), 'offline_data.json'),
                                                   os.path.abspath(os.path.join(os.path.dirname(K.__file__), '..', '..')), K.sympy.__version__))
    first = kn.symbol_units(t, c.ids[p])
    assert atom_reads(c) == (1, 0)
    assert kn.symbol_units(t, c.ids[p]) == first
    assert atom_reads(c) == (1, 0)


def test_a_query_counts_the_reads_it_asked_for(live):
    assert sympy_api.ask(Q.positive(Symbol('p', positive=True))) is True
    assert K.COUNTS['read:symbol'] >= 1
    assert K.COUNTS['read_raised'] == 0


def test_a_root_is_converted_and_asked_with_no_complex_call(live, complex_calls):
    r = CRootOf(X**5 - X + 1, 3)
    c = converted(Q.positive(Y + r))
    assert not isinstance(c, C.Kept)        # no `complex-unbounded`: it's gone
    sympy_api.ask(Q.positive(Y + r))
    assert complex_calls == []
    assert K.COUNTS['converted'] == 1
    complex(r)                              # the counter fires
    assert complex_calls == [r]


def test_a_read_that_raises_is_a_refusal_and_counts(live, monkeypatch):
    """Section 9: the run is discarded and answered on Python. It was a `KnowledgeFault` until term_live gave it a route."""
    def boom(self, t):
        raise ValueError('planted')
    monkeypatch.setattr(C._Walk, '_read_constant', boom)
    assert sympy_api.ask(Q.positive(pi)) is True
    assert K.COUNTS['read_raised'] == 1
    assert K.COUNTS['refused'] == 1
    assert K.RAISED and K.RAISED[0][0] == 'constant' and K.RAISED[0][2] == 'ValueError'


def test_a_baseexception_comes_through_as_itself(live, monkeypatch):
    class Stop(BaseException):
        pass

    def stop(self, t):
        raise Stop
    monkeypatch.setattr(C._Walk, '_read_symbol', stop)
    with pytest.raises(Stop):
        sympy_api.ask(Q.positive(Symbol('p', positive=True)))
