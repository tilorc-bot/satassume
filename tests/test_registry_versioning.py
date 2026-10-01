"""Every engine-level cache is keyed on the registry epoch (#53, group 6).

Registering or unregistering a clause-generating function, registering a
template or changing the theory adapters changes what an answer is; each
starts a new registry epoch (``satassume.epoch``), and everything the engine
keeps between queries (``Engine.cache``, ``Engine.custom_cache``, the reused
contextual sessions, the answer and split memos) was computed under the
registrations in force at the time and is dropped at the next query
(``Engine._check_version``).  The scenarios R1-R4 are the differential
harness's recorded repros: the engine's answer after the prefix must equal a
fresh engine's answer under the same registrations.

A reused session that a query under it made raise, or whose clause set a
query's own nodes made unsatisfiable at root, is dropped
(``dead_sessions``): the raise belongs to that query, and later queries
under the same assumptions are answered as in a fresh engine.
"""
import pytest

sympy = pytest.importorskip("sympy")

from sympy import Abs, Function, I, Predicate, Q, Symbol  # noqa: E402
from sympy.core.function import AppliedUndef  # noqa: E402

from satassume import DictCache, Engine  # noqa: E402
from satassume.epoch import EPOCH  # noqa: E402
from satassume.extensions import Extensions, extensions  # noqa: E402
from satassume.formula import Implies, Not, P  # noqa: E402
from satassume.sympy_api import ask  # noqa: E402
from satassume.templates.registry import registry  # noqa: E402

x = Symbol('x')
y = Symbol('y', real=True)
z = Symbol('z')
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


def contradictory_under_positive(app):
    """An extension whose facts rule out ``positive(arg)``: the root stays
    satisfiable, every query under ``Q.positive(arg)`` raises once the
    session holds the node."""
    return [Implies(P('positive', app.args[0]), P('real', app)),
            Implies(P('positive', app.args[0]), Not(P('real', app)))]


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    extensions.unregister('real')
    extensions.unregister('hbig')


@pytest.fixture
def template_class():
    """A function class of its own for a template registered during the
    test; the template is removed afterwards (the registry has no
    unregister: a test-local class, so nothing else sees it)."""
    G = Function('g_template_test')
    yield G
    registry._by_class.pop(G, None)
    registry._mro_cache.clear()
    registry._clauses_cache.clear()


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
    # the custom path is guarded on its own (tools/query_log.py calls it)
    extensions.unregister('hbig')
    extensions.register('hbig', Symbol)(big)
    assert eng._is_custom(m, 'hbig') is False
    assert eng.stats["version_clears"] == 2


def test_sessions_are_keyed_on_the_registry():
    extensions.register('real', AppliedUndef)(undef_real)
    eng = fresh()
    a = P('positive', y)
    assert eng.ask(P('real', f(y)), a) is True
    assert a in eng._context_sessions
    extensions.unregister('real')
    assert eng.ask(P('real', f(y)), a) is None
    assert a in eng._context_sessions and eng.stats["version_clears"] == 1


def test_engine_entries_are_guarded_on_their_own():
    """``Engine.ask`` without assumptions (a fresh session, the fact cache)
    and ``Engine._context_session`` (called by ``sympy_api._part_consistent``
    and by the harness) are entered directly, not only through
    ``sympy_api.ask``: each checks the epoch itself."""
    eng = fresh()
    a = P('positive', y)
    assert eng.ask(P('real', f(y))) is None
    s1, _ = eng._context_session(a)
    extensions.register('real', AppliedUndef)(undef_real)
    assert eng.ask(P('real', f(y))) is True
    assert eng.stats["version_clears"] == 1
    extensions.unregister('real')
    s2, _ = eng._context_session(a)
    assert s2 is not s1 and eng.stats["version_clears"] == 2


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


def test_adapter_change_drops_the_session():
    """Two sign atoms on sums sharing a symbol start the relation glue
    without a relation atom (``Session._affine_links``), so the session
    holds theory state; without adapters the same query is None."""
    eng = fresh()
    a, q = Q.positive(x - 1), Q.negative(1 - x)
    assert ask(q, a, eng) is True
    assert eng._context_sessions
    assert isinstance(eng.relation_specs, tuple)             # no in-place change
    eng.relation_specs = ()
    assert eng._epoch != EPOCH[0]                            # dropped at the next query
    assert ask(q, a, eng) is None
    assert ask(q, a, Engine(cache=DictCache(), relations=[])) is None
    assert eng.stats["version_clears"] == 1 and len(eng._context_sessions) == 1


def test_assigning_equal_specs_or_a_tuple_clears_nothing():
    """The adapters are compared as tuples: assigning the same adapters, as
    a tuple or a list, is no change, and no query pays a clear."""
    eng = fresh()
    assert ask(Q.positive(y), Q.gt(y, 1), eng) is True
    assert eng.is_(y, 'real') is True
    eng.relation_specs = tuple(eng.relation_specs)
    eng.relation_specs = list(eng.relation_specs)
    hits = eng.stats["cache_hits"]
    for _ in range(5):
        assert ask(Q.positive(y), Q.gt(y, 1), eng) is True
        assert eng.is_(y, 'real') is True
    assert eng.stats["version_clears"] == 0
    assert eng.stats["cache_hits"] == hits + 10
    assert len(eng._context_sessions) == 1


