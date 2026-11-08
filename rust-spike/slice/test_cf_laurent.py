"""Adapters step, part C2: `pi_laurent` on Rust (constfield.rs `pi_laurent_elem`, through lra_cert.rs's `laurent`) against
constfield.py's, on Elements in pi alone (sums of `c * pi**j` over a power of pi or a rational) and on Elements it refuses
(other constants, a denominator that isn't a power of pi, pi with an Element coefficient). Same pairs, same order.
Run from this directory. With `SLICE_SESSION_PLANT=cf-laurent-rational` set by hand, test_matches_python fails."""
import random
from fractions import Fraction as F

import pytest

import sa_solver as S
from satassume.theories.lra import constfield as cf

PI, E = cf.PI, cf.E
S2 = cf.radical(F(2), 2)


def py(x):
    r = cf.pi_laurent(x)
    return None if r is None else list(r.items())


def cases():
    rnd = random.Random(323)
    out = [F(0), F(3, 7), PI, -PI, 1 / PI, PI**3 / 5, (PI + 1) / PI**2, F(2, 3) * PI - F(1, 9), PI**-4 * (PI**2 - 3),
           E, PI + E, S2 * PI, PI / (PI + 1), 1 / (PI**2 + 1), PI * E / PI**2, (PI - S2) / PI]
    for _ in range(300):
        x = F(rnd.randint(-9, 9), rnd.randint(1, 5))
        for _ in range(rnd.randint(1, 4)):
            x = x + F(rnd.randint(-9, 9), rnd.randint(1, 5)) * PI**rnd.randint(1, 6)
        x = x / PI**rnd.randint(0, 5) / F(rnd.randint(1, 7))
        if rnd.random() < 0.2:
            x = x + rnd.choice([E, S2, 1 / (PI + 2), S2 * PI])
        out.append(x)
    return out


def test_matches_python():
    seen = {'some': 0, 'none': 0, 'element': 0}
    for x in cases():
        want = py(x)
        assert S.cf_op('pi_laurent', x) == want, x
        seen['none' if want is None else 'some'] += 1
        seen['element'] += type(x) is cf.Element
    assert seen['some'] > 100 and seen['none'] > 30 and seen['element'] > 200, seen


def test_counter_and_plant_fire():
    """The counter `cf:pi_laurent` counts Element bounds, and the plant drops an Element bound's pi terms."""
    before = S.session_counts()['cf:pi_laurent']
    S.cf_op('pi_laurent', PI**2 / PI**5)
    S.cf_op('pi_laurent', F(1, 2))                  # a Fraction isn't counted
    assert S.session_counts()['cf:pi_laurent'] == before + 1
    S.rel_plant('cf-laurent-rational')
    try:
        assert S.cf_op('pi_laurent', 3 * PI**2 - 1) == [(0, F(-1))]
    finally:
        S.rel_plant(None)
    assert S.cf_op('pi_laurent', 3 * PI**2 - 1) == [(0, F(-1)), (2, F(3))]
