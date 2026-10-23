"""Rows about a function of any number of arguments (#299, U0): the
language of ``_rows`` (a star, ``every``, ``some``, ``count``,
``coefficient``, ``at_most``) and the schemas it compiles to.  No family
has such rows yet; the rows here are test rows."""
import pytest
from sympy import Add, Equivalent, Mul, Pow, Q, Symbol, sqrt

from satassume.knowledge.templates import wiring
from satassume.knowledge.templates._rows import (
    ANY_ARITY, Arguments, base, by_function, coefficient, compile_rows, count, every, exponent,
    f, factor, factors, for_all, generator, number, other, some, term, terms, third, values,
)


def compiled(head, *statements):
    [(_, rows)] = by_function(statements)
    return compile_rows(head, rows)


def gen_of(head, *statements):
    c = compiled(head, *statements)
    return generator(head.__name__, *c[:3], __name__, *c[3:])


def schemas(head, *statements):
    return compiled(head, *statements)[3]


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
