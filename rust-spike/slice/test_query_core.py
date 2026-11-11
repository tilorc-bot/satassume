"""Step 5c3: `Session`'s queries in Rust (`query.rs`: `query_lit`, `prepare_query`, `emit`, `query_literal`, `_query_all`,
`literal_of`, `_relations`, `_ensure_atoms`, `_ensure_twins`) called directly, Python against Rust, each mode in its own process.
Cases record what came back (an `InconsistentAssumptions` as a value), every clause in order, and the session's state after:
test_discovery_core's `_state` plus the table's length, auxiliaries and non-basis atoms, the formula memo `literals`, and the
relations object (test_relations_core's `_rel_state`, its queue, `active`, `top` and `linked`).

The workloads reach most of these through `Engine._ask`, but not all: `literal_of` only runs for a proposition that isn't a
vocabulary atom, `_relations` only once a session has a `Relations`, and the consistency check after a propagated answer only
matters when the assumptions are inconsistent in a way propagation doesn't see. Here `Session(Engine())` (which has relation
specs) gets zero atoms, relation atoms, compound propositions, an assumption set with a zero atom under the query's term, and
forged clauses over auxiliary variables; every moved method is called by name. Each plant must fire and move some case.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLANTS = ('drop-prep-twins', 'drop-prep-rel', 'query-lit-tuple', 'drop-ql-mention', 'ql-skip-consistent', 'drop-qa-mention',
          'drop-lo-memo', 'drop-lo-discover', 'drop-rel-process', 'drop-ea-ensure', 'drop-twins-var', 'drop-emit')
MOVED = ('query_lit', 'prepare_query', 'emit', 'query_literal', 'query_all', 'literal_of', 'relations', 'ensure_atoms',
         'ensure_twins')



def _type_error(f):
    """`f()`'s repr, or the TypeError it raised (an explicit None where the def iterates)."""
    try:
        return repr(f())
    except TypeError as e:
        return 'TypeError: ' + str(e)

def _qstate(s, base):
    import test_relations_core as R
    from satassume.knowledge.rules import BASIS_INDEX
    d = base(s)
    t = s.table
    d.update(nvars=len(t), naux=t.naux,
             atoms=[[v, repr(a)] for v, a in enumerate(t.atom_of) if a is not None and a.pred not in BASIS_INDEX],
             literals=[[repr(k), v] for k, v in s.literals.items()])
    rel = s.relations
    if rel is not None:
        d['rel'] = dict(R._rel_state(rel), queue=[repr(a) for a in rel.queue], active=bool(rel.active),
                        top=[str(k) for k in rel.top], linked=sorted(map(str, rel.linked)))
    return d


