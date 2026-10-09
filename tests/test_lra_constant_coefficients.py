"""LRA with constants in the coefficients (``pi*x``, ``x/pi``, ``sqrt(2)*x``):
the theory over :mod:`satassume.theories.lra.constfield` numbers, the adapter, the
integrality link, and giving up on undecidable comparisons.

Oracles independent of the simplex:

* Fourier-Motzkin over the exact field (the elimination of
  ``test_lra.py``, generic in the number type): exact feasibility of a
  conjunction of ``<, <=, ==, !=`` with coefficients in ``Q(pi, E, ...)``;
* z3's nonlinear real arithmetic for ``sqrt(2)`` coefficients (``s*s == 2,
  s > 0``: exact), skipped without ``z3-solver``;
* refine's 25 integrality queries, all False by hand (``x/pi + 1/2`` on
  ``(-pi/2, pi/2)`` lies in ``(0, 1)``).
"""
from __future__ import annotations

import random
import signal
import threading

import pytest

sympy = pytest.importorskip("sympy")
from sympy import E as sE
from sympy import Q, Rational, pi, sqrt, symbols

from satassume import DictCache, Engine
from satassume.theories.lra import constfield as cf
from satassume.theories.lra import lra
from satassume.theories.lra.constfield import PI, num
from satassume.sympy_api import ask

F = cf.Fraction
SQ2 = cf.radical(2, 2)


@pytest.fixture(autouse=True)
def _time_limit():
    if not hasattr(signal, "SIGALRM") or threading.current_thread() is not threading.main_thread():
        yield
        return

    def expire(signum, frame):
        raise TimeoutError("test ran longer than 120 s")
    old = signal.signal(signal.SIGALRM, expire)
    signal.alarm(120)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def _ask(prop, assum=True):
    try:
        return ask(prop, assum, Engine(cache=DictCache()))
    except ValueError:
        return "inconsistent"


# ----------------------------------------------------------------------
# Fourier-Motzkin over the field (generic copy of test_lra's oracle)
# ----------------------------------------------------------------------

def _ineqs(cons):
    ineqs, diseqs = [], []
    for coeffs, op, rhs in cons:
        c = {t: num(v) for t, v in coeffs.items() if not cf.formally_zero(num(v))}
        rhs = num(rhs)
        neg = {t: -v for t, v in c.items()}
        if op == "<=":
            ineqs.append((c, False, rhs))
        elif op == "<":
            ineqs.append((c, True, rhs))
        elif op == ">=":
            ineqs.append((neg, False, -rhs))
        elif op == ">":
            ineqs.append((neg, True, -rhs))
        elif op == "==":
            ineqs += [(c, False, rhs), (neg, False, -rhs)]
        else:
            diseqs.append((c, rhs))
    return ineqs, diseqs


def _fm(rows) -> bool:
    """Feasibility of ``(coeffs, strict, b)`` rows ``coeffs.x (<|<=) b``."""
    while True:
        for c, strict, b in rows:
            if not c and (b < 0 or (strict and b == 0)):
                return False
        rows = [r for r in rows if r[0]]
        if not rows:
            return True
        var = min({t for c, _, _ in rows for t in c}, key=repr)
        pos = [r for r in rows if r[0].get(var, 0) > 0]
        neg = [r for r in rows if r[0].get(var, 0) < 0]
        new = [r for r in rows if var not in r[0]]
        for cp, sp, bp in pos:
            for cn, sn, bn in neg:
                ap, an = cp[var], -cn[var]
                c = {}
                for t in set(cp) | set(cn):
                    if t != var:
                        v = cp.get(t, F(0)) / ap + cn.get(t, F(0)) / an
                        if not cf.formally_zero(v):
                            c[t] = v
                new.append((c, sp or sn, bp / ap + bn / an))
        rows = new


def fm_feasible(cons) -> bool:
    ineqs, diseqs = _ineqs(cons)
    if not _fm(ineqs):
        return False
    for c, b in diseqs:
        neg = {t: -v for t, v in c.items()}
        if not _fm(ineqs + [(c, True, b)]) and not _fm(ineqs + [(neg, True, -b)]):
            return False
    return True


def holds(con, point) -> bool:
    coeffs, op, rhs = con
    lhs = sum((num(c) * point[t] for t, c in coeffs.items()), F(0))
    return {"<=": lhs <= rhs, "<": lhs < rhs, "==": lhs == rhs, ">=": lhs >= rhs,
            ">": lhs > rhs, "!=": lhs != rhs}[op]


