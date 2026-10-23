"""Rows about a function of any number of arguments (#299, U0): the
language of ``_rows`` (a star, ``every``, ``some``, ``count``,
``coefficient``, ``at_most``), the schemas it compiles to, and
``wiring.expand``, which turns a schema into rules for a node of ``n``
arguments.  No family has such rows yet; the rows here are test rows,
and the last tests check that rows written for some of the rules of
``core`` (Add, Mul) and ``selection`` expand to the same clauses."""
from itertools import combinations, product
from math import comb

import pytest
from sympy import (
    Add, E, Equivalent, Float, I, Integer, Max, Min, Mul, Pow, Q, Rational, S, Symbol, oo, pi,
    sqrt, symbols, zoo,
)

from satassume.knowledge.rules import DEFINITIONS
from satassume.knowledge.templates import core, selection, wiring
from satassume.knowledge.templates._common import Pattern, lits, resolve
from satassume.knowledge.templates._rows import (
    ANY_ARITY, Arguments, base, by_function, coefficient, compile_rows, count, every, exponent,
    f, factor, factors, for_all, generator, number, other, some, term, terms, third, value,
    values,
)
from satassume.knowledge.templates.table import Section, iter_rows, rules_of


def compiled(head, *statements):
    [(_, rows)] = by_function(statements)
    return compile_rows(head, rows)


def gen_of(head, *statements):
    c = compiled(head, *statements)
    return generator(head.__name__, *c[:3], __name__, *c[3:])


def schemas(head, *statements):
    return compiled(head, *statements)[3]


def rules(head, n, consts=None, *statements, leave_out_wide=False):
    return wiring.expand(gen_of(head, *statements).schemas, n, consts or {}, leave_out_wide)


def clauses(rules, n, consts=None):
    """The clauses over the basis of ``rules`` resolved at ``consts``."""
    return {c[0] for c in Pattern(resolve(rules, consts or {}), n, n + 1).clauses}


# --- the language ------------------------------------------------------------

def test_the_arguments_unpack_to_themselves():
    for xs in (terms, factors, values):
        assert isinstance(xs, Arguments) and list(xs) == [xs]
        assert xs != Symbol(xs.name)
    assert f(*factors).args == (factors,)
    assert f(factor, other, *factors).args == (factor, other, factors)
    assert {'Add', 'Mul', 'Max', 'Min', 'Piecewise'} == ANY_ARITY
    assert str(every(~Q.zero, factors)) == '~Q.zero(every(factors))'
    assert str(some(Q.zero, factors)) == 'Q.zero(some(factors))'
    assert str(Q.even(count(factors))) == 'Q.even(count(factors))'


def test_the_examples_compile_to_schemas():
    out = compiled(
        Mul,
        # one negative factor, the others positive: negative
        for_all((Mul,),
            (Q.extended_negative(factor) & every(Q.extended_positive, factors))
            >> Q.extended_negative(f(factor, *factors)), at_most=6),
        # zero if a factor is zero and all are finite
        for_all((Mul,),
            (some(Q.zero, factors) & every(Q.finite, factors)) >> Q.zero(f(*factors))),
        # an even number of negative factors: positive
        for_all((Mul,),
            (every(Q.extended_negative, factors) & Q.even(count(factors)))
            >> Q.extended_positive(f(*factors))),
        # two negative factors, the others positive
        for_all((Mul,),
            (Q.extended_negative(factor) & Q.extended_negative(other)
             & every(Q.extended_positive, factors))
            >> Q.extended_positive(f(factor, other, *factors)), at_most=4),
        # a commutative product of nonzero factors is nonzero
        for_all((Mul,),
            every(Q.commutative, factors) >> (some(Q.zero, factors) | ~Q.zero(f(*factors)))),
    )
    assert out == ((), (), (), (
        (6, ((None, 0),),
         ((((0, 'extended_negative', True), ('every', 'extended_positive', True)),
           (('node', 'extended_negative', True),)),)),
        # zero implies finite: the zero factor leaves finite out
        (None, (), (((('others', 'finite', True), ('some', 'zero', True)),
                     (('node', 'zero', True),)),)),
        (None, (), (((('count', 'even', True), ('every', 'extended_negative', True)),
                     (('node', 'extended_positive', True),)),)),
        # the two picks are interchangeable: one group
        (4, ((None, 0), (None, 0)),
         ((((0, 'extended_negative', True), (1, 'extended_negative', True),
            ('every', 'extended_positive', True)), (('node', 'extended_positive', True),)),)),
        (None, (), (((('every', 'commutative', True),),
                     (('some', 'zero', True), ('node', 'zero', False))),)),
    ))