def _cases():
    import test_discovery_core as D
    from sympy import Function, Symbol, sin
    from sympy import preorder_traversal
    from satassume.engine import InconsistentAssumptions
    from satassume.relations import relation_atom
    from satassume.sat.formula import And, Not, Or, P
    x, y, z, w = (Symbol(c) for c in 'xyzw')
    f = Function('f')
    for t in (x * y, x + y, z * w, sin(x - y), x - y, x * z, y * z + w, sin(y * z + w), f(x - y), f(x + y), f(z * w)):
        D.NODES.extend(preorder_traversal(t))

    def caught(fn):
        def go():
            try:
                return fn()
            except InconsistentAssumptions as e:
                return ['InconsistentAssumptions', str(e)]
        return go

    out = {}

    # query_lit over a visited node: a basis predicate, single-literal derived ones (`infinite`), conjunctions, a disjunction
    # (`antihermitian`) and the empty conjunction (`commutative`)
    preds = ('integer', 'zero', 'positive', 'infinite', 'commutative', 'antihermitian', 'odd', 'nonzero')
    out['query_lit'] = lambda s: [('ensure', lambda: s.ensure(x * y))] + [(p, lambda p=p: s.query_lit(p, x * y)) for p in preds]

    # prepare_query, then query_literal of what it returns, with and without search: the first zero atom allocates its twin
    # eq(t, 0), flushes and makes the session's relations; later queries go through `_relations`; non-vocabulary propositions
    # go through `literal_of`, a second time through its memo
    props = [P('zero', x + y), P('positive', x * y), P('nonnegative', x * y), P('antihermitian', z * w), P('zero', z * w),
             P('infinite', x + y), Or(relation_atom('lt', x, y), P('positive', z)), relation_atom('eq', x, z * w),
             And(P('positive', x), Not(P('zero', y * z + w))), Or(relation_atom('lt', x, y), P('positive', z)),
             And(P('zero', x + y), P('positive', f(x + y))), P('rational', x * y)]

    def prep_steps(order, search):
        def fn(s):
            for i in order:
                p = props[i]
                got = []
                yield f'prepare:{i}', lambda p=p: got.append(s.prepare_query(p)) or got[-1]
                yield f'query:{i}', caught(lambda: s.query_literal(got[-1], (), search))
        return fn
    out['prep:all:search'] = prep_steps(range(len(props)), True)
    out['prep:all:nosearch'] = prep_steps(range(len(props)), False)
    out['prep:rel-first'] = prep_steps((7, 1, 0, 6, 9, 4, 10), True)
    out['prep:compound-first'] = prep_steps((8, 2, 3, 0), True)

    # under an assumption set: its zero atom's argument is under the query's term, so a query that isn't about zero still
    # has twins (`_glue_of` with the set's zero args); query_literal under the set's literals, settled by propagation or not
    sets = {'zero-under': And(P('zero', x - y), P('positive', z)),
            'rel': And(relation_atom('lt', x, y * z), Or(P('negative', w), P('zero', x * z))),
            'plain': Or(P('integer', x * y), P('positive', w)),
            'int': And(P('integer', x * y), P('positive', w)),
            'app': And(P('zero', x + y), P('positive', f(x + y)), P('integer', z * w))}
    qs = [P('positive', sin(x - y)), P('zero', x - y), P('nonzero', x * z), P('real', y * z + w), P('antihermitian', x * y),
          relation_atom('lt', z, w), And(P('positive', z), P('integer', x * y)), P('positive', f(x - y)), P('rational', x * y),
          P('algebraic', w), P('zero', x + y), P('complex', z * w), P('nonzero', f(z * w))]

    def set_steps(af, order=None):
        def fn(s):
            lits = []
            yield 'assume', lambda: lits.extend(s.assume_formula(af)) or list(lits)
            for i in (range(len(qs)) if order is None else order):
                q = qs[i]
                got = []
                yield f'prepare:{i}', lambda q=q: got.append(s.prepare_query(q)) or got[-1]
                yield f'query:{i}', caught(lambda: s.query_literal(got[-1], lits, True))
                yield f'nosearch:{i}', caught(lambda: s.query_literal(got[-1], lits, False))
        return fn
    for k, af in sets.items():
        out[f'set:{k}'] = set_steps(af)
    out['set:zero-under:app-first'] = set_steps(sets['zero-under'], (7, 9, 1, 0))

    # by name: literal_of twice (its memo), _ensure_atoms, _ensure_twins with and without zero atoms, _relations, emit
    def by_name(s):
        g = Or(relation_atom('lt', x, y), And(P('zero', x * y), P('positive', z * w)))
        yield 'ensure_twins:none', lambda: s._ensure_twins((P('positive', x), P('integer', y)))
        yield 'ensure_atoms', lambda: s._ensure_atoms(And(P('positive', x * z), P('zero', y * z + w)))
        yield 'ensure_twins:zero', lambda: s._ensure_twins((P('zero', z * w), P('positive', x)))
        yield 'literal_of', lambda: s.literal_of(g)
        yield 'literal_of:again', lambda: s.literal_of(g)
        yield 'ensure_twins:app', lambda: s._ensure_twins((P('zero', z * w), P('positive', f(z * w))))
        yield 'ensure_atoms:app', lambda: s._ensure_atoms(And(P('zero', x - y), P('integer', f(x - y))))
        yield 'literal_of:other', lambda: s.literal_of(Not(relation_atom('eq', x, z)))
        yield 'relations', lambda: s._relations(And(relation_atom('lt', z, w), P('positive', x * y)))
        yield 'relations:plain', lambda: s._relations(P('integer', z * w))
        yield 'emit', lambda: s.emit([s.query_lit('integer', x * y), -s.query_lit('zero', z * w)])
        yield 'query_lit', lambda: s.query_lit('infinite', z * w)
    out['by-name'] = by_name

    # forged clauses over auxiliary variables: under `a`, b and c have no model, but propagation from `a` only finds q, so the
    # answer propagation settles must still be refused once the assumptions are found inconsistent; a root-decided literal;
    # assumptions inconsistent by propagation; the conjunction path under the same assumptions
    def forged(s):
        v = {}

        def setup():
            s.ensure(x * y)
            for n in 'abcd':
                v[n] = s.table.aux()
            s.solver.ensure_vars(len(s.table))
            q, r = s.query_lit('integer', x * y), s.query_lit('zero', x * y)
            a, b, c, d = v['a'], v['b'], v['c'], v['d']
            for cl in ([-a, b, c], [-a, b, -c], [-a, -b, c], [-a, -b, -c], [-a, q], [-a, -r], [-d, q]):
                s.emit(cl)
            v['q'], v['r'] = q, r
            return sorted(v.items())
        yield 'setup', setup
        # under `d`, q's block implies rational and algebraic, which no clause mentions: written to the trail, and so
        # settled without search, only once the query mentions them
        yield 'block', caught(lambda: s.query_literal(s.query_lit('rational', x * y), [v['d']], False))
        # the defaults (assumptions=(), search=True; query.rs gives the Rust entry the def's signature), by position and
        # keyword, and an explicit None, which the def passes on
        yield 'default', caught(lambda: s.query_literal(v['q']))
        yield 'default:kw', caught(lambda: s.query_literal(v['q'], search=False))
        yield 'default:assume', caught(lambda: s.query_literal(v['r'], assumptions=[v['a']]))
        yield 'none', lambda: _type_error(lambda: s.query_literal(v['q'], None))
        yield 'block:all', caught(lambda: s.query_literal(('&', (s.query_lit('algebraic', x * y), s.query_lit('complex', x * y))), [v['d']], False))
        yield 'propagated', caught(lambda: s.query_literal(v['q'], [v['a']], True))
        yield 'propagated:neg', caught(lambda: s.query_literal(v['r'], [v['a']], False))
        yield 'all:propagated', caught(lambda: s.query_literal(('&', (v['q'], -v['r'])), [v['a']], True))
        yield 'all:false', caught(lambda: s.query_literal(('&', (v['q'], v['r'])), [v['a']], True))
        yield 'or', caught(lambda: s.query_literal(('|', (v['r'], v['q'])), [v['a']], True))
        yield 'contradict', caught(lambda: s.query_literal(v['q'], [v['q'], -v['q']], True))
        yield 'free', caught(lambda: s.query_literal(v['b'], [], True))
        yield 'free:nosearch', caught(lambda: s.query_literal(v['b'], [], False))
        yield 'root', lambda: s.emit([v['b']]) or s.query_literal(v['b'], [], False)
        yield 'all:root', caught(lambda: s.query_literal(('&', (v['b'], v['q'])), [], True))
        yield 'all:nosearch', caught(lambda: s.query_literal(('&', (v['b'], v['q'])), [], False))
        # a rule-block implication of a literal nothing else mentions: on the trail only once it's mentioned
        yield 'root:rule', lambda: s.emit([v['q']]) or s.query_literal(s.query_lit('rational', x * y), [], False)
        yield 'root:rule-all', lambda: s.query_literal(s.query_lit('real', x * y), [], False)
    out['forged'] = forged
    return out


