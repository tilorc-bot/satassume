"""Step 5b: the id-to-term link and C2a, each mode in its own process. What comes back and the clause stream of every session,
Python against Rust's methods. `link-none` is the direct test of the planner's ruling on the link: with every resolve None, so
that nothing depends on a row being there, the stream must not move. The `drop-*` plants show this comparison sees a lost clause.
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


def _queries():
    from sympy import Function, I, Integer, Q, S, Symbol, cos, oo, pi, sin, sqrt
    x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
    rx, ry = Symbol('rx', real=True), Symbol('ry', real=True)
    n = Symbol('n', integer=True)
    f = Function('f')
    return {
        'sides-free': (Q.lt(x, y), True),
        'sides-number': (Q.lt(Integer(1), x), Q.gt(x, 2)),
        'sides-half': (Q.lt(S.Half, x), Q.gt(x, 1)),
        'sides-nan': (Q.lt(x, S.NaN), True),
        'sides-closed-pi': (Q.lt(pi, x), Q.gt(x, 4)),
        'sides-closed-sqrt': (Q.lt(sqrt(2), x), Q.gt(x, 2)),
        'sides-oo': (Q.lt(x, oo), Q.real(x)),
        'sides-minus-oo': (Q.lt(-oo, x), Q.real(x)),
        'sides-I': (Q.lt(I, x), True),
        'infinite-plain': (Q.lt(rx, ry), Q.positive_infinite(ry)),
        'infinite-sum': (Q.lt(x + y, z), Q.positive_infinite(x)),
        'infinite-neg': (Q.lt(x - y, z), Q.negative_infinite(x)),
        'infinite-pi-coeff': (Q.lt(pi * x, y), Q.positive(x)),
        'infinite-cancels': (Q.lt(x - x + y, z), Q.real(y)),
        'infinite-number-term': (Q.lt(x + sqrt(2), y), Q.lt(x, y)),
        'trichotomy': (Q.eq(x, y), Q.le(x, y) & Q.ge(x, y)),
        'trichotomy-real': (Q.eq(rx, ry), Q.le(rx, ry) & Q.ge(rx, ry)),
        'trichotomy-number': (Q.positive(x), Q.le(x, 2) & Q.ge(x, 2)),
        'mention': (Q.positive(sin(2)), Q.eq(sin(2), 1)),
        'mention-two': (Q.eq(f(sin(2)), f(cos(2))), Q.eq(sin(2), cos(2))),
        'mention-with-order': (Q.lt(x, sin(2)), Q.positive(sin(2)) & Q.gt(x, 1)),
        'mention-or': (Q.positive(sin(2)) | Q.lt(x, y), Q.positive(x)),
        'mention-eq': (Q.positive(f(sin(2))), Q.eq(x, sin(2)) & Q.positive(f(x))),
        'integer-link': (Q.integer(x + 1), Q.integer(x)),
        'integer-bound': (Q.lt(2 * n, 2) & Q.gt(2 * n, 0), True),
    }


def _run():
    from satassume import engine
    from satassume.sympy_api import ask
    mod = _rust() if os.environ.get('MODE', 'rust') == 'rust' else None
    streams = [None]
    init = engine.Session.__init__

    def rec_init(self, *a, **k):
        init(self, *a, **k)
        add, stream = self.solver.add_clause, []
        streams[0].append(stream)

        def rec(c):
            stream.append(list(c))
            return add(c)
        self.solver.add_clause = rec
    engine.Session.__init__ = rec_init
    out = {}
    for name, (p, a) in _queries().items():
        streams[0] = []
        try:
            got = repr(ask(p, a, engine=engine.Engine()))
        except BaseException as e:
            got = f'{type(e).__name__}: {e}'
        out[name] = dict(answer=got, streams=streams[0])
    # The reference keeps Python's `VarTable` under `Relations`, so these stay Python's and never reach Rust's.
    from satassume.ref import ref_outcome
    from sympy import Q, Symbol
    x, y = Symbol('x'), Symbol('y')
    before = mod.counts()['rel:order_sides'] if mod else 0
    out['ref'] = dict(answer=repr(ref_outcome(Q.lt(x, y), Q.gt(x, 1))), streams=[])
    out['ref-stayed-python'] = dict(answer=repr((mod.counts()['rel:order_sides'] if mod else 0) == before), streams=[])
    return dict(cases=out, counts=mod.counts() if mod else {})


def _join():
    """A query's input term and the same text under another `Function('f')`, each visited first in turn."""
    from sympy import Function, Q, Symbol
    from sympy.core.cache import clear_cache
    import sa_solver
    from satassume.engine import Engine, Session
    mod = _rust()
    import term_live
    x = Symbol('x')
    held = Function('f')(x)
    clear_cache()
    other = Function('f')(x)
    assert held == other and type(held) is not type(other)
    out = {}
    for order, first in (('held-first', held), ('other-first', other)):
        eng = Engine()
        s = Session(eng)
        q = term_live._convert(Q.positive(held), True, eng)
        assert q.kept is None and q.ids.get(held) is not None
        term_live.stack().append(q)
        try:
            core = s.table.core
            before = mod.counts()
            none_yet = sa_solver.rel_link_probe(core, held)
            n_before = len(s.table)
            after_no_node = mod.counts()
            s.var('positive', first)
            s.var('negative', other if first is held else held)
            joins = mod.counts()['join']
            ids = [sa_solver.rel_link_probe(core, o) for o in (held, other, held, held, other)]
            end = mod.counts()
            out[order] = dict(
                none_yet=none_yet == q.ids[held], ids=ids, want=q.ids[held], no_new_node=n_before == 0,
                no_node=after_no_node['link:no_node'] - before['link:no_node'],
                join_quiet=end['join'] == joins, hit=end['link:hit'] - before['link:hit'],
                second=end['link:second'] - before['link:second'], none=end['link:none'] - before['link:none'])
        finally:
            term_live.stack().pop()
    # Numbering: a resolve before the first var leaves the same numbers as none.
    numbers = []
    for probe in (False, True):
        eng = Engine()
        s = Session(eng)
        q = term_live._convert(Q.positive(held), True, eng)
        term_live.stack().append(q)
        try:
            if probe:
                sa_solver.rel_link_probe(s.table.core, held)
            numbers.append((s.var('positive', x), s.var('positive', held), s.var('real', other)))
        finally:
            term_live.stack().pop()
    out['numbers'] = numbers
    # Outside any query, and in a kept one.
    s = Session(Engine())
    before = mod.counts()['link:no_table']
    out['no_table'] = [sa_solver.rel_link_probe(s.table.core, held), mod.counts()['link:no_table'] - before]
    return out


