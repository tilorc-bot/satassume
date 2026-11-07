"""`_common.resolve` and `Pattern.__init__` from Rust (component 6, issue 323), against Python's by field: seeded random rules, then
the hand cases: contradiction, undecidable constant literal, repeated premise, wide at and past `MAX_EXPAND`, empty clause, unknown
predicate. Also that the counters fire, what a read raises comes through as itself, a Rust failure is loud, and `undo` restores both.
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pytest
from sympy import E as EE, I, Integer, Q, Rational, S, Symbol, pi

from harness.state import reset_module_state
from satassume import engine as E
from satassume import sympy_api
from satassume.knowledge import rules as R
from satassume.knowledge.templates import _common
from satassume.knowledge.templates._common import Compiled, VOCAB

import knowledge_live as K

PY_RESOLVE, PY_PATTERN = _common.resolve, _common.Pattern
CONSTS = [Integer(0), Integer(1), Integer(-1), Integer(2), Integer(4), Rational(1, 2), S.Infinity, S.NegativeInfinity, S.ComplexInfinity,
          S.NaN, pi, EE, I, 2 * I, S.Half + I]
PREDS = sorted(VOCAB)


@pytest.fixture
def live():
    K.COUNTS.clear()
    K.MISMATCHES.clear()
    K.ORDER_DIFFS.clear()
    undo = K.install()
    yield K.COUNTS
    undo()
    reset_module_state(sympy_cache=False)


def outcome(f, *a):
    """What `f` returned or raised, with type and arguments."""
    try:
        return 'returned', f(*a)
    except Exception as e:
        return 'raised', type(e), e.args


def fields(p):
    return {f: getattr(p, f) for f in K.FIELDS}


def same_pattern(rules, node, nobjs=1):
    a, b = outcome(_common.Pattern, rules, node, nobjs), outcome(PY_PATTERN, rules, node, nobjs)
    assert a[0] == b[0] and (a[0] == 'raised' and a == b or a[0] == 'returned' and fields(a[1]) == fields(b[1])), (rules, node, a, b)
    if a[0] == 'returned':
        # The engine iterates `child_preds`; its order and each set's are part of the result.
        assert repr(fields(a[1])) == repr(fields(b[1])), (rules, node)
        assert all(type(fields(a[1])[f]) is type(fields(b[1])[f]) for f in K.FIELDS)
        return a[1]
    return a


def same_resolve(rules, consts):
    """Equal result, and the same reads in the same order, which is what makes a raising read parity."""
    py_read, log = _common.const_value, []

    def read(c, p):
        log.append((repr(c), p))
        return py_read(c, p)
    _common.const_value = read
    try:
        a = outcome(_common.resolve, rules, consts)
        reads, log[:] = list(log), []
        b = outcome(PY_RESOLVE, rules, consts)
        assert reads == log, (rules, consts)
    finally:
        _common.const_value = py_read
    assert a == b, (rules, consts, a, b)
    assert repr(a) == repr(b)
    return a


def lit(rng, slots):
    return (rng.choice(slots), rng.choice(PREDS), rng.random() < .5)


def random_rules(rng, slots):
    out = []
    for _ in range(rng.randrange(0, 14)):
        ps = [lit(rng, slots) for _ in range(rng.randrange(0, 4))]
        cs = [lit(rng, slots) for _ in range(rng.randrange(1, 4))]
        if out and rng.random() < .25:      # a repeat, a repeated premise and a superset of an earlier premise set
            ps = list(rng.choice(out)[0]) + ps[:1]
            cs = list(rng.choice(out)[1])
        if ps and rng.random() < .15:
            ps.append(ps[0])
        out.append((ps, cs))
    return out


@pytest.mark.parametrize('seed', range(4))
def test_random_rules_match_python(live, seed):
    rng = random.Random(seed)
    resolved = contradictions = 0
    for _ in range(600):
        slots = list(range(rng.randrange(1, 5)))
        consts = {k: rng.choice(CONSTS) for k in slots if rng.random() < .5}
        if slots and rng.random() < .2:
            consts[slots[-1]] = None
        rules = random_rules(rng, slots)
        r = same_resolve(rules, consts)
        if r[0] == 'raised':
            contradictions += 1
            continue
        resolved += 1
        same_pattern(r[1], rng.choice(slots), len(slots))
    assert resolved > 100 and contradictions > 10
    assert live['common:resolve'] == 600 and live['common:pattern'] == resolved
    assert not live['fault']


def test_contradiction(live):
    rules = [([], [(0, 'positive', True)])]
    assert same_resolve(rules, {0: Integer(-1)}) == ('raised', ValueError, (K.CONTRADICTION,))
    assert live['common:contradiction'] == 1


def test_a_read_before_the_contradiction_and_none_after_it(live):
    rules = [([(0, 'even', True)], [(1, 'odd', True)]), ([], [(0, 'negative', True)]), ([(0, 'prime', True)], [(1, 'odd', True)])]
    assert same_resolve(rules, {0: Integer(4)})[0] == 'raised'


def test_contrapositive(live):
    rules = [([(1, 'real', True), (2, 'even', False)], [(0, 'negative', True)])]
    r = same_resolve(rules, {0: Integer(1)})
    assert r == ('returned', [((), ((1, 'real', False), (2, 'even', True)))])


def test_undecidable_constant_literal_drops_the_rule(live):
    assert _common.const_value(Integer(2), 'polar') is None or pytest.fail('pick another undecided predicate')
    prem = [([(0, 'polar', True)], [(1, 'real', True)])]
    concl = [([(1, 'real', True)], [(0, 'polar', True), (2, 'real', True)])]
    assert same_resolve(prem, {0: Integer(2)}) == ('returned', [])
    assert same_resolve(concl, {0: Integer(2)}) == ('returned', [])


def test_none_in_consts_is_not_a_constant(live):
    rules = [([(0, 'real', True)], [(1, 'real', True)])]
    assert same_resolve(rules, {0: None})[1] == [(((0, 'real', True),), ((1, 'real', True),))]


def test_repeated_premise_keeps_its_length_and_its_order(live):
    a = (0, 'real', True)
    b = (1, 'even', True)
    c = [(2, 'odd', True)]
    # By length [a, a] sorts after [b], yet as a set has one literal.
    for rules in ([([a, a], c), ([b], c)], [([a, b], c), ([a, a], c), ([a], c)], [([a, a], c), ([a], c)], [([b, a, b], c), ([a, b], c)]):
        same_pattern(same_resolve(rules, {})[1], 2, 3)


def test_subsumed_by_premises_only_under_the_same_conclusion(live):
    a, b, c, d = (0, 'real', True), (0, 'even', True), [(1, 'odd', True)], [(1, 'prime', True)]
    r = same_resolve([([a, b], c), ([a], c), ([a, b], d)], {})
    assert r[1] == [(((0, 'real', True),), ((1, 'odd', True),)), (((0, 'real', True), (0, 'even', True)), ((1, 'prime', True),))]


def by_cnf_size(n, pos=True):
    return next(p for p in PREDS if len(R.cnf_of(p, pos)) == n)


def wide_rule(n_preds):
    """Over distinct slots, so no literal merges and the rule has exactly 2**n clauses by `Pattern`'s product."""
    p = by_cnf_size(2)
    return ((), tuple((k, p, True) for k in range(n_preds)))


