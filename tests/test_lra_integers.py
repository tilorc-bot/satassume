"""Integrality in the LRA theory (``satassume.lra``, "Integrality") and its
link to ``Q.integer`` (``satassume.relations``, "Integrality").

Three layers:

1. unit tests of :class:`satassume.lra.LRATheory` with ``Integral`` atoms
   (rounded bounds, propagation, branch and bound, levels, the budget);
2. a random fuzz of the theory against an exact oracle: every term is boxed,
   so an integrality atom's form has finitely many integer values, and the
   oracle is Fourier-Motzkin (``tests/test_lra.py``) over each choice of
   them.  Every conflict and every propagation reason must be valid for
   the oracle, and with an unlimited budget every infeasible set must give
   a conflict;
3. ``ask`` against models: queries over ``x`` and ``y`` with integer, even,
   odd and order atoms, every definite answer checked at every point of a
   grid of rationals and ``oo``/``-oo`` that satisfies the assumptions.
"""
from __future__ import annotations

import itertools
import random
from fractions import Fraction as F

import pytest

from satassume import lra
from satassume.lra import Integral, LRATheory, constraint

from test_lra import fm_feasible  # noqa: E402

# ----------------------------------------------------------------------
# 1. the theory
# ----------------------------------------------------------------------


def _theory(atoms):
    """A theory with ``atoms`` ({literal: payload}) registered."""
    t = LRATheory()
    for v, p in atoms.items():
        t.register_atom(v, p)
    return t


def _assert(t, lits):
    """Assert ``lits`` in order; the first conflict clause, or None."""
    for l in lits:
        r = t.assert_lit(l)
        if r is not None:
            return r[1]
    return None


@pytest.mark.parametrize("lo, up, m, k, conflict", [
    # m*x + k in Z for x between lo and up ((value, strict))
    ((0, True), (1, True), 1, 0, True),         # 0 < x < 1
    ((0, False), (1, True), 1, 0, False),       # 0 <= x < 1: x = 0
    ((0, True), (1, False), 1, 0, False),       # x = 1
    ((F(1, 3), False), (F(2, 3), False), 1, 0, True),
    ((0, False), (F(1, 4), False), 1, F(1, 2), True),     # x + 1/2
    ((0, False), (F(1, 2), False), 1, F(1, 2), False),    # x = 1/2
    ((0, True), (F(1, 2), True), 2, 0, True),             # 2*x
    ((0, True), (F(1, 2), False), 2, 0, False),           # x = 1/2
    ((0, True), (F(1, 2), True), -2, 0, True),            # -2*x
    ((F(-1, 2), True), (0, True), -2, 0, True),
    ((F(-1, 2), False), (0, True), -2, 0, False),         # x = -1/2
    ((F(1, 3), True), (F(2, 3), True), 3, 0, True),
    ((F(1, 3), False), (F(2, 3), True), 3, 0, False),     # x = 1/3
    ((F(1, 3), True), (F(2, 3), False), -3, 1, False),    # x = 2/3: -1
    ((F(1, 3), True), (F(2, 3), True), -3, 1, True),
])
def test_rounded_bounds(lo, up, m, k, conflict):
    atoms = {1: constraint({"x": 1}, ">" if lo[1] else ">=", lo[0]),
             2: constraint({"x": 1}, "<" if up[1] else "<=", up[0]),
             3: Integral({"x": m}, k)}
    for order in ([1, 2, 3], [3, 1, 2], [1, 3, 2]):
        r = _assert(_theory(atoms), order)
        assert (r is not None) == conflict, order
        if conflict:
            assert sorted(r) == [-3, -2, -1]
    # propagation instead of a conflict: the atom is implied false
    t = _theory(atoms)
    _assert(t, [1, 2])
    props = dict(t.propagate())
    if conflict:
        assert props[-3] == [-3, -1, -2] or sorted(props[-3]) == [-3, -2, -1]
    else:
        assert 3 not in props and -3 not in props


def test_pinned_value_propagates_and_refutes_the_negation():
    atoms = {1: constraint({"x": 1}, ">=", 2), 2: constraint({"x": 1}, "<=", 2),
             3: Integral({"x": 1}), 4: Integral({"x": 2}, F(1, 2))}
    t = _theory(atoms)
    _assert(t, [1, 2])
    props = dict(t.propagate())
    assert sorted(props[3]) == [-2, -1, 3]
    assert sorted(props[-4]) == [-4, -2, -1]
    assert sorted(_assert(_theory(atoms), [1, 2, -3])) == [-2, -1, 3]
    assert _assert(_theory(atoms), [1, 2, 4]) is not None


