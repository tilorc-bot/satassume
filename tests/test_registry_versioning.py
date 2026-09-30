"""Every engine-level cache is keyed on the registry state (#53, group 6).

Registering or unregistering a clause-generating function (or changing the
theory adapters) changes what an answer is; everything the engine keeps
between queries (``Engine.cache``, ``Engine.custom_cache``, the reused
contextual sessions, the answer and split memos) was computed under the
registrations in force at the time and is dropped on a change
(``Engine._check_version``).  The scenarios R1-R4 are the differential
harness's recorded repros: the engine's answer after the prefix must equal a
fresh engine's answer under the same registrations.

A reused session that a query's own nodes make unsatisfiable at root is
dropped with the raise (``dead_sessions``): the raise belongs to that query,
and later queries under the same assumptions are answered as in a fresh
engine.
"""
import pytest

sympy = pytest.importorskip("sympy")

from sympy import Abs, Function, Predicate, Q, Symbol  # noqa: E402
from sympy.core.function import AppliedUndef  # noqa: E402

from satassume import DictCache, Engine  # noqa: E402
from satassume.extensions import extensions  # noqa: E402
from satassume.formula import Implies, Not, P  # noqa: E402
from satassume.sympy_api import ask  # noqa: E402

x = Symbol('x')
y = Symbol('y', real=True)
m = Symbol('m', negative=True)
A = Symbol('A', commutative=False)
f = Function('f')
hbig = Predicate('hbig')


# the registrations of the harness (harness/registry.py)
def undef_real(app):
    """A vocabulary predicate on a class: f(e) is real when e is real."""
    return Implies(P('real', app.args[0]), P('real', app)) if app.args else None


def big(s):
    """hbig(s) -> positive(s) & ~integer(s)."""
    return [Implies(P('hbig', s), P('positive', s)),
            Implies(P('hbig', s), Not(P('integer', s)))]


def big_negative(s):
    """A different meaning for the same name: hbig(s) -> negative(s)."""
    return Implies(P('hbig', s), P('negative', s))


def contradictory(app):
    """An extension whose facts make any session holding the node
    unsatisfiable at root."""
    return [P('real', app), Not(P('real', app))]


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    extensions.unregister('real')
    extensions.unregister('hbig')


def fresh(**kw) -> Engine:
    return Engine(cache=DictCache(), **kw)


def outcome(eng, p, a=True):
    """The answer, or "ValueError"."""
    try:
        return ask(p, a, eng)
    except ValueError:
        return "ValueError"


def same_as_fresh(eng, p, a=True):
    warm = outcome(eng, p, a)
    assert warm == outcome(fresh(), p, a)
    return warm


# -- the recorded repros ----------------------------------------------------

def test_r1_none_cached_before_registration():
    eng = fresh()
    assert same_as_fresh(eng, Q.real(f(y))) is None
    extensions.register('real', AppliedUndef)(undef_real)
    assert same_as_fresh(eng, Q.real(f(y))) is True         # was None: the cached None
    assert eng.stats["version_clears"] == 1


def test_r2_fact_cached_after_unregistration():
    extensions.register('real', AppliedUndef)(undef_real)
    eng = fresh()
    assert same_as_fresh(eng, Q.real(f(y))) is True
    extensions.unregister('real')
    assert same_as_fresh(eng, Q.real(f(y))) is None         # was True: the cached fact


def test_r3_session_keeps_unregistered_clauses():
    extensions.register('real', AppliedUndef)(undef_real)
    eng = fresh()
    assert same_as_fresh(eng, Q.real(f(y)), Q.positive(y)) is True
    extensions.unregister('real')
    assert same_as_fresh(eng, Q.real(f(y)), Q.positive(y)) is None   # was True: the session's clauses


def test_r4_custom_cache_stale_under_new_meaning():
    extensions.register('hbig', Symbol)(big)
    eng = fresh()
    assert same_as_fresh(eng, hbig(m)) is False              # m negative, hbig -> positive
    extensions.unregister('hbig')
    extensions.register('hbig', Symbol)(big_negative)
    assert same_as_fresh(eng, hbig(m)) is None               # was False: the cached ~hbig(m)
    assert eng.stats["version_clears"] == 1


def test_re_registration_restores_the_fact():
    eng = fresh()
    assert same_as_fresh(eng, Q.real(f(y))) is None
    extensions.register('real', AppliedUndef)(undef_real)
    assert same_as_fresh(eng, Q.real(f(y))) is True
    extensions.unregister('real')
    assert same_as_fresh(eng, Q.real(f(y))) is None
    extensions.register('real', AppliedUndef)(undef_real)
    assert same_as_fresh(eng, Q.real(f(y))) is True
    assert eng.stats["version_clears"] == 3


# -- one test per cache ------------------------------------------------------

