"""Step 5c9c: the engine memos moved to Rust (engmemo.rs: `_kids`, `_qcones`, `_glue_adapters`, `_xbasis`, `splits`), Python
against Rust, each mode in its own process under one PYTHONHASHSEED.

- `cert:*`: cert_wl's queries (in the repo) on one engine; then the five memos' contents in insertion order
  (memo_check.engmemo_rows), and their sizes.
- `settings:*`: a settings change between queries (`discovery_budget`, then `transfer`): `_settings_changed` runs Python's
  `_drop_cones` and `_drop_set_memos`, which must empty the memos through their views. The inventory's planted bug (plant 190,
  `em-qcones-clear-skip`: `_drop_cones` not clearing `_qcones`) shows here.
- `xbasis:*`: tests/test_memos.py's `_xbasis` scenario (number bases, a test's write `e._xbasis[S(5)] = ...`, the registry's
  clear), and a second number so a hit isn't on the first entry (plant 193).
- `sums:*`: sign atoms over sums, so `_query_cone`'s `sums` is non-empty (plant 195).
- `kids:*`: a test's write into `_kids` (tests/test_writeback_provenance.py:453's form), read back through the view and by
  Python's `_cone_info`.
- `splits:*`: the harness's assignment `eng.splits = AnswerMemo(n)` (harness/state.py:91) with a small `n`, so `maxsize`
  must survive the assignment (plant 197) and the bound must empty the memo (plant 194); `relevant`'s `put` (plant 198).
Each plant must fire and move some case; the counters `em:slot_set`, `em:full`, `em:py_*` and `bud:query_cone` must fire on
Rust, and every memo must be an `EngineMemo` there.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLANTS = ('em-qcones-clear-skip', 'em-kids-set-drop', 'em-glue-no-store', 'em-xbasis-first', 'em-splits-no-bound',
          'em-qcone-no-sums', 'em-qcone-key-f', 'em-slot-no-maxsize', 'em-splits-put-drop')
NAMES = ('_kids', '_qcones', '_glue_adapters', '_xbasis', 'splits')


def _main(mode):
    live = None
    if mode == 'rust':
        import test_discovery_core as D
        live = D._rust()
    from sympy import Q, S, Symbol
    from satassume import sympy_api as A
    from satassume.engine import AnswerMemo, Engine
    from satassume.engine import DictCache
    import cert_wl
    from memo_check import engmemo_rows
    cases = {}

    def sizes(e):
        return {n: len(getattr(e, n)) for n in NAMES}

    def run(e, qs):
        out = []
        for p, a in qs:
            try:
                out.append(repr(A.ask(p, a, engine=e)))
            except Exception as x:
                out.append(f'raise {type(x).__name__}')
        return out

    qs = cert_wl.queries()
    e = Engine(cache=DictCache())
    cases['cert:answers'] = run(e, qs)
    cases['cert:rows'] = engmemo_rows(e)
    cases['cert:sizes'] = sizes(e)
    types = sorted({type(getattr(e, n)).__name__ for n in NAMES})

    e.discovery_budget = e.discovery_budget + 1
    cases['settings:budget'] = sizes(e)
    cases['settings:rerun'] = run(e, qs)
    cases['settings:rerun_sizes'] = sizes(e)
    e.transfer = not e.transfer
    cases['settings:transfer'] = sizes(e)
    cases['settings:rerun2'] = run(e, qs[:30])
    cases['settings:rows2'] = engmemo_rows(e)

    x, y = Symbol('x'), Symbol('y')
    e = Engine(cache=DictCache())
    xq = [(Q.prime(x), Q.eq(x, 4)), (Q.even(y), Q.eq(y, 6)), (Q.composite(x), Q.eq(x, 6)), (Q.prime(y), Q.eq(y, 4)),
          (Q.odd(x), Q.eq(x, 9)), (Q.composite(y), Q.eq(y, 9)), (Q.prime(x), Q.eq(x, 6)),
          (Q.even(x), Q.eq(x, 9)), (Q.odd(y), Q.eq(y, 9))]
    cases['xbasis:answers'] = run(e, xq)
    cases['xbasis:keys'] = [str(k) for k in e._xbasis]
    cases['xbasis:rows'] = engmemo_rows(e)[3]
    e._xbasis[S(5)] = 'stale'
    cases['xbasis:stale'] = [S(5) in e._xbasis, e._xbasis.get(S(5)), len(e._xbasis)]
    e.memos.clear()
    cases['xbasis:cleared'] = sizes(e)

    e = Engine(cache=DictCache())
    sq = [(Q.positive(x + y), Q.positive(x) & Q.positive(y)), (Q.negative(x - y), Q.lt(x, y)),
          (Q.nonnegative(x + 1), Q.positive(x)), (Q.positive(x * y + x), Q.positive(x) & Q.positive(y))]
    cases['sums:answers'] = run(e, sq)
    cases['sums:qcones'] = engmemo_rows(e)[1]

    e = Engine(cache=DictCache())
    e._kids[('r',)] = (frozenset(), 1)
    cases['kids:write'] = [('r',) in e._kids, repr(e._kids.get(('r',))), len(e._kids), repr(e._cone_info(('r',)))]

    e = Engine(cache=DictCache())
    e.splits = AnswerMemo(4)
    cases['splits:maxsize'] = e.splits.maxsize
    lens = []
    for i in range(6):
        s = Symbol(f's{i}')
        A._relevant(Q.positive(s), Q.positive(s) & Q.integer(Symbol(f't{i}')), e)
        lens.append(len(e.splits))
    cases['splits:lens'] = lens
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
    assert c['settings:budget']['_qcones'] == 0 and c['settings:budget']['_kids'] == 0
    assert c['settings:transfer']['_xbasis'] == 0 and c['settings:transfer']['splits'] == 0
    assert c['cert:sizes']['_qcones'] > 0 and c['cert:sizes']['splits'] > 0 and c['cert:sizes']['_glue_adapters'] > 0
    assert c['xbasis:keys'] and c['xbasis:stale'][0] and c['xbasis:cleared']['_xbasis'] == 0
    assert c['splits:maxsize'] == 4 and c['splits:lens'][-1] < 6
    assert py['types'] == ['AnswerMemo', 'dict'] and rust['types'] == ['EngineMemo']


def test_counters_fire(both):
    _, rust = both
    c = rust['counts']
    for k in ('em:slot_set', 'em:full', 'em:py_kids', 'em:py_qcones', 'em:py_glue', 'em:py_xbasis', 'em:py_splits',
              'bud:query_cone'):
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
