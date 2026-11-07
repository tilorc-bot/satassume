"""`knowledge/realroots.py` from Rust (component 6, issue 323), wired by `knowledge_live.install()`: answers against a Python copy
nothing swaps, what a refused input does, the counters and the shadow firing, a kept query on Python, `undo`, and the trap that a
swap of the module's globals would leave Python's own `root_facts` running on Rust's `squarefree`.
"""
import os
import sys
import types
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pytest
import sa_solver
from sympy import Poly, Q, Symbol
from sympy.polys.rootoftools import ComplexRootOf

from harness.state import reset_module_state
from satassume import engine as E
from satassume import sympy_api
from satassume.knowledge import realroots as R
from satassume.knowledge.templates import rootof

import knowledge_live as K

PY = {n: getattr(R, n) for n in K.REALROOTS}
ROOTOF = rootof.root_facts
POLYS = [[1, 0, -1], [1, 0, -3, 0], [1, 0, 1], [1, 0, 1, 3], [1, 0, 0, 0, -2], [1, 0, 0, 0, 1], [1, 0, -2, 0, 1], [0, 1, 0, -1],
         [Fraction(1, 2), Fraction(-1, 3)], [2**600, 1], [2**511, 1], (1, -1, -1, 1, 5)]


@pytest.fixture
def live():
    K.COUNTS.clear()
    K.MISMATCHES.clear()
    undo = K.install()
    yield K.COUNTS
    undo()


def test_each_public_name_answers_as_python_does(live):
    for p in POLYS:
        # `__wrapped__`, the private copy: `PY[...]`'s globals are the swapped module here, so its `root_facts` would call Rust.
        assert R.squarefree(p) is R.squarefree.__wrapped__(p)
        assert R.real_root_counts(p) == R.real_root_counts.__wrapped__(p)
        assert R.imaginary_root_count(p) == R.imaginary_root_count.__wrapped__(p)
        for q in POLYS:
            ours = R.gcd(p, q)
            assert ours == R.gcd.__wrapped__(p, q) and all(type(c) is Fraction for c in ours)
        for i in (-1, 0, 1, 2, 3, 4, 2**80):
            assert R.root_facts(p, i) == R.root_facts.__wrapped__(p, i)
    assert live['realroots:squarefree'] == len(POLYS) and live['realroots:root_facts'] == 7 * len(POLYS)


def test_the_zero_polynomial_raises_as_python_does(live):
    for p in ([], [0], [0, 0]):
        with pytest.raises(IndexError):
            PY['real_root_counts'](p)
        with pytest.raises(IndexError):
            R.real_root_counts(p)
        assert R.root_facts(p, 0) is None
        assert R.imaginary_root_count(p) == 0


@pytest.mark.parametrize('bad', [[1.5, 1], ['1', 2], [None], [1, 1.0], 5])
def test_what_rust_refuses_is_a_fault_not_a_quiet_exception(live, bad):
    with pytest.raises(K.KnowledgeFault):
        R.root_facts(bad, 0)
    assert live['fault'] == 1
    assert not issubclass(K.KnowledgeFault, Exception)


def test_pythons_copy_runs_no_rust():
    undo = K.install()
    try:
        f = R.root_facts.__wrapped__
        assert f.__globals__['squarefree'].__module__ != K.__name__
        assert f.__globals__['squarefree'] is not R.squarefree
        assert f.__globals__['real_root_counts'].__qualname__ == 'real_root_counts'
        assert not hasattr(f.__globals__['squarefree'], '__wrapped__')
    finally:
        undo()


def test_a_kept_query_stays_on_python(live):
    K._stack().append(types.SimpleNamespace(kept='kept'))
    try:
        assert R.root_facts([1, 0, -1], 0) == {'real': True, 'sign': -1, 'imaginary': False}
    finally:
        K._stack().pop()
    assert live['realroots:kept'] == 1 and live['realroots:root_facts'] == 0


def test_shadow_sees_a_wrong_result():
    K.COUNTS.clear()
    K.MISMATCHES.clear()
    real = sa_solver.realroots_squarefree
    sa_solver.realroots_squarefree = lambda p: not real(p)
    undo = K.install(shadow=True)
    try:
        R.squarefree([1, 0, -1])
        R.real_root_counts([1, 0, -1])
    finally:
        undo()
        sa_solver.realroots_squarefree = real
    assert K.COUNTS['shadow:realroots'] == 2 and K.COUNTS['shadow:mismatch'] == 1
    assert K.MISMATCHES[0][0] == 'realroots:squarefree'
    K.MISMATCHES.clear()


def test_a_limit_that_differs_refuses_to_install(monkeypatch):
    monkeypatch.setattr(R, 'MAX_BITS', R.MAX_BITS + 1)
    with pytest.raises(ValueError, match='realroots_limits'):
        K.install()


def test_undo_restores_and_rootof_is_bound_either_way():
    undo = K.install()
    assert rootof.root_facts is R.root_facts and R.root_facts is not PY['root_facts']
    undo()
    assert rootof.root_facts is ROOTOF
    assert all(getattr(R, n) is PY[n] for n in K.REALROOTS)


def test_a_query_reaches_rust_and_answers_as_python_does():
    z = Symbol('z')
    root = ComplexRootOf(Poly(z**5 - z + 1, z), 0)
    queries = [p(root) for p in (Q.real, Q.positive, Q.negative, Q.imaginary)]

    def answers():
        reset_module_state(sympy_cache=False)
        sympy_api.set_default_engine(E.Engine())
        return [sympy_api.ask(q) for q in queries]

    plain = answers()
    assert plain[0] is True and plain[2] is True and plain[1] is False
    K.COUNTS.clear()
    undo = K.install()
    try:
        assert answers() == plain
    finally:
        undo()
    assert K.COUNTS['realroots:root_facts'] >= 1