# ----------------------------------------------------------------------
# the theory against the oracle
# ----------------------------------------------------------------------

POOL = [F(1), F(-1), F(2), F(1, 2), F(-3), PI, -PI, 1 / PI, PI / 2 + 1, cf.E, PI * cf.E,
        (PI + 1) / (PI - 3)]


def _random_system(rng, pool, nvars=3, ncons=5):
    xs = [f"x{i}" for i in range(nvars)]
    cons = []
    for _ in range(ncons):
        k = rng.randint(1, min(3, nvars))
        coeffs = {t: rng.choice(pool) for t in rng.sample(xs, k)}
        rhs = rng.choice(pool + [F(0), F(5, 3)])
        cons.append((coeffs, rng.choice(["<=", "<", "==", ">=", ">", "!="]), rhs))
    return cons


def _payload(con):
    coeffs, op, rhs = con
    return lra.constraint(coeffs, op, rhs)


def _run(cons):
    """Register and assert every constraint in a fresh theory, check; the
    verdict (False with a conflict, True with a model) or None (gave up)."""
    t = lra.LRATheory()
    for i, con in enumerate(cons, 1):
        t.register_atom(i, _payload(con))
    for i in range(1, len(cons) + 1):
        t.push_level()
        r = t.assert_lit(i)
        if t.gave_up:
            return None, t
        if r is not None:
            return (False, r[1]), t
    r = t.check()
    if t.gave_up:
        return None, t
    return r, t


@pytest.mark.parametrize("seed", range(120))
def test_theory_against_field_fourier_motzkin(seed):
    rng = random.Random(seed)
    pool = POOL if seed % 3 else POOL + [SQ2, SQ2 + 1]
    cons = _random_system(rng, pool, nvars=rng.randint(1, 3), ncons=rng.randint(1, 6))
    r, t = _run(cons)
    if r is None:
        return                                   # gave up: allowed, never a verdict
    feasible = fm_feasible(cons)
    if r[0] is False:
        assert not feasible, cons
        core = [cons[abs(l) - 1] for l in r[1]]
        assert all(l < 0 for l in r[1]) and not fm_feasible(core), (cons, r[1])
    else:
        assert feasible, cons
        model = r[1]
        point = {x: model.get(x, F(0)) for c in cons for x in c[0]}
        assert all(holds(c, point) for c in cons), (cons, model)


def test_pi_coefficient_bounds_are_exact():
    # x/pi + 1/2 on (-pi/2, pi/2): exactly (0, 1) at the ends
    t = lra.LRATheory()
    t.register_atom(1, lra.constraint({"x": 1}, ">", -PI / 2))
    t.register_atom(2, lra.constraint({"x": 1}, "<", PI / 2))
    t.register_atom(3, lra.constraint({"x": 1 / PI}, "<=", F(-1, 2)))   # x/pi + 1/2 <= 0
    t.register_atom(4, lra.constraint({"x": 1 / PI}, ">=", F(1, 2)))    # x/pi + 1/2 >= 1
    for lit in (1, 2):
        assert t.assert_lit(lit) is None
    props = dict(t.propagate())
    assert -3 in props and -4 in props                  # both refuted by the bounds
    assert not t.gave_up


def test_integrality_with_pi_coefficient():
    t = lra.LRATheory()
    t.register_atom(1, lra.constraint({"x": 1}, ">", -PI / 2))
    t.register_atom(2, lra.constraint({"x": 1}, "<", PI / 2))
    t.register_atom(3, lra.Integral((("x", 1 / PI),), F(1, 2)))
    assert t.assert_lit(1) is None and t.assert_lit(2) is None
    r = t.assert_lit(3)
    assert r is not None and r[0] is False and sorted(r[1]) == [-3, -2, -1]


def test_pinned_integral_value_is_decided():
    # x = 2*pi pins x/pi to the integer 2
    t = lra.LRATheory()
    t.register_atom(1, lra.constraint({"x": 1}, "==", 2 * PI))
    t.register_atom(2, lra.Integral((("x", 1 / PI),), 0))
    assert t.assert_lit(1) is None
    assert (2, [2, -1]) in [(l, sorted(e, reverse=True)) for l, e in t.propagate()]


