"""`-p plant_count` in a suite run with SLICE_SUITE_OUT set: each process (each xdist worker) writes counts.PID.json there at
the end, so a suite plant run says whether the plant fired at all. A plant that fired 0 makes that run's "no change" void.
bar_sum.py sums the files.

Each kind of plant counts in its own place, and the file carries all of them under `fired` ([146]: the line used to read
only the crate's `rel:plant_fired`, which a term, dispatch, knowledge or witness plant never moves, so it read 0):
  session    session_live.PLANT_FIRED[0] and the crate's `rel:plant_fired`   (SLICE_SESSION_PLANT)
  term       term_live.COUNTS['plant_fired'] and the dispatch's `plant:fired`  (SLICE_TERM_PLANT)
  knowledge  term_live.COUNTS['knowledge:plant_fired']
  witness    satassume.witness.FIRED[0]                                        (SLICE_WITNESS_PLANT)
  wnative    witness_live.FIRED[0]: plants 762 and 764, whose sites are in witness_live.py (SLICE_WITNESS_RUST_PLANT;
             760, 761 and 763 are in the crate and tick `rel:plant_fired`)
The Rust walker's plants (SLICE_CONVERT_PLANT) have no counter, so a `convert:*` row has no entry and the summary says so.
Tests clear some of these counters, so the counts are summed test by test: after each test the rise since the reading
before it is added (a counter that fell was cleared, and then its whole value is the rise). The crate's counters as they
stand at the end stay at the top level of the file, as before."""
import json
import os

import pytest

FIRED = {}
_LAST = {}


def _read():
    import sys
    out = {}
    try:
        import sa_solver
        out['rel:plant_fired'] = dict(sa_solver.session_counts()).get('rel:plant_fired', 0)
    except Exception:  # no crate: the file's top level reports it
        pass
    m = sys.modules.get('session_live')
    if m is not None:
        out['session'] = m.PLANT_FIRED[0]
    m = sys.modules.get('term_live')
    if m is not None:
        out['term'] = m.COUNTS.get('plant_fired', 0)
        # the dispatch's own count reaches COUNTS only at its flush (atexit, after this plugin's last reading), so the
        # live dispatch is read as well; a flush moves the count from one to the other and leaves the sum
        k = sys.modules.get('knowledge_live')
        d = k.DISPATCH[0] if k is not None else None
        out['plant:fired'] = m.COUNTS.get('plant:fired', 0) + (d.counts().get('plant:fired', 0) if d is not None else 0)
        out['knowledge'] = m.COUNTS.get('knowledge:plant_fired', 0)
    m = sys.modules.get('satassume.witness')
    if m is not None:
        out['witness'] = m.FIRED[0]
    m = sys.modules.get('witness_live')
    if m is not None:
        out['wnative'] = m.FIRED[0]
    return out


def _add():
    now = _read()
    for k, v in now.items():
        last = _LAST.get(k, 0)
        FIRED[k] = FIRED.get(k, 0) + (v - last if v >= last else v)
    _LAST.clear()
    _LAST.update(now)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    yield
    if os.environ.get('SLICE_SUITE_OUT'):
        _add()


def pytest_sessionfinish(session, exitstatus):
    d = os.environ.get('SLICE_SUITE_OUT')
    if not d:
        return
    try:
        import sa_solver
        c = dict(sa_solver.session_counts())
    except Exception as e:  # report it, don't hide it: the summary shows `error`
        c = {'error': repr(e)}
    _add()
    c['fired'] = dict(FIRED)
    with open(os.path.join(d, f'counts.{os.getpid()}.json'), 'w') as f:
        json.dump(c, f, sort_keys=True)
