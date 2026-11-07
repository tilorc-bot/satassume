"""Step 5c1: `Session`'s discovery (`ensure`, `discover`, `_discover`, `incomplete`, `escalate`) called directly on forged state,
Python against Rust's `discovery.rs`, each mode in its own process. A case records what came back, every clause in order, and
the session's discovery state after: `base`, `frontier`, `deferred`, `pending`, `pending_c`, `demand`, `truncated`, `incomplete`.

The workloads never give `discover`'s `_flush` anything to do (new nodes and custom atoms are already visited by then), and the
engine passes `escalate` no budget, so `drop-discover-flush`, `truncated-never` and the `drop-esc-*` plants can't be caught there.
Here the state is forged: formulas compiled straight into the table leave new nodes and custom atoms for `_flush`, and `escalate`
runs under every budget from 0 up. Each plant must fire and move some case.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLANTS = ('drop-ensure-demand', 'drop-discover-flush', 'drop-discover-visit', 'drop-esc-pattern', 'drop-esc-compile',
          'drop-esc-deferred', 'truncated-never', 'incomplete-never')


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


#: every subterm of the cases' terms: Rust's `Session.base` is read by key and length only, so it's read over these.
NODES = []


def _state(s):
    return dict(
        base=sorted([str(k), s.base[k]] for k in set(NODES) if k in s.base), nbase=len(s.base),
        frontier=[str(n) for n in s.frontier],
        deferred=[str(n) for n in s.deferred],
        pending=sorted([str(k), [repr(f) for f in v]] for k, v in s.pending.items()),
        pending_c=sorted([str(k), len(v)] for k, v in s.pending_c.items()),
        demand=sorted([str(k), sorted(v)] for k, v in s.demand.items()),
        truncated=bool(s.truncated), incomplete=bool(s.incomplete), solver=_digest(s.solver))


def _digest(solver):
    """The Python solver's whole state, as `live.py --check entry` hashes it: patterns go in by `add_internal`, not `add_clause`."""
    import state
    from satassume.sat import solver as SV
    return state.digest(dict(sorted(state.with_euf(state.dump_py, SV.Solver.theories)(solver).items())))


def _case(fn):
    from satassume.engine import Engine, Session
    s = Session(Engine())
    clauses = []
    add = s.solver.add_clause

    def rec(c):
        clauses.append(list(c))
        return add(c)
    s.solver.add_clause = rec
    internal = s.solver.add_internal

    def rec_internal(cls, ment):
        clauses.append(['internal', [list(c) for c in cls], [list(m) for m in ment]])
        return internal(cls, ment)
    s.solver.add_internal = rec_internal
    steps = []
    try:
        for name, step in fn(s):
            steps.append([name, repr(step()), len(clauses), _state(s)])
        out = 'ok'
    except BaseException as e:
        out = [type(e).__name__, str(e)]
    return dict(out=out, steps=steps, clauses=clauses)


