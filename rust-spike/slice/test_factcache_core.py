"""Step 5c10a: the fact caches moved to Rust (factcache.rs: `Engine.cache.store`, `Engine.custom_cache.store`), Python against
Rust, each mode in its own process under one PYTHONHASHSEED.

- `shared:*`: two engines with the same settings sharing one `DictCache` (engine.py:98, the public use): the second engine's
  queries hit what the first put. The inventory's planted bug, a put lost on a shared DictCache (plant 200,
  `fc-shared-sync-is`), shows here only: one engine syncs with its own settings tuple every time.
- `engine:*`: queries on one engine, repeated and over several predicates of one node (`facts`, `put`, `is_many`); the stores'
  contents in insertion order and the hit counts.
- `get:*`, `bound:*`, `epoch:*`, `custom:*`: `get` with a default, a sized cache filled past `maxsize` (the harness's form,
  harness/state.py:83), a registry change (`sync` on a new epoch), a custom predicate's fact in `custom_cache`.
- `view:*`: the store read through the view as the tests read it (len, in, [], dict, set, items, values, ==).
- `clear:*`: the registry's clear (`Engine.memos.clear()`) and a settings change after a query (`_settings_changed`'s
  `store.clear()`).
- `rollback:*`: `_Mark`'s rollback (term_live.py) on a refused query, by the cache's own mark; Python's journal on Python.
Each plant must fire and move some case; the counters `fc:*` must fire on Rust, and both caches must be Rust's there.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLANTS = ('fc-shared-sync-is', 'fc-put-new-drop', 'fc-new-no-maxsize', 'fc-sync-no-clear', 'fc-facts-first',
          'fc-get-no-default', 'fc-no-bound', 'fc-custom-put-drop', 'fc-view-drop-last', 'fc-rollback-skip', 'fc-clear-skip')


def _main(mode):
    live = None
    if mode == 'rust':
        import test_discovery_core as D
        live = D._rust()
    from sympy import Symbol
    from satassume import DictCache, Engine
    from satassume.knowledge.extensions import extensions
    from satassume.sat.formula import Implies, Not, P
    from satassume.state.epoch import bump
    from memo_check import _canon
    cases = {}

    def rows(c):
        return [(_canon(k), sorted((p, repr(v)) for p, v in f.items())) for k, f in list(c.store.items())]

    x, y = Symbol('x', positive=True), Symbol('y', integer=True)
    z = Symbol('z')
    nodes = [x, y, x + y, x * y, x + 1, y**2, z]
    preds = ['positive', 'real', 'nonzero', 'integer', 'negative']

    # shared
    c = DictCache()
    a, b = Engine(cache=c), Engine(cache=c)
    ra = [a.is_(n, p) for n in nodes for p in preds]
    rb = [b.is_(n, p) for n in nodes for p in preds]
    cases['shared:answers'] = [repr(v) for v in ra + rb]
    cases['shared:hits'] = [a.stats['cache_hits'], b.stats['cache_hits'], b.stats['sessions']]
    cases['shared:store'] = rows(c)

    # engine
    e = Engine(cache=DictCache())
    r = [e.is_(n, p) for n in nodes for p in preds] + [e.is_(n, p) for n in nodes for p in preds]
    r += e.is_many(x * y + 1, preds) + e.is_many(x * y + 1, preds)
    cases['engine:answers'] = [repr(v) for v in r]
    cases['engine:hits'] = [e.stats['cache_hits'], e.stats['sessions']]
    cases['engine:store'] = rows(e.cache)
    cases['engine:facts'] = [sorted(e.cache.facts(n).items()) if e.cache.facts(n) is not None else None for n in nodes]

    # get
    cases['get'] = [repr(e.cache.get(x, 'positive', 'miss')), repr(e.cache.get(x, 'prime', 'miss')),
                    repr(e.cache.get(Symbol('w'), 'positive', 7)), repr(e.cache.get(Symbol('w'), 'positive'))]

    # bound
    small = DictCache(3)
    cases['bound:maxsize'] = small.maxsize
    lens = []
    for i in range(5):
        small.put(('n', i), 'positive', True)
        lens.append(len(small.store))
    cases['bound:lens'] = lens
    cases['bound:eq'] = repr(small.get(tuple(['n', len(lens) - 1]), 'positive', 'miss'))     # found by ==, not identity
    es = Engine(cache=DictCache(2))
    cases['bound:engine'] = [repr(es.is_(n, 'real')) for n in nodes] + [len(es.cache.store)]

    # epoch
    e2 = Engine(cache=DictCache())
    e2.is_(x, 'positive')
    before = len(e2.cache.store)
    bump()
    e2.is_(y, 'integer')
    cases['epoch'] = [before, rows(e2.cache), e2.stats['version_clears']]

    # custom
    def big(s):
        return [Implies(P('hbig', s), P('positive', s)), Implies(P('hbig', s), Not(P('integer', s)))]
    extensions.register('hbig', Symbol)(big)
    try:
        m = Symbol('m', negative=True)
        e3 = Engine(cache=DictCache())
        cases['custom'] = [repr(e3.is_(m, 'hbig')), repr(e3.is_(m, 'hbig')), e3.stats['cache_hits'], rows(e3.custom_cache),
                           repr(e3.custom_cache.get(m, 'hbig', 'miss'))]
    finally:
        extensions.unregister('hbig')

    # view
    s = e.cache.store
    cases['view'] = [len(s), bool(s), x in s, Symbol('w') in s, sorted(s[x].items()) if x in s else None, len(dict(s)),
                     sorted(map(_canon, set(s))), len(list(s.values())), s == dict(s), s != {}, repr(s.get(Symbol('w'), 'no'))]

    # clear
    e.memos.clear()
    cases['clear:memos'] = [len(e.cache.store), len(e.custom_cache.store)]
    e4 = Engine(cache=DictCache())
    e4.is_(x, 'positive')
    n4 = len(e4.cache.store)
    e4.transfer = not e4.transfer
    cases['clear:settings'] = [n4, len(e4.cache.store)]

    # rollback: a fault in a run that a query's mark covers (term_live._Mark), as on a refused query
    e5 = Engine(cache=DictCache())
    e5.is_(x, 'positive')
    want = rows(e5.cache)
    if mode == 'rust':
        import term_live
        mk = term_live._Mark(e5)
        e5.is_(x, 'real')
        e5.is_(y, 'integer')
        mk.rollback()
    cases['rollback'] = [rows(e5.cache) == want, len(e5.cache.store)]

    types = sorted({type(c).__module__ + '.' + type(c).__name__ for c in (e.cache, e.custom_cache, small)})
    json.dump(dict(cases=cases, types=types, counts=live.counts() if live else None), sys.stdout)


def _run(mode, **env):
    e = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]), PYTHONHASHSEED='0', **env)
    r = subprocess.run([sys.executable, __file__, mode], capture_output=True, text=True, env=e, cwd=HERE)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


@pytest.fixture(scope='module')
def both():
    return _run('py'), _run('rust')


def _differ(a, b):
    return sorted(k for k in a['cases'] if a['cases'][k] != b['cases'][k])


def test_same_as_python(both):
    py, rust = both
    assert _differ(py, rust) == []
    c = py['cases']
    assert c['shared:hits'][1] > 0 and c['engine:hits'][0] > 0
    assert c['bound:maxsize'] == 3 and c['bound:lens'][-1] < 5
    assert c['epoch'][0] == 1 and c['epoch'][2] == 1 and len(c['epoch'][1]) == 1
    assert c['custom'][2] == 1 and c['custom'][4] == 'False'
    assert c['clear:memos'] == [0, 0] and c['clear:settings'][0] == 1 and c['clear:settings'][1] == 0
    assert c['rollback'] == [True, 1]
    assert py['types'] == ['satassume.engine.DictCache'] and rust['types'] == ['sa_solver.DictCache']


def test_counters_fire(both):
    _, rust = both
    c = rust['counts']
    for k in ('fc:py_facts', 'fc:py_get', 'fc:py_put', 'fc:py_sync', 'fc:view', 'fc:clear', 'fc:full', 'fc:key_eq',
              'fc:rollback', 'fc:new'):
        assert c[k] > 0, k
    assert c['rel:plant_fired'] == 0


@pytest.mark.parametrize('plant', PLANTS)
def test_each_plant_fires_and_is_seen(both, plant):
    py, _ = both
    got = _run('rust', SLICE_SESSION_PLANT=plant)
    assert got['counts']['rel:plant_fired'] > 0
    assert _differ(py, got) != []


if __name__ == '__main__':
    _main(sys.argv[1])
