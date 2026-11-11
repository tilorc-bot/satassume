"""Convert once (formula step, gate item 1; rulings H1 and H2): an entry holds a `Hand` (formula.rs) and every formula it
is given, and every fact a user's handler returns, is converted at most once inside that entry's call; nothing a `Hand`
holds outlives the call. One process per run, on Rust, the same queries each time:
- `split`: sets that relevance splits (`rv_relevant` -> `_consistent` -> `verdict`, then `Engine.ask`);
- `ext`: a custom predicate whose handler returns a formula fact, the same object on every call (`same`) or a new, equal
  object on every call (`fresh`): H1's case. The handler reads `formula_held()` when it runs, inside the entry.
- `again`: the first queries once more on a new engine, with the same formula objects (sympy_api's `_formula` memo).
After each query: the answer, the change of `fm:convert`, `fm:twice`, `fm:nosession`, `fm:give`, and `formula_held()`.
Plant 607 `fm-hand-no-give`: the entry hands the session nothing, the session converts again: `fm:twice` above 0.
Plant 608 `fm-hand-kept`: an entry's nodes answer the next entry (a `Hand` reused across queries): something is held
between queries and the repeated queries convert less.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ('fm:convert', 'fm:twice', 'fm:nosession', 'fm:give', 'fm:plant_fired')


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

    e = Engine()
    for p, a in split:
        step('again', lambda: A.ask(p, a, engine=e))
    sa_solver.formula_plant(None)
    json.dump(dict(rows=rows, inside=inside, calls=calls), sys.stdout)


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
    for g in ('split', 'ext:same', 'ext:fresh', 'again'):
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
