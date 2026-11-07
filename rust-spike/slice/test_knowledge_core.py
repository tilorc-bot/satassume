"""Step 6e: core.py's rule builders on Rust against Python's, by enumeration, field by field and in order (`resolve` reads
rules in order). The splits are compared in the engine, by knowledge_fresh --mode shadow."""
import itertools

import pytest
import sa_solver
from sympy import Rational

from satassume.knowledge.templates import core

RATS = sorted({Rational(p, q) for p in range(-9, 10) for q in (1, 2, 3, 4, 7)})


def pq(c):
    return int(c.p), int(c.q)


def test_half_rules():
    for m in range(0, 7):
        for odd in itertools.product((0, 1), repeat=m):
            for a0 in (0, 1):
                assert sa_solver.core_half_rules(a0, [bool(x) for x in odd], m) == core._half_rules(a0, odd, m)


@pytest.mark.parametrize('name', ['bound', 'recip'])
def test_bound_recip_rules(name):
    rs, py = getattr(sa_solver, f'core_{name}_rules'), getattr(core, f'_{name}_rules')
    for c0 in RATS:
        for c1 in RATS:
            if c1 != 0:
                assert rs(*pq(c0), *pq(c1)) == py(c0, c1), (c0, c1)


def test_not_unit_premises():
    for c0 in RATS:
        for c1 in RATS:
            if c1 != 0:
                got = [core._INT_BOUNDS[i][0] for i in sa_solver.core_not_unit_premises(*pq(c0), *pq(c1))]
                assert got == core._not_unit_premises(c0, c1), (c0, c1)


def test_imag_rules():
    for m in range(0, 7):
        for signs in itertools.product((1, -1), repeat=m):
            for cs in (frozenset(), frozenset({1}), frozenset({-1}), frozenset({1, -1})):
                assert sa_solver.core_imag_rules(list(signs), 1 in cs, -1 in cs) == core._imag_rules(signs, cs)
    assert sa_solver.core_imag_number_rules() == core._imag_number_rules()


def test_types_match():
    """`_mismatch` compares types too: lists of (list, list) tuples of (int, str, bool) tuples."""
    r, p = sa_solver.core_bound_rules(1, 2, 1, 1), core._bound_rules(Rational(1, 2), Rational(1))
    assert [(type(a), type(b), [type(x) for x in a]) for a, b in r] == [(type(a), type(b), [type(x) for x in a]) for a, b in p]
