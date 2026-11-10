"""The moved containers' digest (moved_digest.py, in live.py's rows, compared by livecmp.py) on the `twin` workload: equal to
Python's on the clean build, and moved by the plant `rk-class-split` (409) at `_tv`, the dict where the second class's
`f(0)` gets its own key (issue 323: the nine sets' digest alone did not see this plant)."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _live(tmp, mode, plant=None):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    env.pop('SLICE_SESSION_PLANT', None)
    env.pop('SLICE_MOVED', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    out = os.path.join(str(tmp), '%s-%s.jsonl' % (mode, plant))
    r = subprocess.run([sys.executable, os.path.join(HERE, 'live.py'), 'twin', mode, out, '--check', 'entry'], env=env,
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-3000:]
    return out


def _cmp(a, b):
    r = subprocess.run([sys.executable, os.path.join(HERE, 'livecmp.py'), a, b], capture_output=True, text=True)
    lines = r.stdout.splitlines()
    return json.loads(lines[0]), json.loads(lines[1][len('first: '):]), lines[-1]


def test_twin_digest_equal_unarmed_and_moved_by_the_class_split_plant(tmp_path):
    py, rust, plant = _live(tmp_path, 'py'), _live(tmp_path, 'rust'), _live(tmp_path, 'rust', 'rk-class-split')
    n, first, verdict = _cmp(py, rust)
    assert verdict == 'MATCH' and n['moved_diff'] == 0 and n['moved_rows'] == 2 and n['moved_engine_points'] == 1, (n, first)
    tot = json.loads(open(rust).read().splitlines()[-1])['total']['moved']
    # the control: the comparison read the core's exports, and the dict the plant shows in was filled
    assert tot['src'].get('rd_snapshot') == 2 and tot['filled'].get('_tv') == 2 and not tot['names_differ'], tot
    n, first, verdict = _cmp(py, plant)
    assert verdict == 'DIFFER' and n['moved_diff'] >= 1 and '0:_tv' in first['moved'][1], (n, first)
