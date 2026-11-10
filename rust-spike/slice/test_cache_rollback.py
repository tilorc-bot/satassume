"""The `_CACHE` fix, the discarded run (issue 323, sa-port-248): a query Rust refuses and Python reruns leaves `_CACHE`
with the keys Python's own run leaves.

The rollback of a refused run (term_live.py `_Mark`) cut `_CACHE` back to the mark, while Rust's memo of compiled nodes
(dispatch.rs `Dispatch.memo`) kept the run's nodes: the second run was served them and never rebuilt their patterns, so
the table stayed short (f6 query 1008, `cosh(y + 1*I*pi)`: 1 key of Python's 6; wiring 4264; 93 keys on lra). The pattern
cache is no longer rolled back: its key determines its value (cache_det.py, test_cache_fix.py), so the entry a discarded
run left is the one the next run would build. Plant 666 `mark-cuts-patterns` rolls it back as before.

Each run is its own process (cache_rollback.py), with live.py's installs: the refusal needs the whole backend.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(*args):
    env = dict(os.environ)
    for k in ('SLICE_TERM_PLANT', 'SLICE_SESSION_PLANT', 'SLICE_KNOWLEDGE_PLANT', 'SLICE_PLANT'):
        env.pop(k, None)
    out = subprocess.run([sys.executable, os.path.join(HERE, 'cache_rollback.py'), *args], env=env, cwd=HERE,
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


def test_a_refused_query_leaves_pythons_keys():
    py, rust = run('py'), run('rust')
    assert rust['refused'].get('refused', 0) >= 1, rust['refused']      # the path is reached, or the equality proves nothing
    assert py['answers'] == rust['answers']
    assert rust['keys'] == py['keys'] and len(py['keys']) >= 6          # the keys, in Python's order
    assert rust['split'] == py['split'] and py['split'][0] > 0          # no second copy of a pattern's rows


def test_plant_666_a_pattern_cache_cut_back_is_caught():
    py, rust = run('py'), run('rust', 'mark-cuts-patterns')
    assert rust['refused'].get('refused', 0) >= 1
    assert py['answers'] == rust['answers']
    assert set(py['keys']) - set(rust['keys']), 'plant 666 no longer fires'
