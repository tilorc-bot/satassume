"""``satrefine.tools.lib.accepted``: the reviewed differences from v3.

The scoreboard checks every "fired where v3 expects unchanged" numerically
through the harness oracle, except where the sampler cannot draw a point (a
bound with ``pi``, an infinite argument).  Those accepted extras are checked
here at exact points instead."""
from __future__ import annotations

import pytest
from sympy import Abs, I, Max, N, Rational, S, acos, asin, atan, cos, cot, log, oo, pi, sin, symbols, zoo

from satrefine.tools.lib import accepted, battery

x = symbols("x")


def test_entries_are_distinct_and_well_formed():
    keys = [accepted.key(a.kind, a.source, a.case, a.got) for a in accepted.ACCEPTED]
    assert len(keys) == len(set(keys))
    for a in accepted.ACCEPTED:
        assert a.kind in battery.DIFFERENCES and " | " in a.case and a.reason
        assert set(a.modes) <= {"generated", "live"}


def _grid(lo, hi, lo_open=False, hi_open=False, n=40):
    pts = [lo + (hi - lo)*Rational(i, n) for i in range(n + 1)]
    return pts[1 if lo_open else 0:n if hi_open else n + 1]


@pytest.mark.parametrize("expr, got, points", [
    (acos(cos(x)), Abs(x), _grid(-pi, pi)),                     # covers the [-pi/2, pi/2] case too
    (acos(sin(x)), Abs(x - pi/2), _grid(0, pi)),
    (asin(cos(x)), x - 3*pi/2, _grid(pi, 2*pi)),
    (atan(cot(x)), -x + 3*pi/2, _grid(pi, 2*pi, True, True)),
])
def test_accepted_inverse_extras_at_exact_points(expr, got, points):
    for p in points:
        assert abs(N(expr.subs(x, p) - got.subs(x, p), 30)) < 1e-20, p


def test_accepted_extras_at_infinity():
    for p in (oo, -oo, zoo, I*oo, -I*oo):
        assert log(1/x).subs(x, p) == zoo                         # log(1/x) | Q.infinite(x) -> zoo
    for q in (oo, -oo, S.Zero, S(-3), Rational(7, 2), pi, S(10)**30):
        assert Max(oo, q) == oo                                   # Max(x, y) | Q.positive_infinite(x) -> x