def test_wide_at_and_past_max_expand(live):
    assert _common.MAX_EXPAND == 16
    at, past = [wide_rule(4)], [wide_rule(5)]
    assert not same_pattern(at, 0, 5).wide and len(same_pattern(past, 0, 5).wide) == 1
    both = at + past + [((), ((0, 'real', True),))]
    assert same_pattern(both, 0, 5).wide == [past[0]]
    assert live['common:wide'] == 2


def test_max_expand_is_read_at_call_time(live, monkeypatch):
    monkeypatch.setattr(_common, 'MAX_EXPAND', 8)
    assert len(same_pattern([wide_rule(4)], 0, 5).wide) == 1
    monkeypatch.setattr(_common, 'MAX_EXPAND', 32)
    assert not same_pattern([wide_rule(5)], 0, 5).wide


def test_empty_clause_subsumes_every_other(live):
    rules = [((), ((0, 'real', True),)), ((), ()), ((), ((1, 'even', True),))]
    p = same_pattern(rules, 0, 2)
    assert p.clauses == [((), frozenset(), ())] and p.used == ()


def test_unknown_predicate_is_a_keyerror(live):
    for rules in ([((), ((0, 'nosuch', True),))], [(((0, 'nosuch', False),), ((0, 'real', True),))],
                  [((), ((0, 'real', True),)), ((), ((0, 'nosuch', True), (0, 'other', True)))]):
        a = same_pattern(rules, 0)
        assert a[:2] == ('raised', KeyError)


