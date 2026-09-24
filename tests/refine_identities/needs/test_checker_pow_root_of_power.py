"""Checker finding (engine-owned ``_simple.refine_Pow_guarded``, the vendored
``refine_Pow``): ``(x**3)**(1/3)`` is rewritten to ``-x`` for negative ``x``
and to ``Abs(x)`` for real ``x``, but for ``x < 0`` the principal cube root
of ``x**3`` is ``-x*exp(I*pi/3)``, not real.  v3 does not fire here.

The fuzz (``tools/refine_differential.py``, seeds 2, 3, 7) reaches this
through every family that refines its argument first: ``floor``, ``Mod``,
``Max``, ``factorial``, ``gamma``, ``Heaviside``, trig, log, ... (e.g.
``floor((k**3)**(1/3))`` under ``Q.real(k)`` -> ``floor(Abs(k))``, wrong at
``k = -1.77``).  Same kind as the ``sqrt(x**2)``/imaginary case the
``_simple`` docstring already lists; the ``power_exp_log`` family is meant
to replace this key.
"""
from __future__ import annotations

from sympy import Abs, Q, Rational, S, Symbol, floor

from satrefine import refine

x = Symbol('x')
CUBE_ROOT = (x**3)**Rational(1, 3)


def test_cube_root_of_cube_is_not_minus_x_for_negative_x():
    assert refine(CUBE_ROOT, Q.negative(x)) != -x
    assert (CUBE_ROOT.subs(x, -1) - 1).evalf() != 0     # the value it claims is wrong


def test_cube_root_of_cube_is_not_abs_for_real_x():
    assert refine(CUBE_ROOT, Q.real(x)) != Abs(x)


def test_floor_of_cube_root_stays_sound():
    assert refine(floor(CUBE_ROOT), Q.real(x)) != floor(Abs(x))
    assert floor(CUBE_ROOT.subs(x, S(-2))) != floor(Abs(S(-2)))
