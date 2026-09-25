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