def test_a_some_literal_keeps_an_every_literal_it_does_not_imply():
    [(_, _, ((prem, _),))] = schemas(
        Add, for_all((Add,), (some(Q.odd, terms) & every(Q.even, terms) & every(Q.integer, terms))
                     >> Q.odd(f(*terms))))
    assert set(prem) == {('some', 'odd', True), ('every', 'even', True),
                         ('others', 'integer', True)}


def test_rows_without_a_star_stay_positional():
    # f(coefficient, factor) and f(-1, factor): shapes, as for Pow
    arity, terms_, specs = compiled(
        Mul,
        for_all((Mul,),
            (Q.positive(coefficient) & Q.positive(f(coefficient, factor))) >> Q.positive(factor)),
        for_all((Mul,),
            (Q.rational(coefficient) & Q.integer(2*coefficient) & ~Q.integer(coefficient)
             & Q.integer(factor)) >> Equivalent(Q.integer(f(coefficient, factor)), Q.even(factor))),
        for_all((Mul,), Q.even(f(-1, factor)) >> Q.even(factor)))
    assert arity == 2
    assert terms_ == ((2, (('of_constant', 0, '2*coefficient'),)),)
    [(n, rs)] = specs
    assert n == 2
    assert [r[2] for r in rs] == [(('coefficient',), None)] * 3 + [(('value', -1), None)]


def test_picks_are_interchangeable_only_with_the_same_literals_and_kind():
    def groups(row):
        [(_, picks, _)] = schemas(Add, for_all((Add,), row))
        return [g for _, g in picks]
    assert groups((Q.odd(term) & Q.odd(other) & every(Q.even, terms))
                  >> Q.even(f(term, other, *terms))) == [0, 0]
    assert groups((Q.odd(term) & Q.odd(other) & Q.odd(third) & every(Q.even, terms))
                  >> Q.odd(f(term, other, third, *terms))) == [0, 0, 0]
    assert groups((Q.odd(term) & Q.even(other) & every(Q.even, terms))
                  >> Q.odd(f(term, other, *terms))) == [0, 1]
    assert groups((Q.odd(term) & Q.odd(number)) >> Q.even(f(term, number, *terms))) == [0, 1]
    # imaginary times complex, and the flip: one row each, not interchangeable
    assert groups((Q.imaginary(term) & Q.complex(other) & Q.extended_real(f(term, other, *terms)))
                  >> (Q.imaginary(other) | Q.zero(other))) == [0, 1]


