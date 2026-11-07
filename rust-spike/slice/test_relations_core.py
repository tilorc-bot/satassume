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
        # C2b. `_eq_infinity`: fresh dev never reaches it, so these and the fuzz are its evidence.
        'eq-oo-symbol': (Q.eq(x, oo), Q.positive_infinite(x)),
        'eq-oo-left': (Q.eq(oo, x), Q.positive_infinite(x)),
        'eq-minus-oo': (Q.eq(x, -oo), Q.negative_infinite(x)),
        'eq-oo-number': (Q.eq(f(x), oo), Q.eq(f(x), 2)),
        'eq-oo-pi': (Q.eq(pi, oo), True),
        'eq-minus-oo-sqrt': (Q.eq(sqrt(2), -oo), True),
        # `_guard` and `_bound`: a closed term in a guarded atom, twice, so the memo and `_bounded` both answer.
        'guard-twice': (Q.lt(x + pi, y) & Q.lt(x + pi, z), Q.gt(x, 1)),
        'bound-sqrt': (Q.lt(sqrt(2), x) & Q.lt(x, sqrt(3)), Q.gt(x, 5)),
        'link-unlinked-eq': (Q.eq(x + y, 0), Q.positive(x + y)),
    }


def _run():
    from satassume import engine
    from satassume.sympy_api import ask
    from sympy import Q
    Q_lt = Q.lt
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
    # `selectors_of` reaches no clause: what it returned is compared on its own.
    from satassume import relations as _rel
    sels, py_sel = [], _rel.Relations.selectors_of

    def rec_sel(self, atoms):
        got = py_sel(self, atoms)
        sels.append(list(got))
        return got
    _rel.Relations.selectors_of = rec_sel
    out = {}
    for name, (p, a) in _queries().items():
        streams[0] = []
        sels.clear()
        try:
            got = repr(ask(p, a, engine=engine.Engine()))
        except BaseException as e:
            got = f'{type(e).__name__}: {e}'
        out[name] = dict(answer=got, streams=streams[0], selectors=list(sels))
    # `_order_infinite` returns on an unknown sign, past the `ensure` and `var` of the terms before it: those effects stay.
    from sympy import Symbol as Sy, pi as _pi
    from satassume import relations
    from satassume.theories.lra.constfield import Undecided
    real_sign, asked = relations.sign, [0]

    def undecided(c):
        asked[0] += 1
        raise Undecided(c)
    relations.sign = undecided
    streams[0] = []
    a_, b_, c_ = Sy('a_'), Sy('b_'), Sy('c_')
    try:
        got = repr(ask(Q_lt(a_ + _pi * b_, c_), True, engine=engine.Engine()))
    finally:
        relations.sign = real_sign
    out['infinite-undecided'] = dict(answer=got, streams=streams[0], asked=asked[0] > 0)
    # The reference keeps Python's `VarTable` under `Relations`, so these stay Python's and never reach Rust's.
    from satassume.ref import ref_outcome
    from sympy import Q, Symbol
    x, y = Symbol('x'), Symbol('y')
    before = mod.counts()['rel:order_sides'] if mod else 0
    out['ref'] = dict(answer=repr(ref_outcome(Q.lt(x, y), Q.gt(x, 1))), streams=[])
    out['ref-stayed-python'] = dict(answer=repr((mod.counts()['rel:order_sides'] if mod else 0) == before), streams=[])
    return dict(cases=out, counts=mod.counts() if mod else {})


