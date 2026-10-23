"""The row language's shapes, terms and value equality (#294): each form
compiles to the plain data of ``_rows.compile_rows``, and what it cannot
state is refused at compile time."""
import pytest
from sympy import Abs, E, Float, Function, I, Integer, Pow, Q, Rational, S, Symbol, exp

from satassume.knowledge.templates import ROW_FAMILIES, wiring
from satassume.knowledge.templates._compiled_rows import FAMILIES
from satassume.knowledge.templates._rows import (
    VALUE_PREDICATES, Constant, base, by_function, compile_rows, constant_term, constant_value,
    exponent, f, for_all, generator, log_base, number,
)


class g(Function):
    nargs = 2


def compiled(*rows):
    """``(arity, terms, rules)`` of ``rows`` about ``g``, ``f`` bound to ``g``."""
    [(_, bound)] = by_function((for_all((g,), *rows),))
    return compile_rows(g, bound)


def only(*rows):
    """The terms and the rules of rows about a node of two arguments."""
    arity, ((n, terms),), ((m, rules),) = compiled(*rows)
    assert arity == n == m == 2
    return terms, rules


def test_the_names_of_the_arguments_are_plain_symbols_and_the_constant_is_not():
    for s in (base, exponent, log_base):
        assert type(s) is Symbol and s == Symbol(s.name)
    assert isinstance(number, Symbol) and number != Symbol('number')
    # its terms stay terms
    assert (2*number).args == (2, number) and isinstance(Abs(number), Abs)


@pytest.mark.parametrize("arg, data", [
    (-1, -1), (1, 1), (E, 'E'), (I, 'I'), (-I, '-I'), (Rational(1, 2), '1/2')])
def test_a_number_in_the_node_is_a_shape(arg, data):
    terms, rules = only(Q.positive(base) >> Q.positive(f(base, arg)))
    assert terms == ()
    assert rules == ((((0, 'positive', True),), ((2, 'positive', True),),
                      (None, ('value', data))),)
    # the generator gives the number back exactly (-I is Mul(-1, I))
    gen = generator('g', 2, ((2, terms),), ((2, rules),), __name__)
    [(_, _, shape)] = gen.specs[2]
    assert shape[1][1] == S(arg) and type(shape[1][1]) is type(S(arg))
    assert not gen.plain


def test_a_number_first():
    _, rules = only(Q.real(exponent) >> Q.positive(f(E, exponent)))
    assert rules == ((((1, 'real', True),), ((2, 'positive', True),), (('value', 'E'), None)),)


def test_a_function_of_a_symbol_gives_its_argument_a_slot():
    terms, rules = only((Q.imaginary(log_base) & Q.imaginary(exponent))
                        >> Q.positive(f(exp(log_base), exponent)))
    assert terms == (('inner', 0),)
    assert rules == ((((1, 'imaginary', True), (3, 'imaginary', True)),
                      ((2, 'positive', True),), (('head', 'exp'), None)),)


def test_a_repeated_symbol_is_the_slot_of_its_first_argument():
    _, rules = only(Q.extended_nonnegative(base) >> Q.extended_positive(f(base, base)))
    assert rules == ((((0, 'extended_nonnegative', True),),
                      ((2, 'extended_positive', True),), (None, ('same', 0))),)


def test_the_constant_variable_and_literals_about_it():
    terms, rules = only((Q.integer(number) & ~Q.zero(number) & Q.ne(number, 0)
                         & Q.negative(exponent)) >> ~Q.integer(f(number, exponent)))
    assert terms == ()
    [(prem, concl, shape)] = rules
    assert sorted(prem) == [(0, 'integer', True), (0, 'zero', False), (0, 'zero', False),
                            (1, 'negative', True)]
    assert concl == ((2, 'integer', False),) and shape == (('constant',), None)