@pytest.mark.parametrize("head, statement, match", [
    (Pow, lambda: for_all((Pow,), Q.positive(base) >> Q.positive(f(base, *factors))),
     "any number of arguments"),
    (Mul, lambda: for_all((Mul,), Q.positive(f(*factors)) >> every(Q.positive, factors)),
     "every and count are premises"),
    (Mul, lambda: for_all((Mul,), Q.positive(f(*factors)) >> Q.even(count(factors))),
     "every and count are premises"),
    # the precedence trap: a & b >> c is And(a, Implies(b, c))
    (Mul, lambda: for_all((Mul,), Q.positive(factor) & every(Q.positive, factors)
                          >> Q.positive(f(factor, *factors))), "not an implication"),
    (Mul, lambda: for_all((Mul,), Q.positive(Symbol('y')) >> Q.positive(f(*factors))),
     "neither the node"),
    (Mul, lambda: for_all((Mul,), every(Q.positive, terms) >> Q.positive(f(*factors))),
     "is not about factors"),
    (Mul, lambda: for_all((Mul,), Q.positive(factors) >> Q.positive(f(*factors))),
     "write every"),
    (Mul, lambda: for_all((Mul,), Q.diagonal(factor) >> Q.positive(f(factor, *factors))),
     "not a template predicate"),
    (Mul, lambda: for_all((Mul,), Q.gt(factor, 1) >> Q.positive(f(factor, *factors))),
     "no inequalities"),
    (Mul, lambda: for_all((Mul,), every(Q.positive, factors) >> Q.positive(f(factor, other))),
     "node with a star"),
    (Mul, lambda: for_all((Mul,), Q.positive(factor) >> Q.positive(f(factor, factor, *factors))),
     "not distinct"),
    (Mul, lambda: for_all((Mul,), Q.positive(factor) >> Q.positive(f(*factors, factor))),
     "the star is the last argument"),
    (Mul, lambda: for_all((Mul,), (some(Q.zero, factors) & Q.finite(factor))
                          >> Q.zero(f(factor, *factors))), "no picked argument"),
    (Mul, lambda: for_all((Mul,), (some(Q.zero, factors) & some(Q.odd, factors))
                          >> Q.zero(f(*factors))), "one some"),
    (Mul, lambda: for_all((Mul,), Q.positive(f(coefficient, factor)) >> Q.positive(factor),
                          at_most=3), "at_most is for a row with a star"),
    (Mul, lambda: for_all((Mul,), Q.positive(f(*factors)), at_most=0), "positive int"),
    (Mul, lambda: for_all((Mul,), Q.positive(f(factor, coefficient)) >> Q.positive(factor)),
     "coefficient is argument 0"),
    (Pow, lambda: for_all((Pow,), Q.positive(f(coefficient, exponent))), "coefficient is argument 0"),
    (Mul, lambda: for_all((Mul,), Q.positive(f(number, coefficient, *factors))),
     "more than one constant variable"),
    (Mul, lambda: for_all((Mul,), Q.positive(f(sqrt(2), *factors))), "no atomic number"),
    (Mul, lambda: for_all((Mul,), Q.positive(f(*factors)) >> Q.positive(f(factor, *factors))),
     "more than one node"),
])
def test_rows_that_do_not_compile(head, statement, match):
    with pytest.raises((TypeError, ValueError), match=match):
        compiled(head, statement())


def test_a_family_with_a_star_is_not_wired_yet():
    gen = gen_of(Mul, for_all((Mul,), every(Q.odd, factors) >> Q.odd(f(*factors))))
    with pytest.raises(ValueError, match="no function is wired"):
        wiring.template(Mul, gen)


# --- expansion per arity -------------------------------------------------------

ARITIES = (1, 2, 3, 4, 5, 6, 7, 8, 31, 32, 33)


@pytest.mark.parametrize("n", ARITIES)
def test_one_pick_is_each_argument_with_the_others(n):
    rs = rules(Mul, n, None, for_all((Mul,),
        (Q.extended_negative(factor) & every(Q.extended_positive, factors))
        >> Q.extended_negative(f(factor, *factors))))
    assert rs == [([(k, 'extended_negative', True)]
                   + [(j, 'extended_positive', True) for j in range(n) if j != k],
                   [(n, 'extended_negative', True)]) for k in range(n)]


@pytest.mark.parametrize("n", ARITIES)
def test_at_most(n):
    st = for_all((Mul,), (Q.extended_negative(factor) & every(Q.extended_positive, factors))
                 >> Q.extended_negative(f(factor, *factors)), at_most=6)
    assert len(rules(Mul, n, None, st)) == (n if n <= 6 else 0)