def _call(what, **env):
    e = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE] + os.environ.get('PYTHONPATH', '').split(os.pathsep)), **env)
    r = subprocess.run([sys.executable, __file__, what], env=e, capture_output=True, text=True, cwd=HERE)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.splitlines()[-1])


@pytest.fixture(scope='module')
def py():
    return _call('run', MODE='py')


@pytest.fixture(scope='module')
def rust():
    return _call('run')


def _differ(a, b):
    return sorted(k for k in a['cases'] if a['cases'][k] != b['cases'][k])


def test_methods_match_python(py, rust):
    assert _differ(py, rust) == []


def test_same_core_python_methods_match(py):
    assert _differ(py, _call('run', SLICE_REL='py')) == []


def test_each_method_ran(rust):
    c = rust['counts']
    for k in ('closed_extended_real', 'order_sides', 'order_infinite', 'trichotomy', 'mention_number', 'link_integer'):
        assert c['rel:' + k] > 0, k
    assert c['rel:var'] > 0 and c['link:resolved'] > 0 and c['link:hit'] > 0 and c['link:no_node'] > 0


def test_link_none_moves_nothing(py):
    """The ruling: the link doesn't depend on any row being there."""
    got = _call('run', SLICE_SESSION_PLANT='link-none')
    assert got['counts']['rel:plant_fired'] > 0 and got['counts']['link:resolved'] == 0
    assert _differ(py, got) == []


@pytest.mark.parametrize('plant', ['drop-order-sides', 'drop-order-infinite', 'drop-trichotomy'])
def test_dropped_clause_is_seen(py, plant):
    got = _call('run', SLICE_SESSION_PLANT=plant)
    assert got['counts']['rel:plant_fired'] > 0
    assert _differ(py, got) != []


def test_join_second_object_resolves_on_its_own():
    got = _call('join')
    for order in ('held-first', 'other-first'):
        o = got[order]
        # The term's own object has its id, the other class none, in either order and past memo hits.
        assert o['ids'] == [o['want'], None, o['want'], o['want'], None], (order, o)
        assert o['none_yet'] and o['no_new_node'] and o['no_node'] == 1 and o['join_quiet'], (order, o)
        assert o['hit'] >= 2 and o['second'] == 2 and o['none'] == 2, (order, o)
    a, b = got['numbers']
    assert a == b


def test_link_outside_a_query_is_none():
    got = _call('join')
    assert got['no_table'] == [None, 1]


if __name__ == '__main__':
    print(json.dumps({'run': _run, 'join': _join}[sys.argv[1]]()))