@pytest.mark.parametrize("lit, term, pred", [
    (Q.integer(2*number), '2*number', ('integer', True)),
    (Q.odd(number/2), 'number/2', ('odd', True)),
    (~Q.integer(1/number), '1/number', ('integer', False)),
    (Q.integer(Abs(number)), 'Abs(number)', ('integer', True)),
    (Q.gt(Abs(number), 1), 'Abs(number) - 1', ('extended_positive', True)),
    (Q.lt(Abs(number), 1), 'Abs(number) - 1', ('extended_negative', True)),
    (Q.ge(Abs(number), 2), 'Abs(number) - 2', ('extended_nonnegative', True)),
    (Q.ge(number, 2), 'number - 2', ('extended_nonnegative', True)),
    (Q.lt(1, Abs(number)), 'Abs(number) - 1', ('extended_positive', True)),
])
def test_a_term_of_the_constant_is_a_slot_of_its_own(lit, term, pred):
    terms, rules = only((lit & Q.real(base)) >> Q.real(f(base, number)))
    assert terms == (('of_constant', 1, term),)
    assert rules == ((((0, 'real', True), (3, *pred)), ((2, 'real', True),),
                      (None, ('constant',))),)


def test_the_template_computes_a_term_of_the_constant_from_its_text():
    for text, c, value in (('Abs(number) - 1', Integer(-3), 2), ('2*number', Rational(1, 2), 1),
                           ('1/number', Integer(3), Rational(1, 3)),
                           ('number/2', Float(3.0), Float(1.5))):
        t = constant_term(text)
        assert str(t) == text and t.free_symbols == {number}
        assert t.xreplace({number: c}) == value
        # computed from the text, without building the term
        assert constant_value(text, c) == value
    for text in ('Abs(number) - 1', 'Abs(number) - 2', '2*number', 'number/2', '1/number',
                 'number - 2'):
        for c in (Integer(-3), S.Zero, S.Half, Float(2.5), S.Infinity, S.NegativeInfinity,
                  S.ComplexInfinity, S.NaN):
            v = constant_value(text, c)
            assert type(v) is type(constant_term(text).xreplace({number: c})), (text, c)
            assert v == constant_term(text).xreplace({number: c}) or v is S.NaN, (text, c)


def test_the_terms_of_a_row_are_in_their_order():
    # x + c, then the inner argument, then k*x, then the terms of the constant
    terms, rules = only((Q.ne(log_base, 0) & Q.gt(Abs(number), 1) & Q.integer(1/number))
                        >> Q.real(f(exp(log_base), number)),
                        (Q.integer(base) & Q.ne(base, 1) & Q.lt(base, -1) & Q.even(2*exponent)
                         & Q.integer(exponent/2)) >> Q.composite(f(base, exponent)))
    assert terms == ((0, -1), (0, 1), ('inner', 0), ('times', 1, '1/2'), ('times', 1, 2),
                     ('of_constant', 1, '1/number'), ('of_constant', 1, 'Abs(number) - 1'))
    gen = generator('g', 2, ((2, terms),), ((2, rules),), __name__)
    assert gen.terms[2] == ((0, -1), (0, 1), ('inner', 0), ('times', 1, S.Half),
                            ('times', 1, 2), ('of_constant', 1, '1/number'),
                            ('of_constant', 1, 'Abs(number) - 1'))
    assert gen.shifts == () and not gen.plain


def test_k_times_an_argument_is_a_term():
    terms, rules = only((Q.extended_real(base) & Q.rational(exponent) & ~Q.integer(2*exponent))
                        >> ~Q.imaginary(f(base, exponent)))
    assert terms == (('times', 1, 2),)
    assert rules == ((((0, 'extended_real', True), (1, 'rational', True), (3, 'integer', False)),
                      ((2, 'imaginary', False),)),)


def test_a_value_equality_is_an_equivalence_for_each_value_predicate():
    terms, rules = only(Q.eq(f(base, 1), base))
    assert VALUE_PREDICATES == tuple(sorted(set(VALUE_PREDICATES)))
    assert 'commutative' not in VALUE_PREDICATES and 'zero' in VALUE_PREDICATES
    shape = (None, ('value', 1))
    assert terms == () and rules == tuple(
        r for p in VALUE_PREDICATES for r in ((((2, p, True),), ((0, p, True),), shape),
                                              (((0, p, True),), ((2, p, True),), shape)))
    # with a premise, and the sides swapped
    _, swapped = only(Q.real(base) >> Q.eq(base, f(base, 1)))
    assert swapped[0] == (((0, 'real', True), (2, 'algebraic', True)),
                          ((0, 'algebraic', True),), shape)


