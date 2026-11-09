"""State step, part 2 (ii): the solver and the transfer engagement held in the session core (session.rs `SessionCore.solver`,
`session_xfer`, `xfer`).

`_engage_transfer` used to write `rel.xfer_sel`, `rel._xadapter`, `rel.xfer` and `s.xfer = rel` as Python attributes, and
`sync_transfer`/`_xswitch`/`_transfer_terms` read them and `s.solver` back. The core now holds them; Rust reads them natively,
and Python reads `Session.xfer` and `Relations.xfer`/`xfer_sel`/`_xadapter` through views whose writes go to the core's record
methods (`set_xfer_rel`, `set_xfer_field`). Here, in one process per run:
- the guard no workload reaches: the record is per `Relations`, so a second `Relations` on an engaged session reads None;
- the record methods: Python's sequence of writes (`__init__`'s Nones, then `_engage_transfer`'s four, then a test's write of one
  field) reads back as Python's attributes would, field by field;
- the GC traversal: a dropped engaged session is collected.
Each plant (relations_core.rs 257-262) must fire, and each one this file reaches must move a case; the others are named in
`ELSEWHERE` with where they're caught.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLANTS = ('xf-session-none', 'xf-sel-none', 'xf-rel-any', 'xf-solver-fresh', 'xf-rel-view-none', 'xf-traverse-skip')
ELSEWHERE = {
    'xf-solver-fresh': 'test_relations_core.py (the recorded clauses go to the session\'s solver, not the core\'s) and fuzz',
}


def _child():
    from test_relations_core import _rust
    _rust()
    import gc
    import weakref
    from satassume.engine import Engine, Session
    from satassume.relations import Relations
    import sa_solver
    out = {}

    def engaged():
        eng = Engine()
        eng.transfer = True
        s = Session(eng)
        rel = Relations(s, eng._relation_specs)
        s.relations = rel
        rel._engage_transfer()
        return eng, s, rel

    eng, s, rel = engaged()
    other = Relations(s, eng._relation_specs)
    out['engaged'] = [rel.xfer is not None, rel.xfer_sel is not None, rel._xadapter is not None, s.xfer is rel]
    out['other'] = [other.xfer is None, other.xfer_sel is None, other._xadapter is None]
    # A test's write of one field (test_relations_core's `_congruent` cases set `_xadapter` alone): only that field moves.
    marker = object()
    other._xadapter = marker
    out['record-one'] = [other._xadapter is marker, other.xfer is None, other.xfer_sel is None, rel._xadapter is not marker,
                         s.xfer is rel]
    other._xadapter = None
    out['record-none'] = [other._xadapter is None]
    s.xfer = None
    out['session-none'] = [s.xfer is None, rel.xfer is not None]
    s.xfer = rel
    out['session-back'] = [s.xfer is rel]
    # The GC: a dropped engaged session, with its core's solver and records, is collected.
    gc.collect()
    _, s2, rel2 = engaged()
    w = weakref.ref(s2)
    del s2, rel2, _
    gc.collect()
    out['collected'] = [w() is None]
    # ... and one whose record reaches back to its shell (an adapter holding the session), a cycle only the core's
    # traversal shows the collector. The engaged path above makes none: `rel.session` is a proxy.
    _, s3, rel3 = engaged()

    class Holder:
        pass
    h = Holder()
    h.s = s3
    rel3._xadapter = h
    w3 = weakref.ref(s3)
    del s3, rel3, h, _
    gc.collect()
    out['collected-cycle'] = [w3() is None]
    c = sa_solver.session_counts()
    out['counts'] = {k: v for k, v in c.items() if k.startswith('xf:')}
    print(json.dumps(out))


def _run(plant=None):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    env.pop('SLICE_SESSION_PLANT', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    r = subprocess.run([sys.executable, os.path.abspath(__file__), 'child'], env=env, capture_output=True, text=True,
                       timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope='module')
def clean():
    return _run()


def test_clean(clean):
    for k, v in clean.items():
        if k == 'counts':
            # Each counter of this part fires here (a zero on a workload then means something).
            assert all(n > 0 for n in v.values()) and len(v) == 6, v
        else:
            assert all(v), (k, v)


@pytest.mark.parametrize('plant', [p for p in PLANTS if p not in ELSEWHERE])
def test_plant_moves_a_case(clean, plant):
    got = _run(plant)
    moved = [k for k in clean if k != 'counts' and got[k] != clean[k]]
    assert moved, plant


if __name__ == '__main__' and sys.argv[1:] == ['child']:
    _child()