def _direct():
    """`_guard`/`_bound` and `_eq_infinity`'s three paths called directly, `is_` forced where a real query can't choose the path.

    No query reaches `_bound`, on Python's own either, so this is its evidence. `_eq_infinity`'s plan and its trace test went with
    C2b; this replaces them. Each case records clauses, `ensure` and `is_`, in order, and what the method returned."""
    from sympy import Q, S, Symbol, oo, pi, sqrt
    from satassume.engine import Engine, Session
    from satassume.knowledge.extensions import Args
    from satassume.relations import Relations
    from satassume.sat.formula import P
    mod = _rust() if os.environ.get('MODE', 'rust') == 'rust' else None
    if mod:
        import term_live
    x = Symbol('x')

    def fresh(prop, answer=...):
        eng = Engine()
        log = []
        if answer is not ...:
            def is_(e, pred):
                log.append(['is_', str(e), pred])
                return answer
            eng.is_ = is_
        s = Session(eng)
        rel = Relations(s, eng._relation_specs)
        s.relations = rel
        add, ens = s.solver.add_clause, s.ensure

        def rec_add(c):
            log.append(['clause', list(c)])
            return add(c)

        def rec_ensure(e, preds):
            log.append(['ensure', str(e), sorted(preds)])
            return ens(e, preds)
        s.solver.add_clause, s.ensure = rec_add, rec_ensure
        if mod:
            term_live.stack().append(term_live._convert(prop, True, eng))
        return s, rel, log

    def done():
        if mod:
            term_live.stack().pop()

    def lra(rel):
        ad = next(a for a in map(rel._adapter, rel.session.engine._relation_specs) if hasattr(a, 'register_bounds'))
        rel.session.solver.attach_theory(ad.theory)
        return ad

    class NoBounds:
        pass

    class NoneBounds:
        register_bounds = None

    out = {}
    for name, side, inf, answer, path in (
            ('symbolic', x, oo, ..., 'symbolic'), ('symbolic-left', x, -oo, ..., 'symbolic'),
            ('decided-false', S(2), oo, False, 'decided'), ('decided-true', oo, oo, True, 'decided'),
            ('decided-left', S(2), -oo, False, 'decided'), ('undecided', pi, -oo, None, 'undecided')):
        for flip in (False, True):
            s, rel, log = fresh(Q.eq(side, inf), answer)
            try:
                atom = P('eq', Args((inf, side) if flip else (side, inf)))
                var = s.table.var(atom)
                rel._eq_infinity(var, atom)
            finally:
                done()
            out[f'eq-{name}-{"flip" if flip else "plain"}'] = dict(log=log, path=path, var=var)
    # Neither side infinite: no clause, no read.
    s, rel, log = fresh(Q.eq(x, S(2)), True)
    try:
        atom = P('eq', Args((x, S(2))))
        rel._eq_infinity(s.table.var(atom), atom)
    finally:
        done()
    out['eq-no-infinity'] = dict(log=log, path='none')

    y = Symbol('y')
    for name, terms, answer in (('real-at-root', [pi], ...), ('forced-unknown', [pi], None), ('forced-false', [sqrt(2)], False),
                                ('forced-true', [sqrt(2)], True), ('symbol', [x], ...), ('mixed', [pi, x, sqrt(2), y], ...)):
        s, rel, log = fresh(Q.positive(sum(terms) + x), answer)
        try:
            ad = lra(rel)
            g = rel._guard(ad, terms)
            again = rel._guard(ad, terms)
            # A new term list: new memo entry, the constant already bounded.
            other = rel._guard(ad, list(terms) + [x])
        finally:
            done()
        out['guard-' + name] = dict(log=log, guard=list(g), same=g is again, other=list(other))
    for name, ad_of in (('no-attr', lambda rel: NoBounds()), ('none-attr', lambda rel: NoneBounds())):
        s, rel, log = fresh(Q.positive(pi))
        try:
            ad = ad_of(rel)
            got = rel._guard(ad, [pi])
        finally:
            done()
        out['guard-' + name] = dict(log=log, guard=list(got))
    # `_bound` called on its own; a term with symbols registers nothing.
    for name, term in (('pi', pi), ('sqrt', sqrt(2)), ('symbol', x)):
        s, rel, log = fresh(Q.positive(term))
        try:
            got = rel._bound(lra(rel), term)
        finally:
            done()
        out['bound-' + name] = dict(log=log, returned=repr(got))
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


@pytest.fixture(scope='module')
def py_direct():
    return _call('direct', MODE='py')


@pytest.fixture(scope='module')
def rust_direct():
    return _call('direct')


def _differ(a, b):
    return sorted(k for k in a['cases'] if a['cases'][k] != b['cases'][k])


def test_methods_match_python(py, rust):
    assert _differ(py, rust) == []


def test_same_core_python_methods_match(py):
    assert _differ(py, _call('run', SLICE_REL='py')) == []


def test_undecided_return_was_reached(rust):
    assert rust['cases']['infinite-undecided']['asked'] is True


def test_direct_matches_python(py_direct, rust_direct):
    assert _differ(py_direct, rust_direct) == []