@pytest.mark.parametrize("n", ARITIES)
def test_no_pick_is_one_rule(n):
    [(prem, concl)] = rules(Mul, n, None, for_all((Mul,),
        every(Q.commutative, factors) >> (some(Q.zero, factors) | ~Q.zero(f(*factors)))))
    assert prem == lits(range(n), 'commutative')
    assert concl == lits(range(n), 'zero') + [(n, 'zero', False)]


@pytest.mark.parametrize("n", ARITIES)
def test_two_picks(n):
    same = for_all((Add,), (Q.odd(term) & Q.odd(other) & every(Q.even, terms))
                   >> Q.even(f(term, other, *terms)))
    rs = rules(Add, n, None, same)
    assert len(rs) == comb(n, 2)
    assert [sorted(k for k, p, _ in prem if p == 'odd') for prem, _ in rs] == [
        list(c) for c in combinations(range(n), 2)]
    flip = for_all((Mul,), (Q.imaginary(factor) & Q.complex(other)) >> Q.real(f(factor, other,
                                                                                *factors)))
    assert len(rules(Mul, n, None, flip)) == n * (n - 1)


@pytest.mark.parametrize("n", ARITIES)
def test_some_in_the_premises_is_a_rule_per_argument_up_to_32(n):
    st = for_all((Mul,), (some(Q.zero, factors) & every(Q.finite, factors)) >> Q.zero(f(*factors)))
    rs = rules(Mul, n, None, st)
    if n > wiring.SOME_PER_ARGUMENT:
        assert rs == []
        return
    assert rs == [([(j, 'finite', True) for j in range(n) if j != k] + [(k, 'zero', True)],
                   [(n, 'zero', True)]) for k in range(n)]


@pytest.mark.parametrize("n", ARITIES)
def test_count(n):
    even = for_all((Mul,), (every(Q.extended_negative, factors) & Q.even(count(factors)))
                   >> Q.extended_positive(f(*factors)))
    odd = for_all((Mul,), (every(Q.extended_negative, factors) & Q.odd(count(factors)))
                  >> Q.extended_negative(f(*factors)))
    assert len(rules(Mul, n, None, even)) == (n % 2 == 0)
    assert len(rules(Mul, n, None, odd)) == (n % 2 == 1)
    # the count of the others
    one = for_all((Mul,), (Q.positive(factor) & every(Q.extended_negative, factors)
                           & Q.odd(count(factors))) >> Q.extended_negative(f(factor, *factors)))
    assert len(rules(Mul, n, None, one)) == (n if n % 2 == 0 else 0)


def test_a_constant_is_picked_where_there_is_one():
    st = for_all((Add,), (Q.positive_infinite(number) & every(Q.real, terms))
                 >> Q.extended_positive(f(number, *terms)))
    assert [p[0][0] for p, _ in rules(Add, 5, {1: oo, 3: Integer(2)}, st)] == [1, 3]
    assert rules(Add, 5, {}, st) == []
    # a picked number is a constant equal to it
    st = for_all((Mul,), every(Q.even, factors) >> Q.even(f(-1, *factors)))
    assert rules(Mul, 3, {0: Integer(-1), 2: Integer(-1), 1: Integer(2)}, st) == [
        ([(1, 'even', True), (2, 'even', True)], [(3, 'even', True)]),
        ([(0, 'even', True), (1, 'even', True)], [(3, 'even', True)])]
    assert rules(Mul, 3, {0: Float(-1.0)}, st) == []


@pytest.mark.parametrize("c, picked", [
    (Integer(2), True), (Rational(-3, 2), True), (Float(2.5), True), (oo, True), (S.Zero, True),
    (pi, False), (E, False), (I, False), (zoo, False)])
