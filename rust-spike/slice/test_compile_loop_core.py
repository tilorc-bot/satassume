"""Step 5c2: `Session`'s compile loop so far in Rust (`compile_loop.rs`: module `want_of` and `_split`, and `_emit_pattern`,
`_flush`, `_compile`, `_compile_pending`) called directly on forged state, Python against Rust, each mode in its own process.
Cases record what came back, every clause in order (`add_internal` with its mention masks), and the session's state after
(`test_discovery_core._state`: base, frontier, deferred, pending, pending_c, demand, solver digest). `_split` and `want_of` are
also checked for the memo's identity (a second call returns the same object), which Python's callers rely on.

The workloads reach these methods through discovery, but some effects can't be seen there: `_flush`'s custom atoms have no
registered facts on dev and fuzz, and `_split`'s `later` only matters once something is parked. Here a vocabulary function is
registered for a custom predicate, clauses are forged, and every moved method is called by name. Each plant must fire and
move some case. test_discovery_core.py's cases also run every moved method, through discovery, against pure Python.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLANTS = ('drop-split-later', 'drop-emit-ment', 'drop-flush-custom', 'drop-compile-demand', 'drop-pend-compile', 'want-empty',
          'drop-pat-demand', 'drop-custom-rel', 'drop-custom-facts', 'drop-visit-items', 'drop-dv-link',
          'cl-view-nodes-drop')     # the part 3 follow-up (4): compile_loop.rs view_core's read


def _cases():
    import test_discovery_core as D
    from sympy import Add, Mul, Symbol, sin
    from sympy import preorder_traversal
    import satassume.engine as E
    from satassume.knowledge.extensions import register, unregister
    from satassume.sat.formula import And, Implies, Or, P, atoms_of
    x, y, z, w = (Symbol(c) for c in 'xyzw')
    for t in (x * y, y * z, sin(y * z), x * y + sin(z), z * w, sin(x * z) - w, sin(x + y) + z * w):
        D.NODES.extend(preorder_traversal(t))
    # forged pattern clauses: (tag, the predicate indices a clause is about, ((slot, literal offset), ...))
    CL = [('a', frozenset({0, 3}), ((0, 2), (1, 5))), ('b', frozenset({1}), ((1, 0), (2, 7))),
          ('c', frozenset({3, 4}), ((0, 9), (2, 1))), ('d', frozenset({6}), ((2, 3),))]
    CL_ALL = [c for c in CL if c[1] & {0, 1, 3, 4, 6}]

    def split_case(s):
        out = []
        for want in (None, frozenset({3}), frozenset({1, 6}), frozenset({0, 1, 3, 4, 6}), frozenset({9})):
            for cl in (CL, CL_ALL):
                r = E._split(cl, want)
                r2 = E._split(cl, want)
                out.append([sorted(want) if want is not None else None, r[0] is cl, r[1] is cl, repr(r[1]), repr(r[2]),
                            list(r[3]), r is r2])
        return out

    def want_case(s):
        a, b = E.want_of({3, 1}), E.want_of([1, 3, 3])
        return [sorted(a), type(a).__name__, a is b, sorted(E.want_of(set()))]

    def emit(s, ment):
        def go():
            s.solver.ensure_vars(40)
            bases = [2 * 3, 2 * 11, 2 * 19]
            if ment == 'given':
                r = E._split(CL, frozenset({3}))
                s._emit_pattern(r[1], bases, r[3])
            else:
                s._emit_pattern(CL, bases)
        return go

    def mine(n):
        return Implies(P('mine', n), P('positive', n.args[0]))

    def with_mine(steps):
        def fn(s):
            yield 'register', lambda: register('mine', Mul)(mine) and None
            try:
                yield from steps(s)
            finally:
                unregister('mine')
        return fn

    def compiled(f):
        return lambda s: E.compile_formula(f, s.table, s.emit, s.dvar)

    out = {'split': lambda s: [('split', lambda: split_case(s))], 'want_of': lambda s: [('want_of', lambda: want_case(s))],
           'emit:given': lambda s: [('emit', emit(s, 'given'))], 'emit:none': lambda s: [('emit', emit(s, None))]}
    for name, (f, node) in {'direct-args': (And(P('positive', x + y), P('real', x * sin(y))), x + y),
                            'all-deferred': (Or(P('positive', sin(z) * w), P('zero', z)), sin(x)),
                            'none': (And(P('real', z * w), P('positive', sin(y * z))), None),
                            'custom': (Or(P('mine', y * z), P('real', sin(y * z))), y * z)}.items():
        out[f'flush:{name}'] = with_mine(lambda s, f=f, node=node: [('compile', lambda: compiled(f)(s)),
                                                                     ('flush', lambda: s._flush(node)),
                                                                     ('flush', lambda: s._flush(node))])
    for name, (fs, node) in {'mul': ([P('positive', x * y), Implies(P('real', x), P('integer', y * z))], x * y),
                             'custom': ([Or(P('mine', y * z), P('negative', z)), P('real', z * w)], z),
                             'self-only': ([P('positive', x * y)], x * y)}.items():
        out[f'compile:{name}'] = with_mine(lambda s, fs=fs, node=node: [
            ('compile', lambda: s._compile(node, [(f, atoms_of(f)) for f in fs]))])
    def pend(s, p):
        """`_compile_pending` on every node with something parked, demanding the basis of `p` beside what it had."""
        def go():
            for n in list(s.pending) + [n for n in list(s.pending_c) if n not in s.pending]:
                d = set(s.demand.get(n, set()))
                for q in p:
                    d |= E.BASIS_OF[q]
                s._compile_pending(n, d)
        return ('pending', go)

    def own(n):
        return [Implies(P('even', n), P('even', n.args[0])), Implies(P('odd', n), P('integer', n.args[-1]))]

    def own_steps(s, p):
        """A vocabulary function for `Add` whose formulas mention the node itself, parked under a demand that misses them."""
        yield 'register', lambda: register('even', Add)(own) and None
        try:
            yield 'ensure-demanded', lambda: s.ensure(x + y * z, ['positive'])
            yield 'ensure-demanded', lambda: s.ensure(sin(x) + w, ['zero'])
            yield pend(s, p)
        finally:
            yield 'unregister', lambda: unregister('even')

    # `_compile_patterns` through the visit (`_visit` is still Python): nodes with patterns, plain and under a demand
    for t, d in ((x * y + sin(z), None), (x * y + sin(z), ['positive']), (sin(x * z) - w, ['integer']), ((z * w)**2, ['zero'])):
        out[f'patterns:{t}:{d}'] = lambda s, t=t, d=d: [('ensure', lambda: s.ensure(t, d)), ('ensure', lambda: s.ensure(t * w, d))]
    for preds in (['positive'], ['integer', 'real'], ['zero'], ['even'], ['odd'], []):
        k = "+".join(preds) or "none"
        out[f'pending:{k}'] = lambda s, p=preds: list(D._cases()['escalate:0'](s))[:6] + [pend(s, p)]
        out[f'pending-own:{k}'] = lambda s, p=preds: list(own_steps(s, p))

    # 5c2's second part. `_custom`: a relation atom with no Relations yet (made, counted in scope_misses, and given the
    # assumptions' atoms when there are some), and a custom atom whose registered facts compile; by `_flush` and by name.
    from sympy import Integer, pi
    from satassume.relations import relation_atom

    def rel_seen(s):
        r = s.relations
        return [r is None, s.engine.stats.get('scope_misses', 0), None if r is None else [repr(a) for a in r.queue]]

    def rel_steps(af, by):
        def fn(s):
            if af is not None:
                yield 'assume', lambda: setattr(s, 'assumption_formula', af(s)) or rel_seen(s)
            a = relation_atom('lt', x, y * z)
            if by == 'flush':
                yield 'compile', lambda: compiled(Or(a, P('positive', z)))(s)
                yield 'flush', lambda: s._flush(None) or rel_seen(s)
            else:
                yield 'custom', lambda: s._custom(a) or rel_seen(s)
                yield 'custom', lambda: s._custom(relation_atom('eq', z, w)) or rel_seen(s)
            yield 'ensure', lambda: s.ensure(x * y, ['positive'])
        return fn
    for af_name, af in {'none': None, 'set': lambda s: And(P('positive', x), relation_atom('lt', z, w)),
                        'plain': lambda s: Or(P('negative', y), P('zero', x))}.items():
        for by in ('flush', 'name'):
            out[f'custom:rel:{af_name}:{by}'] = rel_steps(af, by)
    out['custom:facts:name'] = with_mine(lambda s: [('custom', lambda: s._custom(P('mine', y * z))),
                                                    ('custom', lambda: s._custom(P('mine', x * y))), ('flush', lambda: s._flush(None))])
    out['custom:no-ext'] = lambda s: [('no-ext', lambda: setattr(s.engine, '_extensions', None)),
                                      ('custom', lambda: s._custom(P('mine', y * z)))]

    # `_link`, by name on forged definitions (the engine's own calls come from `var`/`dvar`, and run in every case that
    # compiles a derived predicate)
    DEFS = [('&', (1,)), ('|', (1, 2)), ('&', (2, -3)), ('&', (3,)), ('|', (2, 3)), ('|', (1, 2)), ('&', (1, 4, -5))]

    def link_steps(s, node, vs):
        yield 'vars', lambda: s.solver.ensure_vars(80)
        for d, v in zip(DEFS, vs):
            yield 'link', lambda d=d, v=v: s._link(d, node, v)
    out['link:one-node'] = lambda s: list(link_steps(s, x * y, [41, 42, 43, 44, 45, 42, 46]))
    out['link:repeat'] = lambda s: list(link_steps(s, x * y, [41, 42, 43, 44, 45, 47, 46])) + list(link_steps(s, z, [50, 51, 52, 53, 54, 55, 56]))
    out['link:derived'] = lambda s: [('compile', lambda: compiled(Or(P('nonpositive', x * y), P('nonzero', x * y)))(s)),
                                     ('compile', lambda: compiled(Implies(P('extended_nonnegative', x * y), P('nonzero', z)))(s)),
                                     ('compile', lambda: compiled(Or(P('nonnegative', z * w), P('nonzero', z * w)))(s))]

    # `_visit` through `Session.node` (the core's visit): node facts from a vocabulary function (compiled now, or parked under
    # a demand), a constant whose complete pattern decides it, and `engine._constructing` empty after
    def visit_own(t, d):
        def fn(s):
            yield 'register', lambda: register('even', Add)(own) and None
            try:
                yield from visit_steps(x + t, d)(s)
            finally:
                unregister('even')
        return fn

    def visit_steps(t, d):
        def fn(s):
            yield 'node', lambda: s.node(t, d)
            yield 'node', lambda: s.node(t * w + 1, d)
            yield 'constructing', lambda: sorted(map(str, s.engine._constructing))
        return fn
    for t, d in ((x * y * z, None), (z * w, ['positive']), (Integer(3), None), (pi, ['positive']), (Integer(2) * x, ['zero'])):
        out[f'visit:{t}:{d}'] = visit_steps(t, d)
        out[f'visit-mine:{t}:{d}'] = with_mine(visit_steps(t, d))
        out[f'visit-own:{t}:{d}'] = visit_own(t, d)
    return out


def _main(mode):
    import test_discovery_core as D
    live = D._rust() if mode == 'rust' else None
    D._cases()      # fills D.NODES the same way in both modes
    got = {k: D._case(fn) for k, fn in _cases().items()}
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
    """No case raised, and each moved method ran on Rust; `_flush` deferred some node and fed the frontier; `_split` parked."""
    py, rust = both
    bad = {k: c['out'] for k, c in py['cases'].items() if c['out'] != 'ok'}
    assert bad == {}
    st = {k: c['steps'] for k, c in py['cases'].items()}
    assert any(s[2][3]['deferred'] for k, s in st.items() if k.startswith('flush:'))
    assert any(s[2][3]['frontier'] for k, s in st.items() if k.startswith('flush:'))
    assert any(r[4] != 'None' for r in eval(st['split'][0][1]))
    # some parked formula was compiled: `pending` shrank across the step
    assert any(sum(len(v) for _, v in s[-2][3]['pending']) < sum(len(v) for _, v in s[-3][3]['pending']) for k, s in st.items() if k.startswith('pending-own:'))
    c = rust['counts']
    assert all(c[f'ses:{m}'] > 0 for m in ('want_of', 'split', 'emit_pattern', 'flush', 'compile', 'compile_pending', 'compile_patterns',
                                         'custom', 'visit', 'core_visit', 'link'))
    # `_custom` made a Relations and counted the scope miss; with the assumptions' atoms noted
    assert any(s[-2][1] != 'None' and 'False, 1' in s[-2][1] for k, s in st.items() if k.startswith('custom:rel:'))


@pytest.mark.parametrize('plant', PLANTS)
def test_each_plant_fires_and_is_seen(both, plant):
    py, _ = both
    got = _run('rust', SLICE_SESSION_PLANT=plant)
    assert got['counts']['rel:plant_fired'] > 0
    assert _differ(py, got) != []


if __name__ == '__main__':
    _main(sys.argv[1])
