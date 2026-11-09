"""Step 5c10d: the query-entry rows in Rust (entry.rs: `is_`, `is_many`, `_decide`, `_put_result`, `_is_custom`, `ask`, `_ask`,
`_check_version`, `_settings_changed`, `_drop_set_memos`, `_fresh_session`; budget.rs `_over_budget`, `_note_budget`) and
`Engine.stats` / `Engine.last_budget_limited` Rust-owned (`EngineStats`), Python against Rust, each mode in its own process
under one PYTHONHASHSEED.
- `wl:cert:*`, `wl:budget:*`: cert_wl's and budget_wl's queries (in the repo) on one engine through `sympy_api.ask`; after each
  query the answer, `list(engine.stats.items())` and `engine.last_budget_limited` (the read-only view pinned equal to Python's
  value after each query; budget_wl puts queries over the budget, so the flag is True after some and False after others).
- `many:*`: `is_many` on a fresh engine and again on the warm one (cache hits, a predicate by definition, a non-commutative term).
- `settings:*`, `epoch:*`: a settings change and a registry epoch bump between queries (`_settings_changed`, `_check_version`,
  `_drop_set_memos`): the counters, the answer memo's and fact caches' sizes after each.
- `writes:*`: Python's sequence of writes through the record methods (sympy_api's and the scope-miss sites'), 400 steps from a
  seeded random choice, the state after each: the same on Python's dict and on Rust's `EngineStats` (the planner's test that
  Python's sequence of writes gives the same state as before).
- `view:*`: the view's read forms the tests use (`[k]`, `get`, `in`, `dict(...)`, `==`, `len`, iteration); on Rust a write
  through the view raises, and the test-only export (`st_snapshot`, read in Rust) equals the view after every query.
Each plant (relations_core.rs 231-250) must fire, and each one this file reaches must move a case; the ones it doesn't reach are
named in `ELSEWHERE` with where they're caught.
"""
import json
import os
import random
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLANTS = ('ent-is-no-hit-count', 'ent-is-many-queries-short', 'ent-decide-no-escalate', 'ent-put-result-no-put',
          'ent-is-custom-no-hit', 'ent-ask-no-clear-flag', 'ent-ask-no-gave-up', 'ent-check-version-no-sync',
          'ent-settings-no-clear', 'ent-drop-memos-keep-answers', 'ent-fresh-no-count', 'st-cache-hit-drop',
          'st-relevant-drop', 'st-consistency-drop', 'st-scope-miss-double', 'st-clear-flag-skip', 'st-keep-flag-drop',
          'st-view-order', 'st-flag-view-stale', 'note-budget-count', 'over-budget-no-flag')
#: plants this file doesn't reach or doesn't move, with where they're caught (none since `split`, `custom`, `gave_up`,
#: `shared` and `flag` were added; see port-5c10d.md)
ELSEWHERE = {}


