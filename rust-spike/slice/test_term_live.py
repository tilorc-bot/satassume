"""Component 4 slice A: a refusal reaches the top of the run, past every handler, and the run leaves nothing behind.

Run from this directory, with `backend.install()` off (Python's solver) and on (`SLICE_TERM_TEST_RUST=1`). Every site says
whether it was reached: a plant that never ran fails here, it doesn't pass.
"""
import os

import pytest
from sympy import Q, Symbol, log, pi, sin

import sa_solver
import term_live
from harness.state import reset_module_state
from satassume import engine as E, relations as R, sympy_api as A
from satassume.state import memos
from satassume.theories.lra import constfield as CF, lra as LR, lra_adapter as L, lra_bounds as B

RUST = bool(os.environ.get('SLICE_TERM_TEST_RUST'))
if RUST:
    import backend
    backend.install()

x, y = Symbol('x', real=True), Symbol('y', real=True)
n, k = Symbol('n'), Symbol('k')
SUM = (Q.gt(x + y, 1), Q.gt(x, 2) & Q.gt(y, 0))

CERT = (Q.zero(x), Q.ge(x, -pi / 2))

# Each of the seven handlers on the engine's path that catch `Exception`, a call inside its `try`, and a query reaching it.
HANDLERS = [
    ('engine.py:1906', E.Engine, '_complete_check', SUM),
    ('sympy_api.py:1107', A, '_formula', SUM),
    ('relations.py:1989', R, '_guarded_adapters', SUM),
    ('relations.py:2011', R, '_termwise', (Q.eq(n, k), Q.integer(n) & Q.nonnegative(n) & Q.gt(k, n))),
    ('relations.py:2018', R, '_terms_of', SUM),
    # On Rust's solver the core runs the certificate and `LRATheory._certify` is never called: the handler is `lra.rs:935`.
    # Nothing inside it calls Python since `pi_laurent` moved to Rust (adapters step, part C2), so the raise is Rust's own:
    # `rel_plant('cf-laurent-refuse')`, at lra_cert.rs's `laurent`, reached as the count `cf:pi_laurent`.
    ('lra.rs:935', None, 'cf-laurent-refuse', CERT) if RUST else ('lra.py:461', LR.LRATheory, '_certify', CERT),
    ('lra_bounds.py:249', B, '_loose', (Q.positive(sin(1)), True)),
]


def fresh():
    reset_module_state(sympy_cache=False)
    A.set_default_engine(E.Engine())


@pytest.fixture
def live():
    undo = term_live.install(keys=True)
    term_live.COUNTS.clear()
    del term_live.REFUSALS[:]
    fresh()
    yield
    if RUST:
        sa_solver.rel_plant(None)
    undo()
    fresh()


class LaurentCalls:
    """`calls[0]` for a Rust fault: `cf:pi_laurent`'s count since it was made."""
    def __init__(self):
        self.base = sa_solver.session_counts()['cf:pi_laurent']

    def __getitem__(self, i):
        return sa_solver.session_counts()['cf:pi_laurent'] - self.base


def plant(monkeypatch, owner, attr, once=True, text='planted'):
    if owner is None:                   # a Rust fault by name (`rel_plant`); `live` turns it off
        calls = LaurentCalls()
        sa_solver.rel_plant(attr)
        return calls
    real = next(c.__dict__[attr] for c in owner.__mro__ if attr in c.__dict__) if isinstance(owner, type) else getattr(owner, attr)
    is_static = isinstance(real, staticmethod)
    f = real.__func__ if is_static else real
    calls = [0]

    def raising(*a, **kw):
        calls[0] += 1
        if calls[0] == 1 or not once:
            if term_live.current() is not None and not isinstance(term_live.current(), term_live._Refused):
                raise sa_solver.TermRefuse(text)
        return f(*a, **kw)
    monkeypatch.setattr(owner, attr, staticmethod(raising) if is_static else raising)
    return calls


@pytest.mark.parametrize('site,owner,attr,query', HANDLERS, ids=[h[0] for h in HANDLERS])
def test_a_refusal_goes_past_the_handler(live, monkeypatch, site, owner, attr, query):
    want = A.ask(*query)
    fresh()
    term_live.COUNTS.clear()
    calls = plant(monkeypatch, owner, attr)
    assert A.ask(*query) is want
    assert calls[0] > 0, f'{site}: the query never reached it'
    assert term_live.COUNTS['refused'] == 1


@pytest.mark.skipif(not RUST, reason="the core's handler")
def test_the_core_certificate_handler_is_quiet_on_an_exception(live, monkeypatch):
    """The plant above is inside `lra.rs:935`'s handler: an `Exception` from the same call doesn't come out. `handler_count`
    doesn't see this one. Since `pi_laurent` moved to Rust (adapters step, part C2) the raise is Rust's: a ValueError from
    lra_cert.rs's `laurent` on each call (`rel_plant('cf-laurent-raise')`)."""
    calls = plant(monkeypatch, None, 'cf-laurent-raise')
    A.ask(*CERT)
    assert calls[0] > 0
    assert term_live.COUNTS['refused'] == 0