def test_slack_of_a_two_term_form():
    """x - y in Z under y < x < y + 1: bounds on one slack."""
    atoms = {1: constraint({"x": 1, "y": -1}, ">", 0),
             2: constraint({"x": 1, "y": -1}, "<", 1),
             3: Integral({"x": 1, "y": -1})}
    assert sorted(_assert(_theory(atoms), [1, 2, 3])) == [-3, -2, -1]
    # the same slack under a scaled, negated spelling: 2*y - 2*x
    atoms[3] = Integral({"y": 2, "x": -2})
    assert _assert(_theory(atoms), [1, 2, 3]) is None      # 2*(x - y) = 1
    atoms[3] = Integral({"y": 1, "x": -1}, F(1, 2))
    assert _assert(_theory(atoms), [1, 2, 3]) is None      # x - y = 1/2


def test_branch_and_bound_through_the_tableau():
    """x in Z, x > 0, y >= 0, x + y < 1: no bound of x alone is crossed."""
    atoms = {1: constraint({"x": 1}, ">", 0), 2: constraint({"y": 1}, ">=", 0),
             3: constraint({"x": 1, "y": 1}, "<", 1), 4: Integral({"x": 1})}
    t = _theory(atoms)
    assert _assert(t, [1, 2, 3, 4]) is None
    ok, clause = t.check()
    assert ok is False and sorted(clause) == [-4, -3, -2, -1]
    assert t.stats["branches"] == 1
    # without y >= 0 it is satisfiable (x = 1, y < 0)
    t = _theory(atoms)
    assert _assert(t, [1, 3, 4]) is None
    assert t.check()[0] is True


def test_branch_and_bound_for_a_negated_atom():
    """not (x in Z) with x + y = 2, y = 0: x = 2 only via the tableau."""
    atoms = {1: constraint({"x": 1, "y": 1}, "==", 2), 2: constraint({"y": 1}, "==", 0),
             3: Integral({"x": 1})}
    t = _theory(atoms)
    assert _assert(t, [1, 2, -3]) is None
    ok, clause = t.check()
    assert ok is False and sorted(clause) == [-2, -1, 3]
    t = _theory(atoms)
    assert _assert(t, [1, -3]) is None
    assert t.check()[0] is True


def test_two_integral_forms():
    """2*x in Z and x in Z, 1/4 < x < 3/4: 2*x = 1, x = 1/2."""
    atoms = {1: constraint({"x": 1}, ">", F(1, 4)), 2: constraint({"x": 1}, "<", F(3, 4)),
             3: Integral({"x": 2}), 4: Integral({"x": 1})}
    t = _theory(atoms)
    assert sorted(_assert(t, [1, 2, 4])) == [-4, -2, -1]
    t = _theory(atoms)
    assert _assert(t, [1, 2, 3, -4]) is None
    assert t.check()[0] is True


def test_levels_restore_integrality():
    atoms = {1: constraint({"x": 1}, ">", 0), 2: constraint({"x": 1}, "<", 1),
             3: Integral({"x": 1})}
    t = _theory(atoms)
    assert t.assert_lit(1) is None
    t.push_level()
    assert t.assert_lit(3) is None
    t.push_level()
    assert t.assert_lit(2) is not None
    t.pop_level()
    t.pop_level()
    assert t._int_lits == []
    assert t.assert_lit(2) is None
    assert t.check()[0] is True
    t.push_level()
    assert t.assert_lit(3) is not None


def test_ground_integral_atoms():
    t = _theory({1: Integral((), 3), 2: Integral((), F(1, 2)), 3: Integral({"x": 0}, 1)})
    assert sorted(t.propagate()) == [(-2, [-2]), (1, [1]), (3, [3])]
    assert t.assert_lit(2) == (False, [-2])


def test_budget_gives_up_without_a_conflict(monkeypatch):
    """x in Z and x + 1/2 in Z is infeasible, but no bound ends the search."""
    atoms = {1: Integral({"x": 1}), 2: Integral({"x": 1}, F(1, 2))}
    t = _theory(atoms)
    assert _assert(t, [1, 2]) is None
    assert t.check()[0] is True
    assert t.stats["branches"] == lra.BRANCH_BUDGET
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 3)
    t = _theory(atoms)
    _assert(t, [1, 2])
    t.check()
    assert t.stats["branches"] == 3


