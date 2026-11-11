"""Convert once (formula step, gate item 1; rulings H1 and H2): an entry holds a `Hand` (formula.rs) and every formula it
is given, and every fact a user's handler returns, is converted at most once inside that entry's call; nothing a `Hand`
holds outlives the call. One process per run, on Rust, the same queries each time:
- `split`: sets that relevance splits (`rv_relevant` -> `_consistent` -> `verdict`, then `Engine.ask`);
- `ext`: a custom predicate whose handler returns a formula fact, the same object on every call (`same`) or a new, equal
  object on every call (`fresh`): H1's case. The handler reads `formula_held()` when it runs, inside the entry.
- `is`: `Engine.is_` and `is_many` on nodes whose cone has facts (the entry reads the cone before its session exists).
- `again`: the first queries once more on a new engine, with the same formula objects (sympy_api's `_formula` memo).
- `instr`: the `split` queries and the `over` query with catch_count installed over `Engine.verdict`. It registers its wrapper
  (session_live.py `INSTRUMENTS`), so Rust still calls its own `verdict` directly with the entry's nodes, and the
  instrument still gets the exception of a planted raise (`caught`).
- `patched`: the `split` queries, and one over the budget with a set inside it (`patched:over`), with a user's own
  `Engine.verdict` on the class, which counts its calls and answers as the one it replaced: called by name, the entry
  behind it has its own `Hand`, and what that converts again is `fm:twice:patched`, not `fm:twice`. `patched:no`: a
  replaced `verdict` that says INCONSISTENT, and the ask raises; `over`: the same query with nothing replaced.
After each query: the answer, the change of `fm:convert`, `fm:twice`, `fm:nosession`, `fm:give`, and `formula_held()`.
Plant 607 `fm-hand-no-give`: the entry hands the session nothing, the session converts again: `fm:twice` above 0.
Plant 608 `fm-hand-kept`: an entry's nodes answer the next entry (a `Hand` reused across queries): something is held
between queries and the repeated queries convert less.
Plant 609 `fm-hand-instrument-by-name`: the registered wrapper is called by name again: `fm:twice:patched` above 0 in `instr`.
Plant 610 `fm-hand-patched-direct`: the user's `verdict` is passed over: it gets no call and its answer isn't used.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ('fm:convert', 'fm:twice', 'fm:twice:patched', 'fm:nosession', 'fm:give', 'fm:plant_fired')


def _main(plant):
    import test_discovery_core as D
    D._rust()
    import sa_solver
    from sympy import Q, Symbol
    from satassume import DictCache, Extensions, P, sympy_api as A
    from satassume.engine import Engine
    from satassume.sat.formula import Implies, Not
    if plant != 'none':
        sa_solver.formula_plant(plant)
    rows = []

    def step(group, f):
        c0 = sa_solver.formula_counts()
        try:
            r = repr(f())
        except Exception as x:
            r = type(x).__name__
        c1 = sa_solver.formula_counts()
        rows.append(dict(group=group, answer=r, held=sa_solver.formula_held(), **{k: c1[k] - c0[k] for k in KEYS}))

    z, w = Symbol('z'), Symbol('w')
    split = [(Q.positive(z), Q.positive(z) & Q.negative(w)),
             (Q.real(w), Q.positive(z) & Q.negative(w) & Q.gt(z, w)),
             (Q.positive(z + 1), Q.positive(z) & Q.real(w)),
             (Q.nonzero(z * w), Q.positive(z) & Q.negative(w) & Q.lt(w, z))]
    e = Engine()
    for p, a in split:
        step('split', lambda: A.ask(p, a, engine=e))

    inside, calls = [], {'same': 0, 'fresh': 0}
    for kind in ('same', 'fresh'):
        ext = Extensions()
        kept = {}

        @ext.register('mine', str)
        def _(node):
            return True if node == 'x' else None

        @ext.register('twice', tuple)
        def _(node, kind=kind, kept=kept):
            calls[kind] += 1
            inside.append(sa_solver.formula_held())
            if node[0] != 'add':
                return None
            if kind == 'same':
                return kept.setdefault(node, Implies(P('mine', node[1]), P('twice', node)))
            return Implies(P('mine', node[1]), P('twice', node))
        eng = Engine(templates=lambda n: [], cache=DictCache(), extensions=ext)
        qs = [(P('twice', ('add', 'y', 'y')), P('mine', 'y')), (Not(P('twice', ('add', 'y', 'y'))), P('mine', 'y')),
              (P('twice', ('add', 'x', 'y')), P('twice', ('add', 'y', 'x')))]
        for p, a in qs:
            step('ext:' + kind, lambda: eng.ask(p, a))
        step('ext:' + kind, lambda: eng.is_(('add', 'x', 'y'), 'twice'))

    # `Engine.is_` and `is_many`: the cone's facts are converted by the entry before its session exists (budget.rs
    # `cone_info`), and the session's discovery reads the same objects (compile_loop.rs `visit`)
    from sympy import I, asin, sqrt
    e = Engine()
    for q in (Q.zero(sqrt(I)), Q.finite(asin(-3)), Q.positive(sqrt(I) + 1)):
        step('is', lambda: A.ask(q, engine=e))
    e = Engine()
    step('is', lambda: e.is_many(sqrt(I), ['zero', 'finite', 'real']))

    e = Engine()
    for p, a in split:
        step('again', lambda: A.ask(p, a, engine=e))

    # a query over the budget with a set inside it: `Engine.ask` reads the set for the budget, then asks its verdict
    heavy = P('positive', ('add', ('add', ('add', 'x', 'y'), ('add', 'z', 'w')), ('add', 'u', 'v')))
    ok = P('positive', 'x')

    def over():
        from satassume import allargs
        eng = Engine(templates=lambda n: [Implies(allargs('positive', n[1:]), P('positive', n))] if isinstance(n, tuple) else [],
                     cache=DictCache(), discovery_budget=3)
        return eng.ask(heavy, ok)
    step('over', over)

    # an instrument over `verdict`: registered, so the path is the one without it
    import catch_count
    catch_count.install()
    e = Engine()
    for p, a in split:
        step('instr', lambda: A.ask(p, a, engine=e))
    step('instr:over', over)
    memoized = Engine.__dict__['_build_context_memoized']

    def boom(self, assumptions, proposition=None):
        raise RuntimeError('planted')
    Engine._build_context_memoized = boom
    before = len(catch_count.sink)
    try:
        step('instr:raise', lambda: A._consistent(split[1][1], Engine()))
    finally:
        Engine._build_context_memoized = memoized
    caught = [x[0] for x in catch_count.sink[before:]]

    # a user's own `verdict`: called by name, and its answer is the one used
    from satassume.engine import INCONSISTENT
    real, mine = Engine.__dict__['verdict'], {'as_real': 0, 'no': 0}

    def as_real(self, assumptions):
        mine['as_real'] += 1
        return real(self, assumptions)

    def no(self, assumptions):
        mine['no'] += 1
        return INCONSISTENT
    try:
        Engine.verdict = as_real
        e = Engine()
        for p, a in split:
            step('patched', lambda: A.ask(p, a, engine=e))
        step('patched:over', over)
        Engine.verdict = no
        step('patched:no', over)
    finally:
        Engine.verdict = real
    sa_solver.formula_plant(None)
    json.dump(dict(rows=rows, inside=inside, calls=calls, caught=caught, mine=mine), sys.stdout)


def _run(plant='none'):
    e = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]), PYTHONHASHSEED='0')
    r = subprocess.run([sys.executable, __file__, plant], capture_output=True, text=True, env=e, cwd=HERE)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


@pytest.fixture(scope='module')
def plain():
    return _run()


def _sum(run, key, group=None):
    return sum(r[key] for r in run['rows'] if group is None or r['group'] == group)


def _answers(run):
    return [r['answer'] for r in run['rows']]


def test_no_object_is_converted_twice_in_one_entry(plain):
    assert _sum(plain, 'fm:twice') == 0 and _sum(plain, 'fm:nosession') == 0
    assert _sum(plain, 'fm:plant_fired') == 0
    for g in ('split', 'ext:same', 'ext:fresh', 'is', 'again'):
        assert _sum(plain, 'fm:convert', g) > 0 and _sum(plain, 'fm:give', g) > 0, g


def test_a_handlers_fact_is_held_by_identity_and_equal_objects_are_not_merged(plain):
    """H1. The handler runs more than once per query. The same object back each time is converted once in an entry
    (`fm:twice` 0); a new, equal object each time is its own object, converted too: more conversions, none merged by ==."""
    assert plain['calls']['same'] == plain['calls']['fresh'] > 4
    same, fresh = _sum(plain, 'fm:convert', 'ext:same'), _sum(plain, 'fm:convert', 'ext:fresh')
    assert fresh > same > 0
    assert _sum(plain, 'fm:twice', 'ext:same') == 0 and _sum(plain, 'fm:twice', 'ext:fresh') == 0
    assert [r['answer'] for r in plain['rows'] if r['group'] == 'ext:same'] == \
        [r['answer'] for r in plain['rows'] if r['group'] == 'ext:fresh'] == ['True', 'False', 'True', 'True']


def test_nothing_in_a_hand_survives_its_query(plain):
    """H2. Held inside an entry (the handler saw it), nothing held after any query, and the same queries on the same
    formula objects convert as much the second time as the first."""
    assert max(plain['inside']) > 0
    assert [r['held'] for r in plain['rows']] == [0] * len(plain['rows'])
    assert _sum(plain, 'fm:convert', 'again') == _sum(plain, 'fm:convert', 'split')


def _group(run, g):
    return [r['answer'] for r in run['rows'] if r['group'] == g]


def test_a_registered_instrument_keeps_the_direct_call_and_still_sees_the_raise(plain):
    """Ruling (a) on catch_count: with its wrapper on the class, nothing is converted a second time on either side of
    `verdict`, the answers are the uninstrumented ones, and a raise under `verdict` still reaches its sink."""
    for g, plain_g in (('instr', 'split'), ('instr:over', 'over')):
        assert _sum(plain, 'fm:twice', g) == 0 and _sum(plain, 'fm:twice:patched', g) == 0
        assert _sum(plain, 'fm:convert', g) == _sum(plain, 'fm:convert', plain_g) > 0
        assert _group(plain, g) == _group(plain, plain_g)
    assert plain['caught'] == ['verdict<_consistent'] and _group(plain, 'instr:raise') == ['False']


def test_a_users_patched_verdict_is_called_and_its_answer_is_used(plain):
    """Ruling (b): a `verdict` that is neither session_live's nor a registered instrument's is called by name. The
    second `Hand` behind it is counted in its own row, outside the per-query rule."""
    assert plain['mine']['as_real'] > 1 and plain['mine']['no'] == 1
    assert _group(plain, 'patched') == _group(plain, 'split')
    assert _group(plain, 'patched:over') == _group(plain, 'over') == ['None']
    assert _group(plain, 'patched:no') == ['InconsistentAssumptions']
    assert _sum(plain, 'fm:twice:patched', 'patched:over') > 0 and _sum(plain, 'fm:twice:patched', 'over') == 0
    assert _sum(plain, 'fm:twice') == 0


def test_plant_609_an_instrument_called_by_name_is_caught(plain):
    got = _run('fm-hand-instrument-by-name')
    assert _sum(got, 'fm:plant_fired') > 0
    assert _sum(got, 'fm:twice:patched', 'instr:over') > 0
    assert _sum(got, 'fm:convert', 'instr:over') > _sum(plain, 'fm:convert', 'instr:over')
    assert _answers(got) == _answers(plain) and got['caught'] == plain['caught']


def test_plant_610_a_patched_verdict_passed_over_is_caught(plain):
    got = _run('fm-hand-patched-direct')
    assert _sum(got, 'fm:plant_fired') > 0
    assert got['mine'] == {'as_real': 0, 'no': 0}
    assert _group(got, 'patched:no') == _group(plain, 'over')


def test_plant_607_no_give_is_caught(plain):
    got = _run('fm-hand-no-give')
    assert _sum(got, 'fm:plant_fired') > 0
    assert _sum(got, 'fm:twice') > 0 and _sum(got, 'fm:give') == 0
    assert _sum(got, 'fm:convert') > _sum(plain, 'fm:convert')
    assert _answers(got) == _answers(plain)


def test_plant_608_a_hand_kept_across_queries_is_caught(plain):
    got = _run('fm-hand-kept')
    assert _sum(got, 'fm:plant_fired') > 0
    assert any(r['held'] > 0 for r in got['rows'])
    assert _sum(got, 'fm:convert', 'again') < _sum(plain, 'fm:convert', 'again')


if __name__ == '__main__':
    _main(sys.argv[1])
