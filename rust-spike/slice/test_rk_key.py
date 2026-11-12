"""The rk_key step (issue 323, item (b)): relkeys.rs `rk_key` reads the innermost query (term_live's stack top, its `kept` and
table) and the isinstance result once per query, not on every get, set and contains.

That is sound because nothing writes them within a query except the stack's push and pop (a nested ask), and the read is
keyed by the top's identity (relkeys.rs, the block above `innermost`). Here, one process with Rust installed, a session's
Relations set is used:
- outside any query (keys by hash), then in a converted query (a push: a new session keys by term id), then in a kept query
  nested in it (a push within the query: the session going on into it goes dict-only, `rk:outlive`), then back in the
  converted query (the pop: a new session keys by term id again). Each step reads the query from Python once
  (`rk:top_read` 1), however many keys it makes;
- the class join in a converted query: after a Symbol (a Basic, keyed by term id), each `==` pair of a Basic and a non-Basic
  of another class (`Integer(2)` and `2`, `Float(2.0)` and `2.0`, `S.true` and `True`, `Tuple(1, 2)` and `(1, 2)`) is one
  member, as in Python's set.

Plants (SLICE_SESSION_PLANT): 621 `rk-top-once` (once read as having no table, the query is never read again) and 668
`rk-type-once` (the first key's isinstance result is every key's in the query). Each is caught here: the steps' paths and the
set's lengths are behaviour, not the plants' flag (`rel:plant_fired` is the control that each plant ran).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ('rk:term', 'rk:outlive', 'rk:migrate', 'rk:top_read', 'rel:plant_fired')


def _child():
    from test_relations_core import _rust
    _rust()
    import sa_solver
    import term_live
    from sympy import Float, Integer, Q, S, Symbol, Tuple, pi
    from satassume.engine import Engine, Session
    from satassume.relations import Relations
    eng = Engine()
    x, y = Symbol('x'), Symbol('y')
    out = {'steps': {}}

    def step(name, f):
        b = dict(sa_solver.session_counts())
        r = f()
        a = dict(sa_solver.session_counts())
        out['steps'][name] = {'d': {k: a[k] - b[k] for k in KEYS}, 'r': r}

    def fresh():
        s = Session(eng)
        return s, Relations(s, eng._relation_specs)

    s0, r0 = fresh()
    step('outside', lambda: [r0._xcand.add(x), x in r0._xcand, len(r0._xcand)][1:])
    q1 = term_live._convert(Q.positive(x + y + pi + 2), True, eng)     # Integer(2) has a term id; 2.0, True, (1, 2) none
    out['q1_kept'] = q1.kept
    term_live.stack().append(q1)
    try:
        s1, r1 = fresh()
        step('converted', lambda: [[r1._xcand.add(e) for e in (x, y, x + y)], [e in r1._xcand for e in (x, y, x + y, pi)],
                                   len(r1._xcand)][1:])
        term_live.stack().append(term_live._Refused())
        try:
            step('nested-kept', lambda: [r1._xcand.add(pi), [e in r1._xcand for e in (x, y, pi)], len(r1._xcand)][1:])
        finally:
            term_live.stack().pop()
        s2, r2 = fresh()
        step('after-pop', lambda: [r2._xcand.add(x), x in r2._xcand, len(r2._xcand)][1:])
        joins = []
        for a, b in ((Integer(2), 2), (Float(2.0), 2.0), (S.true, True), (Tuple(1, 2), (1, 2))):
            for first, second in ((a, b), (b, a)):
                s3, r3 = fresh()
                r3._xcand.add(x)
                r3._xcand.add(first)
                r3._xcand.add(second)
                joins.append([repr(first), repr(second), len(r3._xcand), len({x, first, second}), second in r3._xcand])
        out['joins'] = joins
    finally:
        term_live.stack().pop()
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


def _paths(got):
    """Where each step's keys went, and how often it read the query from Python."""
    st = got['steps']
    return {n: [st[n]['d']['rk:term'] > 0, st[n]['d']['rk:outlive'], st[n]['d']['rk:migrate'] > 0, st[n]['d']['rk:top_read']]
            for n in st}


def _joins_wrong(got):
    return [j for j in got['joins'] if j[2] != j[3] or not j[4]]


EXPECTED = {'outside': [False, 0, False, 1], 'converted': [True, 0, False, 1], 'nested-kept': [False, 1, True, 1],
            'after-pop': [True, 0, False, 1]}


def test_the_query_is_read_once_per_query_and_again_at_each_push_and_pop():
    got = _run()
    assert got['q1_kept'] is None, got
    assert _paths(got) == EXPECTED, got['steps']
    st = got['steps']
    assert st['converted']['r'] == [[True, True, True, False], 3] and st['nested-kept']['r'] == [[True, True, True], 4], st
    assert sum(s['d']['rel:plant_fired'] for s in st.values()) == 0


def test_a_basic_and_a_non_basic_that_are_equal_are_one_member():
    got = _run()
    assert len(got['joins']) == 8 and _joins_wrong(got) == [], got['joins']


def test_rk_top_once_plant_is_caught():
    got = _run('rk-top-once')
    assert sum(s['d']['rel:plant_fired'] for s in got['steps'].values()) > 0, got['steps']   # the control: it ran
    assert _paths(got) != EXPECTED, got['steps']


def test_rk_type_once_plant_is_caught():
    got = _run('rk-type-once')
    assert _joins_wrong(got), got['joins']


if __name__ == '__main__' and sys.argv[1:] == ['child']:
    _child()