def test_algebraic_integer_is_never_declared_non_integral():
    # x = sqrt(2)**2 (formally t**2, value 2): "x in Z" holds; the theory
    # must not call it non-integral: it gives up instead
    t = lra.LRATheory()
    t.register_atom(1, lra.constraint({"x": 1}, "==", SQ2 * SQ2))
    t.register_atom(2, lra.Integral((("x", F(1)),), 0))
    assert t.assert_lit(1) is None
    assert all(l != -2 for l, _ in t.propagate())      # skipped, not refuted
    t.push_level()
    assert t.assert_lit(2) is None and t.gave_up        # no conflict claimed
    assert t.check() is None
    # x = sqrt(2)**2 + 1/2 (value 5/2) is refuted: the value is shown
    # to lie strictly between 2 and 3
    t2 = lra.LRATheory()
    t2.register_atom(1, lra.constraint({"x": 1}, "==", SQ2 * SQ2 + F(1, 2)))
    t2.register_atom(2, lra.Integral((("x", F(1)),), 0))
    assert t2.assert_lit(1) is None
    r = t2.assert_lit(2)
    assert r is not None and r[0] is False and not t2.gave_up


def test_give_up_is_silent_and_final():
    t = lra.LRATheory()
    t.register_atom(1, lra.constraint({"x": 1}, "<=", SQ2 * SQ2))
    t.register_atom(2, lra.constraint({"x": 1}, ">=", F(2)))
    t.register_atom(3, lra.constraint({"x": 1}, "!=", F(2)))
    for lit in (1, 2, 3):
        t.push_level()
        assert t.assert_lit(lit) is None
    assert t.check() is None and t.gave_up and t.stats["gave_up"] >= 1
    assert t.propagate() == [] and t.assert_lit(-1) is None
    t.pop_level()


def test_pivots_with_constants_leave_a_consistent_tableau():
    # a random pivot-heavy system; every row identity holds exactly
    rng = random.Random(3)
    for _ in range(20):
        cons = [c for c in _random_system(rng, POOL, nvars=3, ncons=6) if c[1] != "!="]
        r, t = _run(cons)
        if r is None:
            continue
        for b, row in t._rows.items():
            val = sum((a * t._vq[k] for k, a in row.items()), F(0))
            assert val == t._vq[b]


# ----------------------------------------------------------------------
# sqrt(2) coefficients against z3's nonlinear real arithmetic
# ----------------------------------------------------------------------

def test_sqrt2_systems_against_z3():
    z3 = pytest.importorskip("z3")
    rng = random.Random(11)
    pool = [F(1), F(-1), F(1, 2), F(-2), SQ2, -SQ2, SQ2 + 1, 1 / SQ2, SQ2 / 3 - 1]
    s = z3.Real("s")
    checked = 0
    for _ in range(60):
        cons = _random_system(rng, pool, nvars=2, ncons=rng.randint(2, 5))
        r, _t = _run(cons)
        if r is None:
            continue
        sol = z3.Solver()
        sol.add(s * s == 2, s > 0)
        xs = {x: z3.Real(x) for c in cons for x in c[0]}

        def zv(v):
            v = num(v)
            if type(v) is F:
                return z3.RealVal(f"{v.numerator}/{v.denominator}")
            # v = n(s)/d(s), both polynomials in the one constant sqrt(2)
            def poly(p):
                if type(p) is F:
                    return z3.RealVal(f"{p.numerator}/{p.denominator}")
                return sum((poly(c) * s ** k for k, c in enumerate(p[1])), z3.RealVal(0))
            return poly(v.numerator) / poly(v.denominator)
        for coeffs, op, rhs in cons:
            lhs = sum((zv(c) * xs[x] for x, c in coeffs.items()), z3.RealVal(0))
            rv = zv(rhs)
            sol.add({"<=": lhs <= rv, "<": lhs < rv, "==": lhs == rv, ">=": lhs >= rv,
                     ">": lhs > rv, "!=": lhs != rv}[op])
        z = sol.check()
        assert z != z3.unknown
        assert (r[0] is not False) == (z == z3.sat), cons
        checked += 1
    assert checked > 40


# ----------------------------------------------------------------------
# end to end: refine's integrality queries and relations with constants
# ----------------------------------------------------------------------

x, t_, k_ = symbols("x t k")
xr, yr = symbols("xr yr", real=True)

