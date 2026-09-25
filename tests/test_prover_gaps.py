"""Two prover gaps closed in the templates (refine-identities plan, step 5).

1. Parity arithmetic for sums with half-integer coefficients: ``(n - 1)/2``
   is SymPy's ``Add(-1/2, n/2)``, an integer for odd ``n``.  For
   ``N = c0 + sum(c_k*t_k)`` with rational coefficients of least common
   denominator 2 and integer ``t_k``, ``2*N`` is an integer of parity
   ``2*c0 + #{k : 2*c_k odd and t_k odd}`` (mod 2), and ``N`` is an integer
   iff that is even (``satassume/templates/core.py``, ``_half_rules``).
2. ``re`` and ``im`` of ``floor(y)`` / ``ceiling(y)`` are integers for a
   finite, possibly complex ``y`` (``satassume/templates/functions.py``).

Every definite answer is also checked against concrete values.
"""
from __future__ import annotations

import itertools
import random

import pytest
from sympy import (I, Q, Rational, S, Symbol, ceiling, exp, floor, im, pi, re,
                   symbols)
from sympy.logic.boolalg import And

from satassume.sympy_api import ask

n, m, k, y = symbols('n m k y')


@pytest.mark.parametrize("expr, facts, answer", [
    ((1 - n)/2, Q.odd(n), True),
    ((n - 1)/2, Q.odd(n), True),
    (n/2 + S.Half, Q.odd(n), True),
    (3*n/2 + S.Half, Q.odd(n), True),
    (n/2 + m/2, Q.odd(n) & Q.odd(m), True),
    (n/2 + m/2, Q.odd(n) & Q.even(m), False),
    (n/2 + m + S.Half, Q.odd(n) & Q.integer(m), True),
    ((n - 1)/2, Q.even(n), False),
    (n/2 + m/2 + k/2 + S.Half, Q.odd(n) & Q.odd(m) & Q.even(k), False),
    (n/2 + m/2 + k/2 + S.Half, Q.odd(n) & Q.odd(m) & Q.odd(k), True),
    ((n - 1)/2, Q.integer(n), None),
    ((n - 1)/2, Q.odd(n) | Q.imaginary(n), None),
    (n/2 + m/3, Q.odd(n) & Q.integer(m), None),     # denominator 6: not decided
])
def test_half_integer_sums(expr, facts, answer):
    assert ask(Q.integer(expr), facts) is answer


def test_half_integer_sum_backward():
    # (n - 1)/2 an integer and n an integer: n is odd
    assert ask(Q.odd(n), Q.integer(n) & Q.integer((n - 1)/2)) is True
    assert ask(Q.even(n), Q.integer(n) & Q.integer(n/2 + m/2) & Q.odd(m)) is False


def test_half_integer_sum_is_rational():
    assert ask(Q.rational((n - 1)/2), Q.integer(n)) is True
    assert ask(Q.noninteger((n - 1)/2), Q.even(n)) is True


def test_exp_of_i_pi_times_half_odd_shift():
    # I*pi*(n - 1)/2 is I*pi times an integer for odd n: exp of it is real
    assert ask(Q.real(exp(I*pi*(n - 1)/2)), Q.odd(n)) is True
    assert ask(Q.real(exp(I*pi*(n/2 + S.Half))), Q.odd(n)) is True


def _random_case(rng):
    syms = [n, m, k][:rng.randint(1, 3)]
    coeffs = [Rational(rng.randint(-5, 5), rng.choice([1, 2, 2])) for _ in syms]
    c0 = Rational(rng.randint(-3, 3), rng.choice([1, 2]))
    expr = c0 + sum(c*s for c, s in zip(coeffs, syms))
    kinds = {s: rng.choice(['even', 'odd', 'integer', 'odd', 'even']) for s in syms}
    return expr, syms, kinds


def test_half_integer_sums_against_values():
    rng = random.Random(0)
    decided = 0
    for _ in range(300):
        expr, syms, kinds = _random_case(rng)
        if not expr.free_symbols:
            continue
        facts = And(*[getattr(Q, kinds[s])(s) for s in syms])
        for pred in ('integer', 'even', 'odd'):
            ans = ask(getattr(Q, pred)(expr), facts)
            if ans is None:
                continue
            decided += 1
            pools = {'even': [-4, -2, 0, 2, 6], 'odd': [-3, -1, 1, 3, 5],
                     'integer': [-3, -2, 0, 1, 4]}
            for vals in itertools.product(*[pools[kinds[s]] for s in syms]):
                v = expr.xreplace(dict(zip(syms, map(S, vals))))
                assert getattr(v, 'is_' + pred) is ans, (expr, facts, pred, vals, v)
    assert decided > 200


@pytest.mark.parametrize("f", [floor, ceiling])
@pytest.mark.parametrize("part", [re, im])
def test_parts_of_round_are_integers(f, part):
    assert ask(Q.integer(part(f(y))), Q.finite(y)) is True
    assert ask(Q.integer(part(f(y))), Q.complex(y)) is True
    assert ask(Q.integer(part(f(y))), Q.imaginary(y)) is True
    assert ask(Q.integer(part(f(y)))) is None                 # y may be infinite


@pytest.mark.parametrize("value", [Rational(5, 2) + Rational(7, 3)*I, -Rational(1, 3) - 2*I,
                                   S(3), I/2, -Rational(9, 4) + I*Rational(1, 2)])
def test_parts_of_round_values(value):
    for f in (floor, ceiling):
        for part in (re, im):
            assert part(f(value)).is_integer


def test_parts_of_round_nested_argument():
    assert ask(Q.integer(re(floor(y + 2*I))), Q.finite(y)) is True
