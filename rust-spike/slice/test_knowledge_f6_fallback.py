"""Step 6f: the named SymPy-semantics callbacks on the default Rust backend. Each is counted, answers as Python does, and an
exception inside one is a KnowledgeFault (a BaseException), so it can't come back from a quiet handler as "unknown".
6i(b): asin/acos of a Float no longer reach 6f's swapped `_unit_interval_units` (`f6:unit_interval:float`): conversion
refuses the whole query (`refused:algebra: Float`, a kept reason) before any template runs, so it is answered on Python's
kept path, where nothing is swapped; the Float cases now check that (counted, same answer) and leave LOUD, since no callback
runs. A Float under a query can't reach fn_tpl.rs's unit facts either (asin/acos have the slot `x - 1`, and `f6_shifted`
refuses a Float); test_knowledge_fn_direct.py covers that branch's guards. `_value_units`' `expr.func(c)` is a callback from
Rust now (fn_tpl.rs, `fn:value:sympy`), planted in SymPy's `genocchi.eval`."""
import pytest
from sympy import Float, Integer, Q, acos, asin, genocchi
from sympy.functions.special.gamma_functions import multigamma

import knowledge_live as K
from harness.state import reset_module_state
import term_live
from satassume import engine as E, sympy_api
from satassume.knowledge.templates import functions

#: (module, function install wraps, counter, query builder). Queries are built per call, so no run reuses another's objects.
CASES = [(functions, '_unit_interval_units', 'refused:algebra: Float', lambda: Q.real(acos(Float('0.5'), evaluate=False))),
         (functions, '_unit_interval_units', 'refused:algebra: Float', lambda: Q.real(asin(Float('2.0'), evaluate=False))),
         # 6i(a): multigamma's template is Rust's (outer_tpl.rs), which evaluates `expr.func(x, p)` itself; the raise is planted
         # in SymPy's `multigamma.eval`
         (multigamma, 'eval', 'outer:multigamma_value:sympy', lambda: Q.positive(multigamma(Integer(3), 2,
                                                                                             evaluate=False))),
         # 6i(b): genocchi's slotted template is Rust's (fn_tpl.rs), which evaluates `expr.func(c)` itself (`_value_units`)
         (genocchi, 'eval', 'fn:value:sympy', lambda: Q.positive(genocchi(Integer(8), evaluate=False)))]
IDS = ['acos-float', 'asin-float-out', 'multigamma-3-2', 'genocchi-8']
LOUD = CASES[2:]
LOUD_IDS = IDS[2:]


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


def count(key):
    """`key` in knowledge_live's COUNTS plus 6d's Common counts not yet flushed (outer_tpl.rs counts there)."""
    import knowledge_common_live
    c = knowledge_common_live.COMMON[0]
    return K.COUNTS[key] + (c.counts().get(key, 0) if c is not None else 0)


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
    assert count(key) >= 1 and count('fault') == 0


@pytest.mark.parametrize('mod,name,key,query', LOUD, ids=LOUD_IDS)
def test_fallback_raise_is_loud(env, mod, name, key, query):
    mp, undos = env
    # As in test_fallback_counted: one ask on Python first (before 6i(b), a Float case passed or failed by test order here).
    fresh_ask(query())

    def boom(*a):
        raise RuntimeError('planted')
    mp.setattr(mod, name, boom)            # before install: the fallback calls the function install saw
    undos.append(K.from_env())
    K.COUNTS.clear()
    with pytest.raises(K.KnowledgeFault, match=f'{key}: RuntimeError: planted'):
        fresh_ask(query())
    assert count(key) == 1 and count('fault') == 1
