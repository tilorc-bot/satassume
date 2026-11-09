"""State step, part 2 (iii): `glue_objects` of a relation atom other than a two-sided `eq`, natively.

budget.rs's cone kids used to call `engine.glue_objects` for every relation atom; term_live answers the two-sided `eq` on ids, and
any other atom (an `lt`) fell back to relations.py's own `glue_objects` (relations.py:1994): Python per query on converted
queries (dev 27, fuzz 1,697, zero 2, scope 13, cert 72 calls at c3d0999). relations_core.rs `glue_objects_plain` now answers
those. Here, in one process per run, it is compared with Python's `glue_objects` on `lt` atoms, with the default specs and with
none; plant 263 `gl-plain-no-link` (`link_objects` of the sides left out) must move a case, and counter `gl:plain` must fire.

Also session_live's install: a default engine built before it (scope_wl builds one while its queries load) held Python's
`with_closed_units` closure, which ran per query (scope 518 calls); the install rewraps it on Rust's over the same templates,
and its undo puts Python's back.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _child():
    from test_relations_core import _rust
    _rust()
    from sympy import Function, Rational, Symbol, sin
    from satassume import relations
    from satassume.engine import Engine
    import sa_solver
    py = relations.glue_objects
    py = getattr(py, '__wrapped__', py)
    x, y, z = Symbol('x', real=True), Symbol('y', real=True), Symbol('z', integer=True)
    f = Function('f')
    sides = [(x, y), (x + y, z), (2 * x * y, Rational(1, 3)), (Rational(0), x - 3 * z), (sin(x) + f(y), x * y + 1),
             (f(x + 1), f(y)), (x ** 2 + y, 0)]
    specs = Engine()._relation_specs
    out = {}
    for name, sp in (('default', specs), ('none', [])):
        for i, (a, b) in enumerate(sides):
            atom = relations.relation_atom('lt', a, b)
            want = py(atom, sp, {})
            got = sa_solver.rel_glue_objects_plain(atom, sp, {})
            out[f'{name}-{i}'] = [want == got, sorted(map(str, got))]
    c = sa_solver.session_counts()
    out['counts'] = {'gl:plain': c['gl:plain']}
    print(json.dumps(out))


def _child_rewrap():
    from satassume import sympy_api
    eng = sympy_api.default_engine()
    before = eng.clause_templates
    from test_relations_core import _rust
    sl = _rust()
    import sa_solver
    after = eng.clause_templates
    out = {'python-before': [type(before).__name__ == 'function', before.__qualname__ == 'with_closed_units.<locals>.clauses'],
           'rust-after': [type(after).__module__ != 'satassume.relations', type(after) is type(sa_solver.rel_with_closed_units(None))]}
    print(json.dumps(out))


def _run(plant=None, mode='child'):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    env.pop('SLICE_SESSION_PLANT', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    r = subprocess.run([sys.executable, os.path.abspath(__file__), mode], env=env, capture_output=True, text=True,
                       timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope='module')
def clean():
    return _run()


def test_clean(clean):
    for k, v in clean.items():
        if k == 'counts':
            assert v['gl:plain'] > 0, v
        else:
            assert v[0], (k, v)


def test_plant_moves_a_case(clean):
    got = _run('gl-plain-no-link')
    moved = [k for k in clean if k != 'counts' and got[k][0] != clean[k][0]]
    assert moved


def test_default_engine_rewrapped():
    got = _run(mode='rewrap')
    assert all(all(v) for v in got.values()), got


if __name__ == '__main__' and sys.argv[1:] == ['child']:
    _child()
if __name__ == '__main__' and sys.argv[1:] == ['rewrap']:
    _child_rewrap()
