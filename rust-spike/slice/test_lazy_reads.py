"""Lazy reads, the planner's ruling, item 2: `Q.positive(y + r)` makes zero `complex()` calls, by count and not by clock,
and each plant that restores an eager read fails it. Also the miss path, a raising read, the memo's death with its table,
and nan's key against the line in `term_row` that depends on it.

    python -m pytest rust-spike/slice/test_lazy_reads.py

Nothing here prints an input term: `str(y + r)` goes through `as_ordered_terms` and `complex()` (HANDOFF-sa-port-29).
"""
import gc
import os
import sys
import weakref

import pytest

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)

import sa_solver
from sympy import Function, Pow, Q, Rational, S, Symbol
from sympy.core.expr import Expr
from sympy.core.numbers import NaN
from sympy.polys.rootoftools import CRootOf

from harness.state import reset_module_state
from satassume import engine as E
from satassume import sympy_api

import convert as C
from lazy_probe import _count, terms

x, y = Symbol('x'), Symbol('y')


def root():
    return CRootOf(x**5 - x + 1, 3)


@pytest.fixture
def complex_calls(monkeypatch):
    """Calls of `Expr.__complex__`, the way `complex(t)` reaches it."""
    calls = [0]
    real = Expr.__complex__

    def counted(self):
        calls[0] += 1
        return real(self)
    monkeypatch.setattr(Expr, '__complex__', counted)
    return calls


def fresh():
    reset_module_state(sympy_cache=True)
    eng = E.Engine()
    sympy_api.set_default_engine(eng)
    return eng


def tab(prop, assumptions=True):
    """Convert and build Rust's table. (table, Converted)"""
    eng = fresh()
    c = C.convert(prop, assumptions, eng)
    assert not isinstance(c, C.Kept), c.reason
    return sa_solver.TermTable(c.tables), c


def test_zero_complex_convert_table_and_ask(complex_calls):
    t = y + root()      # built before the count starts: CRootOf's construction isn't what's asked about
    prop = Q.positive(t)
    complex_calls[0] = 0
    table, c = tab(prop)
    assert complex_calls[0] == 0, 'convert and TermTable called complex()'
    assert all(c.counts['read:' + k] == 0 for k in C.READS)
    fresh()
    sympy_api.ask(prop)
    assert complex_calls[0] == 0, 'the ask called complex()'


def test_reading_the_key_calls_complex_once_memoized(complex_calls):
    """The other side of the zero: the counter does fire here, so the zero above isn't a false one."""
    t = y + root()
    table, c = tab(Q.positive(t))
    complex_calls[0] = 0
    table.sort_key(c.ids[t])
    first = complex_calls[0]
    assert first > 0, 'the key of y + r holds complex(r): a zero here means the counter is dead'
    table.sort_key(c.ids[t])
    assert complex_calls[0] == first
    assert c.counts['read:key'] == 1


# ---- plants: wrap term_row so it does the eager read again. Each must fail the zero above.


def eager(kind):
    """As the eager conversion did it, at the same point."""
    def read(w, t):
        if not isinstance(t, Expr):
            return
        if kind == 'key':
            C.default_sort_key(t)
        elif kind == 'complex':
            if t.is_number:
                complex(t)
        elif kind == 'finite':
            t.is_finite
        elif kind == 'power':
            C.decompose_power(t)
        elif kind == 'commutative':
            t.is_commutative
    return read


def planted(monkeypatch, kind):
    real = C._Walk.term_row
    read = eager(kind)

    def term_row(self, t, out):
        real(self, t, out)
        read(self, t)
    monkeypatch.setattr(C._Walk, 'term_row', term_row)


@pytest.mark.parametrize('kind', ['key', 'complex'])
def test_plant_restoring_the_eager_read_is_caught(monkeypatch, complex_calls, kind):
    t = y + root()
    prop = Q.positive(t)
    planted(monkeypatch, kind)
    complex_calls[0] = 0
    tab(prop)
    assert complex_calls[0] > 0, 'this plant restores an eager read and the count did not see it'