def _diseq_theory(lo, up, excluded, integral=True):
    """x >= lo (literal 1), x <= up or x < up (2), x != c for each c in
    ``excluded`` (3, 4, ...), x in Z (last literal) if ``integral``;
    ``up`` is ``(value, strict)``.  The theory with all of them asserted
    and the literals."""
    atoms = {1: constraint({"x": 1}, ">=", lo),
             2: constraint({"x": 1}, "<" if up[1] else "<=", up[0])}
    for c in excluded:
        atoms[len(atoms) + 1] = constraint({"x": 1}, "!=", c)
    if integral:
        atoms[len(atoms) + 1] = Integral({"x": 1})
    t = _theory(atoms)
    assert _assert(t, list(atoms)) is None
    return t, list(atoms)


@pytest.mark.parametrize("lo, up, excluded, conflict", [
    (1, (2, True), [1], True),           # 1 <= n < 2, n != 1
    (1, (3, False), [2], False),         # n = 1 or 3
    (0, (1, False), [0, 1], True),       # 0 <= n <= 1, n != 0, n != 1
    (0, (1, False), [1, 0], True),
    (0, (2, False), [0, 1], False),      # n = 2
    (0, (3, True), [2, 0, 1], True),
])
def test_disequalities_with_integrality(lo, up, excluded, conflict):
    """A disequality the integral point lies on splits with the
    integrality atom (a real point off it, 1 < n < 2, is no integer)."""
    t, lits = _diseq_theory(lo, up, excluded)
    ok, r = t.check()
    if conflict:
        assert ok is False and sorted(r) == sorted(-l for l in lits)
    else:
        assert ok is True and all(r["x"] != c for c in excluded)


def test_disequality_without_integrality_does_not_branch():
    """Real x: 1 <= x < 2, x != 1 is satisfiable, without branching."""
    t, _ = _diseq_theory(1, (2, True), [1], integral=False)
    ok, model = t.check()
    assert ok is True and 1 < model["x"] < 2
    assert t.stats["branches"] == 0


def test_disequality_split_shares_the_budget(monkeypatch):
    """Budget exhausted: no conflict (sound, incomplete)."""
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 0)
    t, _ = _diseq_theory(1, (2, True), [1])
    assert t.check()[0] is True
    assert t.stats["branches"] == 0
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 1)        # 0 <= n <= 1 needs 2
    t, _ = _diseq_theory(0, (1, False), [0, 1])
    assert t.check()[0] is True
    assert t.stats["branches"] == 1


def test_check_leaves_the_bounds_alone():
    atoms = {1: constraint({"x": 1}, ">", 0), 2: constraint({"y": 1}, ">=", 0),
             3: constraint({"x": 1, "y": 1}, "<", 3), 4: Integral({"x": 2}, F(1, 3))}
    t = _theory(atoms)
    _assert(t, [1, 2, 3, 4])
    before = (list(t._lo), list(t._up), list(t._lo_r), list(t._up_r), len(t._trail))
    assert t.check()[0] is True
    assert (list(t._lo), list(t._up), list(t._lo_r), list(t._up_r), len(t._trail)) == before


# ----------------------------------------------------------------------
# 2. fuzz against an exact oracle
# ----------------------------------------------------------------------

_OUTER = 4                                # every term in [-4, 4] for the oracle
_TERMS = ["x", "y", "z"]


def _oracle(cons, ints):
    """Feasibility of the linear constraints ``cons`` (oracle format of
    ``tests/test_lra.py``) and the integrality literals ``ints``
    ``(coeffs, offset, positive)`` inside the outer box (every term in
    ``[-_OUTER, _OUTER]``).  The form of a positive atom takes one of its
    finitely many integer values there, a negated one lies strictly
    between two integers."""
    cons = cons + [({t: 1}, op, s * _OUTER) for t in _TERMS
                   for op, s in ((">=", -1), ("<=", 1))]
    choices = []
    for coeffs, k, positive in ints:
        span = sum(abs(c) for c in coeffs.values()) * _OUTER
        lo, hi = (-span + k).__floor__() - 1, (span + k).__ceil__() + 1
        if positive:
            choices.append([[(coeffs, "==", n - k)] for n in range(lo, hi + 1)])
        else:
            choices.append([[(coeffs, ">", n - k), (coeffs, "<", n + 1 - k)]
                            for n in range(lo, hi + 1)])
    for pick in itertools.product(*choices):
        if fm_feasible(cons + [c for cs in pick for c in cs]):
            return True
    return False


