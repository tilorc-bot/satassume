"""State part 3 (sub-part 3, issue 323): engine.py's `_gave_up`/`_exhausted` read in Rust (theory_flags.rs) from the session
core's solver, against the Python helpers on the same session, each mode in its own process (install() refuses once an
Engine exists).
- `gave_up:*`: test_entry_core's hidden-equality case (LRA gives up on a contextual query), built as `Engine.ask` builds it
  (`_build_context`, then `_ask`), the session read by both.
- `exhausted:*`: test_lra_exhaustion's sets and queries at BRANCH_BUDGET 5 (the budget runs out), `exhausted` cleared between
  the context and the query as that test's `_reached` does.
- `answers`: `ask` on every case and `Engine.stats["theory_gave_up"]`, so a plant's effect on answers is seen too.
Plants (SLICE_SESSION_PLANT): 428 `th-gave-up-skip`, 429 `th-exhausted-skip`, 430 `th-first-only`.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

CHILD = r'''
import json, os, sys
sys.path.insert(0, os.path.join(sys.argv[2], 'tests'))
import backend
backend.install_euf()
import term_live; term_live.from_env()
import lra_live; lra_live.from_env()
import session_live; session_live.from_env()
import knowledge_live; knowledge_live.from_env()
backend.install()                                   # live.py --check plain's sequence (test_install_order.py)
import sa_solver
from sympy import Function, Q, Symbol, sqrt
from satassume import DictCache
from satassume.engine import _exhausted, _gave_up
from satassume.sympy_api import Engine, _formula, ask
from satassume.theories.lra import lra
import test_lra_exhaustion as X

rows, answers = {}, {}


def read(name, e, s, p):
    rel = bool(e.relation_specs)
    try:
        sess, lits = e._build_context(_formula(s, rel, True))
        for t in sess.solver.theories():
            if hasattr(t, 'exhausted'):
                t.exhausted = False
        e._ask(sess, lits, _formula(p, rel), True)
    except ValueError:
        rows[name] = 'raise'
        return
    rows[name] = [_gave_up(sess), sa_solver.th_flag(sess, 'gave_up'), _exhausted(sess), sa_solver.th_flag(sess, 'exhausted')]


z = Symbol('z')
f = Function('f')
a = Q.eq(z, (1 + sqrt(2)) ** 2) & Q.eq(z, 3 + 2 * sqrt(2)) & Q.positive(f(3 + 2 * sqrt(2)))
for i, p in enumerate([Q.positive(f((1 + sqrt(2)) ** 2)), Q.real(z)]):
    read(f'gave_up:{i}', Engine(cache=DictCache()), a, p)
    e = Engine(cache=DictCache())
    answers[f'gave_up:{i}'] = [repr(ask(p, a, e)), e.stats.get('theory_gave_up')]
lra.BRANCH_BUDGET = 5
for j, s in enumerate((X.A & X.B, X.A & X.C)):
    for i, p in enumerate(X.QUERIES):
        read(f'exhausted:{j}:{i}', Engine(), s, p)
        e = Engine()
        answers[f'exhausted:{j}:{i}'] = [X._a(p, s, e), e.stats.get('theory_gave_up')]
c = sa_solver.session_counts()
print(json.dumps({'rows': rows, 'answers': answers, 'counts': {k: v for k, v in c.items() if k.startswith('th:')}}))
'''


def _run(plant):
    env = dict(os.environ)
    env.pop('SLICE_SESSION_PLANT', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    env.setdefault('PYTHONHASHSEED', '0')
    r = subprocess.run([sys.executable, '-c', CHILD, plant or 'none', ROOT], cwd=HERE, env=env, capture_output=True,
                       text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope='module')
def base():
    return _run(None)


def test_rust_reads_as_python(base):
    rows = {k: v for k, v in base['rows'].items() if v != 'raise'}
    bad = {k: v for k, v in rows.items() if v[0] != v[1] or v[2] != v[3]}
    assert bad == {}
    assert any(v[0] for v in rows.values())          # a session that gave up
    assert any(v[2] for v in rows.values())          # a session that ran out of branch budget
    c = base['counts']
    assert c['th:gave_up'] > 0 and c['th:exhausted'] > 0 and c['th:py_flag'] > 0
    assert c['th:py_helper'] == 0


@pytest.mark.parametrize('plant', ['th-gave-up-skip', 'th-exhausted-skip', 'th-first-only'])
def test_plants_are_caught(base, plant):
    out = _run(plant)
    rows = {k: v for k, v in out['rows'].items() if v != 'raise'}
    caught = {k: v for k, v in rows.items() if v[0] != v[1] or v[2] != v[3]}
    moved = {k: (base['answers'][k], v) for k, v in out['answers'].items() if v != base['answers'][k]}
    print(plant, 'caught', len(caught), 'answers moved', len(moved), moved)
    assert caught
