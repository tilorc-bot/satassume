"""live.py's handler plants reach Rust's handlers (issue 323; planner forward-chain-3b ~14:55 9 Nov, Q2).

Since 5c10b, `_build_context`, `verdict` and `_complete_check` run in context.rs and `_consistent` in relevance.rs. live.py
planted `SLICE_PLANT_HANDLER` before `backend.install()`, which replaced the patched rows, so no plant fired on Rust and
its "0 handler rows" proved nothing at those sites. Planted after the installs, context.rs calls the patch by name
(`ctx:cb_patched`) and relevance.rs calls `Engine.verdict` by name (`rv:cb_verdict`), so the raise reaches Rust's own
handlers. `SLICE_SESSION_PLANT=ctx-check-raise` raises inside context.rs's complete check itself.

Each case: the plant fires on Rust, handler_count writes its rows under Python's site name, and the rows equal Python's;
unplanted, both backends write none. As a script: `python test_live_handler_plant.py` (exit 1 on a failure).
"""
import json
import os
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
# (workload, live.py selection, site): scope reaches `_build_context`'s handler, not `_consistent`; these dev queries
# reach `_consistent` through `Engine.verdict` (the first five with a verdict row on the full dev run at 268aedc).
SCOPE = ('scope', ['--limit', '12'], 'Engine._build_context')
DEV = ('dev', ['--only', '5,190,193,371,381'], '_consistent')
CASES = {'complete_check': SCOPE, 'assumption_lits': SCOPE, 'verdict': DEV}


def _rows(wl, mode, sel, **env):
    e = dict(os.environ)
    for k in ('SLICE_PLANT_HANDLER', 'SLICE_SESSION_PLANT'):
        e.pop(k, None)
    e.update(env)
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'out.jsonl')
        r = subprocess.run([sys.executable, 'live.py', wl, mode, out, '--check', 'entry', *sel], capture_output=True,
                           text=True, env=e, cwd=HERE)
        assert r.returncode == 0, r.stderr[-2000:]
        with open(out + '.handlers') as f:
            return sorted(tuple(sorted(json.loads(line).items())) for line in f)


@pytest.mark.parametrize('plant', sorted(CASES))
def test_live_plant_reaches_rust_handler(plant):
    wl, sel, site = CASES[plant]
    rust = _rows(wl, 'rust', sel, SLICE_PLANT_HANDLER=plant)
    assert rust, f'{plant}: no handler row on Rust'
    assert {dict(r)['site'] for r in rust} == {site}
    assert rust == _rows(wl, 'py', sel, SLICE_PLANT_HANDLER=plant)


def test_rust_side_plant_in_complete_check():
    wl, sel, site = SCOPE
    rust = _rows(wl, 'rust', sel, SLICE_SESSION_PLANT='ctx-check-raise')
    assert rust and {(dict(r)['site'], dict(r)['text']) for r in rust} == {(site, 'planted ctx-check-raise')}
    # one row per query that the Python-side plant at the same call also fires on
    assert [dict(r)['where'] for r in rust] == [dict(r)['where'] for r in _rows(wl, 'rust', sel, SLICE_PLANT_HANDLER='complete_check')]


@pytest.mark.parametrize('case', [SCOPE, DEV], ids=['scope', 'dev'])
def test_unplanted_rows_match(case):
    wl, sel, _ = case
    assert _rows(wl, 'rust', sel) == _rows(wl, 'py', sel) == []


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-q']))