def test_a_constant_index_a_discard_frees_can_go_to_another(live):
    """A rollback truncates `_CONSTANTS`, so the next registration reuses the index. Nothing may answer for the new constant
    from the old one: `constfield.rs`'s `ENCLOSURES` is keyed by that index, and the old answer here differs from the new."""
    gone = (Q.gt(x, log(37)), Q.lt(x, 1))        # log(37) > 1: False, and so is half of it, the stale reading of `kept`
    kept = (Q.gt(x, log(5) / 2), Q.lt(x, 1))     # log(5)/2 < 1: open
    eng = E.Engine()
    A.set_default_engine(eng)
    i = len(CF._CONSTANTS)
    mark = term_live._Mark(eng)
    assert A.ask(*gone) is False
    assert len(CF._CONSTANTS) > i
    first = CF._CONSTANTS[i]
    assert any(first._cache.values())           # the enclosure was read, so a stale one could exist
    mark.rollback()
    assert len(CF._CONSTANTS) == i
    assert A.ask(*kept) is None
    assert CF._CONSTANTS[i] is not first and CF._CONSTANTS[i].key != first.key


def test_a_discard_leaves_nothing_inside_a_nested_memo(live):
    """`_INTERPRETED` is a `defaultdict(dict)`. Once its key exists the run's entries sit inside the value, where the outer
    length doesn't move, and one left there reads the index the rollback freed as whichever constant gets it next.
    Without `_note`'s inner tables: 10 entries stay and the last answer is False, the stale reading x > log(41), x < 1."""
    victim = (Q.gt(x, log(3) / 2), Q.lt(x, 1))   # log(3)/2 < 1: open. Constants of its own: `_CONSTANTS` outlives a reset
    other = (Q.gt(x, log(41)), Q.lt(x, 1))       # log(41) > 1: False
    eng = E.Engine()
    A.set_default_engine(eng)
    assert A.ask(Q.gt(Symbol('warm', real=True), 2), Q.lt(Symbol('warm', real=True), 1)) is False   # the key exists now
    inner = L._INTERPRETED[L.GENERIC_CONSTANTS]
    n, i = len(inner), len(CF._CONSTANTS)
    mark = term_live._Mark(eng)
    assert A.ask(*victim) is None
    assert len(inner) > n and len(CF._CONSTANTS) > i
    mark.rollback()
    assert len(inner) == n and len(CF._CONSTANTS) == i
    assert A.ask(*other) is False
    assert A.ask(*victim) is None


def test_the_glue_handler_counts_what_it_catches(monkeypatch):
    """Slice C's one new handler site, Python's `relations.py:2018` over ids. Its count has to fire before its zero means
    anything, and a refusal has to pass it."""
    undo = term_live.install(terms=True)
    try:
        term_live.COUNTS.clear()
        def raises(*a, **k):
            raise ValueError('planted')
        monkeypatch.setattr(R, '_terms_of', raises)
        fresh()
        A.ask(Q.eq(x + Symbol('y', real=True), 2), Q.positive(x))
        assert term_live.COUNTS['caught:glue_objects:ValueError'] > 0
        # The second run reads no table, so the refusal fires once.
        armed = [True]
        def refuses(*a, **k):
            if armed[0]:
                armed[0] = False
                raise sa_solver.TermRefuse('planted')
            return set()
        monkeypatch.setattr(R, '_terms_of', refuses)
        term_live.COUNTS.clear()
        fresh()
        A.ask(Q.eq(x + Symbol('y', real=True), 2), Q.positive(x))
        assert term_live.COUNTS['refused'] == 1 and not term_live.COUNTS['caught:glue_objects:TermRefuse']
    finally:
        undo()
        fresh()


def _nest(eng):
    return A._ask(Q.positive(Symbol('nest', real=True)), True, eng)


def test_a_nested_ask_refuses_to_the_top_only(live, monkeypatch):
    """A refusal inside a nested `_ask` isn't its to handle: the outer run stops there too, and one discard happens."""
    want = A.ask(*SUM)
    fresh()
    term_live.COUNTS.clear()
    real = A._formula
    state = dict(nested=0, depth=0, after=0)

    def formula(*a, **kw):
        depth = len(term_live.stack())
        if isinstance(term_live.current(), term_live._Refused):
            return real(*a, **kw)
        if depth == 2:
            state['depth'] = depth
            raise sa_solver.TermRefuse('nested')
        if not state['nested']:
            state['nested'] = 1
            _nest(A._default_engine() if callable(getattr(A, '_default_engine', None)) else E.Engine())
            state['after'] = 1
        return real(*a, **kw)
    monkeypatch.setattr(A, '_formula', formula)
    assert A.ask(*SUM) is want
    assert state == dict(nested=1, depth=2, after=0)
    assert term_live.COUNTS['refused'] == 1
    assert term_live.REFUSALS[0][0] == 'nested'
    assert term_live.stack() == []