def test_rows_without_a_shape_compile_as_before():
    _, rules = only((Q.positive(base) & Q.real(exponent)) >> Q.positive(f(base, exponent)))
    assert rules == ((((0, 'positive', True), (1, 'real', True)), ((2, 'positive', True),)),)


def test_every_family_but_power_and_mul_compiles_to_plain_rows():
    # the shapes and the new terms are used by the rows of Pow, which
    # wiring.power matches nodes against, and by those of Mul
    # (f(coefficient, factor), 2*coefficient), which wiring.rows_block does
    for family, fns in FAMILIES:
        for name, arity, terms, specs, *schemas in fns:
            plain = generator(name, arity, terms, specs, __name__, *schemas).plain
            assert plain is (family not in ('power', 'mul')), (family, name)
    assert {fam for fam, _ in FAMILIES} == {fam for fam, _ in ROW_FAMILIES}


def test_wiring_refuses_a_generator_with_shapes():
    gen = generator('g', *compiled(Q.positive(base) >> Q.positive(f(base, -1))), __name__)
    with pytest.raises(ValueError, match="shapes or terms other than x \\+ c"):
        wiring.template(g, gen)


k = Constant('k')
br = Symbol('base', real=True)


@pytest.mark.parametrize("row, match", [
    (Q.positive(number) >> Q.positive(f(number, k)), "more than one constant variable"),
    (Q.integer(number**2) >> Q.real(f(base, number)), "not a term of the constant variable"),
    (Q.integer(number + 1) >> Q.real(f(base, number)), "not a term of the constant variable"),
    (Q.positive(2*number) >> Q.real(f(base, number)), "fact about a sign"),
    (Q.zero(Abs(number)) >> Q.real(f(base, number)), "fact about a sign"),
    (Q.gt(2*number, 1) >> Q.real(f(base, number)), "with a number"),
    (Q.integer(number) >> Q.real(f(base, exponent)), "constant variable number is not an argument"),
    (Q.gt(Abs(number), 1) >> Q.real(f(base, exponent)),
     "constant variable number is not an argument"),
    (Q.real(base) >> Q.real(f(number, number)), "no argument but the constant"),
    (Q.real(base) >> Q.real(f(number, -1)), "no argument but the constant"),
    # a shape is an argument of the node, not of another term
    (Q.zero(exp(log_base) - 1) >> Q.real(f(exp(log_base), exponent)), "neither the argument"),
    (Q.integer(2*exp(log_base)) >> Q.real(f(exp(log_base), exponent)), "neither the argument"),
    (Q.integer(exp(base)) >> Q.real(f(base, exponent)), "neither the argument"),
    (Q.integer(log_base) >> Q.real(f(base, exponent)), "more than one argument"),
    (Q.integer(exponent) >> Q.real(f(exp(base + 1), exponent)), "not a function of a plain Symbol"),
    (Q.integer(exponent) >> Q.real(f(exp(number), exponent)), "not a function of a plain Symbol"),
    (Q.integer(exponent) >> Q.real(f(exp(br), exponent)), "plain Symbol"),
    # only a plain symbol is repeated
    (Q.real(base) >> Q.real(f(exp(base), base)), "not distinct"),
    (Q.real(base) >> Q.real(f(base, exp(base))), "not distinct"),
    (Q.real(f(base, Float(2.5))), "not an exact number"),
    (Q.positive(2*exponent) >> Q.real(f(base, exponent)), "sign of exponent"),
    (Q.integer(exponent*base) >> Q.real(f(base, exponent)), "neither the argument"),
    (Q.eq(f(base, 1), 2*base), "does not equate the node with an argument"),
    (Q.eq(f(base, 1), log_base), "more than one argument"),
])
def test_shapes_and_terms_that_do_not_compile(row, match):
    with pytest.raises((TypeError, ValueError), match=match):
        compiled(row)


def test_a_node_of_another_function_is_left_unbound():
    # f(base + 1, exponent) is no node of g: bind leaves it
    with pytest.raises(ValueError, match="neither the argument"):
        compiled(Q.real(base) >> Q.real(f(base + 1, exponent)))
    # Pow binds unevaluated: Pow(base, 1) stays a node
    [(_, (row,))] = by_function((for_all((Pow,), Q.eq(f(base, 1), base)),))
    assert row.arguments[0] == Pow(base, 1, evaluate=False)
