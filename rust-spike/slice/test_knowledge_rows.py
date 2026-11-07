"""`_rows_runtime.py` on Rust: by hand, for what a SymPy-side comparison can't say. `rows_cmp.py` is the comparison against Python."""
import pytest
import sa_solver
from fractions import Fraction
from sympy import E, Float, I, Integer, Rational, S, exp, pi

from satassume.knowledge.templates import _rows_runtime as RT
from satassume.knowledge.templates._compiled_rows import FAMILIES
from satassume.theories.lra import constfield


def same(a, b):
    return type(a) is type(b) and a == b and repr(a) == repr(b)


@pytest.mark.parametrize('text,value', [
    ('1/2', S.Half), ('-1/2', Rational(-1, 2)), (1, S.One), (-3, Integer(-3)), ('E', E), ('exp(-1)', exp(-1)), ('-1/E', -exp(-1)),
    ('pi', pi), ('2**-1', S.Half), ('-2**2', Integer(-4)), ('2**3**2', Integer(512)), ('sqrt(4/9)', Rational(2, 3)), ('Abs(-E)', E)])
def test_read(text, value):
    assert same(sa_solver.rows_from_text(text), value)


@pytest.mark.parametrize('text', ['I', '-I', 'I*I', 'sqrt(2)', 'E+1', '1/0', '0**-1', 'exp(1/2)', '1.5', '007', '+1', ' 1', '1//2', 'x', '',
                                  '(' * 80 + '1' + ')' * 80, '9' * 5000])
def test_declined(text):
    assert sa_solver.rows_from_text(text) is None


@pytest.mark.parametrize('text,c,value', [
    ('Abs(number) - 1', Integer(-3), Integer(2)), ('1/number', Rational(2, 3), Rational(3, 2)), ('2*coefficient', S.Half, S.One),
    ('number/2', Integer(3), Rational(3, 2)), ('number - 2', Integer(10)**30, Integer(10)**30 - 2)])
def test_constant_value(text, c, value):
    assert same(sa_solver.rows_constant_value(text, c), value)


@pytest.mark.parametrize('text,c', [('1/number', S.Zero), ('number/2', Float(2.0)), ('number - 2', S.Infinity), ('2*number', S.NaN),
                                    ('Abs(number) - 1', S.NegativeInfinity)])
def test_constant_value_declined(text, c):
    assert sa_solver.rows_constant_value(text, c) is None
    RT.constant_value(text, c)      # and Python answers it


def test_only_I_stays_on_python():
    """The rows' values that Rust can't read, and that its numbers are the constant field's."""
    python, numbers = [], {}
    for _, fns in FAMILIES:
        for fn_name, _, terms, specs, *schemas in fns:
            g = sa_solver.RowsGen(terms, specs, RT.from_text, *schemas)
            python += [(fn_name, v) for v in g.python_values]
            numbers.update(g.numbers())
    assert sorted(python) == [('Pow', '-I'), ('Pow', 'I')]
    assert numbers['-1/2'] == Fraction(-1, 2)
    assert numbers['E'] == constfield.E
    assert numbers['exp(-1)'] == 1 / constfield.E


def test_I_read_by_python():
    g = sa_solver.RowsGen((), ((2, ((((0, 'zero', True),), ((3, 'zero', True),), (('value', 'I'), None)),)),), RT.from_text)
    assert g.specs[2][0][2][0] == ('value', I)
