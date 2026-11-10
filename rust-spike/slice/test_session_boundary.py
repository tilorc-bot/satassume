"""State part 3 (sub-part 5, issue 323): the session/solver boundary. `Session.truncated`, `_link_pending`, `_neg_shared`, `sel`,
`n_hold` and `verdict` are held in the session core (session.rs `SS_NAMES`) and are views on Python; Rust reads `Session.solver`
from the core (`solver_of`); `_interpret`, `_link`, `_share_guard` and `_visit` are called directly from Rust unless the method
was replaced (`named`). Each mode runs in its own process (install() refuses once an Engine exists).
- `ask:*`: answers of `ask` (an inconsistent set raises), Python against Rust.
- `ctx:*`: the scalars Python can read on the set's session after `_build_context` and again after `_ask` (with the table's
  size, which `_neg_shared` decides), and `Engine.verdict`.
- `dump:*`: Rust only, the solver's dump after the set's queries (its held levels are what `n_hold` decides): for the plants.
- `trunc`: a session cut by `escalate(1)`, its scalars and its complete check (UNKNOWN when truncated).
- `solver-write`: a solver assigned after the session was built is the one the complete check runs on.
- `view`: on Rust, the views equal the core's own export (`ses_snapshot`), and a write through a view is read back natively.
- `keys:*`: each session dict holds its own key objects (ses_cont.rs `SesDict`: `hash()` and `==`, as the Python dict it
  replaces). scope_wl's query 5: a custom fact passes the int `1` to `relation_atom`, so `demand` holds the int and
  `Relations._xside` holds SymPy's `One`; `_transfer_terms` asks `_number_basis` only for a `Rational`, one `is_many`
  session. 7a18df2 keyed the session dicts by the session's RelKeys ids, `_xside` then gave back the int and that session
  was lost (workload scope: Python 3 sessions at query 5, Rust 2). Plant 446 `sc-key-shared` puts that back.
Plants (SLICE_SESSION_PLANT, session.rs `sb_plant`): 431 `sb-truncated-stale`, 432 `sb-link-pending-stale`, 433
`sb-neg-shared-stale`, 434 `sb-sel-zero`, 435 `sb-hold-zero`, 436 `sb-verdict-none`, 437 `sb-fwd-skip-link`, 438 `sb-solver-fresh`.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PLANTS = ('sb-truncated-stale', 'sb-link-pending-stale', 'sb-neg-shared-stale', 'sb-sel-zero', 'sb-hold-zero', 'sb-verdict-none',
          'sb-fwd-skip-link', 'sb-solver-fresh')
KEY_PLANTS = ('sc-key-shared',)      # 446

CHILD = r'''
import json, os, sys
rust = sys.argv[1] == 'rust'
if rust:
    import backend
    backend.install_euf()
    import term_live; term_live.from_env()
    import lra_live; lra_live.from_env()
    import session_live; session_live.from_env()
    import knowledge_live; knowledge_live.from_env()
    backend.install()                                   # live.py --check plain's sequence (test_install_order.py)
    import sa_solver
from sympy import Q, Symbol, gamma, log, sin, symbols
from satassume import DictCache
from satassume.engine import Engine as CoreEngine, Session
from satassume.sat.formula import And, Or, P
from satassume.sympy_api import Engine, _formula, ask

x, y, z, w = (Symbol(c) for c in 'xyzw')
ss = symbols('s0:10')
rows = {}


def scal(s):
    return [bool(s.truncated), bool(s._link_pending), bool(s._neg_shared), s.sel, s.n_hold, s.verdict, len(s.table)]


def guard(f):
    try:
        return f()
    except Exception as e:
        return ['raise', type(e).__name__, str(e)[:80]]


neg = Q.real(x)
for v in ss:
    neg = neg & ~Q.positive(v)
CASES = {
    'plain': (Q.positive(x) & Q.integer(y), [Q.real(x), Q.even(y), Q.nonzero(x)]),
    'incons': (Q.positive(x) & Q.negative(x), [Q.real(x)]),
    'rel': (Q.gt(x, 1) & Q.lt(y, x), [Q.gt(x, 0), Q.lt(y, 0), Q.positive(x)]),
    'eq': (Q.eq(x, y) & Q.positive(x), [Q.positive(y), Q.negative(y)]),
    'chain': (Q.lt(x, y) & Q.lt(y, z) & Q.lt(z, w), [Q.lt(x, w), Q.gt(x, w), Q.lt(w, y)]),
    'neg': (neg, [Q.positive(ss[0]), Q.nonpositive(ss[1]), Q.real(x)]),
    'pending': (Q.gt(x, 1) & Q.integer(y), [Q.integer(y), Q.positive(x), Q.gt(x + y, y)]),
    'linkp': (Q.positive(x) & Q.positive(y), [Q.gt(x + y, 0), Q.gt(x, -1), Q.lt(x * y, 0)]),
    'linkp2': (Q.prime(x) & Q.positive(y - x), [Q.gt(y, 1), Q.gt(x, 1)]),
    'mixed': (Q.eq(x, y + 1) & Q.integer(y) & Q.gt(y, 0), [Q.integer(x), Q.gt(x, 1), Q.positive(x * y)]),
}
for name, (a, ps) in CASES.items():
    for i, p in enumerate(ps):
        rows[f'ask:{name}:{i}'] = guard(lambda: repr(ask(p, a)))
    e = Engine(cache=DictCache())
    rel = bool(e.relation_specs)

    def ctx():
        out = []
        fa = _formula(a, rel, True)
        s, lits = e._build_context(fa)
        out.append(scal(s))
        out.append(e.verdict(fa))
        for p in ps:
            out.append(repr(e._ask(s, lits, _formula(p, rel), True)))
            out.append(scal(s))
        if rust:
            import hashlib
            rows[f'dump:{name}'] = hashlib.sha256(repr(s.solver.dump()).encode()).hexdigest()[:16]
        return out
    rows[f'ctx:{name}'] = guard(ctx)


def trunc():
    e = CoreEngine()
    s = Session(e)
    lits = s.assume_formula(And(P('positive', (x + y)**2 + sin(z)), Or(P('integer', x * y), P('zero', w - 1))))
    s.ensure((x + y) * sin(w) + z**2, ['positive'])
    s.ensure(log(x) + gamma(y) + x**y, ['positive'])
    s.escalate(1)
    out = [scal(s), e._complete_check(s, list(lits))]
    if rust:
        c = s.table.core
        snap = dict(c.ses_snapshot())
        rows['view'] = [snap == dict(truncated=s.truncated, _link_pending=s._link_pending, _neg_shared=s._neg_shared, sel=s.sel,
                                     n_hold=s.n_hold, verdict=s.verdict)]
        s.truncated = False
        s.verdict = 'x'
        s.n_hold = 7
        rows['view'].append([c.ses_snapshot()['truncated'], c.ses_snapshot()['verdict'], c.ses_snapshot()['n_hold'], s.verdict, s.n_hold])
        rows['view'].append(e._complete_check(s, list(lits)))
        rows['view'].append(sorted(k for k in ('defvars', '_dv', '_dv_node') if hasattr(s, k)))
    return out


rows['trunc'] = guard(trunc)


def solver_write():
    """A solver assigned to the session after it was built is the one the complete check runs on, on either backend."""
    hits = []

    class Raises:
        def __getattr__(self, name):
            hits.append(name)
            raise RuntimeError('planted solver')
    e = CoreEngine()
    s = Session(e)
    lits = s.assume_formula(P('positive', x))
    s.solver = Raises()
    r = guard(lambda: e._complete_check(s, list(lits)))
    return [bool(hits), r[:2] if isinstance(r, list) else r, s.solver.__class__.__name__]


rows['solver-write'] = guard(solver_write)


def keys():
    """scope_wl's query 5 (the docstring's `keys:*`), last: scope_wl registers custom predicates for the process."""
    import scope_wl
    from sympy import S
    from satassume import sympy_api
    q, a = scope_wl.queries()[5]
    eng = sympy_api.default_engine()
    made, init = [], Session.__init__

    def recording(self, *args, **kw):
        made.append(self)
        return init(self, *args, **kw)
    Session.__init__ = recording
    before = dict(eng.stats)
    try:
        rows['keys:ask'] = repr(ask(q, a))
    finally:
        Session.__init__ = init
    kind = lambda ks: [[type(k).__name__, repr(k)] for k in ks]
    rows['keys:stats'] = [eng.stats[k] - before[k] for k in ('queries', 'sessions', 'searches')]
    rows['keys:demand'] = [kind(s.demand.keys()) for s in made]
    rows['keys:xside'] = [kind(s.relations._xside.keys()) for s in made if s.relations is not None]
    rows['keys:xbasis'] = sorted(kind(eng._xbasis.keys()))
    d = made[0].demand
    rows['keys:lookup'] = [S.One in d, 1 in d, d.get(S.One) == d.get(1), S.Half in d, kind(k for k, _ in d.items())]


guard(keys)
counts = {k: v for k, v in dict(sa_solver.session_counts()).items()
          if k.startswith(('sb:', 'sc:')) or k == 'rel:plant_fired'} if rust else {}
print(json.dumps(dict(rows=rows, counts=counts)))
'''


def _child(mode, plant=None):
    env = dict(os.environ, PYTHONHASHSEED='0')
    env.pop('SLICE_SESSION_PLANT', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    env['PYTHONPATH'] = os.pathsep.join([ROOT, HERE, env.get('PYTHONPATH', '')])
    r = subprocess.run([sys.executable, '-c', CHILD, mode, ROOT], capture_output=True, text=True, env=env, cwd=HERE)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope='module')
def py():
    return _child('python')


@pytest.fixture(scope='module')
def rs():
    return _child('rust')


def _differ(a, b):
    return sorted(k for k in set(a) | set(b) if k != 'view' and a.get(k) != b.get(k))


def _common(rows):
    return {k: v for k, v in rows.items() if not k.startswith('dump:')}


def test_cases_mean_something(py):
    r = py['rows']
    assert r['ask:incons:0'][0] == 'raise' and r['ask:rel:0'] == 'True' and r['ask:chain:0'] == 'True'
    assert r['trunc'][0][0] is True and r['trunc'][1] == 'unknown' or r['trunc'][1] == 'UNKNOWN', r['trunc']
    assert any(v[0][2] for k, v in r.items() if k.startswith('ctx:')), 'no set reaches _neg_shared'
    assert any(v[0][3] for k, v in r.items() if k.startswith('ctx:')), 'no set has a selector'
    assert any(row[4] for k, v in r.items() if k.startswith('ctx:') for row in v if isinstance(row, list)), 'n_hold stays 0'


def test_rust_matches_python(py, rs):
    assert _differ(py['rows'], _common(rs['rows'])) == []


def test_views_are_the_core(rs):
    v = rs['rows']['view']
    assert v[0] is True
    assert v[1] == [False, 'x', 7, 'x', 7]
    assert v[3] == [], 'defvars/_dv/_dv_node are no longer written on a Rust session'


def test_each_dict_holds_its_own_keys(py, rs):
    """`keys:*` (the docstring): the int in `demand`, `One` in `_xside`, and `_number_basis(1)`'s session, on both."""
    r = py['rows']
    assert r['keys:ask'] == 'False' and r['keys:stats'][1] == 3, r['keys:stats']
    assert ['int', '1'] in r['keys:demand'][0] and ['One', '1'] in r['keys:xside'][0]
    assert r['keys:xbasis'] == [['One', '1'], ['Zero', '0']]
    assert r['keys:lookup'][:4] == [True, True, True, False]
    assert {k: v for k, v in rs['rows'].items() if k.startswith('keys:')} == {k: v for k, v in r.items() if k.startswith('keys:')}
    c = rs['counts']
    assert c['sc:key_hash'] > 0 and c['sc:key_eq'] > 0


def test_solver_write_reaches_rust(py, rs):
    """`Session.solver` is read from the core (`solver_of`); the attribute's record method keeps the core's copy current."""
    assert py['rows']['solver-write'] == [True, ['raise', 'RuntimeError'], 'Raises'] == rs['rows']['solver-write']


def test_counters_fire(rs):
    c = rs['counts']
    assert c['sb:scalar_core'] > 0 and c['sb:scalar_view'] > 0 and c['sb:scalar_record'] > 0 and c['sb:fwd_direct'] > 0
    assert c['sb:attr'] == 0 and c['sb:fwd_named'] == 0
    assert c.get('rel:plant_fired', 0) == 0


@pytest.mark.parametrize('plant', PLANTS + KEY_PLANTS)
def test_plant_caught(rs, plant):
    got = _child('rust', plant)
    assert got['counts']['rel:plant_fired'] > 0, 'the plant never fired'
    assert _differ(rs['rows'], got['rows']), 'the plant fired and nothing differs'


def test_rust_repeats(rs):
    """The plant tests compare two Rust runs: a second unplanted run gives the same rows, the solver dumps included."""
    assert _differ(rs['rows'], _child('rust')['rows']) == []
