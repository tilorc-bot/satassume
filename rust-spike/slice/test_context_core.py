"""Step 5c10b: the context rows in Rust (context.rs: `_context_session`, `_build_context_memoized`, `_build_context`, `verdict`,
`_complete_check`) and their containers Rust-native (engmemo.rs slots 5-7: `_failed`, `_verdict`, `_context_sessions`), Python
against Rust, each mode in its own process under one PYTHONHASHSEED.

- `cert:*`: cert_wl's queries on one engine; then `_verdict`'s and `_failed`'s rows in insertion order, sizes, `set_checks`.
- `verdict:*`: `Engine.verdict` on consistent, inconsistent, over-budget and non-commutative sets, asked twice (the memo).
- `settings:*`: a settings change between queries (`discovery_budget`, then `transfer`): `_drop_set_memos` must empty
  `_verdict` and `_failed` through their views. The inventory's planted bug (plant 211, `ctx-verdict-clear-skip`: `_verdict`
  kept across a settings change) shows here.
- `failed:*`: an assumption no theory interprets under uninterpreted="none" (`Q.lt(x, I*x)`), so `_failed` fills and hits.
- `inconsistent:*`: an inconsistent set raises for every query and is checked once.
- `gaveup:*`: tests/test_lra_constant_coefficients.py's hidden algebraic equality: LRA gives up in the set's check.
- `link:*`: relational sets under relational queries (`link_set`'s links).
- `exhaust:*`: tests/test_lra_exhaustion.py's integer branch-and-bound queries, so `_complete_check` sees an exhausted theory.
Each plant must fire and move some case; every `ctx:*` and `em:py_failed`/`em:py_verdict`/`em:py_ctxs` counter must fire on
Rust, and the three containers must be `EngineMemo`s there.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLANTS = ('ctx-verdict-clear-skip', 'ctx-failed-clear-skip', 'ctx-failed-no-memo', 'ctx-verdict-no-bound',
          'ctx-session-inconsistent-pass', 'ctx-build-no-fallback', 'ctx-build-no-link', 'ctx-verdict-skip-budget',
          'ctx-check-no-escalate', 'ctx-check-no-truncated', 'ctx-check-raise', 'ctx-sessions-store')
#: Plants this test can't move, with the reason (each named in the report).
VOID_HERE = {
    'ctx-verdict-no-bound': 'needs 20,000 distinct sets on one engine; no workload or test has that many',
    'ctx-build-no-fallback': 'the gave-up session answered as the plain one on every case tried (gaveup:*); the bar decides',
    'ctx-build-no-link': 'link:* and cert answers unchanged without link_set; the bar decides',
}
NAMES = ('_failed', '_verdict', '_context_sessions')


def _rows(e, n):
    return [(str(k), str(v)) for k, v in getattr(e, n).items()]


def _main(mode):
    live = None
    if mode == 'rust':
        import test_discovery_core as D
        live = D._rust()
    from sympy import I, Q, Symbol, Function
    f = Function('f')
    from satassume import sympy_api as A
    from satassume.engine import DictCache, Engine
    import cert_wl
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

    def state(e):
        return dict(sizes=sizes(e), verdict=_rows(e, '_verdict'), failed=_rows(e, '_failed'), checks=e.stats['set_checks'])

    qs = cert_wl.queries()
    e = Engine(cache=DictCache())
    cases['cert:answers'] = run(e, qs)
    cases['cert:state'] = state(e)
    types = sorted({type(getattr(e, n)).__name__ for n in NAMES})

    x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
    nx, ny = Symbol('nx', commutative=False), Symbol('ny', commutative=False)
    sets = [Q.positive(x) & Q.negative(y), Q.positive(x) & Q.negative(x), Q.lt(x, y) & Q.lt(y, z) & Q.lt(z, x),
            Q.integer(x) & Q.gt(2 * x, 1) & Q.lt(2 * x, 3), Q.positive(nx * ny), Q.positive(x + y + z) & Q.negative(x)]
    e = Engine(cache=DictCache())
    for rnd in range(2):
        out = []
        for a in sets:
            try:
                out.append(e.verdict(A._formula(a, True, True)))
            except Exception as x_:
                out.append(f'raise {type(x_).__name__}')
        cases[f'verdict:{rnd}'] = out
    cases['verdict:state'] = state(e)
    e = Engine(cache=DictCache(), discovery_budget=3)
    cases['verdict:budget'] = [e.verdict(A._formula(a, True, True)) for a in sets[:4] + sets[5:]]
    cases['verdict:budget_state'] = state(e)

    e = Engine(cache=DictCache())
    run(e, qs[:40])
    cases['settings:before'] = sizes(e)
    e.discovery_budget = e.discovery_budget + 1
    cases['settings:budget'] = sizes(e)
    cases['settings:rerun'] = run(e, qs[:40])
    e.transfer = not e.transfer
    cases['settings:transfer'] = sizes(e)
    cases['settings:rerun2'] = run(e, qs[:20])
    cases['settings:state'] = state(e)

    e = Engine(cache=DictCache(), uninterpreted="none")
    fq = [(Q.real(x), Q.lt(x, I * x)), (Q.negative(x), Q.lt(x, I * x)), (Q.zero(x), Q.lt(x, I * x)),
          (Q.negative(x), Q.positive(x) & Q.lt(x, I * x)), (Q.real(f(x)) | Q.lt(x, I * x), Q.positive(x))]
    cases['failed:answers'] = run(e, fq)
    cases['failed:state'] = state(e)
    fa = A._formula(Q.lt(x, I * x), True, True)
    cases['failed:direct'] = []
    for _ in range(2):
        try:
            e._context_session(fa)
            cases['failed:direct'].append('built')
        except Exception as x_:
            cases['failed:direct'].append(f'raise {type(x_).__name__}')
    e.memos.clear()
    cases['failed:cleared'] = sizes(e)

    e = Engine(cache=DictCache())
    a = Q.positive(x) & Q.negative(x)
    cases['inconsistent:answers'] = run(e, [(Q.real(x), a), (Q.zero(x), a), (Q.real(x), a)])
    cases['inconsistent:state'] = state(e)
    e = Engine(cache=DictCache())
    try:
        s_, lits = e._context_session(A._formula(a, True, True), A._formula(Q.real(x), True))
        cases['inconsistent:direct'] = ['built', s_.verdict]
    except Exception as x_:
        cases['inconsistent:direct'] = [f'raise {type(x_).__name__}']

    e = Engine(cache=DictCache())
    u = [Symbol(f'u{i}', integer=True) for i in range(3)]
    xq = [(Q.ge(u[0], 4), Q.gt(u[0], 1) & Q.lt(3 * u[0], 3 * u[1] + 2) & Q.lt(u[1], u[2]) & Q.lt(2 * u[2], 2 * u[0] + 1)),
          (Q.ge(u[0], 2), Q.gt(7 * u[0], 3 * u[1] + 1) & Q.lt(7 * u[0], 3 * u[1] + 3)),
          (Q.positive(u[0]), Q.gt(5 * u[0] + 3 * u[1], 1) & Q.lt(5 * u[0] + 3 * u[1], 2))]
    cases['exhaust:answers'] = run(e, xq)
    cases['exhaust:state'] = state(e)
    from sympy import sqrt
    e = Engine(cache=DictCache())
    ga = Q.eq(x, (1 + sqrt(2)) ** 2) & Q.eq(x, 3 + 2 * sqrt(2)) & Q.positive(f(3 + 2 * sqrt(2)))
    cases['gaveup:answers'] = run(e, [(Q.positive(f((1 + sqrt(2)) ** 2)), ga), (Q.real(x), ga), (Q.positive(x), ga)])
    cases['gaveup:state'] = state(e)
    e = Engine(cache=DictCache())
    lq = [(Q.gt(x + y, 0), Q.gt(x, 0) & Q.gt(y, 0)), (Q.lt(x, z), Q.lt(x, y) & Q.lt(y, z)),
          (Q.positive(x * y), Q.gt(x, 1) & Q.gt(y, 1)), (Q.gt(f(x), 0), Q.eq(f(x), y) & Q.gt(y, 2)),
          (Q.positive(f(x) - f(y)), Q.eq(x, y) & Q.positive(f(x)))]
    cases['link:answers'] = run(e, lq)
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
    assert c['settings:before']['_verdict'] > 0 and c['settings:budget']['_verdict'] == 0
    assert c['failed:state']['sizes']['_failed'] > 0 and c['failed:cleared']['_failed'] == 0
    assert c['inconsistent:state']['checks'] == 1
    assert all(s['_context_sessions'] == 0 for s in (c['cert:state']['sizes'], c['verdict:state']['sizes']))
    assert py['types'] == ['OrderedDict', 'dict'] and rust['types'] == ['EngineMemo']


def test_counters_fire(both):
    _, rust = both
    c = rust['counts']
    for k in ('em:py_failed', 'em:py_verdict', 'em:py_ctxs', 'ctx:context_session', 'ctx:build_memoized', 'ctx:build_context',
              'ctx:verdict', 'ctx:complete_check', 'ctx:cb_check_version', 'ctx:cb_fresh_session',
              'ctx:py_stats', 'ctx:failed_hit', 'ctx:verdict_hit', 'ctx:fallback'):
        assert c[k] > 0, k
    # `_noncommutative_atoms` is native since B's item 2 (entry.rs `noncommutative_atoms`): no helper callback is left
    assert c['ctx:cb_helpers'] == 0
    assert c['rel:plant_fired'] == 0


def test_caught_fires_on_a_planted_raise(both):
    """FALSE ZEROS: `ctx:caught` (engine.py:1906's handler, now in context.rs) is 0 unplanted and fires on plant 221."""
    _, rust = both
    assert rust['counts']['ctx:caught'] == 0
    got = _run('rust', SLICE_SESSION_PLANT='ctx-check-raise')
    assert got['counts']['ctx:caught'] > 0


@pytest.mark.parametrize('plant', PLANTS)
def test_each_plant_fires_and_is_seen(both, plant):
    py, _ = both
    got = _run('rust', SLICE_SESSION_PLANT=plant)
    if plant in VOID_HERE:
        pytest.skip(VOID_HERE[plant])
    assert got['counts']['rel:plant_fired'] > 0
    assert _differ(py, got) != []


if __name__ == '__main__':
    _main(sys.argv[1])