def test_coefficient_is_argument_0_when_it_is_a_number(c, picked):
    st = for_all((Mul,), (Q.positive(coefficient) & Q.positive(f(coefficient, factor, *factors)))
                 >> Q.positive(factor))
    assert bool(rules(Mul, 3, {0: c}, st)) is picked
    assert rules(Mul, 3, {1: c}, st) == []
    assert rules(Mul, 3, {}, st) == []
    # a row without a star: a node of two arguments whose argument 0 is a Number
    gen = gen_of(Mul, for_all((Mul,), (Q.positive(coefficient) & Q.positive(f(coefficient, factor)))
                              >> Q.positive(factor)))
    [(_, _, shape)] = gen.specs[2]
    x = Symbol('x')
    assert wiring.matches(shape, (c, x), {0: c}) is picked
    assert not wiring.matches(shape, (x, c), {1: c})


def test_leave_out_wide():
    # ~odd(a_i) is a disjunction of two basis literals: 2**n clauses
    st = for_all((Max,), every(~Q.odd, values) >> ~Q.odd(f(*values)))
    for n in range(1, 8):
        kept = rules(Max, n, None, st, leave_out_wide=True)
        assert len(kept) == (2**n <= 16)
        assert len(rules(Max, n, None, st)) == 1


# --- the template ------------------------------------------------------------

def test_the_template_of_any_arity():
    x, y, z = symbols('x y z')
    gen = gen_of(Mul,
        for_all((Mul,), (Q.extended_negative(factor) & every(Q.extended_positive, factors))
                >> Q.extended_negative(f(factor, *factors)), at_most=6),
        for_all((Mul,), (some(Q.zero, factors) & every(Q.finite, factors)) >> Q.zero(f(*factors))),
        for_all((Mul,), (Q.rational(coefficient) & Q.integer(2*coefficient)
                         & ~Q.integer(coefficient) & Q.integer(factor))
                >> Equivalent(Q.integer(f(coefficient, factor)), Q.even(factor))))
    t = wiring.any_arity('test-any-arity', gen)
    block = t(Mul(x, y, z, evaluate=False))
    assert block.objs[:3] == (x, y, z) and len(block.pattern.rules) == 6
    # the half coefficient: the term 2*c is computed, not built
    half = t(Mul(Rational(3, 2), x, evaluate=False))
    assert len(half.objs) == 4 and half.objs[3] is None
    assert {(tuple(ps), cs) for ps, cs in half.pattern.rules} >= {
        (((1, 'integer', True), (2, 'integer', True)), ((1, 'even', True),))}
    assert not any(k == 3 for ps, cs in t(Mul(pi, x, evaluate=False)).pattern.rules
                   for k, _, _ in (*ps, *cs))
    # 40 factors: the zero rule is one formula
    xs = symbols('x:40')
    out = t(Mul(*xs, evaluate=False))
    assert isinstance(out, list) and len(out) == 2
    assert out[1] == core._wide_one(out[0].objs[40], xs, {}, 'finite', 'zero', 'zero')


# --- the shapes of the legacy rules ----------------------------------------------

LEGACY_ARITIES = (1, 2, 3, 4, 5, 6, 7, 8, 33)
CONSTANTS = (S.Zero, S.One, S.NegativeOne, Integer(2), S.Half, Float(2.5), oo, -oo, zoo, pi, I)


def patterns(n):
    """Constants at no position, at the first, at the last, and at both."""
    yield {}
    for c in CONSTANTS:
        yield {0: c}
        yield {n - 1: c}
    for c, d in ((Integer(-2), oo), (S.Half, I), (S.Zero, -oo)):
        if n > 1:
            yield {0: c, n - 1: d}


_MUL = {r.name: r for r in iter_rows(core._table('MUL_TABLE'))}


def mul_legacy(*items):
    def legacy(n, consts):
        return rules_of(items, core.MUL_GUARDS, {'n': n, 'consts': consts},
                        {'N': n, '*': range(n)})
    return legacy


def add_strict(n, consts):
    # verbatim from core._add_rules
    R = []
    A = range(n)
    for k in A if n <= core.MAX_ONEOUT_WIDE else ():
        rest = [j for j in A if j != k]
        for strict, nonstrict in core._STRICT:
            R.append(([(k, strict, True), *lits(rest, nonstrict)], [(n, strict, True)]))
    return R


