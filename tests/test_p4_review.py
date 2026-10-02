"""Review tests for issue #97 P4 (branch issue-97/p4-memos at 43042d3)."""
from sympy import Q, Symbol

from satassume import Engine
from satassume.sympy_api import ask


def test_reregistered_template_key_does_not_reuse_compiled_pattern():
    """``templates._common._CACHE`` is keyed on the template's own key,
    not on the registry epoch, and ``TemplateRegistry.register`` does not
    clear it.  A later template that reuses an earlier template's key gets
    the earlier compiled pattern: here facts saying ``positive`` for a
    class whose template says ``negative``."""
    from satassume.templates import registry
    from satassume.templates._common import units

    class _P4A(Symbol):
        pass

    class _P4B(Symbol):
        pass

    key = ('p4_review_reused_key',)

    @registry.register(_P4A)
    def template_a(expr):
        return units(key, lambda: [('positive', True)], expr)

    a = _P4A('a')
    assert ask(Q.positive(a), True, Engine()) is True

    @registry.register(_P4B)
    def template_b(expr):
        return units(key, lambda: [('negative', True)], expr)

    b = _P4B('b')
    assert ask(Q.negative(b), True, Engine()) is True
    assert ask(Q.positive(b), True, Engine()) is not True


def test_every_adopted_memo_name_resolves():
    """An adopted name that does not resolve must fail, not silently drop
    out of ``Memos.items``, ``clear`` and the inventory."""
    from harness.state import import_all
    from satassume.memos import ADOPTED, ENGINE_MEMOS, PROCESS
    import_all()
    e = Engine()
    assert {n for n, _, _ in e.memos.items()} == set(ENGINE_MEMOS)
    adopted = {f"{m}.{p}" for m, p, _ in ADOPTED}
    assert adopted <= {n for n, _, _ in PROCESS.items()}
    # and the check itself must catch a renamed attribute
    import satassume.memos as memos
    memos.ENGINE_MEMOS = ENGINE_MEMOS + ("_no_such_memo",)
    try:
        from satassume.memos import engine_memos
        assert {n for n, _, _ in engine_memos(e).items()} != set(memos.ENGINE_MEMOS)
    finally:
        memos.ENGINE_MEMOS = ENGINE_MEMOS
