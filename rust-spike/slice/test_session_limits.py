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


_TAGGED = []


def _tagged():
    """`==` objects of different classes, as SymPy's cache gives after an eviction, tagged to read which one a slot holds. Built
    on first use, so collecting the tests doesn't clear the cache."""
    if not _TAGGED:
        from sympy import Function, Symbol
        from sympy.core.cache import clear_cache
        x = Symbol('x')
        for tag in 'AB':
            clear_cache()
            f, g = Function('f'), Function('g')
            f.tag = g.tag = tag
            _TAGGED.extend([f(x), g(f(x))])
    return _TAGGED


def _kept(s):
    t, out = s.table, {}
    for v in range(1, len(t.slots)):
        e = t.slots[v]
        if isinstance(e, tuple):
            out[e[1]] = (str(e[0]), e[0].func.tag)
    return out


def _random_formula(r, d):
    from satassume.sat.formula import And, Implies, Not, Or, P
    k = r.random()
    if d == 0 or k < .35:
        return P(r.choice(('real', 'positive', 'negative', 'zero', 'integer', 'even', 'odd', 'nonzero', 'mine')), r.choice(_tagged()))
    if k < .55:
        return Not(_random_formula(r, d - 1))
    if k < .75:
        return And(*[_random_formula(r, d - 1) for _ in range(r.randint(2, 3))])
    if k < .92:
        return Or(*[_random_formula(r, d - 1) for _ in range(r.randint(2, 5))])
    return Implies(_random_formula(r, d - 1), _random_formula(r, d - 1))


def _kept_formula(seed):
    def run(s):
        import random
        import satassume.engine as E
        E.compile_formula(_random_formula(random.Random(seed), 3), s.table, s.emit, s.dvar)
        return _kept(s)
    return run


def _kept_two_steps(first, second):
    """A node with no slot after a custom atom on one object, then a slot taken through another."""
    def run(s):
        import satassume.engine as E
        from satassume.sat.formula import P
        o = _tagged()
        E.compile_formula(P('mine', o[first]), s.table, s.emit, s.dvar)
        E.compile_formula(P('real', o[second]), s.table, s.emit, s.dvar)
        return _kept(s)
    return run


def _kept_then_node_base(first, second):
    def run(s):
        import satassume.engine as E
        from satassume.sat.formula import P
        o = _tagged()
        E.compile_formula(P('mine', o[first]), s.table, s.emit, s.dvar)
        s.table.node_base(o[second])
        return _kept(s)
    return run


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
        'node-joined:custom': lambda s: s.assume_formula(And(P('mine', 1.0), P('mine', 1))),
        'node-joined:custom-then-block': lambda s: s.assume_formula(And(P('mine', 1.0), P('real', True))),
        'pred-none': lambda s: s.literal_of(Or(a, P(None, 'b'))),
        'pred-list:assume': lambda s: s.assume_formula(And(a, P(['p'], 'b'))),
        'pred-list:compile': _compile_direct(And(a, Or(b, c), P(['p'], 'b'))),
        'pred-custom-str': lambda s: s.assume_formula(And(a, P('mine', 'b'), P('mine', 'c'))),
        'not-a-formula': lambda s: s.assume_formula(And(a, 7)),
        'not-a-formula:compile': _compile_direct(And(a, Or(b, c), 7)),
        'stop-from-args': _compile_direct(BadArgs()),
        'kept:two-steps': _kept_two_steps(0, 2),
        'kept:then-node-base': _kept_then_node_base(0, 2),
    })
    # Which object a slot keeps, when compiling reaches atoms in another order than the formula has them.
    out.update({f'kept:formula:{i}': _kept_formula(i) for i in range(120)})
    out.update(_object_rule_cases())
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


def _twins():
    """Two `==` objects with one hash: after a cache clear `Pow(a, a)` and `Pow(a2, a)` are built apart."""
    from sympy import Pow, Symbol
    from sympy.core.cache import clear_cache
    a = Symbol('a')
    o = Pow(a, a)
    clear_cache()
    y = Pow(Symbol('a'), a)
    assert o == y and o is not y and hash(o) == hash(y)
    return o, y


