"""One `Hand` per ask (the planner's ruling on sa-port-283's item 3; rulings H1/H2): every outermost entry inside one
top-level ask shares one node map (formula.rs `formula_ask`, opened by term_live.py's top-level `_ask`), so no object is
converted twice within an ask. Across asks a reconversion stays intended (H2) and is only reported.

The case is sa-port-283's repro: dev's queries 185-190, where query 190's ask made a second top-level Rust entry that
converted an object an earlier entry of the same ask had converted (`fm:again` 1 within that ask before the fix).
fm_again_split.py's `ask` mode resets the tracking at each top-level ask, so its `again` is the within-ask count.
Plant 622 `fm-hand-per-entry`: each outermost entry makes its own map again, and the check (the within-ask count, not
the plant's own counter) is above 0."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ONLY = '185,186,187,188,189,190'


def _run(tmp_path, plant=None):
    env = dict(os.environ)
    env.pop('SLICE_SESSION_PLANT', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    out = str(tmp_path / ('%s.json' % (plant or 'plain')))
    subprocess.run([sys.executable, os.path.join(HERE, 'fm_again_split.py'), out, 'dev', 'ask', '--only', ONLY],
                   cwd=HERE, env=env, check=True, capture_output=True)
    return json.load(open(out))


def test_no_object_is_converted_twice_within_an_ask(tmp_path):
    j = _run(tmp_path)
    assert j['asks'] == 6 and j['convert'] > 0, j
    assert j['again'] == 0 and j['asks_with_again'] == 0, j


def test_a_map_per_entry_converts_again_within_the_ask(tmp_path):
    j = _run(tmp_path, 'fm-hand-per-entry')
    assert j['again'] >= 1 and j['asks_with_again'] >= 1, j