def test_fact_cache_is_keyed_on_the_registry():
    eng = fresh()
    assert eng.is_(f(y), 'real') is None
    assert eng.cache.get(f(y), 'real', "miss") is None      # the None is cached
    extensions.register('real', AppliedUndef)(undef_real)
    assert eng.is_(f(y), 'real') is True
    assert eng.stats["version_clears"] == 1
    extensions.unregister('real')
    assert eng.is_(f(y), 'real') is None
    assert eng.stats["version_clears"] == 2
    # the next query is a cache hit again: only a change clears
    hits = eng.stats["cache_hits"]
    assert eng.is_(f(y), 'real') is None
    assert eng.stats["cache_hits"] == hits + 1 and eng.stats["version_clears"] == 2


def test_custom_cache_is_keyed_on_the_registry():
    extensions.register('hbig', Symbol)(big)
    eng = fresh()
    assert eng.is_(m, 'hbig') is False
    assert eng.custom_cache.get(m, 'hbig', "miss") is False
    extensions.unregister('hbig')
    extensions.register('hbig', Symbol)(big_negative)
    assert eng.custom_cache.get(m, 'hbig', "miss") is False  # stale until the next query
    assert eng.is_(m, 'hbig') is None
    assert eng.custom_cache.get(m, 'hbig', "miss") is None


def test_sessions_are_keyed_on_the_registry():
    extensions.register('real', AppliedUndef)(undef_real)
    eng = fresh()
    a = P('positive', y)
    assert eng.ask(P('real', f(y)), a) is True
    assert a in eng._context_sessions
    extensions.unregister('real')
    assert eng.ask(P('real', f(y)), a) is None
    assert a in eng._context_sessions and eng.stats["version_clears"] == 1


def test_answer_memo_and_splits_are_keyed_on_the_registry():
    extensions.register('real', AppliedUndef)(undef_real)
    eng = fresh()
    a = Q.positive(y) & Q.positive(x)
    assert ask(Q.real(f(y)), a, eng) is True
    assert eng.answers and eng.splits
    extensions.unregister('real')
    assert ask(Q.real(f(y)), a, eng) is None
    assert (Q.real(f(y)), a) in eng.answers and eng.answers[(Q.real(f(y)), a)] is None


def test_adapter_change_clears_too():
    eng = fresh()
    assert ask(Q.positive(y), Q.gt(y, 1), eng) is True
    eng.relation_specs = []
    assert ask(Q.positive(y), Q.gt(y, 1), eng) is None       # relations out of scope
    assert eng.stats["version_clears"] == 1


def test_no_clear_without_a_change():
    extensions.register('real', AppliedUndef)(undef_real)       # before the first query
    eng = fresh()
    for _ in range(3):
        assert ask(Q.real(f(y)), True, eng) is True
        assert ask(Q.real(f(y)), Q.positive(y), eng) is True
    assert eng.stats["version_clears"] == 0
    assert eng.cache.get(f(y), 'real') is True and len(eng._context_sessions) == 1


# -- dead sessions -----------------------------------------------------------

def test_dead_session_is_dropped():
    """A query whose own nodes make the reused session unsatisfiable at
    root raises, and only that query: later queries under the same
    assumptions are answered as in a fresh engine."""
    extensions.register('real', AppliedUndef)(contradictory)
    a = Q.positive(x)
    eng = fresh()
    assert same_as_fresh(eng, Q.real(x), a) is True
    assert same_as_fresh(eng, Q.positive(f(x) + x), a) == "ValueError"
    assert eng.stats["dead_sessions"] == 1
    assert a not in eng._context_sessions
    assert same_as_fresh(eng, Q.real(x), a) is True
    assert same_as_fresh(eng, Q.negative(x), a) is False
    assert same_as_fresh(eng, Q.zero(x + 1), a) is False
    assert eng.stats["dead_sessions"] == 1


@pytest.mark.parametrize("relevance", [True, False])
def test_dead_session_noncommutative_abs(relevance):
    """The harness's ``declared`` finding: ``Abs(A)`` of a non-commutative
    ``A`` had a non-total block (fixed by the totality gate, #53 stage 1);
    with or without that fix, the queries after it answer as fresh."""
    a = Q.positive(x)
    eng = fresh(relevance=relevance)
    ref = lambda p: outcome(fresh(relevance=relevance), p, a)  # noqa: E731
    assert outcome(eng, Q.real(x), a) is True
    poison = Q.positive(x + Abs(A))
    assert outcome(eng, poison, a) == ref(poison)
    for p in (Q.real(x), Q.negative(x), Q.zero(x + 1), Q.positive(x * Abs(A)), Q.positive(x)):
        assert outcome(eng, p, a) == ref(p), p


def test_inconsistent_assumptions_still_raise_every_time():
    """The rule is about a session's clause set, not about the assumptions:
    an inconsistent set raises for every query, as before."""
    eng = fresh()
    a = Q.positive(x) & Q.negative(x)
    for p in (Q.real(x), Q.zero(x), Q.real(x)):
        with pytest.raises(ValueError):
            ask(p, a, eng)
    assert eng.stats["dead_sessions"] == 0
