"""The moved containers' digest (moved_digest.py, in live.py's rows, compared by livecmp.py) on the `twin` workload: equal to
Python's on the clean build, and moved by the plant `class-is` (661) at `_tv`, the dict where the second class's
`f(0)` gets its own key (issue 323: the nine sets' digest alone did not see this plant)."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _live(tmp, mode, plant=None, split=None):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    for k in ('SLICE_SESSION_PLANT', 'SLICE_MOVED', 'SPLIT_PLANT', 'SPLIT_PROBE'):
        env.pop(k, None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    if split:
        env['SPLIT_PLANT'] = split
    out = os.path.join(str(tmp), '%s-%s.jsonl' % (mode, plant or split))
    r = subprocess.run([sys.executable, os.path.join(HERE, 'live.py'), 'twin', mode, out, '--check', 'entry'], env=env,
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-3000:]
    return out


def _cmp(a, b):
    r = subprocess.run([sys.executable, os.path.join(HERE, 'livecmp.py'), a, b], capture_output=True, text=True)
    lines = r.stdout.splitlines()
    return json.loads(lines[0]), json.loads(lines[1][len('first: '):]), lines[-1]


def test_twin_digest_equal_unarmed_and_moved_by_the_class_split_plant(tmp_path):
    py, rust, plant = _live(tmp_path, 'py'), _live(tmp_path, 'rust'), _live(tmp_path, 'rust', 'class-is')
    n, first, verdict = _cmp(py, rust)
    assert verdict == 'MATCH' and n['moved_diff'] == 0 and n['moved_rows'] == 2 and n['moved_engine_points'] == 1, (n, first)
    tot = json.loads(open(rust).read().splitlines()[-1])['total']['moved']
    # the control: the comparison read the core's exports, and the dict the plant shows in was filled
    assert tot['src'].get('rd_snapshot') == 2 and tot['filled'].get('_tv') == 2 and not tot['names_differ'], tot
    n, first, verdict = _cmp(py, plant)
    assert verdict == 'DIFFER' and n['moved_diff'] >= 1 and '0:_tv' in first['moved'][1], (n, first)


def test_twin_known_rows_and_the_extension(tmp_path):
    """`_SPLIT` and `_CACHE` are exact since the `_CACHE` fix (c170496, 311fb80): 2 rows and 2 keys on both backends (before
    it, the known row was `_SPLIT` 2 against 4 and `_CACHE` 2 against 0, sa-port-239's numbers). Plants 450, 451 and 453 each
    move the verdict; so does a known row that doesn't hold (the mechanism stays for a ruled known difference). The extension's rows (state part 3's session containers, the LRA slot, the handles, the
    engines built in a query, 5c9a's native tables) are filled on this workload, and a dropped `demand` entry (plant 442,
    where the build has it) moves the session's row."""
    py, rust = _live(tmp_path, 'py'), _live(tmp_path, 'rust')
    n, first, verdict = _cmp(py, rust)
    assert verdict == 'MATCH' and n['moved_known_diff'] == 0 and n['moved_native_diff'] == 0, (n, first)
    known = json.load(open(os.path.join(HERE, 'known_moved.json')))
    assert 'twin' not in known and '"known rows (twin): []' not in verdict       # exact: no known row, the counts equal
    seen = json.loads(subprocess.run([sys.executable, os.path.join(HERE, 'livecmp.py'), py, rust], capture_output=True,
                                     text=True).stdout.split('per engine point): ')[1].split(' | known rows')[0])
    assert seen == [[2, 2, 2, 2]], seen
    rows = [json.loads(l) for l in open(rust)]
    tot = rows[-1]['total']['moved']
    assert tot['sessions'] == 4 and tot['engines'] >= 2 and tot['lra_entries'] > 0, tot
    assert tot['filled'].get('ses.demand') and tot['filled'].get('@xfer') and tot['filled'].get('@lra'), tot
    assert any(k.endswith('SPEC_ROWS:pure') and v for k, v in tot['native_checked'].items()) and not tot['native_bad'], tot
    assert all('ses' in r['moved_q'] and 'eng' in r['moved_q'] for r in rows[:-1])
    # 450 and 453 on Rust's read, 451 on Python's templates: each a DIFFER, by the row it touches
    n, first, verdict = _cmp(py, _live(tmp_path, 'rust', split='split-row-drop'))
    assert verdict == 'DIFFER' and (n['moved_known_diff'] or n['moved_diff']), (n, first)
    n, first, verdict = _cmp(py, _live(tmp_path, 'rust', split='closed-row-drop'))
    assert verdict == 'DIFFER' and n['moved_diff'] and '_CLOSED' in json.dumps(first.get('moved_eng')), (n, first)
    n, first, verdict = _cmp(_live(tmp_path, 'py', split='atoms-uncached'), rust)
    assert verdict == 'DIFFER' and n['moved_known_diff'] == 1 and first['moved_known'][2][:2] == [4, 2], (n, first)
    # a known row that no longer holds is a DIFFER too (the table is exact, not a tolerance): the row twin had before the
    # `_CACHE` fix
    old = os.path.join(HERE, 'livecmp.py')
    alt = os.path.join(str(tmp_path), 'alt')
    os.mkdir(alt)
    open(os.path.join(alt, 'livecmp.py'), 'w').write(open(old).read())
    json.dump(dict(known, twin=[[2, 4, 2, 0]]), open(os.path.join(alt, 'known_moved.json'), 'w'))
    r = subprocess.run([sys.executable, os.path.join(alt, 'livecmp.py'), py, rust], capture_output=True, text=True)
    assert r.stdout.splitlines()[-1] == 'DIFFER' and '"moved_known_diff": 1' in r.stdout
    # the session containers' row is live: plant 442 drops a `demand` write
    if "'sc-demand-drop'" in open(os.path.join(HERE, 'session_live.py')).read():
        n, first, verdict = _cmp(py, _live(tmp_path, 'rust', 'sc-demand-drop'))
        assert verdict == 'DIFFER', (n, first)


_COUNTS = '''import atexit, json, runpy, sys
sys.path.insert(0, sys.argv[1])
import sa_solver
atexit.register(lambda: print('COUNTS ' + json.dumps({k: v for k, v in sa_solver.session_counts().items() if k.startswith('sb:fwd')})))
sys.argv = [sys.argv[1] + '/live.py', 'cls', 'rust', sys.argv[2], '--check', 'entry']
runpy.run_path(sys.argv[0], run_name='__main__')
'''


def test_the_digest_observes_and_never_replaces(tmp_path):
    """Item 4g (RULINGS 14): with the digest on, Rust still calls `_interpret` and `_link` directly. The digest used to
    replace both on `Relations`, so Rust called them by name (`sb:fwd_named` 306 of 453 on cls) and the process memos'
    values followed that path. Now its mid-query samples come from `sa_solver.rel_observe` and `sys.monitoring`."""
    got = {}
    for moved in ('1', '0'):
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]), SLICE_MOVED=moved)
        env.pop('SLICE_SESSION_PLANT', None)
        out = os.path.join(str(tmp_path), 'cls-%s.jsonl' % moved)
        r = subprocess.run([sys.executable, '-c', _COUNTS, HERE, out], env=env, capture_output=True, text=True, timeout=900)
        assert r.returncode == 0, r.stderr[-3000:]
        got[moved] = json.loads([x for x in r.stdout.splitlines() if x.startswith('COUNTS ')][-1][len('COUNTS '):])
        if moved == '1':
            tot = json.loads(open(out).read().splitlines()[-1])['total']['moved']
            assert tot['mid_samples'] > 0, tot
    assert got['1'] == got['0'] and got['1']['sb:fwd_named'] == 0 and got['1']['sb:fwd_direct'] > 0, got