def add_parity(n, consts):
    # verbatim from core._add_rules
    R = []
    A = range(n)
    if n > core.MAX_ADD_SMALL:
        R.append((lits(A, 'even'), [(n, 'even', True)]))
    for k in A if n <= core.MAX_ONEOUT_WIDE else ():
        rest = [j for j in A if j != k]
        if n <= core.MAX_ADD_SMALL:
            pass
        elif n <= core.MAX_ONEOUT:
            R.append(([(k, 'odd', True), *lits(rest, 'even')], [(n, 'odd', True)]))
    if n <= core.MAX_ADD_SMALL:
        for parities in product(('even', 'odd'), repeat=n):
            result = 'odd' if parities.count('odd') % 2 else 'even'
            R.append(([(k, p, True) for k, p in enumerate(parities)], [(n, result, True)]))
    return R


def add_infinite_constant(n, consts):
    # verbatim from core._add_rules
    R = []
    A = range(n)
    for k in A if n <= core.MAX_ONEOUT else ():
        rest = [j for j in A if j != k]
        for strict, nonstrict in core._STRICT:
            signed = strict.replace('extended_', '') + '_infinite'
            if k in consts:
                for cond in (nonstrict, 'real'):
                    R.append(([(k, signed, True), *lits(rest, cond)], [(n, strict, True)]))
    return R


def max_bound(n, consts):
    R = core.Rules()
    selection._bound(R, n, selection._MAX_BOUND)
    return R.rules


def selection_all(n, consts):
    R = core.Rules()
    selection._selection(R, n)
    return R.rules


PREDS = {p: getattr(Q, p) for p in selection._BASIS + selection._DERIVED}

GROUPS = {
    'Mul one negative factor (each, at_most=6)': (
        Mul, mul_legacy(Section('each', when='n<=MAX_ONEOUT', rows=[_MUL['one_neg']])),
        [for_all((Mul,), (Q.extended_negative(factor) & every(Q.extended_positive, factors))
                 >> Q.extended_negative(f(factor, *factors)), at_most=6)], False),
    'Add strict sign (some and every)': (
        Add, add_strict,
        [for_all((Add,), (some(Q.extended_positive, terms) & every(Q.extended_nonnegative, terms))
                 >> Q.extended_positive(f(*terms))),
         for_all((Add,), (some(Q.extended_negative, terms) & every(Q.extended_nonpositive, terms))
                 >> Q.extended_negative(f(*terms)))], False),
    'Mul all negative and negsets (count, two and three picks)': (
        Mul, mul_legacy(_MUL['all_neg.even'], _MUL['all_neg.odd'],
                        Section('negsets', when='3<=n<=MAX_PAIRS',
                                rows=[_MUL['m_neg.even'], _MUL['m_neg.odd']])),
        [for_all((Mul,), (every(Q.extended_negative, factors) & Q.even(count(factors)))
                 >> Q.extended_positive(f(*factors))),
         for_all((Mul,), (every(Q.extended_negative, factors) & Q.odd(count(factors)))
                 >> Q.extended_negative(f(*factors))),
         for_all((Mul,), (Q.extended_negative(factor) & Q.extended_negative(other)
                          & every(Q.extended_positive, factors))
                 >> Q.extended_positive(f(factor, other, *factors)), at_most=4),
         for_all((Mul,), (Q.extended_negative(factor) & Q.extended_negative(other)
                          & Q.extended_negative(third) & every(Q.extended_positive, factors))
                 >> Q.extended_negative(f(factor, other, third, *factors)), at_most=4)], False),
    'Add parity (interchangeable picks)': (
        Add, add_parity,
        [for_all((Add,), every(Q.even, terms) >> Q.even(f(*terms))),
         for_all((Add,), (Q.odd(term) & every(Q.even, terms)) >> Q.odd(f(term, *terms)),
                 at_most=6),
         for_all((Add,), (Q.odd(term) & Q.odd(other) & every(Q.even, terms))
                 >> Q.even(f(term, other, *terms)), at_most=3),
         for_all((Add,), (Q.odd(term) & Q.odd(other) & Q.odd(third) & every(Q.even, terms))
                 >> Q.odd(f(term, other, third, *terms)), at_most=3)], False),
    'Add an infinite constant term (number)': (
        Add, add_infinite_constant,
        [for_all((Add,), (Q.positive_infinite(number) & every(Q.extended_nonnegative, terms))
                 >> Q.extended_positive(f(number, *terms)), at_most=6),
         for_all((Add,), (Q.positive_infinite(number) & every(Q.real, terms))
                 >> Q.extended_positive(f(number, *terms)), at_most=6),
         for_all((Add,), (Q.negative_infinite(number) & every(Q.extended_nonpositive, terms))
                 >> Q.extended_negative(f(number, *terms)), at_most=6),
         for_all((Add,), (Q.negative_infinite(number) & every(Q.real, terms))
                 >> Q.extended_negative(f(number, *terms)), at_most=6)], False),
    'Max bound': (
        Max, max_bound,
        [for_all((Max,), Q.extended_positive(value) >> Q.extended_positive(f(value, *values))),
         for_all((Max,), Q.extended_nonnegative(value)
                 >> Q.extended_nonnegative(f(value, *values)))], False),
    'selection (both polarities, derived negatives left out when wide)': (
        Min, selection_all,
        [for_all((Min,), every(PREDS[p], values) >> PREDS[p](f(*values)))
         for p in selection._BASIS]
        + [for_all((Min,), every(~PREDS[p], values) >> ~PREDS[p](f(*values)))
           for p in selection._BASIS + selection._DERIVED], True),
}


