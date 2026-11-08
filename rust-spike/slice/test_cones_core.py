"""Step 5c10c: the cone rows in Rust (budget.rs: `_struct`, `_cone_info`, `_drop_cones`) and their containers Rust-native
(engmemo.rs slots 8-9: `_cones`, `_constructing`), Python against Rust, each mode in its own process under one PYTHONHASHSEED.

- `cert:*`: cert_wl's queries (in the repo) on one engine; then `_kids`, `_cones`, `_constructing` in insertion order
  (memo_check.engmemo_rows; `_constructing` sorted) and their sizes.
- `budget:*`: the same queries, three wide sums and loop_wl's first 80 (in the repo; vocabulary functions registered, so some
  nodes have both compiled patterns and formulas, weight 2) under a small `discovery_budget` (3, then 6, then the default), so cones go over it and `_cone_info`'s walk breaks
  early, meets known sub-cones that don't fit, and `_struct`'s wide-sum guard (#180 C-WIDEADD) runs on a wide sum (plants 224,
  225, 230); the answers, `last_budget_limited` after each query, and `_kids`' and `_cones`' rows.
- `settings:*`: a settings change between queries (`discovery_budget`): `_settings_changed` runs Rust's `_drop_cones`, which must
  empty `_kids`, `_cones`, `_qcones`, `_glue_adapters` (plant 226).
- `constructing:*`: `_constructing` empty after every query (the inventory's planted bug, plant 223: a node left in it), and a
  re-entrant query: a template evaluating a node asks the engine about that same node, and gets None (`is_` reads
  `node in self._constructing` through the view, a counted crossing until 5c10d).
- `bounds:*`: `_kids` at 200,000 entries and `_cones` at 100,000, filled through the views, are emptied by the next `_struct` /
  `_cone_info` miss. No workload reaches either bound (dev's largest `_kids` is in the hundreds), so these drive them (plants 228,
  229, test-only).
- `view:*`: Python's reads of the containers through their views (`is_`'s `_cones.get`, `_Mark`'s copy and restore of
  `_constructing`), and a test's write into `_cones`.
Each plant must fire and move some case; the counters `bud:struct`, `bud:cone_info`, `bud:drop_cones`, `bud:cb_templates`,
`bud:struct_wide`, `em:py_cones`, `em:py_constructing`, `em:full` must fire on Rust, `bud:cb_struct`/`bud:cb_cone_info` must
not (5c9c's crossing is gone), and both containers must be `EngineMemo`s there.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLANTS = ('cn-discard-skip', 'cone-struct-weight-one', 'cone-info-over-fits', 'cone-drop-skip-cones', 'em-cones-store-drop',
          'cone-kids-no-bound', 'cone-cones-no-bound', 'cone-struct-wide-skip')
NAMES = ('_kids', '_cones', '_qcones', '_glue_adapters', '_constructing')


def _main(mode):
    live = None
    if mode == 'rust':
        import test_discovery_core as D
        live = D._rust()
    from sympy import Add, Q, Symbol, symbols
    from satassume import sympy_api as A
    from satassume.engine import DictCache, Engine
    import cert_wl
    from memo_check import engmemo_rows
    cases = {}

    def sizes(e):
        return {n: len(getattr(e, n)) for n in NAMES}

    def rows(e):
        return [r for r in engmemo_rows(e) if r[0] in ('_kids', '_cones', '_constructing')]

    def run(e, qs, flag=False):
        out = []
        for p, a in qs:
            try:
                r = repr(A.ask(p, a, engine=e))
            except Exception as x:
                r = f'raise {type(x).__name__}'
            out.append((r, e.last_budget_limited) if flag else r)
            if len(e._constructing):
                out.append(('left', sorted(map(str, e._constructing))))
        return out

    qs = cert_wl.queries()
    xs = symbols('w0:9')
    wide = [(Q.positive(Add(*xs)), Q.positive(xs[0])), (Q.positive(Add(*xs[:5]) * xs[5]), None),
            (Q.nonnegative(Add(*[v ** 2 for v in xs])), None)]
    e = Engine(cache=DictCache())
    cases['cert:answers'] = run(e, qs)
    cases['cert:rows'] = rows(e)
    cases['cert:sizes'] = sizes(e)
    types = sorted({type(getattr(e, n)).__name__ for n in ('_cones', '_constructing')})

    import loop_wl
    lq = loop_wl.queries()      # registers vocabulary functions: nodes with both compiled patterns and formulas (weight 2)
    for b in (3, 6, None):
        e = Engine(cache=DictCache())
        if b is not None:
            e.discovery_budget = b
        cases[f'budget:{b}:answers'] = run(e, qs[:40] + wide + lq[:80], flag=True)
        cases[f'budget:{b}:rows'] = [r for r in engmemo_rows(e) if r[0] in ('_kids', '_cones')]

    e = Engine(cache=DictCache())
    run(e, qs[:20])
    before = sizes(e)
    e.discovery_budget = e.discovery_budget + 1
    cases['settings:budget'] = [before['_cones'] > 0, sizes(e)]
    cases['settings:rerun'] = run(e, qs[:20])

    x = Symbol('x')
    e = Engine(cache=DictCache())
    seen = []
    tpl = e.templates

    def templates(o):
        if o == x + 1:
            seen.append(repr(e.is_(o, 'positive')))
        return tpl(o)
    e.templates = templates
    cases['constructing:reentrant'] = run(e, [(Q.positive(x + 1), Q.positive(x)), (Q.negative(x + 1), Q.positive(x))])
    cases['constructing:seen'] = seen[:3]
    cases['constructing:after'] = len(e._constructing)

    e = Engine(cache=DictCache())
    for i in range(200_000):
        e._kids[('k', i)] = (set(), 1)
    e._struct(x + 2)
    cases['bounds:kids'] = len(e._kids)
    for i in range(100_000):
        e._cones[('c', i)] = (frozenset(), 1, False)
    e._cone_info(x + 3)
    cases['bounds:cones'] = len(e._cones)

    from term_live import _Mark
    e = Engine(cache=DictCache())
    run(e, qs[:5])
    node = qs[0][0].args[0] if qs[0][0].args else x
    cases['view:cones_get'] = repr(e._cones.get(node) is not None)
    e._constructing.add(x)
    m = _Mark(e)
    e._constructing.discard(x)
    e._constructing.add(x + 7)
    m.rollback()
    cases['view:mark'] = sorted(map(str, e._constructing))
    e._constructing.discard(x)
    e._cones[x + 9] = (None, 99, False)
    cases['view:cones_write'] = [repr(e._cone_info(x + 9)), repr(e.is_(x + 9, 'positive')), e.last_budget_limited]
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
    assert c['cert:sizes']['_cones'] > 0 and c['cert:sizes']['_constructing'] == 0
    assert c['settings:budget'][0] and c['settings:budget'][1]['_cones'] == 0 and c['settings:budget'][1]['_kids'] == 0
    assert c['constructing:seen'] and c['constructing:seen'][0] == 'None' and c['constructing:after'] == 0
    assert c['bounds:kids'] == 1 and c['bounds:cones'] == 1
    assert c['view:mark'] == ['x']
    assert any(lim for r in c['budget:3:answers'] if isinstance(r, list) for lim in r[1:])
    assert py['types'] == ['dict', 'set'] and rust['types'] == ['EngineMemo']


def test_counters_fire(both):
    _, rust = both
    c = rust['counts']
    for k in ('bud:struct', 'bud:cone_info', 'bud:drop_cones', 'bud:cb_templates', 'bud:struct_wide', 'bud:kids_hit',
              'bud:cones_hit', 'em:py_cones', 'em:py_constructing', 'em:full'):
        assert c.get(k, 0) > 0, k
    for k in ('bud:cb_struct', 'bud:cb_cone_info'):
        assert c.get(k, 0) == 0, k
    assert c['rel:plant_fired'] == 0


@pytest.mark.parametrize('plant', PLANTS)
def test_each_plant_fires_and_is_seen(both, plant):
    py, _ = both
    got = _run('rust', SLICE_SESSION_PLANT=plant)
    assert got['counts']['rel:plant_fired'] > 0
    assert _differ(py, got) != []


if __name__ == '__main__':
    _main(sys.argv[1])