REFINE_INTEGRALITY = [
    (sympy.im(t_) / pi + Rational(1, 2), Q.gt(sympy.im(t_), -pi / 2) & Q.lt(sympy.im(t_), pi / 2)),
    (k_ / (2 * pi) + Rational(1, 2), Q.nonpositive(k_) & Q.gt(k_, -pi / 2)),
    (t_ ** 2 / pi + Rational(1, 2), Q.ge(t_ ** 2, 0) & Q.lt(t_ ** 2, pi / 2)),
    (t_ / pi + Rational(1, 2), Q.ge(1, t_) & Q.le(0, t_)),
    (t_ / pi + Rational(1, 2), Q.ge(t_, -5) & Q.ge(t_, 0) & Q.le(t_, 1) & Q.le(t_, 3)),
    (t_ / pi + Rational(1, 2), Q.gt(t_, -pi / 2) & Q.lt(t_, pi / 2)),
    (t_ / pi + Rational(1, 2), Q.nonnegative(t_) & Q.le(t_, 1)),
    ((-x + pi / 2) / pi + Rational(1, 2), Q.gt(x, 0) & Q.lt(x, pi)),
    ((-x + pi / 2) / pi + Rational(1, 2), Q.negative(x) & Q.real(x) & Q.ge(x, -pi / 2) & Q.le(x, pi / 2)),
    ((-x + pi / 2) / pi + Rational(1, 2), Q.positive(x) & Q.real(x) & Q.ge(x, -pi / 2) & Q.le(x, pi / 2)),
    (x / (2 * pi) + Rational(1, 2), Q.ge(x, -pi / 2) & Q.le(x, pi / 2)),
    (x / (2 * pi), Q.positive(x) & Q.real(x) & Q.le(x, pi)),
    (x / pi + Rational(1, 2), Q.ge(x, 0) & Q.le(x, 1)),
    (x / pi + Rational(1, 2), Q.gt(x, pi / 2) & Q.lt(x, 3 * pi / 2)),
    (x / pi + Rational(1, 2), Q.gt(x, -pi / 2) & Q.lt(x, pi / 2)),
    (x / pi + Rational(1, 2), Q.positive(x) & Q.real(x) & Q.gt(x, -pi / 2) & Q.lt(x, pi / 2)),
    (x / pi + Rational(1, 2), Q.real(x) & Q.gt(x, -pi / 2) & Q.lt(x, pi / 2)),
    (-(x - pi / 2) / (2 * pi) + Rational(1, 2), Q.real(x) & Q.ge(x, 0) & Q.le(x, pi)),
    (x / pi, Q.gt(x, 0) & Q.lt(x, pi)),
    (-x / pi, Q.negative(x) & Q.real(x) & Q.ge(x, -pi / 2) & Q.le(x, pi / 2)),
    (x / pi, Q.nonnegative(x) & Q.positive(x) & Q.le(x, pi / 2)),
    (x / pi, Q.nonzero(x) & Q.positive(x) & Q.real(x) & Q.ge(x, -pi / 2) & Q.le(x, pi / 2)),
    (x / pi, Q.positive(x) & Q.real(x) & Q.ge(x, -pi / 2) & Q.le(x, pi / 2)),
    (x / pi, Q.positive(x) & Q.real(x) & Q.gt(x, -pi / 2) & Q.lt(x, pi / 2)),
    (x / pi, Q.positive(x) & Q.real(x) & Q.le(x, pi / 2)),
]


@pytest.mark.parametrize("u,assum", REFINE_INTEGRALITY, ids=str)
def test_refine_integrality_queries_are_refuted(u, assum):
    assert _ask(Q.integer(u), assum) is False


@pytest.mark.parametrize("prop,assum,expected", [
    (Q.integer(x / pi), Q.eq(x, 2 * pi), True),                 # pinned to 2
    (Q.integer(x / pi), Q.gt(x, 0) & Q.lt(x, 4), None),         # x = pi gives 1
    (Q.integer(x / pi + Rational(1, 2)), Q.ge(x, -pi / 2) & Q.le(x, pi / 2), None),  # ends: 0, 1
    (Q.lt(xr, 1), Q.lt(pi * xr, 3), True),                     # xr < 3/pi = 0.95...
    (Q.lt(xr, 1), Q.le(pi * xr, 3), True),
    (Q.lt(xr, Rational(95, 100)), Q.lt(pi * xr, 3), None),
    (Q.lt(xr / pi, 1), Q.lt(xr, pi), True),
    (Q.le(xr / pi, 1), Q.le(xr, pi), True),
    (Q.lt(xr / pi, 1), Q.le(xr, pi), None),                    # xr = pi
    (Q.lt(sqrt(2) * xr, 3), Q.lt(xr, sqrt(2)), True),
    # needs sqrt(2)**2 == 2, which the field does not know: the LRA gives up
    (Q.lt(sqrt(2) * xr, 2), Q.lt(xr, sqrt(2)), None),
    (Q.gt(sE * xr + pi * yr, 0), Q.gt(xr, 0) & Q.gt(yr, 0), True),
    (Q.lt(xr, yr), Q.lt(pi * xr, pi * yr), True),
], ids=str)
def test_end_to_end_answers(prop, assum, expected):
    assert _ask(prop, assum) == expected