class Costly(Expr):
    """A term whose `is_finite` and `is_commutative` and split are expensive, by a count of its own. Stock classes
    don't evaluate through `is_commutative` on the survey's 60 terms (HANDOFF-sa-port-29), so a planted class is how the
    `finite` and `commutative` plants can fire at all."""
    reads = {'finite': 0, 'commutative': 0, 'power': 0}
    is_number = False

    @property
    def is_finite(self):
        Costly.reads['finite'] += 1
        return None

    @property
    def is_commutative(self):
        Costly.reads['commutative'] += 1
        return True

    def as_base_exp(self):
        Costly.reads['power'] += 1
        return self, S.One


@pytest.mark.parametrize('kind', ['finite', 'commutative', 'power'])
def test_other_kinds_are_lazy_and_their_plant_is_caught(monkeypatch, kind):
    t = Costly(y)
    prop = Q.positive(t)
    Costly.reads[kind] = 0
    tab(prop)
    assert Costly.reads[kind] == 0, f'conversion read {kind}'
    planted(monkeypatch, kind)
    tab(prop)
    assert Costly.reads[kind] > 0, f'this plant restores eager {kind} and the count did not see it'


# ---- the ruling's item 1: every hand-built term, by every counter


COUNTERS = None


def build_counters():
    import sympy.core.evalf as evalf_mod
    from sympy.core.evalf import EvalfMixin
    from sympy.polys.rootoftools import ComplexRootOf
    return [(Expr, '__complex__', 'complex'), (EvalfMixin, 'evalf', 'evalf'), (evalf_mod, 'evalf', 'evalf'),
            (ComplexRootOf, '_eval_evalf', 'root'), (ComplexRootOf, 'eval_rational', 'root'),
            (ComplexRootOf, '_refine_complexes', 'root')]


def hand_built():
    return sorted(terms(5))


@pytest.mark.parametrize('name', hand_built())
def test_hand_built_terms_convert_without_evaluating(monkeypatch, name):
    try:
        t = terms(5)[name]()
    except Exception as e:
        pytest.skip('does not build: ' + type(e).__name__)
    prop = Q.positive(t)
    counts = evaluations(monkeypatch)
    eng = fresh()
    c = C.convert(prop, True, eng)
    if isinstance(c, C.Kept):
        pytest.skip('kept: ' + c.reason)
    sa_solver.TermTable(c.tables)
    assert counts == dict(complex=0, evalf=0, root=0)


def evaluations(monkeypatch):
    """The survey's counters, live from here to the end of the test."""
    counts = dict(complex=0, evalf=0, root=0)
    for owner, attr, key in build_counters():
        real = getattr(owner, attr)

        def wrapped(*a, _real=real, _key=key, **k):
            counts[_key] += 1
            return _real(*a, **k)
        monkeypatch.setattr(owner, attr, wrapped)
    return counts


def stock_power():
    return Pow(y**(1 + root()), Rational(3, 2), evaluate=False)


def stock_finite():
    return Pow(y*root(), Rational(3, 2), evaluate=False)


@pytest.mark.parametrize('kind,build', [('power', stock_power), ('finite', stock_finite)])
def test_stock_term_plant_is_caught(monkeypatch, kind, build):
    """The survey's stock terms that evaluate through these two reads: zero as things are, and not zero with the eager
    read back. So the counters are live in this window, and this zero isn't a false one."""
    t = build()
    prop = Q.positive(t)
    counts = evaluations(monkeypatch)
    fresh()
    tab(prop)
    assert sum(counts.values()) == 0, f'conversion evaluated: {counts}'
    planted(monkeypatch, kind)
    tab(prop)
    assert sum(counts.values()) > 0, f'the eager {kind} read is back and no counter saw it'


def test_python_own_ask_fires_the_counter_in_the_ask_window(complex_calls):
    """The ask's window can see a complex() call: pure Python's run of this one makes it."""
    prop = Q.gt(y + root(), 1)
    fresh()
    complex_calls[0] = 0
    sympy_api.ask(prop)
    assert complex_calls[0] > 0


