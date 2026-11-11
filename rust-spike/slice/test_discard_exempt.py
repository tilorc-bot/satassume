"""The discarded run and the `_CACHE` exemption, kept (issue 323, the formula step's gate 4a).

term_discard.py plants a refusal in each query's run and, at the rollback, compares all of Python's state with a copy taken
as the run started. Ruled (10 Nov, rulings 1 and 2 on e8d5adf): the pattern cache `_common._CACHE` is left alone by the
rollback, because its key determines its value (cache_det.py), and term_discard.py exempts `_CACHE` and only `_CACHE`.
An entry a discarded run leaves in any other container is counted as left. Plant 667 `mark-leaves-entry` (term_live.py
`_Mark.rollback`) makes the rollback skip the first other table the run grew.

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


def run(tmp, plant=None):
    env = dict(os.environ)
    for k in ('SLICE_TERM_PLANT', 'SLICE_SESSION_PLANT', 'SLICE_KNOWLEDGE_PLANT', 'SLICE_PLANT'):
        env.pop(k, None)
    out = os.path.join(tmp, 'term.json')
    cmd = [sys.executable, os.path.join(HERE, 'fresh.py'), 'dev', 'rust', os.path.join(tmp, 'rows.txt'), '--first', str(N),
           '--term', 'terms', '--lra', '--discard', '--term-out', out]
    if plant:
        cmd += ['--term-plant', plant]
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