def _main(mode):
    live = None
    if mode == 'rust':
        import test_discovery_core as D
        live = D._rust()
    from sympy import Q, Symbol, symbols
    from satassume import sympy_api as A
    from satassume.engine import Engine
    from satassume.state import epoch
    import budget_wl
    import cert_wl
    snap = None
    if live is not None:
        import sa_solver
        snap = sa_solver.st_snapshot
    cases = {}
    bad_snap = []

    def state(e):
        if snap is not None:
            s = snap(e)
            if s is None or s[0] != dict(e.stats) or s[1] != e.last_budget_limited:
                bad_snap.append(1)
        return [list(e.stats.items()), e.last_budget_limited]

    def run(e, qs):
        out = []
        for p, a in qs:
            try:
                r = repr(A.ask(p, a, engine=e))
            except Exception as x:
                r = type(x).__name__
            out.append([r] + state(e))
        return out

    for name, qs in (('cert', cert_wl.queries()), ('budget', budget_wl.queries())):
        e = Engine()
        cases[f'wl:{name}'] = run(e, qs)
        cases[f'wl:{name}:again'] = run(e, qs[:40])
        cases[f'wl:{name}:sizes'] = [len(e.answers), len(e.cache.store)]

    x, y = symbols('x y', positive=True)
    z = Symbol('z')
    A_ = Symbol('A', commutative=False)
    preds = ['positive', 'real', 'commutative', 'finite', 'zero', 'integer']
    e = Engine()
    out = []
    for t in (x, x + y, z, z ** 2 + 1, A_, x * A_):
        out.append([repr(e.is_many(t, preds))] + state(e))
        out.append([repr(e.is_many(t, preds))] + state(e))
        out.append([repr(e.is_(t, 'nonnegative'))] + state(e))
    cases['many'] = out

    e = Engine()
    out = run(e, [(Q.positive(x + 1), True), (Q.positive(z), Q.positive(z ** 2) & Q.real(z))])
    e.discovery_budget = 50
    out.append(state(e) + [len(e.answers), len(e.cache.store)])
    out += run(e, [(Q.positive(x + 1), True), (Q.positive(z), Q.positive(z ** 2) & Q.real(z))])
    e.discovery_budget = 400
    out.append(state(e) + [len(e.answers), len(e.cache.store)])
    cases['settings'] = out
    out = run(e, [(Q.nonnegative(z ** 2), Q.real(z))])
    epoch.bump()
    out += run(e, [(Q.nonnegative(z ** 2), Q.real(z)), (Q.positive(x + 1), True)])
    out.append(state(e) + [len(e.answers), len(e.cache.store)])
    cases['epoch'] = out

    # a split set (`_consistent` per part, and the whole set's verdict under a relation): consistency_checks
    w = Symbol('w')
    e = Engine()
    cases['split'] = run(e, [(Q.positive(z), Q.positive(z) & Q.negative(w)),
                             (Q.real(w), Q.positive(z) & Q.negative(w) & Q.gt(z, w)),
                             (Q.positive(z + 1), Q.positive(z) & Q.real(w))])
    # a custom predicate (`_is_custom`, custom_cache hits), as test_extensibility's first test
    from satassume import DictCache, Extensions, P
    from sympy import Function, sqrt
    ext = Extensions()

    @ext.register('mine', str)
    def _(node):
        return True if node == 'x' else None
    e = Engine(templates=lambda n: [], cache=DictCache(), extensions=ext)
    cases['custom'] = [[repr(e.is_(n, 'mine'))] + state(e) for n in ('x', 'y', 'x', 'y')]
    # a contextual query whose LRA gives up (theory_gave_up), as test_lra_constant_coefficients' hidden equality
    f = Function('f')
    a = Q.eq(z, (1 + sqrt(2)) ** 2) & Q.eq(z, 3 + 2 * sqrt(2)) & Q.positive(f(3 + 2 * sqrt(2)))
    e = Engine(cache=DictCache())
    cases['gave_up'] = run(e, [(Q.positive(f((1 + sqrt(2)) ** 2)), a), (Q.real(z), a)])
    # one DictCache shared by two engines with different settings (`_check_version`'s sync empties it)
    c = DictCache()
    e1, e2 = Engine(cache=c), Engine(cache=c, transfer=False)
    cases['shared'] = [[repr(e.is_(x + y, 'positive')), repr(e.is_(x, 'real')), len(c.store)] + state(e)
                       for e in (e1, e2, e1, e2)]
    # `Engine.ask` called directly: over the budget, then a non-commutative atom (the early return before
    # `_note_budget`; sympy_api clears the flag itself, so only a direct call shows `ask`'s own clear)
    from satassume.sympy_api import _formula
    e = Engine()
    e.discovery_budget = 1
    out = [[repr(e.ask(_formula(Q.positive(x * y + z ** 2 + 1), False, True)))] + state(e)]
    out += [[repr(e.ask(P(p, A_)))] + state(e) for p in ('positive', 'real')]
    cases['flag'] = out

    e = Engine()
    rnd = random.Random(5)
    steps = [lambda: e._record_cache_hit(), lambda: e._record_relevant(), lambda: e._record_consistency_check(),
             lambda: e._record_scope_miss(), lambda: e._clear_budget_flag(), lambda: e._keep_budget_flag(True),
             lambda: e._keep_budget_flag(False), lambda: e._over_budget()]
    out = []
    for _ in range(400):
        steps[rnd.randrange(len(steps))]()
        out.append(state(e))
    cases['writes'] = out

    e = Engine()
    A.ask(Q.positive(x + 1), True, engine=e)
    s = e.stats
    cases['view'] = [s['queries'], s.get('sessions'), s.get('nope', 7), 'queries' in s, 'nope' in s, dict(s), s == dict(s),
                     len(s), list(s), sorted(s.keys()), list(s.values()), e.last_budget_limited]
    try:
        e.stats['queries'] = 0
        cases['view:write'] = 'wrote'
    except TypeError:
        cases['view:write'] = 'raised'
    types = [type(e.stats).__name__, type(e.last_budget_limited).__name__]
    json.dump(dict(cases=cases, types=types, bad_snap=len(bad_snap), counts=live.counts() if live else None), sys.stdout)


