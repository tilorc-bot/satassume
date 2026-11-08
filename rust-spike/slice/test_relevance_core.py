"""Step 5c8: sympy_api's relevance rows in `relevance.rs`, Rust's against Python's (`session_live.PY_RELEVANCE`).

The 5c8 ruling's catch rules for `_consistent`, which wraps the set's check in `except Exception: return False`:
- a Python exception from a callback (`_formula`, `Engine.verdict`) gives the same quiet False on Rust as on Python, and Rust
  counts it (`rv:consistent_caught`);
- a BaseException (TermFault and KnowledgeFault are BaseException) goes up on both, never a quiet answer;
- the `consistent-fault` plant (a TermFault raised inside Rust's body) comes out loud.
Then `_keys`, `_keys_rel`, `_const_free`, `_relevant` and `_consistent` agree with Python's on hand-built sets (keys as sets,
`_relevant`'s part by `==`).
"""
import pytest

from test_relations_core import _rust

SL = _rust()

import sa_solver  # noqa: E402
from sympy import E, Function, Q, Symbol, pi, sqrt  # noqa: E402
from satassume import sympy_api as A  # noqa: E402
from satassume.engine import Engine  # noqa: E402

x, y, z, w = (Symbol(n) for n in 'xyzw')
f, g = Function('f'), Function('g')
PY = SL.PY_RELEVANCE


def _py(name, *args):
    """Python's `name`, with every wired name Python's while it runs, so it never calls into Rust."""
    saved = {n: getattr(A, n) for n in PY}
    for n, fn in PY.items():
        setattr(A, n, fn)
    try:
        return getattr(A, name)(*args)
    finally:
        for n, fn in saved.items():
            setattr(A, n, fn)


def _count(name):
    return dict(sa_solver.session_counts())[name]


def test_installed():
    assert A._consistent is sa_solver.rv_consistent and A._relevant is sa_solver.rv_relevant
    assert PY['_consistent'].__module__ == 'satassume.sympy_api'


class _Boom(Exception):
    pass


class _Base(BaseException):
    pass


@pytest.mark.parametrize('exc,where', [(_Boom, 'verdict'), (_Boom, 'formula'), (_Base, 'verdict'), (_Base, 'formula')])
def test_same_catches(monkeypatch, exc, where):
    a = Q.positive(x) & Q.negative(y)

    def raise_(*args, **kw):
        raise exc('planted')
    if where == 'verdict':
        monkeypatch.setattr(Engine, 'verdict', raise_)
    else:
        monkeypatch.setattr(A, '_formula', raise_)
    for fn in (lambda a, eng: _py('_consistent', a, eng), sa_solver.rv_consistent):
        before = _count('rv:consistent_caught')
        eng = Engine()
        if issubclass(exc, Exception):
            assert fn(a, eng) is False
            caught = 1 if fn is sa_solver.rv_consistent else 0
        else:
            with pytest.raises(exc):
                fn(a, eng)
            caught = 0
        assert _count('rv:consistent_caught') == before + caught
        assert eng.stats['consistency_checks'] == 1


def test_fault_plant_is_loud():
    import term_live
    sa_solver.rel_plant('consistent-fault')
    try:
        with pytest.raises(term_live.TermFault):
            sa_solver.rv_consistent(Q.positive(x) & Q.negative(y), Engine())
    finally:
        sa_solver.rel_plant(None)
    assert sa_solver.rv_consistent(Q.positive(x) & Q.negative(y), Engine()) is True


EXPRS = [Q.positive(x), Q.positive(x + y), Q.positive(f(x)), Q.positive(f(x) + g(y)), Q.positive(sqrt(2) * x),
         Q.positive(pi + 1), Q.lt(x, y), Q.eq(x, 2), Q.lt(sqrt(2), x), Q.eq(f(x), f(y)),
         Q.positive(x) & ~Q.negative(z), Q.positive(x) | Q.zero(y), Q.positive(E * x * y)]


@pytest.mark.parametrize('e', EXPRS, ids=str)
def test_keys_match(e):
    A._KEYS.clear()
    A._CONST.clear()
    want = _py('_keys_rel', e)
    A._KEYS.clear()
    A._CONST.clear()
    got = sa_solver.rv_keys_rel(e)
    assert (set(got[0]) if got[0] is not None else None, got[1]) == (set(want[0]) if want[0] is not None else None, want[1])
    assert set(sa_solver.rv_keys(e) or ()) == set(_py('_keys', e) or ())


@pytest.mark.parametrize('c', [sqrt(2), pi, E, pi * sqrt(3), 2 * pi, pi + 1, sqrt(x)], ids=str)
def test_const_free_match(c):
    A._CONST.clear()
    want = _py('_const_free', c)
    A._CONST.clear()
    assert sa_solver.rv_const_free(c) == want


SETS = [
    (Q.positive(x), Q.positive(x) & Q.real(y)),
    (Q.positive(x), Q.positive(x) & Q.negative(y) & Q.positive(y)),     # inconsistent elsewhere: whole set, ValueError
    (Q.positive(x + z), Q.positive(x) & Q.positive(z) & Q.integer(y)),
    (Q.lt(x, 3), Q.lt(x, 2) & Q.gt(y, 5)),
    (Q.positive(f(x)), Q.positive(f(y)) & Q.real(z)),                    # f(x), f(y) connect by f's class
    (Q.positive(sqrt(2) * x), Q.positive(x) & Q.positive(sqrt(2) * w) & Q.zero(y)),
    (Q.eq(x, 2), Q.eq(x, 2) & Q.eq(y, 2)),                              # pinned to one value: no key between x and y
    (Q.positive(x), Q.lt(1, 2) & Q.positive(x) & Q.real(y)),            # keyless conjunct
]


@pytest.mark.parametrize('p,a', SETS, ids=lambda v: str(v))
def test_relevant_match(p, a):
    A._KEYS.clear()
    A._CONST.clear()
    want = _py('_relevant', p, a, Engine())
    A._KEYS.clear()
    A._CONST.clear()
    got = sa_solver.rv_relevant(p, a, Engine())
    assert got == want
    assert sa_solver.rv_consistent(a, Engine()) == _py('_consistent', a, Engine())
