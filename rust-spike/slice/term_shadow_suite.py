"""The shadow in a suite run, checks on, so every read of every term a query converts is forced: `-p term_shadow_suite`,
with SLICE_SUITE_OUT set. The nan ruling's point 2: read_term_missing for the suite on the lazy tree, and read_raised with
it. Writes one shadow.PID.json per worker, a row per test that missed or raised to shadow-rows.PID.jsonl, and to
shadow-keys.PID.jsonl a row per key the run used at a sort key site that's a product or not an input term: test id, query,
site, args, Pow factors, derived or not, and what became of it (`term_shadow.KEY_HOOK`). The planner's suite ruling reads
those: the census has counts and no ids.

The shadow only sees queries through `sympy_api._ask`, so a test that drives the engine or a theory directly converts
nothing and can't count here. Tests that count calls or assert on timing can fail under it: read its column against the
plain one by id.
"""
import json
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)


def pytest_configure(config):
    import term_shadow
    term_shadow.install()
    term_shadow.install_algebra()
    term_shadow.KEY_HOOK[0] = _key


_keys = [None]
_test = [None]


def _key(site, e, i, outcome):
    import term_shadow as TS
    from sympy import Mul, Pow
    cur = TS.CUR[0]
    derived = None if cur is None or i is None else i >= cur[1].n_input
    TS.COUNTS[f"key-outcome:{site}:{ {None: 'unknown-id', True: 'derived', False: 'input'}[derived] }:{outcome.split(':')[0]}"] += 1
    if not (isinstance(e, Mul) or derived or (outcome == 'unknown')):
        return
    if _keys[0] is None:
        _keys[0] = open(os.path.join(os.environ['SLICE_SUITE_OUT'], f'shadow-keys.{os.getpid()}.jsonl'), 'a')
    pows = sum(isinstance(a, Pow) for a in e.args) if isinstance(e, Mul) else 0
    _keys[0].write(json.dumps(dict(id=_test[0], q=TS.COUNTS['queries'], pid=os.getpid(), site=site, cls=type(e).__name__,
                                   n=len(e.args), pows=pows, derived=derived, outcome=outcome, term=str(e)[:100])) + '\n')
    _keys[0].flush()


KEYS = ('queries', 'converted', 'mismatch', 'convert:read_term_missing', 'convert:read_raised')


def _now():
    import term_shadow
    return {k: term_shadow.COUNTS[k] for k in KEYS}


_last = [None]
_rows = [None]


def pytest_runtest_logstart(nodeid, location):
    _last[0] = _now()
    _test[0] = nodeid


def pytest_runtest_logfinish(nodeid, location):
    now, last = _now(), _last[0]
    if last is None:
        return
    d = {k: now[k] - last[k] for k in KEYS}
    if d['mismatch'] or d['convert:read_term_missing'] or d['convert:read_raised']:
        if _rows[0] is None:
            _rows[0] = open(os.path.join(os.environ['SLICE_SUITE_OUT'], f'shadow-rows.{os.getpid()}.jsonl'), 'a')
        _rows[0].write(json.dumps(dict(id=nodeid, **d)) + '\n')
        _rows[0].flush()


def pytest_unconfigure(config):
    import term_shadow
    term_shadow.report(os.path.join(os.environ['SLICE_SUITE_OUT'], f'shadow.{os.getpid()}.json'))