def _run(mode, **env):
    e = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]), PYTHONHASHSEED='0', **env)
    r = subprocess.run([sys.executable, __file__, mode], capture_output=True, text=True, env=e, cwd=HERE)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


@pytest.fixture(scope='module')
def both():
    return _run('py'), _run('rust')


def _differ(a, b, skip=('view:write',)):
    return sorted(k for k in a['cases'] if k not in skip and a['cases'][k] != b['cases'][k])


def test_same_as_python(both):
    py, rust = both
    assert _differ(py, rust) == []
    assert py['cases']['view:write'] == 'wrote' and rust['cases']['view:write'] == 'raised'
    assert py['types'] == ['dict', 'bool'] and rust['types'] == ['EngineStats', 'bool']
    assert rust['bad_snap'] == 0
    c = py['cases']
    assert any(r[2] for r in c['wl:budget']) and not all(r[2] for r in c['wl:budget'])     # the flag both ways
    assert c['settings'][2][0][8][1] > 0 or c['epoch'][-1][0][8][1] > 0                    # version_clears


def test_counters_fire(both):
    _, rust = both
    c = rust['counts']
    for k in ('ent:is', 'ent:is_many', 'ent:decide', 'ent:put_result', 'ent:ask', 'ent:ask_inner', 'ent:check_version',
              'ent:settings_changed', 'ent:drop_set_memos', 'ent:fresh_session', 'ent:cb_noncomm', 'ent:cb_scope',
              'ent:cb_basis', 'ent:cb_gave_up', 'st:rec_cache_hit', 'st:rec_relevant', 'st:rec_consistency_check',
              'st:rec_scope_miss', 'st:rec_clear_flag', 'st:rec_keep_flag', 'st:py_read', 'st:slot_set', 'st:flag_set',
              'bud:over_budget', 'bud:note_budget'):
        assert c.get(k, 0) > 0, k
    assert c['rel:plant_fired'] == 0


@pytest.mark.parametrize('plant', PLANTS)
def test_each_plant_fires_and_is_seen(both, plant):
    py, _ = both
    got = _run('rust', SLICE_SESSION_PLANT=plant)
    fired, moved = got['counts']['rel:plant_fired'] > 0, _differ(py, got) != []
    if plant in ELSEWHERE:
        assert not (fired and moved), f'{plant} is caught here now: take it out of ELSEWHERE'
        pytest.skip(ELSEWHERE[plant])
    assert fired
    assert moved


if __name__ == '__main__':
    _main(sys.argv[1])