def _rand_coeffs(rng, n):
    ts = rng.sample(_TERMS, n)
    return {t: F(rng.choice([-2, -1, 1, 1, 2]), rng.choice([1, 1, 2])) for t in ts}


def _instance(rng):
    """``(atoms, lits, meaning)``: registered payloads, the literals to
    assert, and per variable its oracle reading ``("lin", con)`` or
    ``("int", coeffs, k)``.  Every term gets asserted bounds inside
    ``[-2, 2]`` (narrow, so that integrality matters), so that the theory can decide the instance; the outer box
    of the oracle is looser, so a clause that leaves out a bound it needs
    is caught (mostly)."""
    atoms, meaning, lits = {}, {}, []
    v = 0

    def add(p, m, lit_sign=1):
        nonlocal v
        v += 1
        atoms[v] = p
        meaning[v] = m
        lits.append(lit_sign * v)
    for t in _TERMS:
        lo = rng.choice([-2, -1, F(-1, 2), 0, F(1, 3)])
        up = min(lo + rng.choice([F(1, 3), F(1, 2), 1, F(3, 2), 3]), 2)
        for op, b in ((rng.choice([">", ">="]), lo), (rng.choice(["<", "<="]), up)):
            add(constraint({t: 1}, op, b), ("lin", ({t: 1}, op, b)))
    for _ in range(rng.randint(0, 2)):
        coeffs = _rand_coeffs(rng, rng.randint(1, 2))
        op = rng.choice(["<", "<=", ">", ">=", "==", "!="])
        rhs = F(rng.randint(-4, 4), rng.choice([1, 2, 3]))
        add(constraint(coeffs, op, rhs), ("lin", (coeffs, op, rhs)))
    for _ in range(rng.randint(1, 2)):
        coeffs = _rand_coeffs(rng, rng.randint(1, 2))
        k = rng.choice([F(0), F(0), F(1, 2), F(1, 3), F(-2, 3)])
        add(Integral(coeffs, k), ("int", coeffs, k), rng.choice([1, 1, -1]))
    rng.shuffle(lits)
    return atoms, lits, meaning


def _feasible(lits, meaning):
    cons, ints = [], []
    for l in lits:
        m = meaning[abs(l)]
        if m[0] == "lin":
            coeffs, op, rhs = m[1]
            if l < 0:
                op = {"<": ">=", "<=": ">", ">": "<=", ">=": "<", "==": "!=",
                      "!=": "=="}[op]
            cons.append((coeffs, op, rhs))
        else:
            ints.append((m[1], m[2], l > 0))
    return _oracle(cons, ints)


def _valid(clause, meaning):
    """A theory clause is valid iff the negations of its literals are
    jointly infeasible (checked inside the outer box)."""
    return not _feasible([-l for l in clause], meaning)


@pytest.mark.parametrize("seed", range(600))
def test_fuzz_against_the_oracle(seed, monkeypatch):
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 10_000)     # complete on boxes
    rng = random.Random(seed)
    atoms, lits, meaning = _instance(rng)
    t = _theory(atoms)
    conflict = None
    for i, l in enumerate(lits):
        if i == len(lits) // 2:
            t.push_level()
        r = t.assert_lit(l)
        if r is not None:
            conflict = r[1]
            break
        for lit, reason in t.propagate():
            assert lit in reason
            assert _valid(reason, meaning), ("reason", lit, reason)
    if conflict is None:
        r = t.check()
        if r[0] is False:
            conflict = r[1]
    feasible = _feasible(lits, meaning)
    if conflict is not None:
        assert set(conflict) <= {-l for l in lits}, conflict
        assert _valid(conflict, meaning), ("conflict", conflict)
    assert feasible == (conflict is None), (lits, conflict)