def test_splits_are_keyed_on_the_registry(template_class):
    """The split memo holds whether a set is consistent, computed by the
    templates: a template registered later can make the set inconsistent,
    and the memoized "consistent" would answer the query under its part
    where a fresh engine raises."""
    G = template_class
    a = Q.positive(G(y)) & Q.positive(z)
    eng = fresh()
    assert same_as_fresh(eng, Q.positive(z), a) is True
    assert eng.stats["relevant"] == 1 and eng.splits[a].consistent is True
    registry.register(G)(lambda e: Not(P('positive', e)))
    assert same_as_fresh(eng, Q.positive(z), a) == "ValueError"
    assert eng.stats["version_clears"] == 1


# -- inputs that are not the extension registry --------------------------------

def test_template_registration_clears(template_class):
    """A structural template registered after a query (3a): the template
    registry's own memo is cleared by the registration, the engine's caches
    and sessions hold what the old templates derived."""
    G = template_class
    g = G(y)
    eng = fresh()
    assert same_as_fresh(eng, Q.positive(g)) is None
    assert same_as_fresh(eng, Q.positive(g), Q.positive(y)) is None
    registry.register(G)(lambda e: P('positive', e))
    assert same_as_fresh(eng, Q.positive(g)) is True
    assert same_as_fresh(eng, Q.positive(g), Q.positive(y)) is True
    assert eng.stats["version_clears"] == 1


def test_shared_cache_created_before_a_registration():
    """A ``DictCache`` records the epoch it was created under (3b): an
    engine created after a registration, given a cache filled before it,
    drops the cache's contents at its first query."""
    old = fresh()
    assert old.is_(f(y), 'real') is None
    assert old.cache.get(f(y), 'real', "miss") is None       # the None is cached
    extensions.register('real', AppliedUndef)(undef_real)
    new = Engine(cache=old.cache)
    assert new.is_(f(y), 'real') is True
    assert new.stats["version_clears"] == 0                  # nothing of its own to drop
    # the cache carries its own epoch: ``old`` drops its sessions and memos,
    # not what ``new`` derived into the shared cache under the current epoch
    hits = old.stats["cache_hits"]
    assert old.is_(f(y), 'real') is True
    assert old.stats["cache_hits"] == hits + 1 and old.stats["version_clears"] == 1


def test_engine_with_its_own_registry_follows_the_global_scope():
    """``sympy_api.ask`` decides the scope of a custom predicate from the
    default registry, whichever registry the engine uses (3c): a
    registration on the default registry changes the answer of an engine
    with its own."""
    mine = Extensions()
    mine.register('hbig', Symbol)(big)
    eng = Engine(cache=DictCache(), extensions=mine)
    def both():
        warm = ask(hbig(m), True, eng)
        assert warm == ask(hbig(m), True, Engine(cache=DictCache(), extensions=mine))
        return warm
    assert both() is None                    # out of scope: not registered globally
    extensions.register('hbig', Symbol)(lambda s: None)
    assert both() is False                   # in scope; the engine's own handler answers
    extensions.unregister('hbig')
    assert both() is None
    assert eng.stats["version_clears"] == 2


def test_swapping_the_registry_clears():
    eng = fresh()
    assert eng.is_(f(y), 'real') is None
    mine = Extensions()
    mine.register('real', AppliedUndef)(undef_real)
    eng.extensions = mine
    assert eng.is_(f(y), 'real') is True
    eng.extensions = mine                                    # the same one: no change
    assert eng.is_(f(y), 'real') is True
    assert eng.stats["version_clears"] == 1
    eng.extensions = extensions
    assert eng.is_(f(y), 'real') is None
    assert eng.stats["version_clears"] == 2


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


def test_session_raising_under_the_assumptions_only_is_dropped():
    """The contradiction is with the assumptions only: the root stays
    satisfiable, but the session holding the node raises for every later
    query under the set, where a fresh engine answers."""
    extensions.register('real', AppliedUndef)(contradictory_under_positive)
    a = Q.positive(x)
    eng = fresh()
    assert same_as_fresh(eng, Q.real(x), a) is True
    assert same_as_fresh(eng, Q.positive(f(x) + x), a) == "ValueError"
    assert eng.stats["dead_sessions"] == 1 and a not in eng._context_sessions
    assert same_as_fresh(eng, Q.real(x), a) is True
    assert same_as_fresh(eng, Q.negative(x), a) is False
    assert same_as_fresh(eng, Q.zero(x + 1), a) is False
    assert eng.stats["dead_sessions"] == 1


