"""Slice D: `num` against Python's on what the workloads never send, and Rust's `lra_adapter` on the table's own edges."""
import decimal
from fractions import Fraction

import pytest
import sa_solver
import sympy

import lra_live
import term_live
from satassume.theories.lra import constfield as CF


class F2(Fraction):
    pass


class Fl(float):
    pass


class I2(int):
    pass


VALUES = [Fraction(1, 3), CF.PI, CF.E, CF.PI + 1, 0, 5, -7, 10**40, True, False, I2(4), F2(1, 2), 0.5, Fl(1.5), float('nan'),
          decimal.Decimal('0.25'), '1/2', '0.5', 'x', None, [], sympy.Rational(2, 3), sympy.Integer(4), sympy.pi, sympy.Float(0.5)]


@pytest.mark.parametrize('v', VALUES, ids=repr)
def test_num_as_python(v):
    py = _num_py()
    try:
        want = py(v)
    except Exception as x:
        with pytest.raises(type(x)) as got:
            sa_solver.cf_num(v)
        assert str(got.value) == str(x)
        return
    got = sa_solver.cf_num(v)
    assert type(got) is type(want) and got == want
    if type(v) is Fraction or type(v) is CF.Element:
        assert got is v


def _num_py():
    # Python's own, whatever is installed over the name.
    return lra_live._PY_NUM[0]


def test_num_counts_only_what_goes_through_python():
    b = sa_solver.lra_counts()['num_python']
    sa_solver.cf_num(Fraction(1, 2)), sa_solver.cf_num(CF.PI), sa_solver.cf_num(3)
    assert sa_solver.lra_counts()['num_python'] == b
    sa_solver.cf_num(True)
    assert sa_solver.lra_counts()['num_python'] == b + 1


def test_install_and_undo_put_num_back():
    before = CF.num
    u = lra_live.install(check=False)
    try:
        assert CF.num is sa_solver.cf_num
    finally:
        u()
    assert CF.num is before and term_live is not None
