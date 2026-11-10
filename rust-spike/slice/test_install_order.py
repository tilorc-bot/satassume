"""State part 3 (issue 323): install order, OWED [106] and the planner's install-list ruling ([107] Q1).

- The install list: every satassume module-level name the full install replaces (as `live.py --check plain` runs it), found by
  diffing every loaded satassume module's attributes across the install, not by a hand list. A test per entry, each run in a
  child that imports first and installs after:
  * a public name (`satassume.__all__`, or ruled public: `relation_atom`) dispatches at call time: the name held from before
    the install reaches Rust's (`PUBLIC_CHECKS`; a public entry with no check fails);
  * any other name is reached only through a module attribute: after the install no loaded satassume module still holds the
    replaced Python object, except the module that defines it (Python's own fallback, which the Rust side calls on a refusal),
    `satassume.ref` (the reference engine, Python on purpose) and `satassume.sat.solver` (tests that build Python's solver).
- Engine first: install() refuses once an Engine exists (session_live.refuse_built_engines). If it doesn't refuse, the engine
  built before must dispatch as one built after: plant 420 `inst-no-refuse` shows that check catches the stale engine.

Plants (SLICE_SESSION_PLANT): 420 inst-no-refuse, 421 inst-slot-skip, 422 inst-cache-new-skip, 423 inst-importer-skip;
`test_plants_are_caught` shows each one fails its test. Run: `pytest test_install_order.py` from this directory.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ALLOWED_HOLDERS = ('satassume.ref', 'satassume.sat.solver')
#: Modules that keep Python's helpers by name after the install, each with its reason (limits and table are ruled). _rows held
#: Python's `generator` and `constant_value` until state part 3 (planner's _rows ruling, ~06:47 10 Nov): it now looks them up in
#: wiring at each use (test_rows_names_resolve_at_call_time), so it is no longer named.
NAMED_HOLDERS = {
    'satassume.knowledge.templates.limits': 'kept on Python (planner, ownership ruling 7 Nov: limits.py stays on Python)',
    'satassume.knowledge.templates.table': "kept paths only (planner, 8 Nov: table.py counts whole, footnoted 'kept paths only')",
}
RULED_PUBLIC = {('satassume.relations', 'relation_atom'), ('satassume.sympy_api', 'relation_atom')}

CHILD = r'''
import json, os, sys, gc, importlib, pkgutil
sys.path.insert(0, os.getcwd())
mode = sys.argv[1]
if os.environ.get("SLICE_TRANSFER") != "py":
    import p_install; p_install.install()
import satassume
for m in pkgutil.walk_packages(satassume.__path__, "satassume."):
    importlib.import_module(m.name)
from satassume import sympy_api, relations
from satassume import DictCache as HeldDictCache, ObjectCache as HeldObjectCache
from satassume.relations import relation_atom as held_relation_atom

def mods():
    out = {}
    for mod in list(sys.modules.values()):
        n = getattr(mod, "__name__", None)
        if isinstance(n, str) and n.startswith("satassume") and n not in out:
            out[n] = mod
    return out

def snap():
    return {(n, a): v for n, mod in mods().items() for a, v in list(vars(mod).items())}

pre = sympy_api.default_engine() if mode == "engine-first" else None
before = snap()
refused = None
try:
    import backend
    backend.install_euf()
    import term_live; term_live.from_env()
    import lra_live; lra_live.from_env()
    import session_live; session_live.from_env()
    import knowledge_live; knowledge_live.from_env()
    backend.install()
except RuntimeError as e:
    refused = str(e)
out = {"refused": refused}
if mode == "engine-first":
    from satassume.engine import Engine
    import sympy
    x = sympy.Symbol("x", real=True)
    fresh = Engine()
    def disp(e):
        ct = e.clause_templates
        return [getattr(ct, "__module__", None), getattr(ct, "__qualname__", type(ct).__name__), type(e.cache).__name__]
    out["pre"], out["fresh"] = disp(pre), disp(fresh)
    qs = [(sympy.Q.positive(x + 1), sympy.Q.positive(x)), (sympy.Q.positive(x - 2), sympy.Q.gt(x, 3))]
    out["answers"] = [[str(sympy_api.ask(p, a, engine=pre)), str(sympy_api.ask(p, a, engine=fresh))] for p, a in qs]
else:
    after = snap()
    entries = []
    replaced = {}
    for k, v in after.items():
        if k in before and before[k] is not v:
            entries.append(k)
            replaced[id(before[k])] = before[k]
    holders = {}
    for (n, a), v in after.items():
        if id(v) in replaced:
            holders.setdefault(id(v), []).append([n, a])
    rows = []
    for n, a in sorted(set(entries)):
        old = before[(n, a)]
        definer = getattr(old, "__module__", None)
        stale = [h for h in holders.get(id(old), []) if h[0] != definer and h[0] not in %r]
        rows.append({"module": n, "name": a, "public": a in satassume.__all__, "stale": stale,
                     "kind": type(old).__name__, "definer": definer})
    import sa_solver, sympy
    x, y = sympy.symbols("x y")
    impl, hits = relations.RELATION_ATOM_IMPL[0], [0]
    if impl is not None:
        relations.RELATION_ATOM_IMPL[0] = lambda *a: (hits.__setitem__(0, hits[0] + 1), impl(*a))[1]
    held_relation_atom("lt", x, y)
    relations.RELATION_ATOM_IMPL[0] = impl
    out["public"] = {"DictCache": isinstance(HeldDictCache(), sa_solver.DictCache),
                     "ObjectCache": isinstance(HeldObjectCache(), sa_solver.DictCache),
                     "relation_atom": hits[0] == 1}
    out["rows"] = rows
    from satassume.knowledge.templates import _rows, wiring
    out["rows_resolved"] = [_rows.generator is wiring.generator, _rows.constant_value is wiring.constant_value,
                            getattr(wiring.generator, "__module__", None)]
print("JSON" + json.dumps(out))
''' % (ALLOWED_HOLDERS + tuple(NAMED_HOLDERS),)


def child(mode, plant=None):
    env = dict(os.environ)
    env.pop('SLICE_SESSION_PLANT', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    r = subprocess.run([sys.executable, '-c', CHILD, mode], cwd=HERE, env=env, capture_output=True, text=True, timeout=600)
    line = [ln for ln in r.stdout.splitlines() if ln.startswith('JSON')]
    assert r.returncode == 0 and line, r.stderr[-3000:]
    return json.loads(line[-1][4:])


_cache = {}


def listed(plant=None):
    if plant not in _cache:
        _cache[plant] = child('list', plant)
    return _cache[plant]


def entry_failures(out, row):
    if row['public'] or (row['module'], row['name']) in RULED_PUBLIC:
        ok = out['public'].get(row['name'])
        if ok is None:
            return [f"public {row['module']}.{row['name']} replaced with no call-time dispatch check"]
        return [] if ok else [f"public {row['module']}.{row['name']}: a name held from before the install keeps Python's"]
    return [f"{h[0]}.{h[1]} still holds Python's {row['module']}.{row['name']}" for h in row['stale']]


def failures(out):
    return [f for row in out['rows'] for f in entry_failures(out, row)]


def _ids():
    try:
        return [f"{r['module']}.{r['name']}" for r in listed()['rows']]
    except Exception:       # noqa: BLE001 (collection without a build: the test below reports it)
        return ['install-list-unavailable']


@pytest.mark.parametrize('entry', _ids())
def test_install_list_entry(entry):
    out = listed()
    assert out['refused'] is None, out['refused']
    row = next(r for r in out['rows'] if f"{r['module']}.{r['name']}" == entry)
    assert not entry_failures(out, row)


def test_install_list_is_not_empty_and_covers_the_public_names():
    rows = listed()['rows']
    names = {(r['module'], r['name']) for r in rows}
    assert len(rows) > 100
    assert {('satassume', 'DictCache'), ('satassume', 'ObjectCache'), ('satassume.relations', 'relation_atom')} <= names


def test_rows_names_resolve_at_call_time():
    """_rows' `generator`/`constant_value` are wiring's at the time of use, so the install's Rust ones (planner's _rows ruling)."""
    gen_same, cv_same, gen_module = listed()['rows_resolved']
    assert gen_same and cv_same and gen_module != 'satassume.knowledge.templates._rows_runtime', listed()['rows_resolved']


def check_engine_first(out):
    if out['refused'] is not None:
        return []
    bad = [] if out['pre'] == out['fresh'] else [f"engine built before install() dispatches {out['pre']}, after {out['fresh']}"]
    return bad + [f"answers differ: {a}" for a in out['answers'] if a[0] != a[1]]


def test_engine_first_refused():
    out = child('engine-first')
    assert out['refused'] is not None and 'Install first' in out['refused']
    assert not check_engine_first(out)


@pytest.mark.parametrize('plant,mode', [('inst-no-refuse', 'engine-first'), ('inst-slot-skip', 'list'),
                                        ('inst-cache-new-skip', 'list'), ('inst-importer-skip', 'list')])
def test_plants_are_caught(plant, mode):
    out = child(mode, plant)
    found = check_engine_first(out) if mode == 'engine-first' else failures(out)
    assert found, f'plant {plant} not caught'
    print(plant, found)