@pytest.mark.parametrize("seed", range(150))
def test_solver_with_integrality_against_the_oracle(seed, monkeypatch):
    """A CDCL solver over random clauses on linear and integrality atoms,
    solved several times under random assumptions (levels pushed and
    popped, learnt theory clauses kept): each answer against the oracle
    over all assignments of the atoms."""
    from satassume.solver import Solver
    monkeypatch.setattr(lra, "BRANCH_BUDGET", 10_000)
    rng = random.Random(seed)
    atoms, lits, meaning = _instance(rng)
    box = list(range(1, 2 * len(_TERMS) + 1))         # the bounds of the terms
    free = [v for v in atoms if v not in box]
    s = Solver()
    t = LRATheory()
    s.attach_theory(t)
    s.ensure_vars(len(atoms))
    for v, p in atoms.items():
        s.register_atom(t, v, p)
    clauses = [[l] for l in box]
    for _ in range(rng.randint(0, 3)):
        clauses.append([rng.choice([1, -1]) * v
                        for v in rng.sample(free, min(len(free), rng.randint(1, 3)))])
    for c in clauses:
        s.add_clause(c)
    models = []
    for signs in itertools.product((1, -1), repeat=len(free)):
        assign = set(box) | {sg * v for sg, v in zip(signs, free)}
        if all(any(l in assign for l in c) for c in clauses) \
                and _feasible(sorted(assign), meaning):
            models.append(assign)
    for _ in range(4):
        assumptions = [rng.choice([1, -1]) * v
                       for v in rng.sample(free, rng.randint(0, min(2, len(free))))]
        expected = any(all(a in m for a in assumptions) for m in models)
        assert s.solve(assumptions) is expected, (assumptions, clauses)


# ----------------------------------------------------------------------
# 3. ask against models
# ----------------------------------------------------------------------

sympy = pytest.importorskip("sympy")
from hypothesis import HealthCheck, given, settings, strategies as st  # noqa: E402
from sympy import Q, Rational, S, oo, symbols                           # noqa: E402
from sympy.logic.boolalg import And                                     # noqa: E402

from satassume import DictCache, Engine                                 # noqa: E402
from satassume.sympy_api import ask                                     # noqa: E402

x, y = symbols("x y")
h = Rational(1, 2)


def _ask(prop, assum):
    try:
        return ask(prop, assum, Engine(cache=DictCache()))
    except ValueError:
        return "inconsistent"


@pytest.mark.parametrize("prop, assum, expected", [
    (Q.integer(x), Q.gt(x, 0) & Q.lt(x, 1), False),
    (Q.integer(x + h), Q.ge(x, 0) & Q.le(x, Rational(1, 4)), False),
    (Q.integer(2 * x), Q.gt(x, 0) & Q.lt(x, h), False),
    (Q.integer(x - y), Q.gt(x, y) & Q.lt(x, y + 1), False),
    (Q.even(x), Q.gt(x, 0) & Q.lt(x, 1), False),
    (Q.odd(x), Q.gt(x, 0) & Q.lt(x, 1), False),
    (Q.integer(x), Q.ge(x, 2) & Q.le(x, 2), True),
    (Q.integer(x), Q.integer(2 * x) & Q.gt(x, Rational(3, 4)) & Q.lt(x, Rational(5, 4)), True),
    (Q.integer(x), Q.integer(2 * x) & Q.gt(x, Rational(1, 4)) & Q.lt(x, Rational(3, 4)), False),
    (Q.ge(x, 1), Q.integer(x) & Q.gt(x, 0), True),
    (Q.le(x, 0), Q.integer(x) & Q.lt(x, 1), True),
    (Q.gt(x, 0), Q.integer(x) & Q.gt(x, -1), None),               # x = 0
    (Q.integer(x), Q.gt(x, 0) & Q.le(x, 1), None),                # x = 1
    (Q.integer(x), Q.gt(x, 0) & Q.lt(x, 2), None),
    (Q.integer(x), Q.gt(x, 0), None),
    (Q.integer(x / S.Pi), Q.gt(x, 0) & Q.lt(x, 1), False),        # 0 < x/pi < 1/pi (exact coefficient)
    (Q.integer(x), Q.gt(x, 0) & Q.lt(x, S.Pi - 3), False),        # pi's bounds
    (Q.integer(x), Q.gt(x, 0) & Q.lt(x, 1) & Q.integer(y), False),
    (Q.positive(x), Q.integer(x) & Q.gt(x, 0) & Q.lt(x, 1), "inconsistent"),
    (Q.integer(x + y), Q.gt(x, 0) & Q.gt(y, 0) & Q.lt(x + y, 1), False),
    (Q.eq(x, 1), Q.integer(x) & Q.ge(x, 1) & Q.lt(x, 2), True),
    (Q.eq(x, 1), Q.ge(x, 1) & Q.lt(x, 2), None),                  # real x
    (Q.eq(x, 2), Q.integer(x) & Q.ge(x, 1) & Q.le(x, 3), None),
    (Q.eq(x, 1), Q.integer(x) & Q.ge(x, 0) & Q.le(x, 1) & Q.ne(x, 0), True),
])
def test_answers(prop, assum, expected):
    assert _ask(prop, assum) == expected


