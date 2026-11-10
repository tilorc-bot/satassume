"""twin_wl.py: live.py's workload `twin`, test_rs_core.py's `_twin` as two rows (issue 323).

One query that meets `f(u)` and `f(0)` under two equal `Function("f")` classes (the cause of the eight zero-twin answers lost
on the bar of 0576370; see `_twin`'s docstring). Row 0 asks class B's query between a registry snapshot and its restore, as
harness.checker.execute does; row 1 asks class A's held query on a fresh engine, whose session meets A's objects from the
query and B's from the process-wide memos. No bar workload holds two equal classes, so this is the one where the plant
`class-is` (661; `rk-class-split`, 409, until the formula step) fires in RelKeys, and where the moved containers' digest
(moved_digest.py) has to catch it: `_tv` holds `f(0)` twice. Each row is a callable (live.CALL), since the engines are the rows' own.
"""


def queries():
    import live
    from sympy import Function, Q, Symbol
    from sympy.core.cache import clear_cache
    from satassume import sympy_api
    from satassume.engine import DictCache, Engine
    from satassume.knowledge.extensions import extensions
    u = Symbol('u')
    fa = Function('f')
    pa, aa = Q.positive(fa(u)), Q.zero(u) & Q.positive(fa(0))
    clear_cache()
    fb = Function('f')
    pb, ab = Q.positive(fb(u)), Q.zero(u) & Q.positive(fb(0))
    assert fa is not fb and fa == fb and hash(fa) == hash(fb) and pa == pb and aa == ab

    def first():
        snap = extensions.snapshot()
        try:
            return sympy_api.ask(pb, ab, engine=Engine(cache=DictCache(), uninterpreted='none'))
        finally:
            extensions.restore(snap)

    def second():
        return sympy_api.ask(pa, aa, engine=Engine(cache=DictCache(), uninterpreted='none'))
    return [(first, live.CALL), (second, live.CALL)]
