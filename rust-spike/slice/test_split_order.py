"""test_split_order.py: split_order.py's comparison and guard on workload twin, clean and with plants 450 to 453 (issue 323).
Run from rust-spike/slice with the bar's environment: `pytest test_split_order.py`."""
import json
import os
import subprocess
import sys

import split_order

HERE = os.path.dirname(os.path.abspath(__file__))


def run(tmp, mode, plant=None):
    out = os.path.join(str(tmp), '%s-%s.probe' % (mode, plant))
    env = dict(os.environ, SPLIT_PROBE=out, SLICE_MOVED_EVERY='1')
    env.pop('SPLIT_PLANT', None)
    if plant:
        env['SPLIT_PLANT'] = plant
    subprocess.run([sys.executable, 'live.py', 'twin', mode, out + '.jsonl', '--check', 'entry'], cwd=HERE, env=env, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return [json.loads(l) for l in open(out)][-1]


def test_twin(tmp_path):
    py, rust = run(tmp_path, 'py'), run(tmp_path, 'rust')
    assert (len(py['rows']['_SPLIT']), len(rust['rows']['_SPLIT'])) == (2, 4)
    assert split_order.compare(py['rows'], rust['rows']) == ([], 2)
    # 451: Python's atom templates uncached, as Rust's are: Python's `_SPLIT` has Rust's rows
    unc = run(tmp_path, 'py', 'atoms-uncached')
    assert unc['plant_fired'] > 0 and len(unc['rows']['_SPLIT']) == 4
    assert split_order.compare(unc['rows'], rust['rows']) == ([], 0)
    # 450 and 453: a row lost from Rust's read is a difference, though counts and order already differ on the clean build
    for plant, name in (('split-row-drop', '_SPLIT'), ('closed-row-drop', '_CLOSED')):
        bad = run(tmp_path, 'rust', plant)
        assert bad['plant_fired'] > 0
        diffs, _ = split_order.compare(py['rows'], bad['rows'])
        assert diffs and all(name in d for d in diffs), diffs


def test_guard():
    assert split_order.guard(os.path.join(HERE, '..', '..', 'satassume')) == []
    assert len(split_order.guard(text=split_order.PLANTED_READER)) == 1       # 452
