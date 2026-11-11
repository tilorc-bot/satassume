"""The part 3 follow-up, item 2: a session dict (ses_cont.rs `SesDict`) finds an object it has already resolved by identity,
with no `hash()` (counted `sc:key_id`), and still behaves as the Python dict it replaces: the first key object is the one
held, a deleted key set again goes last with its new object, an equal object of its own is found by `hash()` and `==`.

Each case runs the same operations on a plain dict and on `Session.demand` (the Rust view) and compares every result.
Plant 615 `sc-key-id-stale` (the memo ignores the entry's generation) gives a deleted key's old object the value of the
key set after it at the same index: the comparison with the plain dict catches it.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


class K:
    """`==` by value; each `hash()` is logged."""
    calls = []

    def __init__(self, v):
        self.v = v

    def __eq__(self, other):
        return isinstance(other, K) and other.v == self.v

    def __hash__(self):
        K.calls.append(self.v)
        return hash(self.v)


def _ops(d):
    a, a2, c = K(1), K(1), K(2)
    out = []
    d[a] = 'x'
    out.append(('get a x3', [d[a], d[a], d[a]]))
    out.append(('get a2 (equal object)', d[a2]))
    d[a2] = 'y'                                    # a present key set again keeps its object (a) and place
    out.append(('first key held', [k is a for k in d.keys()], d[a]))
    del d[a2]
    d[c] = 'z'                                     # a's entry is gone; c lands where it was
    out.append(('a after delete', d.get(a, 'missing'), a in d))
    d[a2] = 'w'
    out.append(('order and objects', [(k.v, k is a2) for k in d.keys()], d[a], d[c]))
    return out


def _child(mode):
    from test_relations_core import _rust
    _rust()
    import sa_solver
    from satassume.engine import DictCache, Engine, Session
    s = Session(Engine(cache=DictCache(), uninterpreted='none'))
    view = s.demand
    out = dict(view=type(view).__name__)
    K.calls.clear()
    out['py'] = _ops({})
    out['py_hashes'] = len(K.calls)
    before = dict(sa_solver.session_counts())
    K.calls.clear()
    out['rust'] = _ops(view)
    out['rust_hashes'] = len(K.calls)
    after = dict(sa_solver.session_counts())
    out['counts'] = {k: after[k] - before.get(k, 0) for k in ('sc:key_id', 'sc:key_hash', 'sc:key_eq', 'rel:plant_fired')}
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


def test_session_dict_is_a_python_dict_with_fewer_hashes():
    got = _run()
    assert got['view'] == 'SesDictView', got     # the control: the Rust container is the one under test
    assert got['rust'] == got['py'], (got['py'], got['rust'])
    # the repeats of `a` and `a2` go by identity: fewer `hash()` calls than the plain dict made
    assert got['counts']['sc:key_id'] > 0 and got['rust_hashes'] < got['py_hashes'], got
    assert got['rust_hashes'] == got['counts']['sc:key_hash'], got


def test_key_id_stale_plant_is_caught():
    got = _run('sc-key-id-stale')
    assert got['counts']['rel:plant_fired'] > 0, got
    assert got['rust'] != got['py'], got['rust']


if __name__ == '__main__' and sys.argv[1:2] == ['child']:
    _child(sys.argv[2] if len(sys.argv) > 2 else 'rust')