def _main(mode):
    import test_discovery_core as D
    live = D._rust() if mode == 'rust' else None
    base = D._state
    D._state = lambda s: _qstate(s, base)
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


def test_query_literal_defaults_are_the_defs(both):
    py, rust = both
    st = {k: {n: r for n, r, _, _ in c['steps']} for k, c in rust['cases'].items()}['forged']
    sp = {k: {n: r for n, r, _, _ in c['steps']} for k, c in py['cases'].items()}['forged']
    keys = ('default', 'default:kw', 'default:assume', 'none')
    assert [st[k] for k in keys] == [sp[k] for k in keys], ([st[k] for k in keys], [sp[k] for k in keys])
    assert 'TypeError' in st['none'], st['none']


def test_cases_run_and_reach_what_they_say(both):
    """No case raised past its step, each moved method ran on Rust, and the paths the cases are for were taken on Python."""
    py, rust = both
    bad = {k: c['out'] for k, c in py['cases'].items() if c['out'] != 'ok'}
    assert bad == {}
    st = {k: {n: r for n, r, _, _ in c['steps']} for k, c in py['cases'].items()}
    # propagation settled the answer, and the consistency check refused it
    assert st['forged']['propagated'].startswith("['InconsistentAssumptions'")
    assert st['forged']['all:propagated'].startswith("['InconsistentAssumptions'")
    # relations were made and processed some queued atom; the zero twin eq(t, 0) was allocated
    last = py['cases']['prep:all:search']['steps'][-1][3]
    assert last['rel']['active'] and any('eq(' in a for _, a in last['atoms'])
    # literal_of's memo answered the second call
    assert st['by-name']['literal_of'] == st['by-name']['literal_of:again']
    assert st['query_lit']['infinite'].lstrip('-').isdigit() and st['query_lit']['antihermitian'].startswith("('|'")
    c = rust['counts']
    assert {m: c[f'ses:{m}'] for m in MOVED if not c[f'ses:{m}']} == {}


@pytest.mark.parametrize('plant', PLANTS)
def test_each_plant_fires_and_is_seen(both, plant):
    py, _ = both
    got = _run('rust', SLICE_SESSION_PLANT=plant)
    assert got['counts']['rel:plant_fired'] > 0
    assert _differ(py, got) != []


if __name__ == '__main__':
    _main(sys.argv[1])
