"""D "adapters cost" (issue 323): the count of attribute misses Rust takes and drops (miss_count.py), and kept tests for
adapters.rs' C1 (py_class), C3 (intern_into) and C5 (module()).
- The count has to fire: plant 470 `ad-swallow` puts a `getattr_opt` miss back in py_class, and the count must see it on every
  EUF parse of a live run, while the answers stay the same. Without the plant, py_class's own name (`_PyEUFAdapter`) misses 0 times.
- C3, plant 471 `ad-ready-args`: Rust's `_terms`, and the theory's interned keys, equal Python's `_intern` on the same
  expressions, one theory each.
- C5, plant 472 `ad-module-swap`: a theory-less adapter takes `EUFTheory` from the module sys.modules holds at build time.
Plants are adapters.rs' own family (`sa_solver.ad_cost_plant`), off unless a test sets them.
"""
import json
import os
import subprocess
import sys
import types

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

CHILD = r'''
import json, os, sys
sys.path.insert(0, os.path.join(sys.argv[2], 'tests'))
import backend
backend.install_euf()
import term_live; term_live.from_env()
import lra_live; lra_live.from_env()
import session_live; session_live.from_env()
import knowledge_live; knowledge_live.from_env()
backend.install()
import sa_solver
import miss_count
from sympy import Function, Q, Symbol
from satassume import DictCache
from satassume.sympy_api import Engine, ask
miss_count.install()
plant = sys.argv[1]
sa_solver.ad_cost_plant(None if plant == 'none' else plant)
x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
f, g = Function('f'), Function('g')
cases = [(Q.eq(f(x), f(y)), Q.eq(x, y)), (Q.eq(g(f(x), z), g(f(y), z)), Q.eq(x, y)), (Q.ne(f(x), f(y)), Q.eq(x, y)),
         (Q.eq(f(x + 1), f(y)), Q.eq(y, x + 1)), (Q.eq(f(x), y), Q.eq(f(y), x))]
answers = [repr(ask(p, a, Engine(cache=DictCache()))) for p, a in cases]
sa_solver.ad_cost_plant(None)
c = sa_solver.session_counts()
print(json.dumps({'answers': answers, 'misses': miss_count.snapshot(), 'parse': c.get('ad:cb_parse', 0)}))
'''


def _run(plant):
    env = dict(os.environ)
    env.setdefault('PYTHONHASHSEED', '0')
    r = subprocess.run([sys.executable, '-c', CHILD, plant or 'none', ROOT], cwd=HERE, env=env, capture_output=True,
                       text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope='module')
def runs():
    return {k: _run(k) for k in (None, 'ad-swallow')}


EUF = 'satassume.theories.euf.euf_adapter'


def test_count_sees_a_swallowed_raise(runs):
    got = runs['ad-swallow']
    assert got['parse'] > 0
    assert got['misses'].get(f'{EUF}:_PyEUFAdapter_planted_470', 0) >= got['parse'], got['misses']
    assert runs[None]['misses'].get(f'{EUF}:_PyEUFAdapter_planted_470', 0) == 0


def test_py_class_builds_no_miss(runs):
    assert runs[None]['parse'] > 0
    assert runs[None]['misses'].get(f'{EUF}:_PyEUFAdapter', 0) == 0, runs[None]['misses']


def test_answers_unchanged_by_the_swallow(runs):
    assert runs['ad-swallow']['answers'] == runs[None]['answers']


@pytest.fixture
def plant():
    import sa_solver
    yield sa_solver.ad_cost_plant
    sa_solver.ad_cost_plant(None)


def _terms(adapter_cls, exprs):
    from satassume.theories.euf.euf_adapter import EUFTheory
    ad = adapter_cls(EUFTheory())
    for e in exprs:
        ad.term(e)
    return list(ad._terms.items()), list(ad.theory._keys.items())     # the terms, and what each was built from


@pytest.mark.parametrize('on', [False, True])
def test_intern_matches_python(plant, on):
    import sa_solver
    from sympy import Function, Symbol
    from satassume.theories.euf import euf_adapter
    py = getattr(euf_adapter, '_PyEUFAdapter', euf_adapter.EUFAdapter)
    if py is sa_solver.EUFAdapter:
        pytest.skip("Python's EUFAdapter isn't reachable")
    x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
    f, g, h = Function('f'), Function('g'), Function('h')
    exprs = [g(f(x), h(y, z)), h(f(y), g(x, z)) + f(z), f(g(x, y)) * h(z, x) + 2]
    want = _terms(py, exprs)
    plant('ad-ready-args' if on else None)
    try:
        got = _terms(sa_solver.EUFAdapter, exprs)
    except KeyError:
        got = 'KeyError'
    assert (got == want) is (not on), (got, want)


@pytest.mark.parametrize('on', [False, True])
def test_module_is_sys_modules_entry(plant, on):
    import sa_solver
    from satassume.theories.euf import euf_adapter
    sa_solver.EUFAdapter()                      # the name has given its module once
    marker = type('EUFTheory', (euf_adapter.EUFTheory,), {})
    fresh = types.ModuleType(EUF)
    fresh.__dict__.update(euf_adapter.__dict__)
    fresh.EUFTheory = marker
    plant('ad-module-swap' if on else None)
    sys.modules[EUF] = fresh
    try:
        th = sa_solver.EUFAdapter().theory
    finally:
        sys.modules[EUF] = euf_adapter
    assert (type(th) is marker) is (not on)
