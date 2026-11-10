"""Step scope: scope.py's six port rows in `scope_core.rs`, Rust's against Python's, each in its own process.

`funcs` wraps each wired module attribute (scope's and the by-name imports in engine.py and sympy_api.py): it runs Python's, then
Rust's, on the same arguments, and returns Rust's. While Python's runs, the nested wired names are Python's too, so each side is
whole: Python's never sees a Rust `Scope` and Rust's never calls a wrapper. A `Scope` call checks that Rust's holds and reads back
what it was given. Order counts: `linked_terms`' iteration order and `extension_atoms`' list are compared as sequences.

The workload: test_relations_core's queries, the queries below, and hand-built custom predicates whose facts hold relation atoms
two levels down (so `_custom_pred` and `extension_atoms`' transitive step decide `glue`), through `theory_scope` and `Engine.ask`.
"""
import json
import os
import sys

import pytest

from test_relations_core import _queries, _rust

HERE = os.path.dirname(os.path.abspath(__file__))
FUNCS = ('Scope', 'linked_terms', 'scope_of_atoms', 'theory_scope', '_custom_pred', 'extension_atoms')


def _norm(v):
    if isinstance(v, tuple) and len(v) == 3 and isinstance(v[2], frozenset) or type(v).__name__ == 'Scope':
        return ['Scope', repr(v[0]), repr(v[1]), [str(x) for x in v[2]]]
    if isinstance(v, (frozenset, set, list, tuple)):
        return [str(x) for x in v]
    return repr(v)


def _custom():
    """Custom predicates on symbols: `mine(s)` implies `deep(s)`, and `deep(s)` implies `s < 1`; `flat(s)` is a fact with no relation."""
    from sympy import Symbol
    from satassume import Extensions, Implies, P
    from satassume.relations import relation_atom
    ext = Extensions()
    ext.register('mine', Symbol)(lambda s: Implies(P('mine', s), P('deep', s)))
    ext.register('deep', Symbol)(lambda s: Implies(P('deep', s), relation_atom('lt', s, 1)))
    ext.register('flat', Symbol)(lambda s: Implies(P('flat', s), P('mine', s)) if s.name == 'z' else True)
    return ext


