"""Step 5a's limits, Python against rust mode, each in its own process: what comes back, the clause stream, and the table.

Depth guard (`FORMULA_DEPTH` in session.rs) and conversion errors both end in Python's compiler over the same table, because
nothing has been emitted when conversion stops. `refuse:*` shows each path ran, since a MATCH on a path that never ran says
nothing. Within a few frames of Python's own limit the two differ by construction: see `test_threshold_is_near_pythons`.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _rust():
    import backend
    backend.install_euf()
    backend.install_transfer()
    import term_live
    term_live.from_env()
    import lra_live
    lra_live.from_env()
    import session_live
    session_live.from_env()
    return session_live


SHAPES = ('orand', 'notor', 'implies')


def _deep(shape, d):
    from satassume.sat.formula import And, Implies, Not, Or, P
    f = P('real', 'x0')
    for i in range(d):
        a = P('positive', f'y{i}')
        f = {'orand': lambda: (And if i % 2 else Or)(f, a), 'notor': lambda: Not(Or(f, a)), 'implies': lambda: Implies(f, a)}[shape]()
    return f


def _case(fn):
    from satassume.engine import Engine, Session
    s = Session(Engine())
    clauses = []
    add = s.solver.add_clause

    def rec(c):
        clauses.append(list(c))
        return add(c)
    s.solver.add_clause = rec
    try:
        out = ['ok', repr(fn(s))]
    except BaseException as e:
        out = [type(e).__name__, str(e)]
    t = s.table
    return dict(out=out, clauses=clauses, n=len(t), naux=t.naux, true_var=t.true_var, atoms=[repr(a) for a in t.atom_of])


def _compile_direct(f):
    import satassume.engine as E
    return lambda s: E.compile_formula(f, s.table, s.emit, s.dvar)


def _literal_direct(f):
    import satassume.engine as E
    return lambda s: E.formula_literal(f, s.table, s.emit, s.dvar)


def _cases():
    from satassume.sat.formula import And, Implies, Or, P

    class Stop(BaseException):
        pass

    class BadArgs(And):
        def __init__(self):
            pass

        @property
        def args(self):
            raise Stop('from args')
    a, b, c = P('real', 'a'), P('positive', 'b'), P('zero', 'c')
    bad = P('real', ['l'])
    out = {}
    for shape in SHAPES:
        for d in (1, 10, 63, 64, 65, 66, 100, 300, 3500):
            f = _deep(shape, d)
            out[f'assume:{shape}:{d}'] = lambda s, f=f: s.assume_formula(f)
            out[f'literal_of:{shape}:{d}'] = lambda s, f=f: s.literal_of(f)
    out.update({
        # Emitted before the bad atom on Python: the point of this limit is that those clauses still appear, first.
        'unhashable:compile': _compile_direct(And(a, Or(b, c), Implies(b, a), bad)),
        'unhashable:literal': _literal_direct(Or(a, Implies(b, c), bad)),
        'unhashable:assume': lambda s: s.assume_formula(And(a, Or(b, c), bad)),
        'unhashable:literal_of': lambda s: s.literal_of(Or(a, bad)),
        'pred-int:assume': lambda s: s.assume_formula(And(a, P(5, 'b'))),
        'pred-int:literal_of': lambda s: s.literal_of(Or(a, P(5, 'b'))),
        'pred-int:compile': _compile_direct(And(a, P(5, 'b'))),
        'pred-joined': lambda s: s.assume_formula(And(P(1, 'b'), P(1.0, 'b'))),
        'pred-joined-across-nodes': lambda s: s.assume_formula(And(P(1, 'b'), P(True, 'c'))),
        # Limit 3: objects `==` across classes, first seen in different orders.
        'node-joined': lambda s: s.assume_formula(And(P('real', 1), P('positive', 1.0), P('zero', True))),
        'node-joined:or': lambda s: s.literal_of(Or(P('real', 1.0), P('positive', 1), P('zero', True))),
        'node-joined:custom': lambda s: s.assume_formula(And(P('mine', 1.0), P('mine', 1), P('real', True))),
        'pred-none': lambda s: s.literal_of(Or(a, P(None, 'b'))),
        'pred-list:assume': lambda s: s.assume_formula(And(a, P(['p'], 'b'))),
        'pred-list:compile': _compile_direct(And(a, Or(b, c), P(['p'], 'b'))),
        'pred-custom-str': lambda s: s.assume_formula(And(a, P('mine', 'b'), P('mine', 'c'))),
        'not-a-formula': lambda s: s.assume_formula(And(a, 7)),
        'not-a-formula:compile': _compile_direct(And(a, Or(b, c), 7)),
        'stop-from-args': _compile_direct(BadArgs()),
    })
    return out


def _main(mode):
    live = _rust() if mode == 'rust' else None
    got = {k: _case(fn) for k, fn in _cases().items()}
    report = dict(cases=got, counts=live.counts() if live else None)
    json.dump(report, sys.stdout)


def _run(mode):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    r = subprocess.run([sys.executable, __file__, mode], capture_output=True, text=True, env=env, cwd=HERE)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


@pytest.fixture(scope='module')
def both():
    return _run('py'), _run('rust')


def _ids():
    # Named without importing the engine at collection.
    names = [f'{e}:{s}:{d}' for s in SHAPES for d in (1, 10, 63, 64, 65, 66, 100, 300, 3500) for e in ('assume', 'literal_of')]
    return names + ['unhashable:compile', 'unhashable:literal', 'unhashable:assume', 'unhashable:literal_of', 'pred-int:assume',
                    'pred-int:literal_of', 'pred-int:compile', 'pred-joined', 'node-joined', 'node-joined:or', 'node-joined:custom', 'pred-none', 'pred-list:assume',
                    'pred-list:compile', 'pred-custom-str', 'not-a-formula', 'not-a-formula:compile', 'stop-from-args']


@pytest.mark.parametrize('name', _ids())
def test_same_as_python(both, name):
    py, rust = both
    assert rust['cases'][name] == py['cases'][name]


def test_pred_joined_across_nodes_differs_only_in_shown_pred(both):
    """Named difference. Python's atom keeps the `pred` object it was first made with, per atom; Rust keeps one per predicate
    id. `1` and `True` are `==` with one hash, so no dict lookup can tell them apart, and only the shown form differs."""
    py, rust = (b['cases']['pred-joined-across-nodes'] for b in both)
    assert py['atoms'][-1] == 'True(c)' and rust['atoms'][-1] == '1(c)'
    assert {k: v for k, v in py.items() if k != 'atoms'} == {k: v for k, v in rust.items() if k != 'atoms'}


def test_cases_exercise_what_they_name(both):
    py = both[0]['cases']
    # An error after clauses: without these the test couldn't see an error that moved earlier.
    for name in ('unhashable:compile', 'unhashable:literal', 'pred-list:compile', 'not-a-formula:compile'):
        assert py[name]['out'][0] == 'TypeError' and py[name]['clauses'], name
    assert py['pred-int:assume']['out'][0] == 'ok'
    assert py['stop-from-args']['out'][0] == 'Stop'
    for shape in SHAPES:
        assert py[f'assume:{shape}:3500']['out'][0] == 'RecursionError'
        assert py[f'assume:{shape}:300']['out'][0] == 'ok' or shape == 'implies'


def test_counters_fired(both):
    c = both[1]['counts']
    assert c['refuse:depth'] > 0 and c['refuse:convert'] > 0 and c['rs:emit_callback'] > 0


def _depth_ok(shape, d, entry):
    from satassume.engine import Engine, Session
    try:
        getattr(Session(Engine()), entry)(_deep(shape, d))
        return True
    except RecursionError:
        return False


def _threshold(shape, entry):
    lo, hi = 1, 4000
    while hi - lo > 1:
        m = (lo + hi) // 2
        if _depth_ok(shape, m, entry):
            lo = m
        else:
            hi = m
    return hi


def _thresholds(mode):
    if mode == 'rust':
        _rust()
    json.dump({f'{s}:{e}': _threshold(s, e) for s in SHAPES for e in ('assume_formula', 'literal_of')}, sys.stdout)


def test_threshold_is_near_pythons():
    """Not reproduced, by ruling: it depends on the caller's stack. Frames differ by the shell's own and by the views', so it
    moves a little, but it stays far above the guard and close to Python's. Printed for the report."""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    got = {}
    for mode in ('py', 'rust'):
        r = subprocess.run([sys.executable, __file__, 'thresholds', mode], capture_output=True, text=True, env=env, cwd=HERE)
        assert r.returncode == 0, r.stderr[-2000:]
        got[mode] = json.loads(r.stdout)
    print(got)
    for k, v in got['py'].items():
        assert v > 3 * 64 and abs(got['rust'][k] - v) <= 5, (k, v, got['rust'][k])


if __name__ == '__main__':
    if sys.argv[1] == 'thresholds':
        _thresholds(sys.argv[2])
    else:
        _main(sys.argv[1])
