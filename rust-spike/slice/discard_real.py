"""pytest plugin: the suite's real refusals, per test, and the state check of `term_discard.py` on them.

    -p discard_real, with SLICE_SUITE_OUT=DIR. Writes DIR/refused.PID.jsonl, one line per test that refused, by reason.
    SLICE_DISCARD_REAL=1: compare all of Python's state at each real rollback against the run's start, and write
    DIR/discard.PID.json. It copies the state at every top-level query, so run it on the ids the first pass named, not the suite.
    SLICE_DISCARD_NOROLL=1: skip the rollback as well: the control, which has to show `left-something` on the same refusals.

`term_discard.py`'s planted sites aren't installed, so every refusal here is one the query really reached.
"""
import json
import os

import pytest

_out = [None]


def _write(row):
    d = os.environ.get('SLICE_SUITE_OUT')
    if not d:
        return
    if _out[0] is None:
        os.makedirs(d, exist_ok=True)
        _out[0] = open(os.path.join(d, f'refused.{os.getpid()}.jsonl'), 'a', buffering=1)
    _out[0].write(json.dumps(row) + '\n')


def pytest_configure(config):
    import term_live
    if os.environ.get('SLICE_DISCARD_REAL'):
        import term_discard
        term_live.BEFORE_RUN[0] = term_discard._before
        term_live.AFTER_ROLLBACK[0] = term_discard.check
    if os.environ.get('SLICE_DISCARD_NOROLL'):
        term_live.PLANT_NO_ROLLBACK[0] = True


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    import term_live
    def refused():
        return {k: v for k, v in term_live.COUNTS.items() if k.startswith('refused')}
    before = refused()
    yield
    moved = {k: v - before.get(k, 0) for k, v in refused().items() if v != before.get(k, 0)}
    if moved:
        _write({'id': item.nodeid, 'refused': moved})


def pytest_unconfigure(config):
    d = os.environ.get('SLICE_SUITE_OUT')
    if d and os.environ.get('SLICE_DISCARD_REAL'):
        import term_discard as TD
        with open(os.path.join(d, f'discard.{os.getpid()}.json'), 'w') as f:
            json.dump(dict(counts=TD.COUNTS, left=TD.LEFT, examples=TD.EXAMPLES), f, indent=0, sort_keys=True)