def _cases():
    from sympy import Add, Symbol, gamma, log, sin
    from satassume.knowledge.extensions import unregister
    import satassume.engine as E
    from satassume.sat.formula import And, Or, P
    from sympy import preorder_traversal
    x, y, z, w = (Symbol(c) for c in 'xyzw')
    for t in ((x + y)**2 + sin(z), x * y, w - 1, x * y * sin(z + w), sin(x + y) + z * w, z * w, y * z, sin(y * z), x * y + sin(z),
              (z * w)**2, (x + y) * sin(w) + z**2, sin(x * z) - w, log(x) + gamma(y) + x**y, sin(x + y) + z):
        NODES.extend(preorder_traversal(t))

    def compiled(f):
        return lambda s: E.compile_formula(f, s.table, s.emit, s.dvar)

    def parked(s):
        """A session with parked patterns and formulas and deferred nodes: assumptions over nested terms, nodes ensured."""
        yield 'assume', lambda: s.assume_formula(And(P('positive', (x + y)**2 + sin(z)), Or(P('integer', x * y), P('zero', w - 1))))
        yield 'ensure', lambda: s.ensure(x * y * sin(z + w))
        yield 'literal_of', lambda: s.literal_of(P('negative', sin(x + y) + z * w))
        # demanded: the node's other templates are parked in `pending` for `escalate`
        yield 'ensure-demanded', lambda: s.ensure((x + y) * sin(w) + z**2, ['positive'])
        yield 'ensure-demanded', lambda: s.ensure(sin(x * z) - w, ['integer'])
        # derived nodes go to `deferred`
        yield 'ensure-demanded', lambda: s.ensure(log(x) + gamma(y) + x**y, ['positive'])

    def registered(s):
        """A vocabulary function registered for `Add`: its formulas are items, parked in `pending` under a demand."""
        from satassume.knowledge.extensions import register

        def even(n):
            return And(P('even', n.args[0]), P('even', n.args[1]))
        yield 'register', lambda: register('even', Add)(even) and None
        yield from parked(s)
        yield 'ensure-demanded', lambda: s.ensure(sin(x + y) + z, ['negative'])

    out = {}
    for name, f in {'nodes': And(P('positive', x + y), P('real', z * w)),
                    'custom': And(P('mine', x), P('real', x)),
                    'custom-on-new-node': Or(P('mine', y * z), P('positive', sin(y * z)))}.items():
        out[f'discover:{name}'] = lambda s, f=f: [('compile', lambda: compiled(f)(s)), ('discover', s.discover)]
        out[f'discover-twice:{name}'] = lambda s, f=f: [('compile', lambda: compiled(f)(s)), ('discover', s.discover),
                                                       ('discover', s.discover)]
    out['ensure:plain'] = lambda s: [('ensure', lambda: s.ensure(x * y + sin(z)))]
    for preds in (['positive'], ['integer', 'real'], ['zero']):
        out[f'ensure:demanded:{"+".join(preds)}'] = lambda s, p=preds: [('ensure', lambda: s.ensure(x * y + sin(z), p))]
        out[f'ensure:then-demanded:{"+".join(preds)}'] = lambda s, p=preds: [
            ('ensure', lambda: s.ensure(x * y + sin(z))), ('ensure', lambda: s.ensure(x * y + sin(z), p)),
            ('ensure', lambda: s.ensure(x * y, p))]
    out['ensure:after-compile'] = lambda s: [('compile', lambda: compiled(P('positive', x + y))(s)),
                                             ('ensure', lambda: s.ensure(x + y, ['positive']))]
    for budget in list(range(0, 13)) + [20, 40, None]:
        out[f'escalate:{budget}'] = lambda s, b=budget: list(parked(s)) + [
            ('incomplete', lambda: s.incomplete), ('escalate', lambda: s.escalate(b)), ('incomplete', lambda: s.incomplete)]
        out[f'escalate-registered:{budget}'] = lambda s, b=budget: list(registered(s)) + [
            ('incomplete', lambda: s.incomplete), ('escalate', lambda: s.escalate(b)), ('incomplete', lambda: s.incomplete),
            ('unregister', lambda: unregister('even'))]
        out[f'escalate-after-compile:{budget}'] = lambda s, b=budget: [
            ('compile', lambda: compiled(And(P('positive', x + y), P('mine', sin(z)), P('real', (z * w)**2)))(s)),
            ('escalate', lambda: s.escalate(b)), ('incomplete', lambda: s.incomplete)]
    out['escalate:twice'] = lambda s: list(parked(s)) + [('escalate', lambda: s.escalate(2)), ('escalate', lambda: s.escalate(3)),
                                                         ('escalate', lambda: s.escalate())]
    return out


def _main(mode):
    live = _rust() if mode == 'rust' else None
    got = {k: _case(fn) for k, fn in _cases().items()}
    json.dump(dict(cases=got, counts=live.counts() if live else None), sys.stdout)


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


def test_cases_run_and_reach_what_they_say(both):
    """No case raised; `_flush` had new nodes and custom atoms to schedule; some budget truncated and some didn't."""
    py, rust = both
    assert all(c['out'] == 'ok' for c in py['cases'].values())
    steps = {k: c['steps'] for k, c in py['cases'].items()}
    # discover visited the compiled nodes (`_flush` scheduled them): base grew across the discover step.
    assert all(len(st[1][3]['base']) > len(st[0][3]['base']) for k, st in steps.items() if k.startswith('discover:'))
    assert any(st[-2][3]['truncated'] for k, st in steps.items() if k.startswith('escalate:'))
    assert not steps['escalate:None'][-2][3]['truncated'] and not steps['escalate:None'][-1][3]['incomplete']
    assert steps['escalate:0'][-3][1] == 'True'
    c = rust['counts']
    assert all(c[f'ses:{m}'] > 0 for m in ('ensure', 'discover', 'escalate', 'incomplete'))


@pytest.mark.parametrize('plant', PLANTS)
def test_each_plant_fires_and_is_seen(both, plant):
    py, _ = both
    got = _run('rust', SLICE_SESSION_PLANT=plant)
    assert got['counts']['rel:plant_fired'] > 0
    assert _differ(py, got) != []


if __name__ == '__main__':
    _main(sys.argv[1])
