"""Step 6f: the two named SymPy-semantics callbacks (knowledge_f6_live.py) on the default Rust backend. Each is counted, answers as
Python does, and an exception inside one is a KnowledgeFault (a BaseException), so it can't come back from a quiet handler as
"unknown". `f6:unit_interval:float` fires on no workload (dev, fuzz, f6, value, rootof, core), so this is its firing case."""
import pytest
from sympy import Float, Integer, Q, acos, asin
from sympy.functions.special.gamma_functions import multigamma

import knowledge_live as K
from harness.state import reset_module_state
import term_live
from satassume import engine as E, sympy_api
from satassume.knowledge.templates import functions, special

#: (module, function install wraps, counter, query builder). Queries are built per call, so no run reuses another's objects.
CASES = [(functions, '_unit_interval_units', 'f6:unit_interval:float', lambda: Q.real(acos(Float('0.5'), evaluate=False))),
         (functions, '_unit_interval_units', 'f6:unit_interval:float', lambda: Q.real(asin(Float('2.0'), evaluate=False))),
         (special, '_multigamma_value', 'f6:multigamma_value:python', lambda: Q.positive(multigamma(Integer(3), 2,
                                                                                                    evaluate=False)))]
IDS = ['acos-float', 'asin-float-out', 'multigamma-3-2']


@pytest.fixture
def env(monkeypatch):
    for v in ('SLICE_KNOWLEDGE', 'SLICE_SESSION_PLANT', 'SESSION_REPORT', 'SLICE_TERM', 'SA_F6_PLANT'):
        monkeypatch.delenv(v, raising=False)
    undo_term = term_live.from_env()
    undos = []
    yield monkeypatch, undos
    for u in undos:
        if u is not None:
            u()
    undo_term()
    K.COUNTS.clear()


def fresh_ask(q):
    reset_module_state()                   # the engine's memos and its answer memo would answer a repeat without the template
    sympy_api.set_default_engine(E.Engine())
    return sympy_api.ask(q)


@pytest.mark.parametrize('mod,name,key,query', CASES, ids=IDS)
def test_fallback_counted(env, mod, name, key, query):
    mp, undos = env
    want = fresh_ask(query())              # knowledge on Python
    undos.append(K.from_env())
    K.COUNTS.clear()
    assert fresh_ask(query()) is want
    assert K.COUNTS[key] >= 1 and K.COUNTS['fault'] == 0


@pytest.mark.parametrize('mod,name,key,query', CASES, ids=IDS)
def test_fallback_raise_is_loud(env, mod, name, key, query):
    mp, undos = env
    # As in test_fallback_counted: one ask on Python first. Cold, the Float case's `shifted` is refused (algebra: Float)
    # and the query reruns on Python before the fallback is reached, so this test passed or failed by test order.
    fresh_ask(query())

    def boom(*a):
        raise RuntimeError('planted')
    mp.setattr(mod, name, boom)            # before install: the fallback calls the function install saw
    undos.append(K.from_env())
    K.COUNTS.clear()
    with pytest.raises(K.KnowledgeFault, match=f'{key}: RuntimeError: planted'):
        fresh_ask(query())
    assert K.COUNTS[key] == 1 and K.COUNTS['fault'] == 1
