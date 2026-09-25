"""The combined backend's guard on SymPy's ``Q.nonzero`` handlers.

Checker finding (was ``needs/test_checker_abs_of_imaginary_is_zero.py``):
SymPy's ``ask`` calls ``Abs(x)`` zero for an imaginary ``x`` (``Q.zero(Abs(x))``
is ``True`` and ``Q.positive(Abs(x))`` is ``False`` under ``Q.imaginary(x)``,
while ``Q.zero(x)`` is ``False``), and the ``combined`` backend passed that
answer on whenever satassume returned ``None`` (a relation among the
assumptions is enough).  Rows then fired on it:

* ``refine(log(exp(I*Abs(x))), Q.imaginary(x))`` gave ``0``: complex_parts'
  ``arg(a) -> 0`` for ``Q.positive(a)`` fired on ``exp(I*Abs(x))``, which
  SymPy calls positive; the fuzz reaches it as ``log(exp(sqrt(x**2)))``
  (differential seed 3);
* ``refine(arg(log(z)), Q.imaginary(z) & Q.ne(z, 0))`` gave ``nan``: the
  shared zero row rewrote ``log(Abs(z))`` to ``zoo`` (differential seed 7);
* ``refine(c**2*X*Y**2, Q.imaginary(c) & ...)`` gave the zero matrix: SymPy
  calls ``c**2`` zero for imaginary ``c`` (the matrix fuzz, seed 1).

The cause is SymPy's ``Q.nonzero`` handlers for ``Abs``, ``Pow`` and ``Mul``,
which answer ``False`` ("zero or not real") whenever an argument is not a real
nonzero number, and ``Q.zero(e) = ~Q.nonzero(e) & Q.real(e)``.  The guard is in
``satrefine/backend.py``.
"""
from __future__ import annotations

import pytest
from sympy import Abs, I, MatrixSymbol, Q, Symbol, ZeroMatrix, arg, exp, log, sqrt, symbols
from sympy.assumptions.ask import ask as sympy_ask

from satrefine import backend, refine
from satrefine.backend import ask

x, y, z, b, c = Symbol('x'), Symbol('y'), Symbol('z'), Symbol('b'), Symbol('c')


def test_abs_of_an_imaginary_number_is_positive():
    with backend.using("combined"):
        assert ask(Q.zero(Abs(x)), Q.imaginary(x) & Q.ne(x, 0)) is not True
        assert ask(Q.positive(exp(I*Abs(x))), Q.imaginary(x)) is not True


def test_log_exp_of_imaginary_abs_is_not_zero():
    with backend.using("combined"):
        assert refine(log(exp(I*Abs(x))), Q.imaginary(x)) != 0


def test_arg_log_of_imaginary_is_not_nan():
    with backend.using("combined"):
        assert refine(arg(log(z)), Q.imaginary(z) & Q.ne(z, 0)) == arg(log(z))


def test_scalar_square_of_imaginary_is_not_zero_in_a_matrix_product():
    X, Y = MatrixSymbol('X', 2, 2), MatrixSymbol('Y', 2, 2)
    with backend.using("combined"):
        r = refine(c**2*X*Y**2, Q.imaginary(c) & Q.integer_elements(Y) & Q.real_elements(X))
    assert r != ZeroMatrix(2, 2)


# (proposition, assumptions, SymPy's answer, the guarded answer); every guarded
# answer is true: |x| > 0, x**2 < 0 and x*y real nonzero for imaginary x, y.
CASES = [
    (Q.zero(Abs(x)), Q.imaginary(x), True, False),
    (Q.zero(Abs(x)), Q.imaginary(x) & Q.ne(x, 0), True, False),
    (Q.positive(Abs(x)), Q.imaginary(x), False, True),
    (Q.zero(b**2), Q.imaginary(b), True, False),
    (Q.nonzero(b**2), Q.imaginary(b), False, True),
    (Q.nonzero(x*y), Q.imaginary(x) & Q.imaginary(y), False, True),
]


@pytest.mark.parametrize("prop, assumptions, sympy_answer, guarded", CASES)
def test_guarded_answers(prop, assumptions, sympy_answer, guarded):
    assert backend._guarded_sympy_ask(prop, assumptions) is guarded
    # the guard is scoped to the combined backend: plain SymPy is unchanged
    assert sympy_ask(prop, assumptions) is sympy_answer
    with backend.using("sympy"):
        assert ask(prop, assumptions) is sympy_answer


# answers SymPy gets right, which the guard must keep
KEPT = [
    (Q.zero(Abs(x)), Q.zero(x), True),
    (Q.zero(x**2), Q.zero(x), True),
    (Q.nonzero(Abs(x)), Q.real(x) & Q.nonzero(x), True),
    (Q.nonzero(I*x), Q.positive(x), False),        # not real
    (Q.nonzero(x*y), Q.imaginary(x) & Q.real(y) & Q.nonzero(y), False),
    (Q.zero(x*y), Q.zero(x), True),
    (Q.nonzero(x**2), Q.zero(x), False),
    (Q.nonzero(sqrt(x)), Q.negative(x), False),    # imaginary
    (Q.zero(Abs(x)), True, None),
]


@pytest.mark.parametrize("prop, assumptions, answer", KEPT)
def test_guard_keeps_right_answers(prop, assumptions, answer):
    assert backend._guarded_sympy_ask(prop, assumptions) is answer


def test_fuzz_case_log_exp_sqrt_square():
    # differential seed 3's form of the first case
    with backend.using("combined"):
        assert refine(log(exp(I*sqrt(x**2))), Q.imaginary(x)) != 0
