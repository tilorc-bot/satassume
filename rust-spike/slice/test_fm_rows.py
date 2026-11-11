"""The exact conversion rows per workload (fm_rows.py; the planner's ruling (2) on sa-port-268's report): the check that
catches plant 608 `fm-hand-kept` without reading the plant's own counter. Two small workloads, one process each."""
import json
import os
import subprocess
import sys

import pytest

import fm_rows

HERE = os.path.dirname(os.path.abspath(__file__))
WLS = ('cert', 'opaque')


def _run(d, plant=None):
    env = dict(os.environ)
    env.pop('SLICE_SESSION_PLANT', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    os.makedirs(d, exist_ok=True)
    for wl in WLS:
        subprocess.run([sys.executable, os.path.join(HERE, 'fm_rows.py'), 'run', os.path.join(d, wl + '.row.json'), wl],
                       cwd=HERE, env=env, check=True, capture_output=True)


def _check(d, known):
    r = subprocess.run([sys.executable, os.path.join(HERE, 'fm_rows.py'), 'check', d, known], cwd=HERE, capture_output=True, text=True)
    return r.returncode, r.stdout


@pytest.fixture(scope='module')
def known(tmp_path_factory):
    """The two workloads' rows of results/fm_rows.json, as their own file: `check` wants a run for every row."""
    rows = json.load(open(fm_rows.KNOWN))
    p = tmp_path_factory.mktemp('known') / 'fm_rows.json'
    p.write_text(json.dumps({wl: rows[wl] for wl in WLS}))
    return str(p)


@pytest.fixture(scope='module')
def plain(tmp_path_factory):
    d = str(tmp_path_factory.mktemp('plain'))
    _run(d)
    return d


def test_rows_are_the_known_rows(plain, known):
    code, out = _check(plain, known)
    assert code == 0 and 'fm rows: 2 workloads, 0 differ' in out, out
    rows = json.load(open(fm_rows.KNOWN))
    assert all(rows[wl]['fm:again'] > 0 for wl in WLS), 'a row of 0 could not show a kept Hand'


def test_a_hand_kept_across_queries_changes_the_row(tmp_path, known):
    """Plant 608: the later queries are answered from the kept nodes, so they convert less. The check reads the row only."""
    d = str(tmp_path / 'p608')
    _run(d, 'fm-hand-kept')
    code, out = _check(d, known)
    assert code == 1, out
    for wl in WLS:
        assert 'DIFFER %s: fm:again 0, known 30' % wl in out, out
    assert 'plant_fired' not in out and 'fm:plant_fired' not in fm_rows.ROW


def test_a_missing_run_and_an_unknown_workload_fail(plain, known, tmp_path):
    one = tmp_path / 'one.json'
    one.write_text(json.dumps({'cert': json.load(open(known))['cert']}))
    code, out = _check(plain, str(one))
    assert code == 1 and 'DIFFER opaque: no known row' in out, out
    more = tmp_path / 'more.json'
    more.write_text(json.dumps(dict(json.load(open(known)), dev={})))
    code, out = _check(plain, str(more))
    assert code == 1 and 'DIFFER dev: no run' in out, out
