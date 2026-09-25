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
    """Assumptions holding a relation no theory interprets make every query
    None (``Uninterpreted`` while building the session).  The engine
    remembers such sets instead of rebuilding a doomed session per query;
    the answers are the same, including None (not ValueError) for
    assumptions that are also inconsistent."""
    from sympy import pi
    from satassume import Engine, DictCache
    from satassume.sympy_api import ask
    eng = Engine(cache=DictCache())
    a = Q.le(x, pi) & Q.nonnegative(x)
    assert ask(Q.positive(x), a, eng) is None
    n = eng.stats["sessions"]
    assert a is not None and len(eng._failed) == 1
    assert ask(Q.real(x), a, eng) is None
    assert ask(Q.negative(x), a, eng) is None
    assert eng.stats["sessions"] == n              # no doomed rebuilds
    bad = Q.le(x, pi) & Q.positive(x) & Q.negative(x)
    assert ask(Q.real(x), bad, eng) is None
    assert ask(Q.zero(x), bad, eng) is None
    # a change of the theory adapters invalidates the memo
    eng.relation_specs = list(eng.relation_specs)[:1]
    assert ask(Q.finite(x), a, eng) is None
    assert eng.stats["sessions"] == n + 2