@pytest.mark.skipif(not __import__("satassume.theories.lra.lra_adapter").theories.lra.lra_adapter.GENERIC_CONSTANTS,
                    reason="general constants are bounded terms")
def test_general_constants_are_numbers():
    from sympy import log, sin
    from satassume.theories.lra import lra_adapter as ad
    assert ad.terms(Q.lt(x, log(2))) == [x] and ad.terms(Q.lt(log(2) * x, 1)) == [x]
    assert _ask(Q.lt(xr, 2), Q.le(log(2) * xr, 1)) is True           # xr <= 1.44...
    assert _ask(Q.lt(xr, Rational(144, 100)), Q.le(log(2) * xr, 1)) is None
    assert _ask(Q.integer(xr / sin(1)), Q.gt(xr, 0) & Q.lt(xr, sin(1))) is False
    # exact ties beyond the old 128-bit bounds
    near = Rational(int(sympy.log(2).evalf(80) * 10 ** 60), 10 ** 60)
    assert _ask(Q.lt(near, log(2))) is True


def test_inconsistent_with_constant_coefficients():
    assert _ask(Q.positive(xr), Q.gt(pi * xr, 4) & Q.lt(xr, 1)) == "inconsistent"
    assert _ask(Q.positive(xr), Q.gt(pi * xr, 3) & Q.lt(xr, 1)) is True


def test_hidden_algebraic_equality_gives_up_but_other_theories_answer():
    # x = (1 + sqrt(2))**2 and x = 3 + 2*sqrt(2): equal values, LRA cannot
    # tell (it gives up); EUF still merges f's arguments through x
    f = sympy.Function("f")
    a = Q.eq(x, (1 + sqrt(2)) ** 2) & Q.eq(x, 3 + 2 * sqrt(2)) & Q.positive(f(3 + 2 * sqrt(2)))
    eng = Engine(cache=DictCache())
    assert ask(Q.positive(f((1 + sqrt(2)) ** 2)), a, eng) is True
    # the session whose LRA gave up is rebuilt for the next query
    ask(Q.real(x), a, eng)
    assert eng.stats["theory_gave_up"] >= 1


def test_random_relations_with_pi_against_the_oracle():
    rng = random.Random(5)
    cs = [Rational(1), Rational(-2), Rational(1, 3), pi, -pi, 1 / pi, pi / 2 + 1, sE]
    ops = {"lt": ("<", Q.lt), "le": ("<=", Q.le), "gt": (">", Q.gt), "ge": (">=", Q.ge)}
    decided = 0
    for _ in range(80):
        atoms, cons = [], []
        for _ in range(rng.randint(1, 3)):
            a, b, r = rng.choice(cs), rng.choice(cs), rng.choice(cs)
            name = rng.choice(list(ops))
            op, pred = ops[name]
            atoms.append(pred(a * xr + b * yr, r))
            cons.append(({"x": cf.from_sympy(a), "y": cf.from_sympy(b)}, op, cf.from_sympy(r)))
        a, b, r = rng.choice(cs), rng.choice(cs), rng.choice(cs)
        name = rng.choice(list(ops))
        op, pred = ops[name]
        q = pred(a * xr + b * yr, r)
        qc = ({"x": cf.from_sympy(a), "y": cf.from_sympy(b)}, op, cf.from_sympy(r))
        neg = {"<": ">=", "<=": ">", ">": "<=", ">=": "<"}[op]
        got = _ask(q, sympy.And(*atoms))
        feasible = fm_feasible(cons)
        if not feasible:
            assert got == "inconsistent", (atoms, q)
            continue
        can_true = fm_feasible(cons + [qc])
        can_false = fm_feasible(cons + [(qc[0], neg, qc[2])])
        if got is True:
            assert not can_false, (atoms, q)
        elif got is False:
            assert not can_true, (atoms, q)
        else:
            assert got is None
        decided += got is not None
    assert decided > 15