def _object_case(first, body):
    """`body(s, slot, passed)`, reporting which of the two objects each visit got and which one the slot holds. Sa-port-34's rule,
    `results/port-1a.md`: the first object to reach, in the session. So Python's slot keeps the first and its visit takes the one
    passed; `first` swaps the two objects, for both orders."""
    def fn(s):
        twins = _twins()
        slot, passed = twins[first], twins[1 - first]
        name = lambda n: 'slot' if n is slot else 'passed' if n is passed else repr(n)
        seen = []
        orig = s._visit

        def visit(n, *r):
            seen.append(name(n))
            return orig(n, *r)
        s._visit = visit
        out = body(s, slot, passed)
        held = s.table.slots[s.table.node_base(slot)][0]
        return dict(out=out, visited=seen, slot_holds=name(held))
    return fn


def _kept_second_visited(first, how):
    return _object_case(first, lambda s, slot, passed: (s.table.node_base(slot), how(s, passed))[1])


def _visit_reenters(first):
    """A template passes a second object while a formula holding the first compiles: the slot takes the template's, and Python's
    compiler still visits the formula's own atom."""
    from sympy import Symbol
    from satassume.sat.formula import And, P

    def body(s, slot, passed):
        w = Symbol('w')
        orig = s._visit

        def visit(n, *r):
            if n is w:
                s.table.node_base(passed)
            return orig(n, *r)
        s._visit = visit
        return s.assume_formula(And(P('real', w), P('positive', slot)))
    return _object_case(first, body)


def _second_custom(first, how):
    """An `Args` and a `Tuple` are `==` with one hash. The custom atom keeps its own expr, and the first to reach `table.var`."""
    def fn(s):
        from sympy import Symbol, Tuple
        from satassume.knowledge.extensions import Args
        a, b = Symbol('a'), Symbol('b')
        pair = (Tuple(a, b), Args((a, b)))
        assert pair[0] == pair[1] and hash(pair[0]) == hash(pair[1])
        v = how(s, *(pair if first == 0 else pair[::-1]))
        t = s.table
        return dict(v=v, expr=type(t.slots[v].expr).__name__, new=[type(x.expr).__name__ for x in t.new_custom])
    return fn


def _object_rule_cases():
    from satassume.engine import DEF_LITS
    from satassume.sat.formula import And, Or, P
    ways = {
        'var-basis': lambda s, n: s.var('extended_real', n),
        'var-one-lit': lambda s, n: s.var('infinite', n),
        'var-several': lambda s, n: s.var('positive', n),
        'dvar-one-lit': lambda s, n: s.dvar((DEF_LITS['infinite'], n)),
        'dvar-several': lambda s, n: s.dvar((DEF_LITS['positive'], n)),
        'dvar-pos': lambda s, n: s.dvar((DEF_LITS['positive'], n), 'pos'),
        'dvar-negunit': lambda s, n: s.dvar((DEF_LITS['positive'], n), 'negunit'),
        'dvar-basis': lambda s, n: s.dvar(P('extended_real', n), 'basis'),
        '_dvar': lambda s, n: s._dvar(DEF_LITS['positive'], n, 3),
        'node': lambda s, n: s.node(n),
        'assume': lambda s, n: s.assume_formula(P('positive', n)),
        'assume-and': lambda s, n: s.assume_formula(And(P('real', n), P('positive', n))),
        'literal_of': lambda s, n: s.literal_of(Or(P('positive', n), P('real', 'z'))),
    }
    out = {}
    for first in (0, 1):
        for k, how in ways.items():
            out[f'a1:{k}:{first}'] = _kept_second_visited(first, how)
        out[f'a1:reenter:{first}'] = _visit_reenters(first)
        node_then_var = lambda s, x, y: (s.table.node_base(x), s.table.var(P('sexyprime', y)))[1]
        var_then_node = lambda s, x, y: (lambda v: (s.table.node_base(x), v)[1])(s.table.var(P('sexyprime', y)))
        vars_two = lambda s, x, y: (s.table.var(P('sexyprime', x)), s.table.var(P('sexyprime', y)))[1]
        out[f'a2:node-then-var:{first}'] = _second_custom(first, node_then_var)
        out[f'a2:var-then-node:{first}'] = _second_custom(first, var_then_node)
        out[f'a2:two-atoms:{first}'] = _second_custom(first, vars_two)
        out[f'a2:dvar-basis:{first}'] = _second_custom(first, lambda s, x, y: (s.table.node_base(x), s.dvar(P('sexyprime', y), 'basis'))[1])
        out[f'a2:formula:{first}'] = _second_custom(first, lambda s, x, y: (s.assume_formula(And(P('real', x), P('sexyprime', y))), s.table.var(P('sexyprime', y)))[1])
        out[f'a2:formula-two:{first}'] = _second_custom(first, lambda s, x, y: (s.assume_formula(And(P('sexyprime', x), P('sexyprime', y))), s.table.var(P('sexyprime', y)))[1])
    return out


