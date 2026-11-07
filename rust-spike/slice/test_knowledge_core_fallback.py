"""Step 6e: core's two named SymPy-semantics callbacks (planner, 7 Nov) on the default Rust backend. Each is counted, and an
exception inside one is a KnowledgeFault (a BaseException), so it can't come back from a quiet handler as "unknown"."""
import pytest
from sympy import Add, Float, I, Mul, Pow, Q, pi, sqrt

import knowledge_live as K
from harness.state import reset_module_state
import term_live
from satassume import engine as E, sympy_api
from satassume.knowledge.templates import core

#: Queries built per test, so no test reuses another's objects.
CASES = [('_unit_power_units', 'core:unit_power:python', lambda: Q.real(Pow(I, pi, evaluate=False)), False),
         ('_imag_templates', 'core:imag_number:python',
          lambda: Q.imaginary(Add(Mul(-sqrt(3) / 2, I), Mul(Float('0.866025403784439'), I), evaluate=False)), True)]


@pytest.fixture
def env(monkeypatch):
    for v in ('SLICE_KNOWLEDGE', 'SLICE_SESSION_PLANT', 'SESSION_REPORT', 'SLICE_TERM'):
        monkeypatch.delenv(v, raising=False)
    undo_term = term_live.from_env()
    undos = []
    yield monkeypatch, undos
    for u in undos:
        if u is not None:
            u()
    undo_term()
    K.COUNTS.clear()


@pytest.mark.parametrize('name,key,query,answer', CASES)
def test_fallback_counted(env, name, key, query, answer):
    mp, undos = env
    undos.append(K.from_env())
    reset_module_state()                   # the engine's memos and its answer memo would answer a repeat without the template
    sympy_api.set_default_engine(E.Engine())
    K.COUNTS.clear()
    assert sympy_api.ask(query()) is answer
    assert K.COUNTS[key] == 1 and K.COUNTS['fault'] == 0


@pytest.mark.parametrize('name,key,query,answer', CASES)
def test_fallback_raise_is_loud(env, name, key, query, answer):
    mp, undos = env

    def boom(*a):
        raise RuntimeError('planted')
    mp.setattr(core, name, boom)   # before install: the fallback calls the function install saw
    undos.append(K.from_env())
    reset_module_state()                   # the engine's memos and its answer memo would answer a repeat without the template
    sympy_api.set_default_engine(E.Engine())
    K.COUNTS.clear()
    with pytest.raises(K.KnowledgeFault, match=f'{key}: RuntimeError: planted'):
        sympy_api.ask(query())
    assert K.COUNTS[key] == 1 and K.COUNTS['fault'] == 1
