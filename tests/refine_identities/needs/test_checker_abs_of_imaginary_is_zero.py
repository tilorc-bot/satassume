"""Checker finding, not in handlers_identities: SymPy's ``ask`` calls ``Abs(x)``
zero for an imaginary ``x`` (``Q.zero(Abs(x))`` is ``True`` and
``Q.positive(Abs(x))`` is ``False`` under ``Q.imaginary(x)``, while
``Q.zero(x)`` is ``False``), and the default ``combined`` backend passes that
answer on whenever satassume returns ``None`` (a relation among the
assumptions is enough).  Rows then fire on it:

* ``refine(log(exp(I*Abs(x))), Q.imaginary(x))`` gives ``0``: complex_parts'
  ``arg(a) -> 0`` for ``Q.positive(a)`` fires on ``exp(I*Abs(x))``, which
  SymPy calls positive (it is ``exp(I*t)`` with ``t = |x| > 0``); the fuzz
  reaches it as ``log(exp(sqrt(x**2)))`` (differential seed 3);
* ``refine(arg(log(z)), Q.imaginary(z) & Q.ne(z, 0))`` gives ``nan``: the
  shared zero row rewrites ``log(Abs(z))`` to ``zoo`` (differential seed 7).

The request is for the backend: do not accept this SymPy answer (or fix the
handler, which appears to read ``~Q.nonzero(x)``, "not a nonzero real", as
"zero").
"""
from __future__ import annotations

from sympy import Abs, I, Q, Symbol, arg, exp, log

from satrefine import refine
from satrefine.backend import ask

x, z = Symbol('x'), Symbol('z')


def test_abs_of_an_imaginary_number_is_positive():
    assert ask(Q.zero(Abs(x)), Q.imaginary(x) & Q.ne(x, 0)) is not True
    assert ask(Q.positive(exp(I*Abs(x))), Q.imaginary(x)) is not True


def test_log_exp_of_imaginary_abs_is_not_zero():
    assert refine(log(exp(I*Abs(x))), Q.imaginary(x)) != 0


def test_arg_log_of_imaginary_is_not_nan():
    assert refine(arg(log(z)), Q.imaginary(z) & Q.ne(z, 0)) == arg(log(z))
