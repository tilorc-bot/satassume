"""State step, part 1: lra_live `_memoized` on the Rust adapter (adapters.rs `LraQuery`).

On a query with a table, `LRAAdapter.interpret`/`order_sides`/`integer_form` answer from the adapter's own slot: the query's
table, ids and objects, the atoms' term ids and the results, keyed by kind, the argument's identity and `GENERIC_CONSTANTS`.
Here, on cert_wl's queries plus a few with integer forms, in one process per run:
- answers, Python against Rust;
- the test-only snapshot export (`sa_solver.ad_lra_export`, every slot entry as it's stored; adapters die with their sessions,
  so slots can't be read after the query): each entry against lra_live's own function on the same query, and the digest of
  the slot's results equal to the digest of lra_live's (the switch's digest);
- the two guards no workload reaches, directly: a `GENERIC_CONSTANTS` flip inside a query is served that flag's result, and a
  patched `_memoized` is called rather than bypassed.
Each plant (relations_core.rs 251-255) must fire, and each one this file reaches must move a case; the others are named in
`ELSEWHERE` with where they're caught.
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLANTS = ('ad-lra-kind-key', 'ad-lra-slot-stale', 'ad-lra-flag-key', 'ad-lra-patch-guard', 'ad-lra-pair-swap')
#: plants this file doesn't move, with where they're caught
ELSEWHERE = {}


def _queries():
    from sympy import Q, Symbol, cos, log, pi, sqrt
    import cert_wl
    x, y = Symbol('x', real=True), Symbol('y', real=True)
    out = list(cert_wl.queries())
    out += [(Q.positive(x + y), Q.positive(x) & Q.positive(y)),
            (Q.lt(x, 2 * y + 1), Q.lt(x, y) & Q.positive(y)),
            (Q.lt(x + pi, 4), Q.lt(x, 0)),
            (Q.ge(2 * x + 3 * y, 1), Q.ge(x, 1) & Q.ge(y, 0) & Q.integer(x)),
            # closed constants other than pi: `GENERIC_CONSTANTS` decides how they linearise (the flag guard's case)
            (Q.lt(x, log(3)), Q.lt(x, 1)), (Q.lt(x + sqrt(2), 3), Q.lt(x, 0)), (Q.gt(x, cos(1)), Q.gt(x, 1))]
    return out


def _typed(x):
    """Each node's class and, at the leaves, its repr: the comparison `lra_live._same` makes, for Rust `Element`s too (they have
    no `==`, and the table builds a new one per read)."""
    if isinstance(x, dict):
        return ('dict', tuple((_typed(k), _typed(v)) for k, v in x.items()))
    if isinstance(x, (tuple, list)):
        return (type(x).__name__, tuple(_typed(y) for y in x))
    if type(x).__name__ == 'Integral' and hasattr(x, '__iter__'):
        return ('Integral:' + type(x).__module__, tuple(_typed(y) for y in x))
    if type(x).__name__ == 'Element':
        # By value: the table hands back a number's cached Python Element once Python's `constant` path has attached one, and
        # Rust's otherwise (Element._new step), so a slot hit and a later read can differ in class only.
        return ('Element', repr(x))
    return (type(x).__module__, type(x).__name__, repr(x))


def _main(mode):
    live = lra_live = term_live = None
    if mode == 'rust':
        import test_discovery_core as D
        live = D._rust()
        import lra_live
        import term_live
        import sa_solver
    from satassume import sympy_api as A
    from satassume.engine import Engine
    from satassume.theories.lra import lra_adapter as L
    e = Engine()
    if mode == 'rust':
        sa_solver.ad_lra_export(True)
    answers = []
    for p, a in _queries():
        try:
            answers.append(str(A.ask(p, a, engine=e)))
        except Exception as x:          # a plant that breaks a result's shape raises here: a moved answer
            answers.append('raised: ' + type(x).__name__)
    cases = {'answers': answers}
    out = dict(cases=cases, counts=live.counts() if live else None)
    if mode == 'rust':
        exported = sa_solver.ad_lra_export(False)
        reads = {0: 'interpret', 1: 'order_sides', 2: 'integer_form'}
        slot_d, py_d, bad = hashlib.sha256(), hashlib.sha256(), []
        flag_case = patch_case = None
        ad = sa_solver.LRAAdapter()             # the guards, on an adapter of our own over the queries' tables
        for q, k, arg, flag, r in exported:
            term_live.stack().append(q)
            try:
                L.GENERIC_CONSTANTS = flag
                theirs = getattr(L, reads[k])(arg)      # lra_live's function, on the same query
                L.GENERIC_CONSTANTS = True
                slot_d.update(repr((k, arg, flag, _typed(r))).encode())
                py_d.update(repr((k, arg, flag, _typed(theirs))).encode())
                if _typed(r) != _typed(theirs):
                    bad.append(repr((k, arg))[:200])
                if k == 0 and flag_case is None:
                    # A flip inside the query is served that flag's result, as lra_live gives it.
                    L.GENERIC_CONSTANTS = False
                    off = L.interpret(arg)
                    L.GENERIC_CONSTANTS = True
                    if _typed(off) != _typed(r):
                        ad.interpret(arg)
                        L.GENERIC_CONSTANTS = False
                        flag_case = _typed(ad.interpret(arg)) == _typed(off)
                if patch_case is None:
                    # A patched `_memoized` is called, not bypassed.
                    calls, saved = [], L._memoized
                    L._memoized = lambda key, read, a: (calls.append(1), saved(key, read, a))[1]
                    try:
                        getattr(ad, reads[k])(arg)
                    finally:
                        L._memoized = saved
                    patch_case = len(calls) == 1
            finally:
                term_live.stack().pop()
                L.GENERIC_CONSTANTS = True
        cases['slot'] = dict(entries=len(exported) > 0, bad=bad[:5], same_digest=slot_d.hexdigest() == py_d.hexdigest(),
                             flag=flag_case, patch=patch_case)
        out['digest'] = slot_d.hexdigest()[:16]
        out['entries'] = len(exported)
        out['counts'] = live.counts()
    json.dump(out, sys.stdout)


def _run(mode, **env):
    e = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]), PYTHONHASHSEED='0', **env)
    r = subprocess.run([sys.executable, __file__, mode], capture_output=True, text=True, env=e, cwd=HERE)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


@pytest.fixture(scope='module')
def both():
    return _run('py'), _run('rust')


GOOD = dict(entries=True, bad=[], same_digest=True, flag=True, patch=True)


def _moved(py, got):
    return got['cases']['answers'] != py['cases']['answers'] or got['cases']['slot'] != GOOD


def test_same_as_python_and_slot_matches(both):
    py, rust = both
    assert rust['cases']['answers'] == py['cases']['answers']
    assert rust['cases']['slot'] == GOOD


def test_counters_fire(both):
    _, rust = both
    c = rust['counts']
    for k in ('ad:lra_native', 'ad:lra_hit', 'ad:lra_relation', 'ad:cbm_patched'):
        assert c.get(k, 0) > 0, k
    assert c['rel:plant_fired'] == 0


@pytest.mark.parametrize('plant', PLANTS)
def test_each_plant_fires_and_is_seen(both, plant):
    py, _ = both
    got = _run('rust', SLICE_SESSION_PLANT=plant)
    fired, moved = got['counts']['rel:plant_fired'] > 0, _moved(py, got)
    if plant in ELSEWHERE:
        assert not (fired and moved), f'{plant} is caught here now: take it out of ELSEWHERE'
        pytest.skip(ELSEWHERE[plant])
    assert fired
    assert moved


if __name__ == '__main__':
    _main(sys.argv[1])