def _funcs():
    import importlib
    from sympy import Eq, Function, Q, Symbol, pi, sqrt
    from satassume import P, engine, relations, scope
    from satassume.sat.formula import atoms_of
    from satassume.relations import relation_atom
    from satassume.sympy_api import ask
    mod = _rust()
    PYF = mod.PY_SCOPE_FUNCS
    rs = {n: getattr(mod.sa_solver, mod._SCOPE_FUNCS[n]) for n in FUNCS}
    seen, bad, calls = {}, {}, {}
    in_py = [False]

    def note(n, ok, a, want, got):
        calls[n] = calls.get(n, 0) + 1
        if not ok:
            bad[n] = bad.get(n, 0) + 1
            seen.setdefault(n, [repr(a)[:200], repr(want)[:200], repr(got)[:200]])

    def wrap(n):
        def w(*a, **k):
            if in_py[0]:
                return PYF[n](*a, **k)
            if n == 'Scope':
                got = rs[n](*a, **k)
                note(n, (got.glue, got.transfer, got.linked_terms) == tuple(a) and tuple(got) == tuple(a)
                     and got == PYF[n](*a), a, a, got)
                return got
            a = tuple(list(x) if isinstance(x, list) else x for x in a)
            in_py[0] = True
            try:
                want = PYF[n](*[list(x) if isinstance(x, list) else x for x in a], **k)
            finally:
                in_py[0] = False
            got = rs[n](*[list(x) if isinstance(x, list) else x for x in a], **k)
            note(n, _norm(want) == _norm(got), a, want, got)
            if n == 'theory_scope':
                parts(*a, **k)
            return got
        return w

    def same(n, *a):
        in_py[0] = True
        try:
            want = PYF[n](*a)
        finally:
            in_py[0] = False
        got = rs[n](*a)
        note(n, _norm(want) == _norm(got), a, want, got)
        return want

    def parts(assumptions, proposition, extensions=None):
        # The pieces `theory_scope` is made of, on this call's atoms: each moved item gets the same arguments on both sides.
        atoms = [b for g in (assumptions, proposition) if g is not None and g is not True for b in atoms_of(g)]
        for b in atoms:
            same('_custom_pred', b)
        if extensions is not None:
            atoms = atoms + same('extension_atoms', list(atoms), extensions)
        same('scope_of_atoms', list(atoms))
        glued = relations.glue_atoms(tuple(atoms))
        lt = same('linked_terms', glued)
        wrap('Scope')(True, False, lt)
        wrap('Scope')(False, True, frozenset())
    sets = [(scope, n, n) for n in FUNCS] + [(importlib.import_module(m), mine, theirs) for m, ns in mod._SCOPE_IMPORTERS
                                            for mine, theirs in ns if theirs in FUNCS]
    for m, mine, theirs in sets:
        setattr(m, mine, wrap(theirs))
    x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
    f = Function('f')
    extra = [(Q.positive(x - 1), Q.negative(1 - x)), (Q.positive(x - y), Q.nonzero(y - x + 1)), (Q.zero(f(x)), Q.zero(x)),
             (Q.positive(x), Eq(x, pi)), (Q.lt(x, sqrt(2)), Q.lt(x, 1) & Q.lt(1, x)), (Q.eq(x, y), Q.positive(x - y)),
             (Q.le(x, y), Q.ge(x, y)), (Q.positive(x + y), Q.negative(x) & Q.negative(y)), (Q.nonzero(x * y), Q.lt(0, x))]
    for p, a in list(_queries().values()) + extra:
        try:
            ask(p, a, engine=engine.Engine())
        except BaseException:
            pass
    ext = _custom()
    lt = relation_atom('lt', x, 0)
    cases = [(None, P('mine', x)), (P('flat', z), None), (P('flat', y), P('mine', y)), (lt, P('flat', z)), (None, P('flat', y)),
             (P('mine', x) & lt, P('deep', y)), (True, P('deep', x)), (None, None)]
    for a, p in cases:
        scope.theory_scope(a, p, ext)
        scope.theory_scope(a, p)
    eng = engine.Engine(extensions=ext)
    for a, p in cases:
        if p is not None:
            try:
                eng.ask(p, a)
            except BaseException:
                pass
    return dict(calls=calls, bad=bad, seen=seen, counts={k: v for k, v in mod.counts().items() if k.startswith(('scope:', 'rel:pl'))})


def _call(what, **env):
    import subprocess
    e = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE] + os.environ.get('PYTHONPATH', '').split(os.pathsep)), **env)
    r = subprocess.run([sys.executable, __file__, what], env=e, capture_output=True, text=True, cwd=HERE)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.splitlines()[-1])


def test_scope_funcs_agree():
    got = _call('funcs')
    assert got['bad'] == {}, got['seen']
    assert all(got['calls'].get(n, 0) > 0 for n in FUNCS), got['calls']
    # Every counter fires, each callback included. `scope:cb_atoms_of` is the exception since the formula step: the atoms
    # come from a conversion in Rust (formula.rs `atoms_nosession`), so that callback is gone and reads 0.
    assert all(v > 0 for k, v in got['counts'].items() if k.startswith('scope:') and k != 'scope:cb_atoms_of'), got['counts']
    assert got['counts']['scope:cb_atoms_of'] == 0, got['counts']


PLANTS = [('scope-linked-empty', 'Scope'), ('linked-no-rel', 'linked_terms'), ('scope-no-affine', 'scope_of_atoms'),
          ('theory-no-assume', 'theory_scope'), ('custom-never', '_custom_pred'), ('ext-shallow', 'extension_atoms')]


@pytest.mark.parametrize('plant,fn', PLANTS)
def test_scope_plant_is_seen(plant, fn):
    got = _call('funcs', SLICE_SESSION_PLANT=plant)
    assert got['counts']['rel:plant_fired'] > 0
    assert got['bad'].get(fn, 0) > 0, got['bad']


if __name__ == '__main__':
    print(json.dumps({'funcs': _funcs}[sys.argv[1]]()))
