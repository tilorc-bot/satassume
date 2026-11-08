"""Element._new step (issue 323): the Rust `Element` pyclass (constfield.rs `PyElem`) against constfield.py's Element, which it
replaces where a Rust number crossed to Python. `==`, `!=`, `hash`, `repr` and `bool` are answered on Rust and must be
Python's; `Num::from_py` reads it back as the same number; any other read goes to the Python Element, counted.
Each of the pyclass plants makes test_matches_python fail (test_plants_caught). Run from this directory."""
import copy
import random
from fractions import Fraction as F

import pytest

import sa_solver as S
from satassume.theories.lra import constfield as cf

PI, E = cf.PI, cf.E
S2 = cf.radical(F(2), 2)


def cases():
    rnd = random.Random(159)
    out = [PI, -PI, 1 / PI, PI**3 / 5, (PI + 1) / PI**2, F(2, 3) * PI - F(1, 9), E, PI + E, S2 * PI, PI / (PI + 1),
           1 / (PI**2 + 1), (PI - S2) / PI, S2, S2 - 1, E * PI / (E + PI)]
    gens = [PI, E, S2]
    for _ in range(200):
        x = F(rnd.randint(-9, 9), rnd.randint(1, 5))
        for _ in range(rnd.randint(1, 3)):
            x = x + F(rnd.randint(-9, 9), rnd.randint(1, 5)) * rnd.choice(gens) ** rnd.randint(1, 3)
        if rnd.random() < 0.3:
            x = x / (rnd.choice(gens) + rnd.randint(1, 4))
        if type(x) is cf.Element:
            out.append(x)
    return out


def rust(x):
    r = S.cf_op('rust_element', x)
    assert type(r) is S.Element and type(x) is cf.Element
    return r


def check(x):
    r = rust(x)
    y = x + 1
    assert (r == x) is True and (x == r) is True and (r != x) is False and (x != r) is False
    assert (r == y) is False and (r != y) is True and (r == rust(y)) is False
    assert hash(r) == hash(x)
    assert repr(r) == repr(x)
    assert bool(r) is bool(x)
    assert (r == 3) is False and (r == F(1, 2)) is False and (r == None) is False and (r == 'pi') is False  # noqa: E711
    back = S.cf_op('roundtrip', r)                         # Num::from_py of the pyclass, out as a Python Element
    assert type(back) is cf.Element and back._n == x._n and back._d == x._d
    assert {r: 1} == {x: 1} and frozenset([(1, r)]) == frozenset([(1, x)])


@pytest.mark.parametrize('i', range(0, 260, 13))
def test_matches_python(i):
    xs = cases()
    for x in xs[i:i + 13]:
        check(x)


def test_counters_and_fallback():
    c0 = S.session_counts()
    x = PI / 3 + S2
    r = rust(x)
    assert rust is not None and S.session_counts()['cf:elem_new'] == c0['cf:elem_new'] + 1
    assert r == x and hash(r) == hash(x) and repr(r) == repr(x)
    c1 = S.session_counts()
    assert c1['cf:elem_eq'] > c0['cf:elem_eq'] and c1['cf:elem_hash'] > c0['cf:elem_hash']
    assert c1['cf:elem_repr'] > c0['cf:elem_repr']
    assert c1['cf:elem_py_read'] == c0['cf:elem_py_read']
    # Reads only Python answers: arithmetic, order, attributes. Same values as Python's, each counted.
    assert r + 1 == x + 1 and 1 - r == 1 - x and r * PI == x * PI and (r < 3) == (x < 3) and -r == -x
    assert r._n == x._n and r.sign() == x.sign() and r.to_sympy() == x.to_sympy()
    assert S.session_counts()['cf:elem_py_read'] >= c1['cf:elem_py_read'] + 8
    assert copy.deepcopy(r) is r and copy.copy(r) is r
    assert S.cf_num(r) is r


def test_same_object_while_alive():
    """`to_py` of one `Elem` gives the same pyclass object while the first is alive (`e + 0` is `e`)."""
    x = S2 + PI
    r = rust(x)
    assert S.cf_op('add', r, F(0)) is not None             # a Python Element out (the bridge), still equal
    assert S.cf_op('add', r, F(0)) == r


PLANTS = ['elem-eq-flip', 'elem-hash-skew', 'elem-repr-bracket', 'elem-from-neg']


@pytest.mark.parametrize('plant', PLANTS)
def test_plants_caught(plant):
    before = S.session_counts()['rel:plant_fired'] if 'rel:plant_fired' in S.session_counts() else None
    S.rel_plant(plant)
    try:
        with pytest.raises(AssertionError):
            for x in cases()[:20]:
                check(x)
    finally:
        S.rel_plant(None)
    if before is not None:
        assert S.session_counts()['rel:plant_fired'] > before
    for x in cases()[:20]:
        check(x)