def test_direct_reaches_bound_and_every_infinity_path(py_direct, rust_direct):
    """So the MATCH above covers what it's for, on Python's side and Rust's."""
    for run in (py_direct, rust_direct):
        cases = run['cases']
        for name, case in cases.items():
            kinds = {step[0] for step in case['log']}
            if case.get('path') == 'symbolic':
                assert 'is_' not in kinds and 'ensure' in kinds and 'clause' in kinds, name
            elif case.get('path') == 'decided':
                assert 'is_' in kinds and 'ensure' not in kinds and [s for s in case['log'] if s[0] == 'clause'] == [
                    ['clause', [case['var'] if 'true' in name else -case['var']]]], name
            elif case.get('path') == 'undecided':
                assert 'is_' in kinds and 'ensure' in kinds and 'clause' in kinds, name
            elif case.get('path') == 'none':
                assert case['log'] == [], name
        # `_bound`'s root facts, once per constant, the memo's list kept.
        for name in ('guard-real-at-root', 'guard-forced-unknown', 'guard-forced-true', 'bound-pi', 'bound-sqrt'):
            facts = [s for s in cases[name]['log'] if s[0] == 'clause']
            assert len(facts) >= 2 and all(len(s[1]) == 1 for s in facts[:2]), name
        # Three `_guard` calls, one `_bound`: two root facts, and the rest is `ensure(x, real)`'s, none of them a unit.
        assert sum(s[0] == 'clause' and len(s[1]) == 1 for s in cases['guard-real-at-root']['log']) == 2
        assert cases['guard-real-at-root']['guard'] == [] and cases['guard-real-at-root']['same'] is True
        assert cases['guard-forced-unknown']['guard'] != []
        assert cases['bound-symbol']['log'] == [] and cases['guard-no-attr']['log'] == cases['guard-none-attr']['log']
    assert rust_direct['counts']['rel:bound'] > 0 and rust_direct['counts']['rel:eq_infinity'] > 0


@pytest.mark.parametrize('plant', ['drop-bound', 'drop-guard', 'drop-eq-infinity'])
def test_direct_sees_its_plants(py_direct, plant):
    got = _call('direct', SLICE_SESSION_PLANT=plant)
    assert got['counts']['rel:plant_fired'] > 0
    assert _differ(py_direct, got) != []


def test_each_method_ran(rust):
    c = rust['counts']
    for k in ('closed_extended_real', 'order_sides', 'order_infinite', 'trichotomy', 'mention_number', 'link_integer',
              'fresh', 'interpret', 'guard', 'link', 'selectors_of', 'eq_infinity'):
        assert c['rel:' + k] > 0, k
    # Not `bound`: no query here reaches it, on Python's own `_bound` either. `_direct` calls it.
    assert c['rel:var'] > 0 and c['link:resolved'] > 0 and c['link:hit'] > 0 and c['link:no_node'] > 0


def test_link_none_moves_nothing(py):
    """The ruling: the link doesn't depend on any row being there."""
    got = _call('run', SLICE_SESSION_PLANT='link-none')
    assert got['counts']['rel:plant_fired'] > 0 and got['counts']['link:resolved'] == 0
    assert _differ(py, got) == []


@pytest.mark.parametrize('plant', ['drop-order-sides', 'drop-order-infinite', 'drop-trichotomy', 'drop-interpret', 'drop-guard',
                                   'drop-link', 'drop-selector', 'drop-eq-infinity', 'fresh-skew'])
def test_dropped_clause_is_seen(py, plant):
    got = _call('run', SLICE_SESSION_PLANT=plant)
    assert got['counts']['rel:plant_fired'] > 0
    assert _differ(py, got) != []


def test_fresh_not_inert_fires():
    """The clause stream can't see `set_inert`, so this plant only shows it fires here. Its comparison is the fresh digests."""
    assert _call('run', SLICE_SESSION_PLANT='fresh-not-inert')['counts']['rel:plant_fired'] > 0


def test_link_crossings_add_up(rust):
    """Each kind of crossing the report quotes, against the calls that make it."""
    c = rust['counts']
    assert c['link:calls'] == c['link:cross_current'] > 0
    assert c['link:cross_hash'] == c['link:calls'] - c['link:no_table']
    assert c['link:cross_term_id'] == c['link:cross_hash'] - c['link:hit']


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
    print(json.dumps({'run': _run, 'join': _join, 'direct': _direct}[sys.argv[1]]()))