def test_dead_session_after_an_uninterpreted_exit():
    """The query's nodes kill the session at root, but the query leaves by
    ``Uninterpreted`` (a relation no theory reads: None), not by
    ``InconsistentAssumptions``: the dead session is found when it is
    reused."""
    # (the Uninterpreted exit exists only with uninterpreted="none")
    extensions.register('real', AppliedUndef)(contradictory)
    a = Q.positive(x)
    eng = fresh(uninterpreted="none")

    def same(p):
        warm = outcome(eng, p, a)
        assert warm == outcome(fresh(uninterpreted="none"), p, a)
        return warm
    assert same(Q.real(x)) is True
    assert same(Q.real(f(x)) | Q.lt(x, I * x)) is None
    assert eng.stats["dead_sessions"] == 0                   # nothing raised
    assert same(Q.negative(x)) is False     # was ValueError
    assert eng.stats["dead_sessions"] == 1
    assert same(Q.real(x)) is True
    assert same_as_fresh(eng, Q.zero(x + 1), a) is False
    assert eng.stats["dead_sessions"] == 1


def test_inconsistent_assumptions_still_raise_every_time():
    """An inconsistent set raises for every query, as before and as a fresh
    engine does: the set's complete check (``Engine._complete_check``) finds
    it inconsistent once, the verdict is memoized, and no session of it is
    ever kept."""
    eng = fresh()
    a = Q.positive(x) & Q.negative(x)
    for p in (Q.real(x), Q.zero(x), Q.real(x)):
        assert same_as_fresh(eng, p, a) == "ValueError"
    assert eng.stats["set_checks"] == 1 and not eng._context_sessions


# -- engine settings (I7) ----------------------------------------------------

def _no_templates(node):
    return ()


#: a non-default value of every engine setting
SETTINGS = [("discovery_budget", 1), ("session_limit", 0), ("keep_sessions", 0),
            ("cone_search", False), ("cone_threshold", 0), ("transfer", False),
            ("uninterpreted", "none"), ("relevance", False),
            ("templates", _no_templates)]

SETTING_QUERIES = [(Q.real(x), Q.real(x) & Q.le(y, 1.5)),
                   (Q.real(x + 1), Q.real(x)),
                   (Q.positive(x * y), Q.positive(x) & Q.gt(y, 0)),
                   (Q.positive(y), Q.eq(x, y) & Q.positive(x)),
                   (Q.nonzero(x + 1), Q.positive(x) & Q.real(z))]


@pytest.mark.parametrize("name,value", SETTINGS, ids=[s[0] for s in SETTINGS])
def test_setting_change_after_queries_answers_as_fresh(name, value):
    """I7: a setting changed after queries gives the answers of a fresh
    engine with that setting (the change drops this engine's caches)."""
    eng = fresh()
    for p, a in SETTING_QUERIES:
        outcome(eng, p, a)
    setattr(eng, name, value)
    assert getattr(eng, name) == value
    kw = {name: value}
    if name == "templates":
        # Engine(templates=...) defaults to no adapters; keep the same ones
        kw["relations"] = eng.relation_specs
        assert eng.clause_templates is None
    for p, a in SETTING_QUERIES:
        assert outcome(eng, p, a) == outcome(fresh(**kw), p, a), (p, a)
    assert eng.stats["version_clears"] == 1


@pytest.mark.parametrize("name", [s[0] for s in SETTINGS])
def test_assigning_the_same_setting_clears_nothing(name):
    eng = fresh()
    for p, a in SETTING_QUERIES:
        outcome(eng, p, a)
    epoch = EPOCH[0]
    setattr(eng, name, getattr(eng, name))
    assert EPOCH[0] == epoch
    memo = dict(eng.answers)
    for p, a in SETTING_QUERIES:
        outcome(eng, p, a)
    assert eng.stats["version_clears"] == 0
    assert all(eng.answers.get(k) == v for k, v in memo.items())


@pytest.mark.parametrize("name,value", SETTINGS, ids=[s[0] for s in SETTINGS])
def test_setting_change_is_local_to_its_engine(name, value):
    """A setting change drops the changed engine's caches (its fact caches
    included) and nothing of another engine's: the registry epoch is not
    bumped, so a long-lived engine keeps its history."""
    other, eng = fresh(), fresh()
    for p, a in SETTING_QUERIES:
        outcome(other, p, a)
        outcome(eng, p, a)
    epoch = EPOCH[0]
    memo, sessions = dict(other.answers), dict(other._context_sessions)
    facts = dict(other.cache.store)
    setattr(eng, name, value)
    assert EPOCH[0] == epoch
    assert eng.stats["version_clears"] == 1
    assert not eng.answers and not eng.splits and not eng._context_sessions
    assert not eng.cache.store and not eng.custom_cache.store
    assert other.stats["version_clears"] == 0 and other._epoch == EPOCH[0]
    assert dict(other.answers) == memo
    assert dict(other._context_sessions) == sessions
    assert dict(other.cache.store) == facts


def test_setting_change_before_any_query_counts_nothing():
    eng = fresh()
    eng.transfer = False
    assert eng.stats["version_clears"] == 0


def test_construction_bumps_nothing():
    epoch = EPOCH[0]
    for name, value in SETTINGS:
        Engine(**{name: value})
    assert EPOCH[0] == epoch


def test_uninterpreted_is_validated_on_assignment():
    eng = fresh()
    with pytest.raises(ValueError):
        eng.uninterpreted = "bogus"
    assert eng.uninterpreted == "free"