_OBJECT_WAYS = ('var-basis', 'var-one-lit', 'var-several', 'dvar-one-lit', 'dvar-several', 'dvar-pos', 'dvar-negunit', 'dvar-basis', '_dvar',
                'node', 'assume', 'assume-and', 'literal_of', 'reenter')
_CUSTOM_WAYS = ('node-then-var', 'var-then-node', 'two-atoms', 'dvar-basis', 'formula', 'formula-two')
_OBJECT_IDS = [f'a1:{k}:{i}' for i in (0, 1) for k in _OBJECT_WAYS] + [f'a2:{k}:{i}' for i in (0, 1) for k in _CUSTOM_WAYS]


def _ids():
    # Named without importing the engine at collection.
    names = [f'{e}:{s}:{d}' for s in SHAPES for d in (1, 10, 63, 64, 65, 66, 100, 300, 3500) for e in ('assume', 'literal_of')]
    return names + ['unhashable:compile', 'unhashable:literal', 'unhashable:assume', 'unhashable:literal_of', 'pred-int:assume',
                    'pred-int:literal_of', 'pred-int:compile', 'pred-joined', 'node-joined', 'node-joined:or', 'node-joined:custom', 'node-joined:custom-then-block', 'pred-none', 'pred-list:assume',
                    'pred-list:compile', 'pred-custom-str', 'not-a-formula', 'not-a-formula:compile', 'stop-from-args',
                    'kept:two-steps', 'kept:then-node-base'] + [f'kept:formula:{i}' for i in range(120)] + _OBJECT_IDS


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


def test_node_joined_custom_atom_keeps_its_own_expr(both):
    """A custom atom keeps its own `expr` on both, so `mine(1.0)` stays that when a block atom on `True` joins its node. Once a
    named difference, ended by keeping each custom atom's expr apart from the node's object."""
    py, rust = (b['cases']['node-joined:custom-then-block'] for b in both)
    assert 'mine(1.0)' in py['atoms'] and 'mine(1.0)' in rust['atoms']
    assert py == rust


def test_visit_takes_the_object_passed_and_the_slot_the_first(both):
    """Sa-port-34's rule for `Session`, both orders: `node_base(slot)` first, so the slot keeps it, and the object passed after it
    is the one visited. A template that reads identity (`Pow`'s `same` row) sees that object on both."""
    for first in (0, 1):
        for way in ('var-basis', 'var-one-lit', 'var-several', 'dvar-one-lit', 'dvar-several', 'dvar-pos', 'dvar-basis', '_dvar', 'node'):
            py, rust = (b['cases'][f'a1:{way}:{first}']['out'] for b in both)
            assert py == rust, way
            assert "'slot_holds': 'slot'" in py[1], way
            # A basis atom under a connective takes a variable and no visit.
            assert ("'visited': []" if way == 'dvar-basis' else "'visited': ['passed'") in py[1], (way, py)


def test_custom_atom_keeps_the_first_to_reach_the_table(both):
    """Sa-port-34's rule, both orders, and `facts_for` reads this `expr`: a `Tuple` there means no two-argument handler matches."""
    for way, want in (('node-then-var', ('Args', 'Tuple')), ('var-then-node', ('Args', 'Tuple')), ('two-atoms', ('Tuple', 'Args')), ('dvar-basis', ('Args', 'Tuple'))):
        for first, name in enumerate(want):
            py, rust = (b['cases'][f'a2:{way}:{first}']['out'] for b in both)
            assert py == rust, way
            assert f"'expr': '{name}'" in py[1], (way, first, py)


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
    assert c['refuse:object'] > 0 and c['join'] > 0


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
