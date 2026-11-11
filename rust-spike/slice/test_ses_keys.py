"""The part 3 follow-up, item 2: a session dict (ses_cont.rs `SesDict`) finds an object it has already resolved by identity,
with no `hash()` (counted `sc:key_id`), and still behaves as the Python dict it replaces: the first key object is the one
held, a deleted key set again goes last with its new object, an equal object of its own is found by `hash()` and `==`.

Each case runs the same operations on a plain dict and on `Session.demand` (the Rust view) and compares every result.
Plant 615 `sc-key-id-stale` (the memo ignores the entry's generation) gives a deleted key's old object the value of the
key set after it at the same index: the comparison with the plain dict catches it.

The planner's conditions on the memo (11 Nov): (a) it holds each object, so an address isn't reused while its row lives;
(c) it is per dict, never process-wide. `_reuse` looks up short-lived objects, each freed before the next is made, so
CPython hands their addresses on: plant 616 `sc-key-id-weak` (no reference held) gives a new object a freed one's row.
`_two` uses one dict in each of two sessions: plant 617 `sc-key-id-shared` (one memo for all) finds an object set in the
first in the second. Each is compared with plain dicts, which no plant touches.

The planner's ruling (2) on 293's deviations: the memo keeps each object it looked up alive for its session, which is
acceptable only if no session outlives its query. `_queries` asks contextual and plain queries through `sympy_api.ask` and
reads gauge 701 `sc:ses_live` (the sessions' containers alive, ses_cont.rs) after each, with `gc.collect()` first: 0 each
time, while `Engine.stats['sessions']` shows sessions were made. The control is plant 222 `ctx-sessions-store` (context.rs
keeps each contextual session in `_context_sessions`, as the reuse design before #97 P1 did): the gauge then stays above 0.
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


def _reuse(d):
    held = K(1)
    d[held] = 'a'
    out = []
    for n in range(200):
        out.append(d.get(K(1000 + n), 'missing'))     # a miss; the object is freed when the call returns
        out.append(d.get(K(1), 'missing'))            # an equal object, often at the freed one's address
        out.append(d.get(K(2000 + n), 'missing'))     # likewise after a hit
    return out


def _two(d1, d2):
    a, b = K(1), K(2)
    d1[a] = 'x'
    d2[b] = 'y'
    return [d2.get(a, 'missing'), d1.get(b, 'missing'), d1.get(a), d2.get(b), a in d2, b in d1]


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
    out['py_reuse'] = _reuse({})
    out['rust_reuse'] = _reuse(Session(Engine(cache=DictCache(), uninterpreted='none')).demand)
    out['py_two'] = _two({}, {})
    s1, s2, s3 = (Session(Engine(cache=DictCache(), uninterpreted='none')) for _ in range(3))
    out['rust_two'] = _two(s1.demand, s2.demand)
    out['rust_two_one_session'] = _two(s3.pending, s3.demand)
    out['fired'] = dict(sa_solver.session_counts()).get('rel:plant_fired', 0) - before.get('rel:plant_fired', 0)
    print(json.dumps(out))


def _queries():
    import gc
    from test_relations_core import _rust
    _rust()
    import sa_solver
    from sympy import Q, Symbol
    from satassume.engine import DictCache, Engine
    from satassume.sympy_api import ask
    x, y = Symbol('x'), Symbol('y')
    e = Engine(cache=DictCache(), uninterpreted='none')
    qs = [(Q.positive(x + 1), Q.positive(x)), (Q.negative(x * y), Q.positive(x) & Q.positive(y)), (Q.real(x), True),
          (Q.positive(x), Q.positive(x) & Q.negative(x)), (Q.nonzero(x * y), Q.positive(x) & Q.negative(y)),
          (Q.positive(x + y), Q.positive(x) & Q.positive(y))]
    out = dict(answers=[], live=[], sessions=0)
    s0 = e.stats['sessions']
    for prop, assume in qs:
        try:
            out['answers'].append(str(ask(prop, assume, engine=e)))
        except ValueError as exc:                  # inconsistent assumptions
            out['answers'].append(type(exc).__name__)
        gc.collect()
        out['live'].append(dict(sa_solver.session_counts())['sc:ses_live'])
    out['sessions'] = e.stats['sessions'] - s0
    out['peak'] = dict(sa_solver.session_counts())['sc:memo_peak']
    print(json.dumps(out))


def _run(plant=None, child='child'):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    env.pop('SLICE_SESSION_PLANT', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    r = subprocess.run([sys.executable, os.path.abspath(__file__), child], env=env, capture_output=True, text=True,
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


def test_memo_holds_its_objects_and_is_per_dict():
    got = _run()
    assert got['rust_reuse'] == got['py_reuse'], got['rust_reuse'][:12]
    assert got['rust_two'] == got['py_two'] == got['rust_two_one_session'], got


def test_key_id_weak_plant_is_caught():
    got = _run('sc-key-id-weak')
    assert got['fired'] > 0, got
    assert got['rust_reuse'] != got['py_reuse']


def test_key_id_shared_plant_is_caught():
    got = _run('sc-key-id-shared')
    assert got['fired'] > 0, got
    assert got['rust_two'] != got['py_two'] and got['rust_two_one_session'] != got['py_two'], got


def test_key_id_stale_plant_is_caught():
    got = _run('sc-key-id-stale')
    assert got['counts']['rel:plant_fired'] > 0, got
    assert got['rust'] != got['py'], got['rust']


def test_no_session_outlives_its_query():
    got = _run(child='queries')
    assert got['sessions'] > 0 and got['peak'] > 0, got        # sessions were made, and their memos used
    assert got['live'] == [0] * len(got['live']), got


def test_a_kept_session_is_seen_between_queries():
    """The control: plant 222 keeps each contextual session past its query, and the gauge sees it."""
    got = _run('ctx-sessions-store', child='queries')
    assert got['live'][-1] > 0, got
    assert got['answers'] == _run(child='queries')['answers'], got


if __name__ == '__main__' and sys.argv[1:2] == ['queries']:
    _queries()
if __name__ == '__main__' and sys.argv[1:2] == ['child']:
    _child(sys.argv[2] if len(sys.argv) > 2 else 'rust')