def test_the_second_run_stays_on_python(live, monkeypatch):
    """The second run has a `_Refused` query, with no table, and a nested `_ask` in it stays there and converts nothing."""
    want = A.ask(*SUM)
    fresh()
    term_live.COUNTS.clear()
    real = A._formula
    state = dict(first=0, second=0)

    def formula(*a, **kw):
        if isinstance(term_live.current(), term_live._Refused):
            if not state['second']:
                state['second'] = 1
                _nest(E.Engine())
        elif not state['first']:
            state['first'] = 1
            raise sa_solver.TermRefuse('once')
        return real(*a, **kw)
    monkeypatch.setattr(A, '_formula', formula)
    assert A.ask(*SUM) is want
    assert state == dict(first=1, second=1)
    assert term_live.COUNTS['nested-in-refused'] == 1
    assert term_live.COUNTS['converted'] == 1
    assert term_live.COUNTS['fault'] == 0


def test_a_refusal_in_the_second_run_is_a_fault_not_a_loop(live, monkeypatch):
    real = A._formula

    def always(*a, **kw):
        raise sa_solver.TermRefuse('again')
    monkeypatch.setattr(A, '_formula', always)
    with pytest.raises(term_live.TermFault, match='second run'):
        A.ask(*SUM)
    monkeypatch.setattr(A, '_formula', real)


def test_a_rust_refusal_is_not_an_exception():
    assert issubclass(sa_solver.TermRefuse, BaseException)
    assert not issubclass(sa_solver.TermRefuse, Exception)


def test_a_python_theory_on_the_rust_solver_refusing_from_a_hook():
    """The crate unwinds a hook's exception (`solver_rs/src/lib.rs` `ok`, `run`) and raises it as itself."""
    class Refuses:
        checks = 0

        def register_atom(self, literal, payload):
            pass

        def assert_lit(self, literal):
            return None

        def check(self):
            Refuses.checks += 1
            raise sa_solver.TermRefuse('from a hook')

        def push_level(self):
            pass

        def pop_level(self):
            pass

    s = sa_solver.Solver()
    v = s.new_var()
    s.add_clause([v])
    t = Refuses()
    s.attach_theory(t)
    s.register_atom(t, v, 'atom')
    with pytest.raises(sa_solver.TermRefuse, match='from a hook'):
        s.solve()
    assert Refuses.checks == 1


def test_read_raised_reaches_the_top(live, monkeypatch):
    import convert as C
    want = A.ask(*SUM)
    fresh()
    term_live.COUNTS.clear()
    calls = []

    def boom(self, t):
        calls.append(t)
        raise ValueError('planted')
    monkeypatch.setattr(C._Walk, '_read_key', boom)
    assert A.ask(*SUM) is want
    assert calls
    assert term_live.COUNTS['read_raised'] == 1
    assert term_live.COUNTS['refused'] == 1
    assert term_live.COUNTS['fault'] == 0


def test_read_term_missing_reaches_the_top(live, monkeypatch):
    import convert as C
    want = A.ask(*SUM)
    fresh()
    term_live.COUNTS.clear()
    real = C._Walk._read_key

    def holds(self, t):
        return (Symbol('not_in_this_table'), real(self, t))
    monkeypatch.setattr(C._Walk, '_read_key', holds)
    assert A.ask(*SUM) is want
    assert term_live.COUNTS['read_term_missing'] == 1
    assert term_live.COUNTS['refused'] == 1


# ---- rollback


def test_a_restamp_during_the_run_comes_back(live):
    """A table restamped in the run gets its stamp back, and what the run put in it goes."""
    t = A._KEYS
    assert t.stamp is None
    m = term_live._Mark(E.Engine())
    t.restamp('run')
    t['k'] = 1
    m.rollback()
    assert t.stamp is None and len(t) == 0
    assert term_live.COUNTS['rollback:restamped'] >= 1


def test_a_table_emptied_and_regrown_past_the_mark_keeps_nothing_of_the_run():
    """`popitem` alone would keep the run's first n entries as if they were the table's old ones."""
    t = memos.Table('term_live_test', 'pure', 10)
    t['old1'] = 1
    t['old2'] = 2
    m = term_live._Mark.__new__(term_live._Mark)
    m.tables, m.natives, m.engines, m.cache, m.facts = {}, {}, {}, [], {}
    m._note(t)
    t.clear()
    for i in range(5):
        t[f'run{i}'] = i
    term_live.COUNTS.clear()
    m.rollback()
    assert not [k for k in t if k.startswith('run')]
    assert term_live.COUNTS['rollback:cleared'] == 1


def test_what_was_there_before_the_run_stays():
    t = memos.Table('term_live_test2', 'pure', 10)
    t['old1'] = 1
    m = term_live._Mark.__new__(term_live._Mark)
    m.tables, m.natives, m.engines, m.cache, m.facts = {}, {}, {}, [], {}
    m._note(t)
    t['run'] = 2
    term_live.COUNTS.clear()
    m.rollback()
    assert dict(t) == {'old1': 1} and not term_live.COUNTS['rollback:cleared']