@pytest.mark.parametrize("group", GROUPS)
@pytest.mark.parametrize("n", LEGACY_ARITIES)
def test_rows_expand_to_the_legacy_clauses(group, n):
    head, legacy, statements, leave_out = GROUPS[group]
    gen = gen_of(head, *statements)
    for consts in patterns(n):
        mine = wiring.expand(gen.schemas, n, consts, leave_out)
        assert clauses(mine, n, consts) == clauses(legacy(n, consts), n, consts), consts


def test_the_selection_cap_is_legacys():
    # width**n <= MAX_EXPAND of selection._selection
    for p in selection._DERIVED:
        width = DEFINITIONS[p].count('&') + 1
        st = for_all((Min,), every(~PREDS[p], values) >> ~PREDS[p](f(*values)))
        for n in range(1, 9):
            assert len(rules(Min, n, None, st, leave_out_wide=True)) == (width ** n <= 16), (p, n)


@pytest.mark.parametrize("n", (33, 40))
def test_past_32_the_some_rows_are_legacys_formula(n):
    # Add's strict sign (add_templates) and Mul's zero (mul_templates)
    xs = symbols(f'x:{n}')
    add = gen_of(Add, *GROUPS['Add strict sign (some and every)'][2])
    zero = gen_of(Mul, for_all((Mul,), (some(Q.zero, factors) & every(Q.finite, factors))
                               >> Q.zero(f(*factors))))
    for consts in patterns(n):
        args = tuple(consts.get(k, x) for k, x in enumerate(xs))
        node = Symbol('node')
        legacy = [core._wide_one(node, args, consts, nonstrict, strict, strict)
                  for strict, nonstrict in core._STRICT]
        assert wiring.wide_formulas(add.schemas, node, args, consts) == [
            g for g in legacy if g is not None], consts
        legacy = core._wide_one(node, args, consts, 'finite', 'zero', 'zero')
        assert wiring.wide_formulas(zero.schemas, node, args, consts) == (
            [legacy] if legacy is not None else []), consts
    assert wiring.wide_formulas(add.schemas, Symbol('node'), xs[:32], {}) == []
