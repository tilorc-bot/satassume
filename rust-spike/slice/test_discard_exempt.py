"""The discarded run and the `_CACHE` exemption, kept (issue 323, the formula step's gate 4a).

term_discard.py plants a refusal in each query's run and, at the rollback, compares all of Python's state with a copy taken
as the run started. Ruled (10 Nov, rulings 1 and 2 on e8d5adf): the pattern cache `_common._CACHE` is left alone by the
rollback, because its key determines its value (cache_det.py), and term_discard.py exempts `_CACHE` and only `_CACHE`.
An entry a discarded run leaves in any other container is counted as left. Plant 667 `mark-leaves-entry` (term_live.py
`_Mark.rollback`) makes the rollback skip the first other table the run grew.

The Rust-native tables (the planner's ruling on lra's cause, sa-port-268): a discarded run left its `_Split` in `Engine.splits`,
its verdict in `Engine._verdict` and its rows in `_kids`, `_cones` and `_qcones`, and the rerun read them (lra queries 73, 204,
585, 6). `_Mark` now marks every native table (`_nt_mark`) and takes out what the run added (`_nt_rollback`), and the check
reads the native tables' rows, which `--full` installs (session_live, knowledge_live, as live.py does). Plant 611
`mark-skips-native` leaves the native tables as the run wrote them.

Each run is its own process: `fresh.py dev rust --first 30 --term terms --lra --discard`, 30 planted refusals, a few seconds.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
N = 30
CACHE = 'satassume.knowledge.templates._common._CACHE'


def run(tmp, plant=None, full=False, formula_plant=None):
    env = dict(os.environ)
    for k in ('SLICE_TERM_PLANT', 'SLICE_SESSION_PLANT', 'SLICE_KNOWLEDGE_PLANT', 'SLICE_PLANT'):
        env.pop(k, None)
    out = os.path.join(tmp, 'term.json')
    cmd = [sys.executable, os.path.join(HERE, 'fresh.py'), 'dev', 'rust', os.path.join(tmp, 'rows.txt'), '--first', str(N),
           '--term', 'terms', '--lra', '--discard', '--term-out', out]
    if full:
        cmd.append('--full')
    if plant:
        cmd += ['--term-plant', plant]
    if formula_plant:
        cmd += ['--formula-plant', formula_plant]
    subprocess.run(cmd, env=env, cwd=HERE, capture_output=True, text=True, check=True)
    return json.load(open(out)), open(os.path.join(tmp, 'rows.txt')).read()


@pytest.fixture(scope='module')
def plain(tmp_path_factory):
    return run(str(tmp_path_factory.mktemp('plain')))


@pytest.fixture(scope='module')
def planted(tmp_path_factory):
    return run(str(tmp_path_factory.mktemp('p667')), 'mark-leaves-entry')


def test_the_exemption_names_the_pattern_cache_only():
    sys.path.insert(0, HERE)
    import term_discard
    assert sorted(term_discard.EXEMPT) == ['module:' + CACHE, 'process:' + CACHE]


def test_a_discarded_run_leaves_the_pattern_cache_and_nothing_else(plain):
    d, _ = plain
    c = d['counts']
    assert c['armed'] == c['raised'] == c['checked'] == N       # every query's run was refused at a planted site and checked
    assert d['term'].get('refused', 0) >= N
    assert c.get('left-something', 0) == 0 and c['clean'] == N
    # the rollback left `_CACHE` with the discarded run's entries (the reason the exemption exists), counted, not silent
    assert c['exempt:_CACHE'] > 0
    assert d['left'] and set(d['left']) == {'module:' + CACHE + ':exempt', 'process:' + CACHE + ':exempt'}
    assert not d['term'].get('plant:mark-leaves-entry')


def test_plant_667_an_entry_left_in_another_container_is_caught(plain, planted):
    d, rows = planted
    c = d['counts']
    assert d['term']['plant:mark-leaves-entry'] > 0, 'plant 667 no longer fires'
    assert c['checked'] == N and c['left-something'] > 0 and c.get('clean', 0) < N
    named = {k for k in d['left'] if not k.endswith(':exempt')}
    assert named and not any(CACHE in k for k in named)         # the container is named, and it is not `_CACHE`
    assert c['exempt:_CACHE'] == plain[0]['counts']['exempt:_CACHE']    # the exemption covered `_CACHE` and nothing more


NATIVE = ('engine:splits', 'engine:_verdict', 'engine:_kids', 'engine:_cones', 'engine:_qcones')


@pytest.fixture(scope='module')
def full(tmp_path_factory):
    return run(str(tmp_path_factory.mktemp('full')), full=True)


@pytest.fixture(scope='module')
def planted_native(tmp_path_factory):
    return run(str(tmp_path_factory.mktemp('p611')), 'mark-skips-native', full=True)


def test_a_discarded_run_leaves_nothing_in_a_native_table(full):
    d, _ = full
    c = d['counts']
    assert c['armed'] == c['raised'] == c['checked'] == N
    assert c['native-read'] > 0, 'the check read no native table: its clean count says nothing of them'
    assert d['term']['rollback:native'] > 0 and not d['term'].get('plant:mark-skips-native')
    assert c.get('left-something', 0) == 0 and c['clean'] == N
    assert set(d['left']) == {'module:' + CACHE + ':exempt', 'process:' + CACHE + ':exempt'}


def test_plant_611_a_native_table_left_as_the_run_wrote_it_is_caught(full, planted_native):
    d, rows = planted_native
    c = d['counts']
    assert d['term']['plant:mark-skips-native'] > 0, 'plant 611 no longer fires'
    assert c['checked'] == N and c['left-something'] > 0 and c.get('clean', 0) < N
    named = {k for k in d['left'] if not k.endswith(':exempt')}
    assert set(NATIVE) <= named, named        # the tables lra's cause went through, each named
    assert not any(CACHE in k for k in named)
    assert c['exempt:_CACHE'] == full[0]['counts']['exempt:_CACHE']


# The gate for sa-port-269 (4): the Rust stores outside the memo registry. `Dispatch.memo`, `Dispatch.classes` and formula.rs
# `SEEN` are rolled back and read; `KEPT` (plant 608's store) and adapters.rs `LIVE` are read, and nothing but the plant or an
# install writes them.
STORES = ('Dispatch.memo', 'Dispatch.classes', 'formula.SEEN', 'formula.KEPT', 'adapters.LIVE')


def test_the_stores_outside_the_registry_are_read_at_every_discard(full):
    c = full[0]['counts']
    for name in STORES:
        assert c['read:' + name] >= 2 * N, name       # before each run and after each rollback
    assert c.get('left-something', 0) == 0


@pytest.mark.parametrize('name', ['Dispatch.memo', 'Dispatch.classes'])
def test_plant_611_on_a_dispatch_store_is_caught(tmp_path, name):
    d, _ = run(str(tmp_path), 'mark-skips-native:' + name, full=True)
    assert d['term']['plant:mark-skips-native'] == N
    named = {k for k in d['left'] if not k.endswith(':exempt')}
    assert named == {'native:' + name}, named
    assert d['counts']['left-something'] > 0


def test_plant_608_the_nodes_an_ended_entry_kept_are_caught_by_the_discard_check(tmp_path):
    d, _ = run(str(tmp_path), full=True, formula_plant='fm-hand-kept')
    named = {k for k in d['left'] if not k.endswith(':exempt')}
    assert named == {'native:formula.KEPT'}, named
    assert d['counts']['left-something'] > 0


def test_seen_is_cut_back_to_its_mark_and_live_is_read():
    sys.path.insert(0, HERE)
    import sa_solver
    import term_live
    seen, kept, live = (next(t for t in term_live.NATIVE_EXTRA if t.name == n) for n in ('formula.SEEN', 'formula.KEPT', 'adapters.LIVE'))
    assert seen.items() == [] and kept.items() == []       # outside any entry, and with no plant
    a, b = object(), object()
    try:
        sa_solver.formula_seen_restore([(a, 0, [1])])
        mark = seen._nt_mark()
        sa_solver.formula_seen_restore([(a, 0, [1, 2]), (b, 3, [])])        # what a refused run inside an entry would add
        assert len(seen.items()) == 2
        assert seen._nt_rollback(mark) is False
        assert seen.items() == [(a, (0, (1,)))] and seen.items()[0][0] is a
    finally:
        sa_solver.formula_seen_restore([])
    was = sa_solver.ad_lra_live_get()
    cfg = tuple(object() for _ in range(9)) + (False,)
    try:
        sa_solver.ad_lra_live(cfg)
        rows = live.items()
        assert [k for k, _ in rows] == [(i,) for i in range(10)] and all(v is x for (_, v), x in zip(rows, cfg))
        sa_solver.ad_lra_live(None)
        assert live.items() == []
    finally:
        sa_solver.ad_lra_live(was)
    assert not hasattr(kept, '_nt_mark') and not hasattr(live, '_nt_mark')      # read by the check, written by no query