def test_tautologies_and_merged_literals(live):
    p = by_cnf_size(2)
    same_pattern([((), ((0, 'real', True), (0, 'real', False))), ((), ((0, p, True), (0, p, True))), (((0, p, True),), ((0, p, True),))], 0)


def test_node_and_child_slots(live):
    rules = [(((0, 'real', True), (1, 'even', True)), ((2, 'odd', True), (3, 'prime', False))), ((), ((3, 'real', True),)), ((), ((0, 'real', True),))]
    for node in range(4):
        same_pattern(rules, node, 4)


def test_a_read_that_raises_comes_through_as_itself(live):
    class Boom(Exception):
        pass
    boom = Boom('from the read')

    class Bad:
        @property
        def is_real(self):
            raise boom
    with pytest.raises(Boom) as e:
        _common.resolve([([(0, 'real', True)], [(1, 'real', True)])], {0: Bad()})
    assert e.value is boom and not live['fault']


def test_a_read_that_is_not_a_bool_is_a_fault_not_a_quiet_exception(live):
    class Odd:
        is_real = 7
    with pytest.raises(K.KnowledgeFault):
        _common.resolve([([(0, 'real', True)], [(1, 'real', True)])], {0: Odd()})
    assert live['fault'] == 1


@pytest.mark.parametrize('bad', [[((), ((0, 'real'),))], [((), ((0, 'real', 'yes'),))], [((0, 'real', True),)]])
def test_a_rule_rust_cant_read_is_a_fault(live, bad):
    with pytest.raises(K.KnowledgeFault):
        _common.Pattern(bad, 0)
    with pytest.raises(K.KnowledgeFault):
        _common.resolve(bad, {})
    assert live['fault'] == 2


def test_shadow_sees_a_wrong_field_and_a_generator():
    K.COUNTS.clear()
    K.MISMATCHES.clear()
    undo = K.install(shadow=True)
    try:
        r = [([(0, 'real', True)], [(1, 'even', True)])]
        assert _common.resolve(iter(r), {}) == PY_RESOLVE(r, {})
        assert K.COUNTS['shadow:common'] == 1 and not K.COUNTS['shadow:mismatch']
        K._mismatch('pattern', 0, 'used', (1,), (0,))
        assert K.COUNTS['shadow:mismatch'] == 1 and K.MISMATCHES[0][2] == 'used'
        K._mismatch('pattern', 0, 'child_preds', {1: frozenset(), 2: frozenset()}, {2: frozenset(), 1: frozenset()})
        assert K.COUNTS['shadow:order'] == 1 and K.COUNTS['shadow:mismatch'] == 1
    finally:
        undo()
    K.MISMATCHES.clear()
    K.ORDER_DIFFS.clear()


def test_every_template_goes_through_rust_and_the_answers_stand():
    K.COUNTS.clear()
    K.MISMATCHES.clear()
    K.ORDER_DIFFS.clear()
    undo = K.install(shadow=True)
    try:
        x, y = Symbol('x', positive=True), Symbol('y', integer=True)
        reset_module_state(sympy_cache=False)
        sympy_api.set_default_engine(E.Engine())
        assert sympy_api.ask(Q.positive(x + 1)) is True
        assert sympy_api.ask(Q.even(2 * y)) is True
        assert sympy_api.ask(Q.real(x * y)) is True
        assert isinstance(_common.Compiled, type) and _common.Compiled is Compiled
        assert K.COUNTS['common:resolve'] > 0 and K.COUNTS['common:pattern'] > 0
        assert K.COUNTS['shadow:common'] >= K.COUNTS['common:resolve'] + K.COUNTS['common:pattern']
        assert not K.COUNTS['shadow:mismatch'], K.MISMATCHES
        assert not K.COUNTS['shadow:order'], K.ORDER_DIFFS
        assert not K.COUNTS['fault']
    finally:
        undo()
        reset_module_state(sympy_cache=False)


def test_undo_restores_both_globals():
    undo = K.install()
    assert _common.resolve is not PY_RESOLVE and _common.Pattern is not PY_PATTERN
    assert _common.resolve.__wrapped__ is PY_RESOLVE and _common.Pattern.__wrapped__ is PY_PATTERN
    undo()
    assert _common.resolve is PY_RESOLVE and _common.Pattern is PY_PATTERN
