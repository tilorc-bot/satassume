"""Step 5c9b: the moved process memos (procmemo.rs) where no workload reaches them, Python against Rust, each mode in its own
process.

- `_SPLIT`'s bound: 100,001 fresh clause lists through `_split` (Rust: `sa_solver.ses_split`), keeping every list alive as
  the memo does. Python empties the memo when it holds 100,000 and a write comes, so it holds 1 after the last; then the
  registry's `clear()`. The size is read where Python reads it, through `memos.PROCESS`. No workload makes 100,000 entries
  (dev holds 783), so plant 180 (`pm-split-no-full-clear`) and counter `pm:full` are reached only here.
- `neighbourhood` (`_NEIGH`): every basis name, then every index, in a fixed order, and the memo's identity. Its only other
  caller is tests/test_engine.py:195, which runs Rust's under rust_plugin but can't see plants 183 or 184: the predicate is
  in its own rule clauses there, and `odd`'s two sides share the planted first entry. `polar` is in no rule clause, so 183
  shows only on it.
- `items()` order: `_NEIGH`'s keys and 40 fresh `_SPLIT` keys in Python's insertion order (a `HashMap`'s order before).
Each plant must fire and move some case; the counters `pm:full`, `pm:neigh` and `pm:cb_rules` must fire on Rust.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLANTS = ('pm-split-no-full-clear', 'pm-split-clear-skip', 'pm-neigh-no-self', 'pm-neigh-memo-first')
N_SPLIT = 100_001
ORDER = [(i * 7) % 40 for i in range(40)]


def _main(mode):
    live = None
    if mode == 'rust':
        import test_discovery_core as D
        live = D._rust()
        import sa_solver
        split = sa_solver.ses_split
    import satassume.engine as E
    from satassume.knowledge import rules as R
    from satassume.state import memos
    if mode == 'py':
        split = E._split
    neighbourhood = E.neighbourhood
    if mode == 'rust':
        assert neighbourhood is sa_solver.pm_neighbourhood

    def split_len():
        return [len(c) for n, _, c in memos.PROCESS.items() if n.endswith('._SPLIT')]

    cases = {}
    keep = []
    lens = []
    for i in range(N_SPLIT):
        cl = []
        keep.append(cl)
        r = split(cl, None)
        assert r[0] is cl
        if i in (0, N_SPLIT - 2, N_SPLIT - 1):
            lens.append(split_len())
    cases['split:lens'] = lens
    cases['split:hit'] = split(keep[-1], None) is split(keep[-1], None)
    memos.PROCESS.clear()
    cases['split:after_clear'] = split_len()
    cases['neigh:names'] = [(n, sorted(neighbourhood(n))) for n in sorted(R.BASIS_OF)]
    cases['neigh:index'] = [(i, sorted(neighbourhood(i))) for i in range(R.NPRED)]
    cases['neigh:index_rev'] = [(i, sorted(neighbourhood(i))) for i in reversed(range(R.NPRED))]
    cases['neigh:same'] = all(neighbourhood(i) is neighbourhood(i) for i in range(R.NPRED))
    # items() in insertion order, as a dict iterates (procmemo.rs read its HashMap's per-process order before, so the
    # digest's order hash of these memos differed between two processes of one source; issue 323)
    cases['neigh:order'] = [repr(k) for n, _, c in memos.PROCESS.items() if n.endswith('._NEIGH') for k, _ in c.items()]
    memos.PROCESS.clear()
    fresh = [[] for _ in range(40)]
    for i in ORDER:
        split(fresh[i], None)
    pos = {id(cl): i for i, cl in enumerate(fresh)}
    cases['split:order'] = [pos.get(k[0], -1) for n, _, c in memos.PROCESS.items() if n.endswith('._SPLIT') for k, _ in c.items()]
    json.dump(dict(cases=cases, counts=live.counts() if live else None), sys.stdout)


def _run(mode, **env):
    e = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]), **env)
    r = subprocess.run([sys.executable, __file__, mode], capture_output=True, text=True, env=e, cwd=HERE)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


@pytest.fixture(scope='module')
def both():
    return _run('py'), _run('rust')


def _differ(a, b):
    return sorted(k for k in a['cases'] if a['cases'][k] != b['cases'][k])


def test_same_as_python(both):
    py, rust = both
    assert _differ(py, rust) == []
    # the bound: one entry after the 100,001st write; the registry's clear empties it
    assert py['cases']['split:lens'] == [[1], [100_000], [1]]
    assert py['cases']['split:after_clear'] == [0]
    assert py['cases']['neigh:index'][10] == [10, [10]]      # polar: in no rule clause
    assert py['cases']['split:order'] == ORDER and len(py['cases']['neigh:order']) > 10


def test_counters_fire(both):
    _, rust = both
    c = rust['counts']
    assert c['pm:full'] == 1
    assert c['pm:neigh'] > 0 and c['pm:cb_rules'] > 0
    assert c['rel:plant_fired'] == 0


@pytest.mark.parametrize('plant', PLANTS)
def test_each_plant_fires_and_is_seen(both, plant):
    py, _ = both
    got = _run('rust', SLICE_SESSION_PLANT=plant)
    assert got['counts']['rel:plant_fired'] > 0
    assert _differ(py, got) != []


if __name__ == '__main__':
    _main(sys.argv[1])