_VALUES = [-oo, S(-1), -h, S(0), Rational(1, 3), h, S(1), Rational(3, 2), S(2), oo]
_EXPRS = [x, y, 2 * x, x + h, x - y, x + y, 2 * x - y, -x + 1]
_UNARY = ["integer", "even", "odd", "noninteger", "positive", "zero"]
_CONSTS = [S(0), h, S(1), S(2), Rational(-1, 3)]


def _unary(pred, v):
    """SymPy's meaning of the unary predicate at the value ``v`` (a nan
    value, ``oo - oo``, satisfies none)."""
    if v is S.NaN:
        return False
    return {"integer": v.is_integer, "even": v.is_even, "odd": v.is_odd,
            "noninteger": v.is_extended_real and not v.is_integer,
            "positive": v.is_positive, "zero": v.is_zero}[pred] is True


def _rel(op, a, b):
    if op in ("eq", "ne"):
        return (a == b) == (op == "eq")
    for v in (a, b):
        if v is S.NaN or v.is_extended_real is not True:
            return False
    return bool({"lt": a < b, "le": a <= b, "gt": a > b, "ge": a >= b}[op])


def _holds(t, env):
    if t[0] == "not":
        return not _holds(t[1], env)
    if t[0] == "u":
        return _unary(t[1], t[2].subs(env))
    return _rel(t[1], S(t[2]).subs(env), S(t[3]).subs(env))


def _to_sympy(t):
    if t[0] == "not":
        return ~_to_sympy(t[1])
    if t[0] == "u":
        return getattr(Q, t[1])(t[2])
    return getattr(Q, t[1])(t[2], t[3])


@st.composite
def _atom(draw):
    if draw(st.booleans()):
        a = ("u", draw(st.sampled_from(_UNARY)), draw(st.sampled_from(_EXPRS)))
    else:
        e = draw(st.sampled_from(_EXPRS))
        if draw(st.integers(0, 3)) == 0:
            b = draw(st.sampled_from(_EXPRS))
        else:
            b = draw(st.sampled_from(_CONSTS))
        a = ("r", draw(st.sampled_from(["lt", "le", "gt", "ge", "eq", "ne"])), e, b)
    return ("not", a) if draw(st.integers(0, 4)) == 0 else a


def _check(prop_t, assum_ts):
    prop = _to_sympy(prop_t)
    assum = And(*[_to_sympy(t) for t in assum_ts])
    if prop in (S.true, S.false) or assum in (S.true, S.false):
        return
    got = _ask(prop, assum)
    for vals in itertools.product(_VALUES, repeat=2):
        env = {x: vals[0], y: vals[1]}
        if not all(_holds(t, env) for t in assum_ts):
            continue
        assert got != "inconsistent", (prop, assum, env)
        if got is not None:
            assert _holds(prop_t, env) is got, (prop, assum, env, got)


@settings(max_examples=400, deadline=None, derandomize=True,
          suppress_health_check=list(HealthCheck))
@given(_atom(), st.lists(_atom(), min_size=1, max_size=3))
def test_ask_against_models(prop_t, assum_ts):
    _check(prop_t, assum_ts)


def test_every_integer_query_under_one_interval():
    """Each unary integer predicate of each expression under every pair of
    bounds on ``x`` (strict or not) from a small set of constants."""
    bounds = [S(0), Rational(1, 4), h, S(1), Rational(3, 2)]
    for (lo, up) in itertools.combinations(bounds, 2):
        for lop, uop in itertools.product(("gt", "ge"), ("lt", "le")):
            assum = [("r", lop, x, lo), ("r", uop, x, up)]
            for e in (x, 2 * x, x + h, -x + 1):
                for pred in ("integer", "even", "odd", "noninteger"):
                    _check(("u", pred, e), assum)
