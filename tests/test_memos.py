"""The pure-function memos of the engine's front end: the template registry's
``clauses_for`` per expression and ``sympy_api``'s ``to_formula`` per SymPy
Boolean.  Both must be invalidated by the registrations they depend on."""
import pytest

sympy = pytest.importorskip("sympy")

from sympy import Predicate, Q, Symbol  # noqa: E402

from satassume.formula import P  # noqa: E402
from satassume.sympy_api import _formula, to_formula, Unsupported, register, unregister  # noqa: E402
from satassume.templates.registry import TemplateRegistry  # noqa: E402

x = Symbol('x')


def test_clauses_for_is_memoized_and_cleared_by_register():
    reg = TemplateRegistry()
    calls = []

    @reg.register(Symbol)
    def t(e):
        calls.append(e)
        return P('positive', e)

    r1 = reg.clauses_for(x)
    assert reg.clauses_for(x) is r1 and calls == [x]

    @reg.register(Symbol)
    def u(e):
        return P('real', e)

    r2 = reg.clauses_for(x)
    assert r2 is not r1 and len(r2[1]) == 2


def test_formula_memo_follows_registrations():
    class MemoPredicate(Predicate):
        pass

    try:
        Q.memo_key = MemoPredicate()
        with pytest.raises(Unsupported):
            _formula(Q.memo_key(x), False)
        with pytest.raises(Unsupported):          # the failure is memoized too
            _formula(Q.memo_key(x), False)

        @register(Q.memo_key, Symbol)
        def _(e):
            return None

        f = _formula(Q.memo_key(x), False)
        assert f == to_formula(Q.memo_key(x))
        assert _formula(Q.memo_key(x), False) is f
        unregister(Q.memo_key)
        with pytest.raises(Unsupported):
            _formula(Q.memo_key(x), False)
    finally:
        unregister(Q.memo_key)
        del Q.memo_key


def test_uninterpreted_assumptions_are_remembered():
    """With ``uninterpreted="none"`` (opt-in), assumptions holding a
    relation no theory interprets make every query None (``Uninterpreted``
    while building the session).  The engine
    remembers such sets instead of rebuilding a doomed session per query;
    the answers are the same, including None (not ValueError) for
    assumptions that are also inconsistent."""
    from sympy import pi
    from satassume import Engine, DictCache
    from satassume.sympy_api import ask
    eng = Engine(cache=DictCache(), uninterpreted="none")
    a = Q.le(0.5 * x, 1) & Q.nonnegative(x)          # a Float: unread
    assert ask(Q.positive(x), a, eng) is None
    n = eng.stats["sessions"]
    assert a is not None and len(eng._failed) == 1
    assert ask(Q.real(x), a, eng) is None
    assert ask(Q.negative(x), a, eng) is None
    assert eng.stats["sessions"] == n              # no doomed rebuilds
    bad = Q.le(0.5 * x, 1) & Q.positive(x) & Q.negative(x)
    assert ask(Q.real(x), bad, eng) is None
    assert ask(Q.zero(x), bad, eng) is None
    # a change of the theory adapters invalidates the memo, with every
    # other engine-level cache (Engine._check_version)
    eng.relation_specs = list(eng.relation_specs)[:1]
    assert ask(Q.finite(x), a, eng) is None
    assert eng.stats["sessions"] == n + 2
    assert eng.stats["version_clears"] == 1 and not eng._context_sessions


# -- the memo objects (issue #97, P4) ------------------------------------------

def test_two_engines_do_not_share_memos():
    """Every engine has its own ``Memos``; none of its memo containers is
    another engine's, filling one leaves the other's empty, and clearing
    one leaves the other's alone.  What engines do share is
    ``memos.PROCESS``, and only memos keyed on nothing but their key and
    the registry epoch (or the default registry's version) may live there."""
    from satassume import Engine
    from satassume.memos import ENGINE_MEMOS, PROCESS, PROCESS_KEYS
    from satassume.sympy_api import ask
    e1, e2 = Engine(), Engine()
    assert e1.memos is not e2.memos
    c1 = {n: c for n, _, c in e1.memos.items()}
    c2 = {n: c for n, _, c in e2.memos.items()}
    assert set(c1) == set(c2) == set(ENGINE_MEMOS) and len(ENGINE_MEMOS) == 10
    assert not {id(c) for c in c1.values()} & {id(c) for c in c2.values()}
    y = Symbol('y')
    a = Q.positive(x) & Q.positive(y)
    assert ask(Q.positive(x + y), a, e1) is True
    assert ask(Q.nonnegative(x * y), a, e1) is True
    assert any(e1.memos.sizes().values())
    assert not any(e2.memos.sizes().values())
    assert ask(Q.positive(x + y), a, e2) is True
    n2 = e2.memos.sizes()
    e1.memos.clear()
    assert not any(e1.memos.sizes().values())
    assert e2.memos.sizes() == n2 and any(n2.values())
    assert ask(Q.positive(x + y), a, e1) is True          # works after a clear
    for name, key, _ in PROCESS.items():
        assert key in PROCESS_KEYS, name


def test_process_memos_registered_and_cleared():
    """Every module-level memo is registered with ``memos.PROCESS``
    (``harness.state.MODULE_STATE`` is derived from it, also after every
    module is imported), and one ``PROCESS.clear()`` empties all of them
    and forgets the stamps of the epoch-keyed tables."""
    from harness.state import MODULE_STATE, import_all
    from satassume import memos
    from satassume import sympy_api as api
    import_all()
    assert set(memos.module_locations()) == set(MODULE_STATE)
    assert ("satassume.sympy_api", "_KEYS") in MODULE_STATE
    api._keys(Q.positive(x))
    _formula(Q.positive(x), False)
    assert api._KEYS and api._FORMULAS and api._KEYS.stamp is not None
    memos.PROCESS.clear()
    assert not any(memos.PROCESS.sizes().values())
    assert api._KEYS.stamp is None and api._FORMULAS.stamp is None
    assert api._keys(Q.positive(x)) == frozenset([x])


def test_table_bound_and_process_key_check():
    from satassume.memos import Memos, PROCESS, Table
    t = Memos("t").table("t.x", "settings", size=2)
    assert isinstance(t, Table) and type(t).get is dict.get
    t.put(1, 1); t.put(2, 2); t.put(3, 3)
    assert dict(t) == {3: 3}
    t.restamp(7)
    assert not t and t.stamp == 7
    with pytest.raises(ValueError):
        PROCESS.table("satassume.test.bad", "settings")
    with pytest.raises(ValueError):
        Memos("t").table("t.y", "nonsense")
