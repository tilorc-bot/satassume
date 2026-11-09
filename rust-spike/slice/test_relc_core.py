"""State step, part 2 (iii)(b): Relations' scalar cursors held in the session core (session.rs `SessionCore.relc`, `RC_NAMES`).

`_xtcur`, `_xhn`, `_xhseen`, `_xslot`, `_xterm`, `_xnsides` and `_xsides_n` were Python ints on each `Relations`, written by
rel_init and read and written by relations_core.rs's `_transfer_terms`, `sync_transfer` and `_note_sides` through the C API.
The core now holds them; Rust reads them natively, and Python reads them through views whose writes go to the core's record
method (`set_relc_field`). Here, one process per run:
- the switch: the same queries on Python (each `Relations`' own attributes, the old state) and on Rust (the core's test-only
  snapshot export `relc_snapshot`, and the views), after every query; the digests must be equal, and the cursors must move;
- the record method: Python's sequence of writes (`__init__`'s seven, then a test's `+= 1`) reads back as Python's would;
- the plants (relations_core.rs 266-267) each move a case; the counters (rc:*, 347-349) each fire.
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ('_xtcur', '_xhn', '_xhseen', '_xslot', '_xterm', '_xnsides', '_xsides_n')
PLANTS = ('rc-xterm-stale', 'rc-hseen-stale')
WLS = ('transfer:7:60', 'transfer2:3:40', 'fuzz:200', 'scope')


def _queries(wl):
    import live
    if wl.startswith('fuzz:'):
        return list(live.load('fuzz'))[:int(wl.split(':')[1])]
    return list(live.load(wl))


def _child(mode):
    if mode == 'rust':
        from test_relations_core import _rust
        sl = _rust()
    from satassume import sympy_api
    from satassume.relations import Relations
    made = []
    init = Relations.__init__

    def tracked(self, *a, **k):
        r = init(self, *a, **k)
        t = getattr(a[0], 'table', None) if mode == 'rust' else None
        made.append((self, getattr(t, 'core', None)))    # the session goes with its query; its core is kept here
        return r
    Relations.__init__ = tracked
    out = dict(rows=[], moved=0, in_dict=0, view_eq=True)
    for wl in WLS:
        for i, (p, a) in enumerate(_queries(wl)):
            del made[:]
            try:
                sympy_api.ask(p, a)
            except Exception as e:
                pass
            row = []
            for rel, core in made:
                if mode == 'rust':
                    snap = [d for r, d in core.relc_snapshot() if r is rel]
                    out['in_dict'] += any(n in rel.__dict__ for n in NAMES)
                    vals = [snap[0][n] for n in NAMES] if snap else None
                    try:
                        view = [getattr(rel, n) for n in NAMES]
                    except ReferenceError:      # the view reads through `rel.session`, gone with its query
                        view = vals
                    if vals is not None and vals != view:
                        out['view_eq'] = False
                else:
                    vals = [rel.__dict__.get(n) for n in NAMES]
                out['moved'] += vals is not None and vals != [0, 0, -1, 1, 0, -1, 0]
                row.append(vals)
            out['rows'].append([wl, i, row])
    Relations.__init__ = init
    out['digest'] = hashlib.blake2b(json.dumps(out['rows']).encode(), digest_size=8).hexdigest()
    out['n'] = len(out['rows'])
    if mode == 'rust':
        # The record method: Python's own writes, through the views.
        from satassume.engine import Engine, Session
        eng = Engine()
        s = Session(eng)
        rel = Relations(s, eng._relation_specs)
        first = [getattr(rel, n) for n in NAMES]
        rel._xsides_n += 1
        rel._xslot = 7
        out['record'] = [first == [0, 0, -1, 1, 0, -1, 0], rel._xsides_n == 1, rel._xslot == 7,
                         not any(n in rel.__dict__ for n in NAMES)]
        import sa_solver
        out['counts'] = {k: v for k, v in sa_solver.session_counts().items() if k.startswith('rc:')}
    del out['rows']
    print(json.dumps(out))


def _run(mode, plant=None):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    env.pop('SLICE_SESSION_PLANT', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    r = subprocess.run([sys.executable, os.path.abspath(__file__), 'child', mode], env=env, capture_output=True, text=True,
                       timeout=1800)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope='module')
def py():
    return _run('py')


@pytest.fixture(scope='module')
def rust():
    return _run('rust')


def test_snapshot_digest_equal_at_the_switch(py, rust):
    assert py['moved'] > 0 and py['n'] == rust['n']
    assert rust['digest'] == py['digest'], (py, rust)
    assert rust['in_dict'] == 0 and rust['view_eq']


def test_record_method_and_counters(rust):
    assert all(rust['record']), rust['record']
    assert len(rust['counts']) == 3 and all(v > 0 for v in rust['counts'].values()), rust['counts']


@pytest.mark.parametrize('plant', PLANTS)
def test_plant_moves_the_digest(rust, plant):
    got = _run('rust', plant)
    assert got['digest'] != rust['digest'], plant


if __name__ == '__main__' and sys.argv[1:2] == ['child']:
    _child(sys.argv[2])
