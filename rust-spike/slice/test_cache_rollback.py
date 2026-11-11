"""The `_CACHE` fix, the discarded run (issue 323, sa-port-248): a query Rust refuses and Python reruns leaves `_CACHE`
with the keys Python's own run leaves.

The rollback of a refused run (term_live.py `_Mark`) cut `_CACHE` back to the mark, while Rust's memo of compiled nodes
(dispatch.rs `Dispatch.memo`) kept the run's nodes: the second run was served them and never rebuilt their patterns, so
the table stayed short (f6 query 1008, `cosh(y + 1*I*pi)`: 1 key of Python's 6; wiring 4264; 93 keys on lra). The pattern
cache is no longer rolled back: its key determines its value (cache_det.py, test_cache_fix.py), so the entry a discarded
run left is the one the next run would build. Plant 666 `mark-wrong-pattern` (a wrong value at that site: one entry of the
discarded run gets another key's pattern) must be caught by cache_det.py and by the digest's `_CACHE` value row.
(The old plant 666, a `_CACHE` cut back to the mark, is speed-only since ded8c3f: the rerun refills it.)

Each run is its own process (cache_rollback.py), with live.py's installs: the refusal needs the whole backend.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(*args, **extra):
    env = dict(os.environ, **extra)
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
    assert rust['vals'] == py['vals']                                   # and the patterns (the digest's `_CACHE` row)
    assert rust['split'] == py['split'] and py['split'][0] > 0          # no second copy of a pattern's rows


def test_the_key_determines_the_pattern_after_a_discard():
    """cache_det.py on the same queries: every hit's own build equals the cached pattern, on both backends."""
    py, rust = run('py', CACHE_DET='1'), run('rust', CACHE_DET='1')
    assert rust['refused'].get('refused', 0) >= 1
    assert sum(rust['det']['hits'].values()) > 0, rust['det']      # the rerun after the discard hits (Python runs once)
    assert py['det']['mismatch'] == {} and rust['det']['mismatch'] == {}, (py['det'], rust['det'])


def test_plant_666_a_wrong_pattern_is_caught():
    """Plant 666 `mark-wrong-pattern`: the rollback gives one `_CACHE` entry of the discarded run another key's pattern.
    Two independent checks see it: cache_det.py (the rerun's hit builds its own pattern and it differs) and the digest's
    `_CACHE` row against Python's. Neither reads the plant's counter; the counter only shows the plant ran."""
    py = run('py')
    rust = run('rust', 'mark-wrong-pattern')
    assert rust['fired'].get('plant:mark-wrong-pattern', 0) >= 1, rust['fired']
    assert rust['vals'] != py['vals']
    det = run('rust', 'mark-wrong-pattern', CACHE_DET='1')['det']
    assert sum(det['mismatch'].values()) >= 1, det