def test_rounding_an_exact_integer_element():
    # r = 4**(1/2) is exactly 2 with exact enclosures: 1 < x < r has no
    # integer; the rounding may see (1, 2] (floor(r) without the delta),
    # which is wider, so no conflict is claimed wrongly, and 1 < x <= r
    # with x = 2 stays possible
    r = cf.radical(4, 2)
    for op, integer_possible in (("<", False), ("<=", True)):
        t = lra.LRATheory()
        t.register_atom(1, lra.constraint({"x": 1}, ">", 1))
        t.register_atom(2, lra.constraint({"x": 1}, op, r))
        t.register_atom(3, lra.Integral((("x", F(1)),), 0))
        assert t.assert_lit(1) is None and t.assert_lit(2) is None
        res = t.assert_lit(3)
        if integer_possible:
            assert res is None
            res = t.check()
            assert res is None or res[0] is True
        else:
            assert res is None or res[0] is False


# an integrality atom whose offset is an integer-valued Element (its floor
# is undecidable): the offset is kept unreduced instead of giving up at
# registration, which silenced the theory for every query (PR #48 review)
_log8 = sympy.log(8) / sympy.log(2)                        # 3, not formally
_sq = -2 * sqrt(2) + (1 + sqrt(2)) ** 2                    # 3, not formally


@pytest.mark.parametrize("offset", [_log8, _sq], ids=["log8/log2", "sqrt2"])
def test_integer_valued_offset_does_not_silence_the_theory(offset):
    from satassume.engine import _gave_up
    from satassume.sympy_api import _formula
    y = symbols("y")
    a = Q.integer(x + offset) & Q.gt(x, 1) & Q.gt(y, x + 1)
    eng = Engine(cache=DictCache())
    # the property: the theory is not silenced at registration, so the
    # set's complete check runs it and the bounds decide the query
    s, _ = eng._build_context(_formula(a, True, True))
    assert not _gave_up(s)
    assert ask(Q.gt(y, 2), a, eng) is True
    assert ask(Q.gt(y, 2), a, Engine(cache=DictCache())) is True
    # (``stats["theory_gave_up"] == 0`` was asserted here; on main the
    # counter was fed only when a kept session was reused by the next
    # query, so a single query left it 0 whatever the theory did.  The
    # branch and bound does give up on this query's integrality atom after
    # the bounds have decided it, on main as well; since #97 P1 the counter
    # counts that at the query, so the assertion would read 1.)


@pytest.mark.parametrize("offset", [_log8, _sq], ids=["log8/log2", "sqrt2"])
def test_undecidable_integral_offset_never_answers_wrongly(offset):
    # x + 3 in Z with 1 < x < 2 is impossible, x + 3 in Z with x = 2 holds:
    # the theory cannot round the offset, so it may not know, but it must
    # never claim the opposite
    assert _ask(Q.integer(x + offset), Q.gt(x, 1) & Q.lt(x, 2)) in (False, None)
    assert _ask(Q.integer(x + offset), Q.eq(x, 2)) in (True, None)
    assert _ask(Q.integer(x), Q.integer(x + offset)) in (True, None)
    assert _ask(Q.gt(x, 1), Q.integer(x + offset) & Q.gt(x, 1) & Q.lt(x, 2)) \
        in (True, "inconsistent", None)
    t = lra.LRATheory()
    t.register_atom(1, lra.constraint({"x": 1}, ">", 1))
    t.register_atom(2, lra.constraint({"x": 1}, "<", 2))
    t.register_atom(3, lra.Integral((("x", F(1)),), cf.from_sympy(offset)))
    assert not t.gave_up                                   # registered
    for lit in (1, 2, 3):
        r = t.assert_lit(lit)
        assert r is None or r[0] is False
    r = t.check()
    assert r is None or r[0] is False
    t2 = lra.LRATheory()
    t2.register_atom(1, lra.constraint({"x": 1}, "==", 2))
    t2.register_atom(2, lra.Integral((("x", F(1)),), cf.from_sympy(offset)))
    assert t2.assert_lit(1) is None
    assert all(l != -2 for l, _ in t2.propagate())         # never refuted
    assert t2.assert_lit(2) is None
    r = t2.check()
    assert r is None or r[0] is True