# ---- the miss path


class HoldsNew(Expr):
    """Its key holds a term `.args` doesn't reach: the miss."""
    is_number = False

    def sort_key(self, order=None):
        return (Symbol('never_in_the_table'),)


def test_a_key_holding_a_new_term_refuses_and_counts_a_miss():
    t = HoldsNew(y)
    table, c = tab(Q.positive(t))
    with pytest.raises(sa_solver.TermRefuse, match='holds a term'):
        table.sort_key(c.ids[t])
    assert c.counts['read_term_missing'] == 1
    assert sympy_api.ask(Q.positive(t)) is None


def test_nan_key_holds_what_term_row_adds():
    """term_row adds -oo's row on reaching nan because NaN.sort_key holds -oo (the planner's nan ruling). This fails if
    nan's key stops matching, whereupon that line stops being a fact about SymPy."""
    key = S.NaN.sort_key()
    found = []

    def walk(v):
        if isinstance(v, tuple):
            for e in v:
                walk(e)
        elif v is S.NegativeInfinity:
            found.append(v)
    walk(key)
    assert found, 'NaN.sort_key no longer holds -oo: term_row is adding a row for nothing'
    assert 'sort_key' in NaN.__dict__
    table, c = tab(Q.positive(S.NaN))
    table.sort_key(c.ids[S.NaN])
    assert c.counts['read_term_missing'] == 0


def test_without_the_nan_line_nan_refuses_with_a_miss(monkeypatch):
    """The ruling's plant in small: the line removed, nan's key misses and refuses."""
    real = C._Walk.term
    NEG = S.NegativeInfinity

    def term(self, t):
        if t is NEG and sys._getframe(1).f_code.co_name == 'term_row':
            return -1
        return real(self, t)
    monkeypatch.setattr(C._Walk, 'term', term)
    table, c = tab(Q.positive(S.NaN))
    with pytest.raises(sa_solver.TermRefuse, match='holds a term'):
        table.sort_key(c.ids[S.NaN])
    assert c.counts['read_term_missing'] == 1


# ---- a read that raises


class Raises(Expr):
    is_number = False

    def sort_key(self, order=None):
        raise ValueError('planted')


def test_a_raising_read_refuses_and_counts():
    t = Raises(y)
    table, c = tab(Q.positive(t))
    with pytest.raises(sa_solver.TermRefuse):
        table.sort_key(c.ids[t])
    assert c.counts['read_raised'] == 1
    assert c.tables['reads'].__self__.raised == [('key', c.ids[t], 'ValueError')]


class Stops(BaseException):
    pass


class RaisesBase(Expr):
    is_number = False

    def sort_key(self, order=None):
        raise Stops()


def test_a_baseexception_comes_through_as_itself():
    t = RaisesBase(y)
    table, c = tab(Q.positive(t))
    with pytest.raises(Stops):
        table.sort_key(c.ids[t])


# ---- nothing read survives the query


def test_memo_dies_with_its_table(complex_calls):
    t = y + root()
    table, c = tab(Q.positive(t))
    i = c.ids[t]
    complex_calls[0] = 0
    table.sort_key(i)
    first = complex_calls[0]
    assert first > 0
    table.sort_key(i)
    assert complex_calls[0] == first, 'the memo did not hold within a table'
    # A second table for the same query reads again, so no read lives outside its table.
    second = sa_solver.TermTable(c.tables)
    n = c.counts['read:key']
    second.sort_key(i)
    assert c.counts['read:key'] == n + 1, 'a second table did not read: a read survived its table'


def test_the_walk_dies_with_table_and_converted():
    t = y + root()
    table, c = tab(Q.positive(t))
    table.sort_key(c.ids[t])
    w = weakref.ref(c.tables['reads'].__self__)
    assert w() is not None
    del table, c
    gc.collect()
    assert w() is None, 'something kept the per-query walk, and through it every read'
