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
- `cont:*`: the seven session containers held in the core (ses_cont.rs: `frontier`, `deferred`, `pending`, `pending_c`,
  `demand`, `literals`, `_groups`): each one's content, keys with their class and values, in order, after `_build_context`
  and after the asks, and on `trunc`'s session before and after `escalate(1)` (where `pending`, `pending_c` and `deferred`
  are not empty), Python against Rust. `cont:mid`, `mid`: `frontier` and `pending` are empty between calls, so they are
  read at each `_visit` of a like session (sizes at every visit, the first contents where each is not empty); that session
  has a vocabulary function registered for `Add`, whose formulas a demand parks in `pending` until `escalate`. `cview` (Rust): the core's own export (`sc_snapshot`) equals the views each time,
  and a write through a view or an assignment is read back from the core. `test_python_methods_on_the_views`: one Rust
  run with SLICE_DISC=py SLICE_LOOP=py SLICE_GLUE=py, Python's own methods working on the views.
  Plants 439-445 `sc-<name>-drop` (the container's write is a no-op): each fires and is caught; `test_container_plants`
  also says which kind of row caught it (an answer, or only the container's content).
- `core`: session.rs `core_of` and `table_of` read the session's `_core` and `_table_view` (plain instance attributes that
  session_live `_table_set` stores), not the `table` property, whose getter `_table_get` is a Python frame per read. `tget`
  counts `_table_get`'s calls over one set's asks (sys.setprofile); `sb:core_prop` (570) counts the reads that still go
  through the property. Plant 447 `sb-core-unset` (no read of `_core`/`_table_view`): equal answers by construction, caught
  by `sb:core_prop` and by `tget` rising. Plant 448 `sb-core-stale` (the first core seen, for every session): rows differ.
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
CORE_PLANTS = ('sb-core-stale',)     # 448; 447 `sb-core-unset` has its own test
#: 439-445, by container (session.rs SB_PLANTS' order)
CONT_PLANTS = {'frontier': 'sc-frontier-drop', 'pending': 'sc-pending-drop', 'pending_c': 'sc-pending_c-drop',
               'demand': 'sc-demand-drop', 'deferred': 'sc-deferred-drop', 'literals': 'sc-literals-drop',
               '_groups': 'sc-groups-drop'}

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


SEQ, DCT = ('frontier', 'deferred'), ('pending', 'pending_c', 'demand', 'literals', '_groups')


def rnd(v):
    if isinstance(v, (set, frozenset)):
        return [type(v).__name__, sorted(map(repr, v))]
    if isinstance(v, dict):
        return ['dict', [[rnd(k), rnd(u)] for k, u in v.items()]]
    if isinstance(v, (list, tuple)):
        return [type(v).__name__, [rnd(u) for u in v]]
    return [type(v).__name__, repr(v)]


def cont(s, get=None):
    """Each container's content, in its own order: a sequence's items, a dict's (key, value) pairs, each with its class."""
    get = get or (lambda n: getattr(s, n))
    out = {n: [rnd(v) for v in get(n)] for n in SEQ}
    out.update({n: [[rnd(k), rnd(v)] for k, v in get(n).items()] for n in DCT})
    return out


def csnap(s):
    """Rust: the core's own export against the views."""
    sn = s.table.core.sc_snapshot()
    rows.setdefault('cview', []).append(cont(s, sn.__getitem__) == cont(s))


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
        cs = rows[f'cont:{name}'] = [cont(s)]
        out.append(e.verdict(fa))
        for p in ps:
            out.append(repr(e._ask(s, lits, _formula(p, rel), True)))
            out.append(scal(s))
        cs.append(cont(s))
        if rust:
            csnap(s)
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
    cs = rows['cont:trunc'] = [cont(s)]
    s.escalate(1)
    cs.append(cont(s))
    out = [scal(s), e._complete_check(s, list(lits))]
    if rust:
        csnap(s)
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
        # a write through a view, and an assignment (the record method), read back from the core
        from collections import deque
        t = Session(CoreEngine())
        t.frontier = deque([x, y])
        t.frontier.append(z)
        t.deferred.extend([w, x])
        t.deferred.pop()
        t.demand = {x: {'positive'}}
        t.demand[y] = {'real'}
        t.pending.setdefault(z, []).append(1)
        t.pending_c[w] = [(1, 2)]
        del t.pending_c[w]
        t.literals.update({x: 3})
        t._groups[None] = [4]
        t._groups[True] = [5]
        sn = t.table.core.sc_snapshot()
        rows['cview-write'] = cont(t, sn.__getitem__)
        csnap(t)
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


def core():
    """The docstring's `core`, after the counts are taken (the profile is this function's only)."""
    made, init = [], Session.__init__

    def recording(self, *args, **kw):
        init(self, *args, **kw)
        made.append(self)
    code, n = session_live._table_get.__code__, [0]

    def prof(frame, event, arg):
        if event == 'call' and frame.f_code is code:
            n[0] += 1
    a, ps = CASES['mixed']
    Session.__init__ = recording
    sys.setprofile(prof)
    try:
        out = [repr(ask(p, a)) for p in ps]
    finally:
        sys.setprofile(None)
        Session.__init__ = init
    counts['tget'] = n[0]
    rows['core'] = [out, len(made) > 0, all(s.__dict__['_core'] is s.table.core for s in made),
                    all(s.__dict__['_table_view'] is s.table for s in made)]


if rust:
    guard(core)


def mid():
    """`frontier` and `pending` are empty between calls, so they are read at each `_visit` of `trunc`'s session (Rust calls
    a replaced `_visit` by name, which is why this runs after the counts are taken): the sizes at every visit, and the
    first three contents with a non-empty frontier and with a non-empty `pending`."""
    sizes, fr, pe = [], [], []
    orig = Session._visit

    def visiting(self, node, b, demanded):
        sizes.append([len(self.frontier), len(self.pending)])
        if sizes[-1][0] and len(fr) < 3:
            fr.append(cont(self))
        if sizes[-1][1] and len(pe) < 3:
            pe.append(cont(self))
        return orig(self, node, b, demanded)
    # a vocabulary function registered for `Add`: its formulas are items, parked in `pending` under a demand that leaves
    # them out (test_discovery_core.py's `registered`); last in the process, the registration stays
    from sympy import Add
    from satassume.knowledge.extensions import register
    register('even', Add)(lambda n: And(P('even', n.args[0]), P('even', n.args[1])))
    Session._visit = visiting
    last = []
    try:
        s = Session(CoreEngine())
        s.assume_formula(And(P('positive', (x + y)**2 + sin(z)), Or(P('integer', x * y), P('zero', w - 1))))
        s.ensure((x + y) * sin(w) + z**2, ['positive'])
        s.ensure(log(x) + gamma(y) + x**y, ['positive'])
        s.ensure(sin(x + y) + z, ['negative'])
        last.append(cont(s))
        s.escalate(1)
        last.append(cont(s))
    finally:
        Session._visit = orig
        rows['mid'] = sizes
        rows['cont:mid'] = fr + pe + last


guard(mid)
print(json.dumps(dict(rows=rows, counts=counts)))
'''


def _child(mode, plant=None, **more):
    env = dict(os.environ, PYTHONHASHSEED='0', **more)
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
    return {k: v for k, v in rows.items() if not k.startswith(('dump:', 'cview')) and k != 'core'}


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
    assert c['sb:core_prop'] == 0, 'a session was read through the table property'
    assert c['sc:core'] > 0 and c['sc:view'] > 0 and c['sc:record'] > 0


def test_containers_mean_something(py, rs):
    """Every container is non-empty somewhere, on Python (so a drop plant has something to drop), and Rust's export equals
    its views at every point."""
    r = py['rows']
    for n in CONT_PLANTS:
        assert any(c[n] for k, v in r.items() if k.startswith('cont:') for c in v), f'{n} is empty everywhere'
    t0, t1 = r['cont:trunc']
    assert t0['pending_c'] and t0['deferred'] and t0 != t1, 'escalate(1) changes nothing'
    assert any(a for a, _ in r['mid']) and any(b for _, b in r['mid']), 'no visit sees a frontier or a pending node'
    assert rs['rows']['cview'] and all(rs['rows']['cview'])
    w = rs['rows']['cview-write']
    assert [v[1] for v in w['frontier']] == ['x', 'y', 'z'] and [v[1] for v in w['deferred']] == ['w']
    assert [k[1] for k, _ in w['demand']] == ['x', 'y'] and w['pending_c'] == [] and len(w['pending']) == 1
    assert [k for k, _ in w['_groups']] == [['NoneType', 'None'], ['bool', 'True']] and len(w['literals']) == 1


def test_python_methods_on_the_views(py):
    """SLICE_DISC=py SLICE_LOOP=py SLICE_GLUE=py: Python's own discovery, loop and glue methods on a Rust session read and
    write the containers through the views and the record methods; rows as Python's."""
    got = _child('rust', SLICE_DISC='py', SLICE_LOOP='py', SLICE_GLUE='py')
    assert _differ(py['rows'], _common(got['rows'])) == []
    assert all(got['rows']['cview'])
    c = got['counts']
    assert c['sc:view'] > 100 and c['sc:record'] > 0, (c['sc:view'], c['sc:record'])


@pytest.mark.parametrize('name', sorted(CONT_PLANTS))
def test_container_plants(rs, name):
    """439-445: the container's writes dropped. Fired, and caught by the container's own content row; `kinds` says whether
    an answer (ask, ctx, trunc, dump) differs too (printed for the report: pytest -s, or -rA)."""
    got = _child('rust', CONT_PLANTS[name])
    assert got['counts']['rel:plant_fired'] > 0, 'the plant never fired'
    diff = _differ(rs['rows'], got['rows'])
    assert any(k.startswith('cont:') and rs['rows'][k] != got['rows'].get(k) and
               any(a[name] != b[name] for a, b in zip(rs['rows'][k], got['rows'].get(k) or [{name: None}] * 2))
               for k in diff), f'{name}: no content row differs'
    kinds = sorted({k.split(':')[0] for k in diff})
    print(f'PLANT {CONT_PLANTS[name]}: fired {got["counts"]["rel:plant_fired"]}, differing rows by kind '
          f'{ {x: sum(k.split(":")[0] == x for k in diff) for x in kinds} }')


def test_core_read_without_the_property(py, rs):
    """`core` (the docstring): every session carries `_core` and `_table_view`; with plant 447 the answers are the same and
    the property is what gets read (`sb:core_prop` fires, `_table_get` runs more often)."""
    assert rs['rows']['core'][1:] == [True, True, True]
    assert rs['rows']['core'][0] == [py['rows'][f'ask:mixed:{i}'] for i in range(3)]
    got = _child('rust', 'sb-core-unset')
    assert got['counts']['rel:plant_fired'] > 0, 'the plant never fired'
    assert got['counts']['sb:core_prop'] > 0
    assert _differ(rs['rows'], got['rows']) == [], 'plant 447 changes only which attribute is read'
    assert got['counts']['tget'] > rs['counts']['tget'], (got['counts']['tget'], rs['counts']['tget'])


@pytest.mark.parametrize('plant', PLANTS + KEY_PLANTS + CORE_PLANTS)
def test_plant_caught(rs, plant):
    got = _child('rust', plant)
    assert got['counts']['rel:plant_fired'] > 0, 'the plant never fired'
    assert _differ(rs['rows'], got['rows']), 'the plant fired and nothing differs'


def test_rust_repeats(rs):
    """The plant tests compare two Rust runs: a second unplanted run gives the same rows, the solver dumps included."""
    assert _differ(rs['rows'], _child('rust')['rows']) == []
