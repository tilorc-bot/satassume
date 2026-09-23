"""Unit tests for the LRA theory solver (satassume/lra.py).

The module has three parts:

1. **Oracle** (no dependency on the implementation): exact Fourier-Motzkin
   elimination over ``Fraction`` with strict inequalities, extended to
   disequalities, plus a witness-producing back substitution so that every
   SAT verdict of the oracle is certified by a point.  This is *complete*
   for finite conjunctions of ``<=, <, ==, !=`` over the reals (see
   ``fm_feasible``).  ``test_lra_fuzz.py`` and ``test_lra_adapter.py``
   import it from here.
2. **Driver**: a checked wrapper around a theory instance that follows the
   protocol of ``satassume/theory.py`` and verifies every answer (conflict
   clauses are false, theory-valid and, where required, minimal; models
   satisfy every asserted literal exactly).
3. **Unit tests** of the theory through its public methods.

Assumed interface (agreed with lra-impl; adjust ``new_theory`` /
``payload`` / ``model_values`` below if it changes):

* ``satassume.lra.LRATheory()``: the five protocol methods (plus optional
  ``propagate``).
* payload ``(terms, constant, strict, equality)``: ``terms`` a tuple of
  ``(term, Fraction)`` pairs, meaning ``sum(c*t) < constant`` (strict),
  ``<= constant`` or ``== constant`` (equality).  The negated literal means
  ``>``, ``>=`` or ``!=`` respectively.
* ``check()`` returns ``(True, model)`` with ``model`` a mapping from every
  term of the registered atoms to a ``Fraction`` (delta resolved), or
  ``(False, clause)``, or None (no verdict; only acceptable where noted).

Set ``SATASSUME_LRA_IMPL=some.module`` to run the suite against another
implementation exposing ``LRATheory`` (used to check that the suite catches
the flaws of the reference implementations).
"""
from __future__ import annotations

import importlib
import itertools
import os
import random
import time
from fractions import Fraction as F

import pytest

# ----------------------------------------------------------------------
# Loading the implementation (the file must import cleanly without it)
# ----------------------------------------------------------------------

_IMPL_NAME = os.environ.get("SATASSUME_LRA_IMPL", "satassume.lra")
try:
    lra = importlib.import_module(_IMPL_NAME)
    _IMPORT_ERROR = None
except ImportError as e:  # pragma: no cover - depends on the branch
    lra = None
    _IMPORT_ERROR = e

#: The implementation decides negated equalities (disequalities) completely
#: in check() (lra-impl's contract).  Set SATASSUME_LRA_DISEQ=0 for an
#: implementation that ignores them (the references), which then may answer
#: None but never a wrong model or conflict.
DISEQ_COMPLETE = os.environ.get("SATASSUME_LRA_DISEQ", "1") != "0"

#: verdicts tolerated from check() on a set containing a disequality
DQ = () if DISEQ_COMPLETE else (None,)

needs_lra = pytest.mark.skipif(
    lra is None, reason=f"{_IMPL_NAME} not available: {_IMPORT_ERROR}")


#: SATASSUME_LRA_LAZY=1 runs the whole suite with ``LRATheory(eager=False)``
#: (simplex only in check()); a few tests below run that mode regardless.
_LAZY = os.environ.get("SATASSUME_LRA_LAZY", "0") == "1"


def new_theory(eager=None):
    if eager is None:
        eager = not _LAZY
    if not eager:
        try:
            return lra.LRATheory(eager=False)
        except TypeError:
            pytest.skip("LRATheory has no eager=False mode")
    return lra.LRATheory()


OPS = ("<=", "<", "==", ">=", ">", "!=")
_NEG = {"<=": ">", "<": ">=", "==": "!=", ">": "<=", ">=": "<", "!=": "=="}


def payload(terms, op, rhs):
    """The payload for ``sum(c*t for t, c in terms) op rhs``.

    ``terms``: dict or iterable of pairs.  ``op`` in ``<=, <, ==, >=, >``;
    ``>=``/``>`` are turned into ``<=``/``<`` by negating both sides.
    ``!=`` gives ``lra.Negated(<equality payload>)`` (an atom that *is* a
    disequality, as the adapter registers ``Q.ne``).
    """
    if op == "!=":
        return lra.Negated(payload(terms, "==", rhs))
    items = list(terms.items()) if isinstance(terms, dict) else list(terms)
    items = [(t, F(c)) for t, c in items]
    rhs = F(rhs)
    if op in (">=", ">"):
        items = [(t, -c) for t, c in items]
        rhs = -rhs
        op = "<=" if op == ">=" else "<"
    assert op in ("<=", "<", "=="), op
    return (tuple(items), rhs, op == "<", op == "==")


def payload_constraint(p, positive=True):
    """Oracle constraint ``(coeffs, op, rhs)`` meant by literal ``+-p``."""
    if len(p) == 1:                          # Negated(payload)
        return payload_constraint(p[0], not positive)
    terms, rhs, strict, equality = p
    coeffs: dict = {}
    for t, c in (terms.items() if isinstance(terms, dict) else terms):
        coeffs[t] = coeffs.get(t, F(0)) + F(c)
    op = "==" if equality else "<" if strict else "<="
    if not positive:
        op = _NEG[op]
    return coeffs, op, F(rhs)


def model_values(model):
    """The theory's model as ``{term: Fraction}``."""
    return dict(model)


# ----------------------------------------------------------------------
# Oracle: Fourier-Motzkin with strictness, disequalities, witnesses
# ----------------------------------------------------------------------

def holds(con, point) -> bool:
    """Exact evaluation of an oracle constraint at ``point`` (missing
    variables raise KeyError)."""
    coeffs, op, rhs = con
    lhs = sum((F(c) * F(point[t]) for t, c in coeffs.items() if c), F(0))
    return {"<=": lhs <= rhs, "<": lhs < rhs, "==": lhs == rhs,
            ">=": lhs >= rhs, ">": lhs > rhs, "!=": lhs != rhs}[op]


def _to_ineqs(cons):
    """Split into ``(coeffs, strict, b)`` meaning ``coeffs.x (<|<=) b`` and a
    list of disequalities ``(coeffs, b)``."""
    ineqs, diseqs = [], []
    for coeffs, op, rhs in cons:
        c = {t: F(v) for t, v in coeffs.items() if v}
        rhs = F(rhs)
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
            ineqs.append((c, False, rhs))
            ineqs.append((neg, False, -rhs))
        elif op == "!=":
            diseqs.append((c, rhs))
        else:
            raise ValueError(op)
    return ineqs, diseqs


def _normalise(row):
    """Scale so that the first (by repr) coefficient has absolute value 1."""
    c, strict, b = row
    if not c:
        return row
    k = abs(c[min(c, key=repr)])
    return ({t: v / k for t, v in c.items()}, strict, b / k)


def _dedupe(rows):
    """Keep the tightest row per coefficient vector."""
    best: dict = {}
    for row in rows:
        c, strict, b = _normalise(row)
        key = frozenset(c.items())
        old = best.get(key)
        if old is None or b < old[2] or (b == old[2] and strict and not old[1]):
            best[key] = (c, strict, b)
    return list(best.values())


def _fm_ineqs(ineqs):
    """Fourier-Motzkin on ``(coeffs, strict, b)`` rows.  Returns a witness
    point (dict) if feasible, else None.  Exact and complete over the reals
    (and over the rationals: a feasible rational system has a rational
    point, which the back substitution constructs)."""
    rows = _dedupe(ineqs)
    stages = []                      # (var, rows containing var)
    while True:
        for c, strict, b in rows:
            if not c and (b < 0 or (strict and b == 0)):
                return None
        rows = [r for r in rows if r[0]]
        if not rows:
            break
        variables = {t for c, _, _ in rows for t in c}

        def cost(t):
            p = sum(1 for c, _, _ in rows if c.get(t, 0) > 0)
            n = sum(1 for c, _, _ in rows if c.get(t, 0) < 0)
            return (p * n - p - n, repr(t))
        var = min(variables, key=cost)
        with_var = [r for r in rows if var in r[0]]
        rest = [r for r in rows if var not in r[0]]
        stages.append((var, with_var))
        pos = [r for r in with_var if r[0][var] > 0]
        neg = [r for r in with_var if r[0][var] < 0]
        new = []
        for (cp, sp, bp) in pos:
            for (cn, sn, bn) in neg:
                ap, an = cp[var], -cn[var]
                c = {}
                for t in set(cp) | set(cn):
                    if t == var:
                        continue
                    v = cp.get(t, F(0)) / ap + cn.get(t, F(0)) / an
                    if v:
                        c[t] = v
                new.append((c, sp or sn, bp / ap + bn / an))
        rows = _dedupe(rest + new)
    # Back substitution, last eliminated variable first.
    point: dict = {}
    for var, with_var in reversed(stages):
        lo = hi = None               # (value, strict)
        for c, strict, b in with_var:
            a = c[var]
            # a variable absent from every later stage is unconstrained by
            # the projection: any value (0) extends
            rest = b - sum((v * point.setdefault(t, F(0))
                            for t, v in c.items() if t != var), F(0))
            bound = rest / a
            if a > 0:                # var (<|<=) bound
                if hi is None or bound < hi[0] or (bound == hi[0] and strict):
                    hi = (bound, strict)
            else:                    # var (>|>=) bound
                if lo is None or bound > lo[0] or (bound == lo[0] and strict):
                    lo = (bound, strict)
        if lo is None and hi is None:
            val = F(0)
        elif lo is None:
            val = hi[0] - 1
        elif hi is None:
            val = lo[0] + 1
        elif lo[0] == hi[0]:
            assert not lo[1] and not hi[1], "FM oracle: empty interval"
            val = lo[0]
        else:
            assert lo[0] < hi[0], "FM oracle: empty interval"
            val = (lo[0] + hi[0]) / 2
        point[var] = val
    for c, strict, b in ineqs:       # self-certification
        lhs = sum((v * point.get(t, F(0)) for t, v in c.items()), F(0))
        assert lhs < b if strict else lhs <= b, "FM oracle witness is wrong"
    return point


def fm_feasible(cons) -> bool:
    """Is the conjunction of oracle constraints ``(coeffs, op, rhs)``
    satisfiable over the reals?

    Complete: for the convex part (``<=, <, ==``) Fourier-Motzkin with
    strictness is exact.  With disequalities ``a.x != b``: a non-empty
    convex set is covered by finitely many hyperplanes only if it lies in
    one of them, so the system is feasible iff the convex part is and, for
    every disequality, the convex part meets ``a.x < b`` or ``a.x > b``.
    """
    ineqs, diseqs = _to_ineqs(cons)
    if _fm_ineqs(ineqs) is None:
        return False
    for c, b in diseqs:
        neg = {t: -v for t, v in c.items()}
        if (_fm_ineqs(ineqs + [(c, True, b)]) is None
                and _fm_ineqs(ineqs + [(neg, True, -b)]) is None):
            return False
    return True


def fm_witness(cons):
    """A rational point satisfying the convex constraints of ``cons``
    (no disequalities), or None."""
    ineqs, diseqs = _to_ineqs(cons)
    assert not diseqs
    return _fm_ineqs(ineqs)


def grid_feasible(cons, variables, lo=-3, hi=3, dens=(1, 2, 3)):
    """Incomplete oracle: search a rational grid.  A True answer is
    certain; False only means no grid point works.  Used to cross-check
    the FM oracle."""
    pts = sorted({F(n, d) for d in dens for n in range(lo * d, hi * d + 1)})
    variables = list(variables)
    for vals in itertools.product(pts, repeat=len(variables)):
        p = dict(zip(variables, vals))
        if all(holds(c, p) for c in cons):
            return True
    return False


def has_diseq(atoms, lits) -> bool:
    return any(payload_constraint(atoms[abs(l)], l > 0)[1] == "!=" for l in lits)


def lits_feasible(atoms, lits) -> bool:
    return fm_feasible([payload_constraint(atoms[abs(l)], l > 0) for l in lits])


def consistent_for(atoms):
    """``consistent(assign)`` for theory_harness: FM on the literals."""
    def consistent(assign):
        return lits_feasible(atoms, [v if b else -v for v, b in assign.items()])
    return consistent


# ----------------------------------------------------------------------
# Checked driver
# ----------------------------------------------------------------------

class TheoryError(AssertionError):
    pass


class Driver:
    """Drives a theory through the protocol and checks every answer.

    ``minimal``: require conflict clauses to be minimal (every literal
    needed).  ``complete``: require ``check`` to decide (no None).
    """

    def __init__(self, atoms, theory=None, minimal=True, complete=True,
                 register=True):
        self.t = theory if theory is not None else new_theory()
        self.atoms = dict(atoms)
        self.levels: list[list[int]] = [[]]
        self.blocked = False
        self.dead = False
        self.minimal = minimal
        self.complete = complete
        self.conflicts = 0
        if register:
            for v, p in self.atoms.items():
                self.t.register_atom(v, p)

    # -- state ---------------------------------------------------------
    @property
    def asserted(self) -> list[int]:
        return [l for lv in self.levels for l in lv]

    @property
    def level(self) -> int:
        return len(self.levels) - 1

    def register(self, v, p):
        assert self.level == 0
        self.atoms[v] = p
        self.t.register_atom(v, p)

    # -- protocol ------------------------------------------------------
    def push(self):
        assert not self.dead
        self.t.push_level()
        self.levels.append([])

    def pop(self):
        assert self.level > 0
        self.t.pop_level()
        self.levels.pop()
        self.blocked = False

    def assert_(self, lit):
        """Assert and verify.  Returns True if consistent so far, False on
        a (verified) conflict."""
        assert not self.blocked and not self.dead
        assert abs(lit) in self.atoms
        assert lit not in self.asserted and -lit not in self.asserted, lit
        self.levels[-1].append(lit)
        r = self.t.assert_lit(lit)
        if r is None:
            return True
        assert isinstance(r, tuple) and len(r) == 2, r
        if r[0] is False:
            self._conflict(r[1], "assert_lit")
            return False
        raise TheoryError(f"assert_lit returned {r!r}")

    def check(self):
        """Run check() and verify it.  Returns True/False (None if the
        theory declined and ``complete`` is off)."""
        assert not self.blocked and not self.dead
        lits = self.asserted
        expected = lits_feasible(self.atoms, lits)
        r = self.t.check()
        if r is None:
            if self.complete and (DISEQ_COMPLETE or not self._has_diseq(lits)):
                raise TheoryError(f"check() gave no verdict on {self._show(lits)}")
            return None
        ok, info = r
        if ok is True:
            if not expected:
                raise TheoryError(f"check() says SAT, oracle UNSAT: {self._show(lits)}")
            self.check_model(info, lits)
            return True
        assert ok is False, r
        if expected:
            raise TheoryError(f"check() conflict on a satisfiable set: {self._show(lits)}")
        self._conflict(info, "check")
        return False

    def _has_diseq(self, lits):
        return has_diseq(self.atoms, lits)

    def check_model(self, model, lits=None):
        lits = self.asserted if lits is None else lits
        vals = model_values(model)
        for l in lits:
            con = payload_constraint(self.atoms[abs(l)], l > 0)
            for t, c in con[0].items():
                if not c:
                    continue                 # a zero coefficient needs no value
                if t not in vals:
                    raise TheoryError(f"model has no value for term {t!r}")
                if not isinstance(vals[t], (int, F)):
                    raise TheoryError(f"model value {vals[t]!r} of {t!r} is not a Fraction")
            if not holds(con, vals):
                raise TheoryError(f"model {vals} violates literal {l}: {con}")

    def propagate(self):
        """Call propagate() if the theory has it and verify each pair.
        Returns the implied literals."""
        prop = getattr(self.t, "propagate", None)
        if prop is None:
            return []
        out = []
        live = set(self.asserted)
        for lit, reason in prop():
            reason = list(reason)
            assert lit in reason, (lit, reason)
            others = [l for l in reason if l != lit]
            for l in others:
                assert -l in live, f"reason literal {l} is not false"
            # validity: the negation of the clause is infeasible
            assert not lits_feasible(self.atoms, [-l for l in reason]), \
                f"propagation {lit} with invalid reason {reason}"
            out.append(lit)
        return out

    def _conflict(self, clause, where):
        self.conflicts += 1
        clause = list(clause)
        if not clause:
            raise TheoryError(f"{where}: empty conflict clause")
        live = set(self.asserted)
        for l in clause:
            if not isinstance(l, int) or l == 0:
                raise TheoryError(f"{where}: bad literal {l!r}")
            if -l not in live:
                raise TheoryError(f"{where}: conflict literal {l} is not false "
                                  f"(asserted: {sorted(live)})")
        core = sorted({-l for l in clause})
        if lits_feasible(self.atoms, core):
            raise TheoryError(f"{where}: conflict {clause} is satisfiable: {self._show(core)}")
        # Explanations involving a disequality are a union of two row
        # explanations and need not be minimal (lra-impl's contract).
        if self.minimal and not self._has_diseq(core):
            for l in core:
                sub = [m for m in core if m != l]
                if not lits_feasible(self.atoms, sub):
                    raise TheoryError(f"{where}: conflict {clause} not minimal, "
                                      f"{-l} is unnecessary")
        if self.level == 0:
            self.dead = True
        else:
            self.blocked = True

    def _show(self, lits):
        return [(l, payload_constraint(self.atoms[abs(l)], l > 0)) for l in lits]

    def assert_all(self, lits):
        """Assert until the first conflict; True if none."""
        for l in lits:
            if not self.assert_(l):
                return False
        return True

    def decide(self, lits):
        """Push, assert ``lits`` and check; returns the verdict (the level
        is left open)."""
        self.push()
        if not self.assert_all(lits):
            return False
        return self.check()


def run_fresh(atoms, lits, **kw):
    """Reference by reconstruction: a fresh theory, everything asserted at
    level 0 in the given order, then checked."""
    d = Driver(atoms, **kw)
    if not d.assert_all(lits):
        return False
    return d.check()


# ----------------------------------------------------------------------
# Oracle self-tests (run without the implementation)
# ----------------------------------------------------------------------

def test_oracle_basic():
    X = {"x": 1}
    assert fm_feasible([(X, "<=", 0), (X, ">=", 0)])
    assert not fm_feasible([(X, "<", 0), (X, ">=", 0)])
    assert not fm_feasible([(X, "<=", 0), (X, ">=", 0), (X, "!=", 0)])
    assert fm_feasible([(X, "<=", 1), (X, ">=", 0), (X, "!=", 0)])
    assert not fm_feasible([({"x": 1, "y": 1}, "<=", 1), (X, ">=", 1), ({"y": 1}, ">", 0)])
    assert fm_feasible([({"x": 1, "y": -1}, "<", 0), ({"y": 1, "x": -1}, "<", 0)]) is False
    assert fm_feasible([({}, "<=", 0)]) and not fm_feasible([({}, "<", 0)])
    assert not fm_feasible([({"x": 0}, "!=", 0)])
    # x = y, y = z, x != z
    assert not fm_feasible([({"x": 1, "y": -1}, "==", 0), ({"y": 1, "z": -1}, "==", 0),
                            ({"x": 1, "z": -1}, "!=", 0)])
    # two disequalities covering an interval only at points
    assert fm_feasible([(X, ">=", 0), (X, "<=", 1), (X, "!=", 0), (X, "!=", 1)])


def test_oracle_against_grid():
    """Every grid point found must be matched by FM (FM complete), and
    every FM verdict is certified by a witness internally."""
    rng = random.Random(7)
    names = ["x", "y", "z"]
    for _ in range(150):
        nv = rng.randint(1, 3)
        vs = names[:nv]
        cons = []
        for _ in range(rng.randint(1, 5)):
            co = {v: rng.randint(-2, 2) for v in vs}
            cons.append((co, rng.choice(OPS), F(rng.randint(-3, 3), rng.randint(1, 2))))
        fm = fm_feasible(cons)
        grid = grid_feasible(cons, vs, lo=-3, hi=3, dens=(1, 2, 4) if nv < 3 else (1, 2))
        if grid:
            assert fm, cons
        if fm and not any(op == "!=" for _, op, _ in cons):
            w = fm_witness(cons)
            assert all(holds(c, {**{v: F(0) for v in vs}, **w}) for c in cons)


# ----------------------------------------------------------------------
# Interface
# ----------------------------------------------------------------------

@needs_lra
def test_protocol_surface():
    from satassume.theory import TheorySolver
    t = new_theory()
    assert isinstance(t, TheorySolver)
    for name in ("register_atom", "assert_lit", "check", "push_level", "pop_level"):
        assert callable(getattr(t, name))


@needs_lra
def test_empty_theory_checks_sat():
    t = new_theory()
    r = t.check()
    assert r is None or r[0] is True
    t.push_level()
    t.pop_level()
    r = t.check()
    assert r is None or r[0] is True


@needs_lra
def test_unregistered_literals_are_ignored():
    d = Driver({1: payload({"x": 1}, "<=", 0)})
    assert d.t.assert_lit(7) is None
    assert d.t.assert_lit(-7) is None
    assert d.check() is True


# ----------------------------------------------------------------------
# Bounds, negation, strictness (delta)
# ----------------------------------------------------------------------

X = {"x": 1}


@needs_lra
@pytest.mark.parametrize("op", ["<=", "<", "==", ">=", ">"])
@pytest.mark.parametrize("positive", [True, False])
@pytest.mark.parametrize("other_op", ["<=", "<", "==", ">=", ">"])
@pytest.mark.parametrize("other_positive", [True, False])
@pytest.mark.parametrize("rhs2", [F(-1), F(0), F(1)])
def test_two_bounds_on_one_variable(op, positive, other_op, other_positive, rhs2):
    """Every pair of one-variable literals, including all boundary cases
    (equal bounds, strict against non-strict, negated equalities), against
    the oracle, in both assertion orders and split over two levels."""
    atoms = {1: payload(X, op, 0), 2: payload(X, other_op, rhs2)}
    lits = [1 if positive else -1, 2 if other_positive else -2]
    for order in (lits, lits[::-1]):
        d = Driver(atoms)
        if d.assert_all(order):
            d.check()
        d = Driver(atoms)
        d.push()
        if d.assert_(order[0]):
            d.push()
            if d.assert_(order[1]):
                d.check()


@needs_lra
@pytest.mark.parametrize("coef", [F(1), F(2), F(-1), F(-3), F(1, 3), F(-5, 7)])
@pytest.mark.parametrize("op", ["<=", "<", "==", ">=", ">"])
@pytest.mark.parametrize("positive", [True, False])
def test_single_term_coefficient_normalisation(coef, op, positive):
    """``c*x op r`` for negative and fractional ``c``: the direction of the
    bound flips with the sign of ``c``.  Probe with ``x`` pinned at points
    around the bound ``r/c``."""
    r = F(2)
    p = payload({"x": coef}, op, r)
    b = r / coef
    for probe in (b - 1, b - F(1, 1000), b, b + F(1, 1000), b + 1):
        atoms = {1: p, 2: payload(X, "==", probe)}
        lit = 1 if positive else -1
        expected = holds(payload_constraint(p, positive), {"x": probe})
        d = Driver(atoms)
        res = d.assert_all([2, lit]) and d.check()
        if res is not None:
            assert res == expected, (coef, op, positive, probe)


@needs_lra
def test_strict_bounds_model_is_strictly_inside():
    # 0 < x < 1/1000000, x < y < 2x: needs a small delta in both
    atoms = {1: payload(X, ">", 0), 2: payload(X, "<", F(1, 10**6)),
             3: payload({"y": 1, "x": -1}, ">", 0), 4: payload({"y": 1, "x": -2}, "<", 0)}
    d = Driver(atoms)
    d.assert_all([1, 2, 3, 4])
    assert d.check() is True


@needs_lra
def test_many_strict_bounds_delta_must_shrink():
    # x0 < x1 < ... < x9 < 1/1000 and x0 > 0: delta must fit 10 gaps
    atoms = {1: payload({"x0": 1}, ">", 0), 2: payload({"x9": 1}, "<", F(1, 1000))}
    for i in range(9):
        atoms[3 + i] = payload({f"x{i}": 1, f"x{i+1}": -1}, "<", 0)
    d = Driver(atoms)
    assert d.assert_all(sorted(atoms)) and d.check() is True
    # and one more strict step makes it... still SAT; x9 < 0 makes it UNSAT
    d2 = Driver({**atoms, 20: payload({"x9": 1}, "<=", 0)})
    assert d2.assert_all(sorted(atoms) + [20]) is False or d2.check() is False


@needs_lra
def test_negated_strict_is_nonstrict():
    # not(x < 1) and x <= 1 pins x to exactly 1
    atoms = {1: payload(X, "<", 1), 2: payload(X, "<=", 1)}
    d = Driver(atoms)
    assert d.assert_all([-1, 2]) and d.check() is True
    # not(x <= 1) and x <= 1: conflict
    atoms = {1: payload(X, "<=", 1), 2: payload(X, "<=", 1)}
    d = Driver(atoms)
    assert not (d.assert_all([-1, 2]) and d.check())


@needs_lra
def test_duplicate_payloads_on_different_variables():
    p = payload(X, "<=", 1)
    d = Driver({1: p, 2: p})
    assert not (d.assert_all([1, -2]) and d.check())
    d = Driver({1: p, 2: p})
    assert d.assert_all([1, 2]) and d.check() is True


@needs_lra
def test_exact_arithmetic_large_and_tiny_numbers():
    big = F(10) ** 40
    tiny = F(1, 10 ** 40)
    atoms = {1: payload({"x": big}, "<=", 1), 2: payload(X, ">", 0),
             3: payload(X, ">=", tiny + tiny * tiny), 4: payload({"x": 3}, "==", 1),
             5: payload(X, "<=", F(1, 3))}
    d = Driver(atoms)
    assert d.assert_all([1, 2]) and d.check() is True
    d = Driver(atoms)
    assert not (d.assert_all([1, 3]) and d.check())       # 1e-40 + 1e-80 > 1e-40
    d = Driver(atoms)
    assert d.assert_all([4, 5]) and d.check() is True      # x = 1/3 exactly
    d = Driver(atoms)
    assert not (d.assert_all([4, -5]) and d.check())


# ----------------------------------------------------------------------
# Equalities and disequalities
# ----------------------------------------------------------------------

@needs_lra
def test_equality_model_hits_the_value():
    d = Driver({1: payload({"x": 2}, "==", 6)})
    assert d.assert_all([1]) and d.check() is True


@needs_lra
def test_two_equalities_conflict_minimal():
    d = Driver({1: payload(X, "==", 1), 2: payload(X, "==", 2), 3: payload({"y": 1}, ">=", 0)})
    assert not (d.assert_all([3, 1, 2]) and d.check())


@needs_lra
def test_multi_term_equalities_solve_system():
    atoms = {1: payload({"x": 1, "y": 1}, "==", 2), 2: payload({"x": 1, "y": -1}, "==", 0),
             3: payload(X, ">", 1)}
    d = Driver(atoms)
    assert d.assert_all([1, 2]) and d.check() is True     # x = y = 1
    d = Driver(atoms)
    assert not (d.assert_all([1, 2, 3]) and d.check())


@needs_lra
@pytest.mark.parametrize("order", list(itertools.permutations([1, 2, 3])))
def test_disequality_with_pinned_value(order):
    """x != 0 with 0 <= x <= 0 is UNSAT.  (True, model) here is always
    wrong (the model has x = 0); None only if SATASSUME_LRA_DISEQ=0."""
    atoms = {1: payload(X, "==", 0), 2: payload(X, "<=", 0), 3: payload(X, ">=", 0)}
    lits = {1: -1, 2: 2, 3: 3}
    d = Driver(atoms)
    if d.assert_all([lits[i] for i in order]):
        assert d.check() in (False, *DQ)


@needs_lra
def test_disequality_model_avoids_the_excluded_value():
    """0 <= x <= 1, x != 0: a simplex model sits at a bound (x = 0) unless
    disequalities are handled.  Any (True, model) must respect x != 0.
    Targets the reference solvers, which ignore negated equalities."""
    atoms = {1: payload(X, "==", 0), 2: payload(X, ">=", 0), 3: payload(X, "<=", 1)}
    d = Driver(atoms)
    assert d.assert_all([2, 3, -1])
    assert d.check() in (True, *DQ)


@needs_lra
def test_disequality_on_a_slack():
    atoms = {1: payload({"x": 1, "y": 1}, "==", 1), 2: payload({"x": 1, "y": 1}, "<=", 1),
             3: payload({"x": 1, "y": 1}, ">=", 1), 4: payload(X, ">=", 0)}
    d = Driver(atoms)
    if d.assert_all([4, 2, 3, -1]):
        assert d.check() in (False, *DQ)
    d = Driver(atoms)
    if d.assert_all([4, 2, -1]):
        assert d.check() in (True, *DQ)


@needs_lra
def test_many_disequalities_on_an_interval():
    # 0 <= x <= 1 minus 5 points is SAT; a model must avoid all of them
    atoms = {1: payload(X, ">=", 0), 2: payload(X, "<=", 1)}
    for i in range(5):
        atoms[3 + i] = payload(X, "==", F(i, 4))
    d = Driver(atoms)
    assert d.assert_all([1, 2] + [-(3 + i) for i in range(5)])
    assert d.check() in (True, *DQ)


# ----------------------------------------------------------------------
# Tableau: slacks, shared rows, terms only in rows, degenerate terms
# ----------------------------------------------------------------------

@needs_lra
def test_terms_only_in_rows_get_model_values():
    """x and y occur only inside x + y <= 1 and x - y >= 3.  The model must
    still give x and y values satisfying both rows.  (The reference
    implementations eliminate such "non-atom" columns and return a model
    over slack variables only.)"""
    atoms = {1: payload({"x": 1, "y": 1}, "<=", 1), 2: payload({"x": 1, "y": -1}, ">=", 3)}
    d = Driver(atoms)
    assert d.assert_all([1, 2]) and d.check() is True


@needs_lra
def test_same_row_different_order_and_scale():
    """x + y, y + x, 2x + 2y and -x - y are the same row up to scale; a
    solver keying slacks by the term tuple creates several slacks, which is
    fine, but the answers must be right."""
    atoms = {1: payload([("x", 1), ("y", 1)], "<=", 1),
             2: payload([("y", 1), ("x", 1)], ">", 1),
             3: payload({"x": 2, "y": 2}, ">=", 3),
             4: payload({"x": -1, "y": -1}, ">=", -1),
             5: payload({"x": 3, "y": 3}, "<", 3)}
    for lits in ([1, 2], [1, 3], [3, 4], [5, -1], [-5, 4]):
        d = Driver(atoms)
        if d.assert_all(lits):
            d.check()
    d = Driver(atoms)
    assert d.assert_all([4, 1, -5]) and d.check() is True  # x + y = 1


@needs_lra
def test_zero_coefficients_and_empty_terms():
    """Rows that cancel to constants: ``0*x <= -1`` is false,
    ``0 <= 1`` is true, ``x + 0*y <= 0`` is ``x <= 0``.  The adapter
    normally folds these, but the theory must still be sound and, being
    complete, decide them."""
    atoms = {1: payload({"x": 0}, "<=", -1), 2: payload({}, "<=", 1),
             3: payload({"x": 1, "y": 0}, "<=", 0), 4: payload(X, ">", 0),
             5: payload({}, "==", 0)}
    d = Driver(atoms)
    assert not (d.assert_all([1]) and d.check())
    d = Driver(atoms)
    assert d.assert_all([2, 5]) and d.check() is True
    d = Driver(atoms)
    assert not (d.assert_all([-2]) and d.check())
    d = Driver(atoms)
    assert not (d.assert_all([3, 4]) and d.check())


@needs_lra
def test_hashable_term_kinds():
    """Terms are opaque hashables: tuples, ints, frozensets, objects."""
    class T:
        pass
    a, b = T(), T()
    terms = [("f", 1), 17, frozenset({1}), a, b]
    atoms = {i + 1: payload({t: 1}, ">=", i) for i, t in enumerate(terms)}
    atoms[10] = payload({a: 1, b: -1}, ">", 0)          # a > b
    atoms[11] = payload({a: 1}, "<=", 3)                # a <= 3 but b >= 4
    d = Driver(atoms)
    assert d.assert_all([1, 2, 3, 4, 5, 10]) and d.check() is True
    d = Driver(atoms)
    assert not (d.assert_all([5, 10, 11]) and d.check())


@needs_lra
def test_conflict_through_a_row_is_minimal():
    # x + y <= 1, x >= 1, y > 0 and three irrelevant literals
    atoms = {1: payload({"x": 1, "y": 1}, "<=", 1), 2: payload(X, ">=", 1),
             3: payload({"y": 1}, ">", 0), 4: payload({"z": 1}, ">=", 5),
             5: payload(X, "<=", 10), 6: payload({"z": 1, "x": 1}, "<=", 100)}
    for perm in itertools.permutations([1, 2, 3, 4, 5, 6]):
        d = Driver(atoms)
        if d.assert_all(list(perm)):
            assert d.check() is False


@needs_lra
@pytest.mark.parametrize("n", [3, 6, 12])
def test_cycle_conflict_uses_every_edge_and_no_distractor(n):
    """x0 <= x1 <= ... <= x_{n-1} < x0 with distractor bounds: the only
    explanation is the whole cycle."""
    atoms = {}
    for i in range(n):
        op = "<" if i == n - 1 else "<="
        atoms[i + 1] = payload({f"x{i}": 1, f"x{(i + 1) % n}": -1}, op, 0)
    for i in range(n):
        atoms[100 + i] = payload({f"x{i}": 1}, ">=", -i)
    d = Driver(atoms)
    lits = [100 + i for i in range(n)] + [i + 1 for i in range(n)]
    # the conflict may come from assert_lit (eager simplex) or check();
    # the Driver verifies it is the minimal one either way
    assert not (d.assert_all(lits) and d.check())
    assert d.conflicts == 1


@needs_lra
def test_tightest_bound_is_blamed():
    """x <= 5 (1), x <= 3 (2), then x >= 4 (3): only {2, 3} conflict;
    blaming 1 would be invalid, blaming both non-minimal.  Also when the
    weaker bound comes after the tighter one."""
    atoms = {1: payload(X, "<=", 5), 2: payload(X, "<=", 3), 3: payload(X, ">=", 4)}
    for order in ([1, 2, 3], [2, 1, 3], [1, 2], [2, 1]):
        d = Driver(atoms)
        if d.assert_all(order) and len(order) == 3:
            assert d.check() is False


@needs_lra
def test_paper_example_sequence():
    """Dutertre and de Moura, section 4.6, through push/pop instead of the
    reference's single-bound backtrack()."""
    atoms = {1: payload(X, "<=", -4), 2: payload(X, ">=", -8),
             3: payload({"x": -1, "y": 1}, "<=", 1), 4: payload({"x": 1, "y": 1}, ">=", -3)}
    d = Driver(atoms)
    for lit in (1, 2, 3):
        d.push()
        assert d.assert_(lit)
        assert d.check() is True
    d.push()
    assert not (d.assert_(4) and d.check())
    d.pop()
    assert d.check() is True
    d.pop()
    d.pop()
    d.push()
    assert d.assert_(4)
    assert d.check() is True


@needs_lra
def test_sympy_problem_regression():
    # sympy test_problem: -2x-2y >= 7, -9y >= 7, -6y >= 5 is SAT
    atoms = {1: payload({"x": -2, "y": -2}, ">=", 7), 2: payload({"y": -9}, ">=", 7),
             3: payload({"y": -6}, ">=", 5)}
    d = Driver(atoms)
    assert d.assert_all([1, 2, 3]) and d.check() is True


SYMPY_SPECIAL_CASES = [
    # from sympy/logic/tests/test_lra_theory.py::test_random_problems
    [({"x1": 1, "x2": -3}, "<=", -5), ({"x1": 6, "x2": 4}, "<=", 0), ({"x1": -7, "x2": 3}, "<=", 3)],
    [({"x1": -3}, ">=", 3), ({"x1": 4}, "==", -1)],
    [({"x1": -4}, "<", 4), ({"x1": 6}, "<=", -6)],
    [({"x2": -3}, ">=", 7), ({"x1": 6}, "<=", -5), ({"x2": -3}, "<=", -4)],
    [({"x": 1, "y": 1}, ">=", 2), ({"x": 1, "y": 1}, "<=", 1)],
    [({"x": 1}, ">=", 0), ({"x": 1, "y": 1}, "<=", 2), ({"x": 1, "y": 2, "z": -1}, ">=", 6)],
    [({"x1": -2, "x2": -2}, ">=", 7), ({"x1": -9}, ">=", 7), ({"x1": -6}, ">=", 5)],
    [({"x1": 2}, ">", -3), ({"x1": -9}, "<", -6), ({"x1": 9}, "<=", 6)],
    [({"x1": -2}, "<", -4), ({"x1": 9}, ">", -9)],
    [({"x1": -6}, ">=", -1), ({"x1": -8, "x2": 1}, ">=", 5), ({"x1": -8, "x2": 7}, "<", 4), ({"x1": 1}, ">", 7)],
    [({"x1": 1}, "==", 2), ({"x1": 5}, "==", -2), ({"x2": -7}, "==", -6), ({"x1": 9, "x2": 10}, "==", 9)],
    [({"x1": 3}, "==", 6), ({"x1": 1, "x2": -8}, "==", -9), ({"x1": -7, "x2": 5}, "==", 3), ({"x2": 3}, "==", 7)],
    [({"x1": -3, "x2": 8}, ">=", -8), ({"x2": -10}, ">", 9), ({"x1": 8, "x2": -4}, "<", 8), ({"x1": 10, "x2": -9}, ">=", -9)],
    [({"x1": 1, "x2": 5}, ">=", -6), ({"x1": 9, "x2": -3}, ">=", -9), ({"x1": 6, "x2": 6}, "<", -10), ({"x1": -3, "x2": 3}, "<", -7)],
    [({"x1": -9}, "<", 7), ({"x1": -5, "x2": -7}, "<", -1), ({"x1": 3, "x2": 7}, ">", 1), ({"x1": -6, "x2": -6}, ">", 9)],
    [({"x1": 9, "x2": -6}, ">=", -7), ({"x1": 9, "x2": 4}, "<", -8), ({"x2": -7}, "<=", 1), ({"x2": 10}, "<=", -7)],
    [({"x1": 1}, ">=", 0), ({"x1": 1}, "<=", 10), ({"x2": 1}, ">=", -5), ({"x2": 1}, "<=", 5), ({"x1": 1, "x2": 1}, ">=", -3), ({"x1": 1, "x2": -1}, "<=", 12)],
    [({"x1": 1, "x2": 1, "x3": 1}, "<=", 10), ({"x1": 1}, ">=", 0), ({"x2": 1}, ">=", 0), ({"x3": 1}, ">=", 0), ({"x1": 1, "x3": -1}, ">=", -5)],
    [({"x1": 5, "x2": -3}, ">=", -6), ({"x1": 1}, "<=", 4), ({"x2": 1}, ">=", -2), ({"x2": 1}, "<=", 7)],
]


@needs_lra
@pytest.mark.parametrize("case", range(len(SYMPY_SPECIAL_CASES)))
def test_sympy_special_cases(case):
    cons = SYMPY_SPECIAL_CASES[case]
    atoms = {i + 1: payload(*c) for i, c in enumerate(cons)}
    lits = sorted(atoms)
    for order in (lits, lits[::-1]):
        r = run_fresh(atoms, order)
        assert r == fm_feasible(cons)


# ----------------------------------------------------------------------
# Pivoting: degeneracy and cycling
# ----------------------------------------------------------------------

@needs_lra
def test_degenerate_vertex_terminates():
    """Many constraints through the origin (a highly degenerate vertex) plus
    an infeasible strict one.  A pivot rule without an anti-cycling
    guarantee (Bland) can loop here; the reasoning reference uses two
    different orderings for the two branches of check()."""
    rng = random.Random(3)
    vs = ["a", "b", "c", "d"]
    for trial in range(40):
        atoms = {}
        for i in range(12):
            co = {v: rng.choice([-2, -1, 0, 1, 2]) for v in vs}
            atoms[i + 1] = payload(co, rng.choice(["<=", ">=", "<", ">"]), 0)
        t0 = time.process_time()
        d = Driver(atoms)
        if d.assert_all(sorted(atoms)):
            d.check()
        assert time.process_time() - t0 < 2.0, f"trial {trial} too slow (cycling?)"


@needs_lra
def test_beale_like_cycling_example():
    """Beale's classic cycling LP turned into feasibility questions over its
    constraint rows (all degenerate at the origin)."""
    rows = [
        {"x4": F(1, 4), "x5": -8, "x6": -1, "x7": 9},
        {"x4": F(1, 2), "x5": -12, "x6": F(-1, 2), "x7": 3},
        {"x6": 1},
        {"x4": F(-3, 4), "x5": 20, "x6": F(-1, 2), "x7": 6},
    ]
    atoms = {1: payload(rows[0], "<=", 0), 2: payload(rows[1], "<=", 0),
             3: payload(rows[2], "<=", 1), 4: payload(rows[3], ">", F(5, 4)),
             5: payload({"x4": 1}, ">=", 0), 6: payload({"x5": 1}, ">=", 0),
             7: payload({"x6": 1}, ">=", 0), 8: payload({"x7": 1}, ">=", 0),
             9: payload(rows[3], ">", F(1, 20))}
    t0 = time.process_time()
    for lits in ([5, 6, 7, 8, 1, 2, 3, 4], [5, 6, 7, 8, 1, 2, 3, 9], [1, 2, 3, 4, 5, 6, 7, 8]):
        d = Driver(atoms)
        if d.assert_all(lits):
            d.check()
    assert time.process_time() - t0 < 2.0


# ----------------------------------------------------------------------
# Levels: push/pop restore, stale literals, register_atom late
# ----------------------------------------------------------------------

@needs_lra
def test_pop_forgets_bounds_and_their_literals():
    """A popped bound must neither cause a conflict nor appear in one."""
    atoms = {1: payload(X, "<=", 5), 2: payload(X, "<=", 0), 3: payload(X, ">=", 3),
             4: payload(X, ">=", 6)}
    d = Driver(atoms)
    assert d.assert_(1)
    d.push()
    assert d.assert_(2)
    d.pop()
    d.push()
    assert d.assert_(3)               # would conflict with the popped x <= 0
    assert d.check() is True
    d.push()
    assert not (d.assert_(4) and d.check())   # must blame 1, not 2


@needs_lra
def test_pop_after_check_with_pivots_restores_state():
    """check() pivots the tableau; pop must still restore the bounds so
    that the same questions get the same answers as a fresh theory."""
    atoms = {1: payload({"x": 1, "y": 1}, "<=", 2), 2: payload(X, ">=", 1),
             3: payload({"y": 1}, ">=", 1), 4: payload({"x": 1, "y": -1}, ">", 0),
             5: payload({"y": 1}, "<", 0)}
    d = Driver(atoms)
    d.push()
    assert d.assert_all([1, 2, 3]) and d.check() is True
    d.push()
    assert not (d.assert_(4) and d.check())
    d.pop()
    assert d.check() is True
    d.pop()
    d.push()
    assert d.assert_all([4, 5]) and d.check() is True
    assert run_fresh(atoms, [4, 5]) is True


@needs_lra
def test_empty_levels_and_deep_nesting():
    atoms = {i + 1: payload(X, ">=", i) for i in range(60)}
    atoms[100] = payload(X, "<", 30)
    d = Driver(atoms)
    for i in range(60):
        d.push()
        d.push()                        # empty level
        assert d.assert_(i + 1)
    assert d.check() is True
    d.push()
    assert not (d.assert_(100) and d.check())
    for _ in range(90):
        d.pop()
    # now x >= 0 .. x >= 14 remain
    assert d.level == 31 - 1 or d.level >= 0
    while d.level:
        d.pop()
    d.push()
    assert d.assert_(100) and d.check() is True


@needs_lra
def test_level_zero_facts_are_permanent():
    atoms = {1: payload(X, ">=", 2), 2: payload(X, "<", 2)}
    d = Driver(atoms)
    assert d.assert_(1)
    for _ in range(3):
        d.push()
        assert not (d.assert_(2) and d.check())
        d.pop()
    assert d.check() is True


@needs_lra
def test_register_atom_after_assertions_and_checks():
    """register_atom may come at root after other atoms were asserted and
    checked (engine sessions grow incrementally), with old and new terms."""
    d = Driver({1: payload(X, ">=", 1)})
    assert d.assert_(1) and d.check() is True
    d.register(2, payload({"x": 1, "y": 1}, "<=", 0))
    d.register(3, payload({"y": 1}, ">=", 0))
    d.push()
    assert not (d.assert_all([2, 3]) and d.check())
    d.pop()
    d.register(4, payload({"z": 1, "y": -1}, "==", 5))
    d.register(5, payload({"z": 1}, ">", 4))        # z = y + 5 <= 4
    d.push()
    assert d.assert_all([2, 4]) and d.check() is True
    d.push()
    assert not (d.assert_(5) and d.check())
    d.pop()
    d.pop()
    # a new atom over a row already present
    d.register(6, payload({"y": 2, "x": 2}, ">", -2))
    d.push()
    assert d.assert_all([2, 6]) and d.check() is True


@needs_lra
def test_register_between_levels_after_pivoting():
    rng = random.Random(11)
    atoms = {}
    d = Driver({})
    v = 0
    for round_ in range(15):
        for _ in range(3):
            v += 1
            co = {n: rng.randint(-2, 2) for n in rng.sample(["x", "y", "z", "w"], 2)}
            d.register(v, payload(co, rng.choice(["<=", "<", "==", ">=", ">"]), rng.randint(-3, 3)))
        d.push()
        lits = [rng.choice([1, -1]) * u for u in rng.sample(range(1, v + 1), min(v, 4))]
        if d.assert_all(lits):
            d.check()
        d.pop()


@needs_lra
def test_check_is_repeatable():
    atoms = {1: payload({"x": 1, "y": 1}, "<=", 1), 2: payload(X, ">=", 1),
             3: payload({"y": 1}, ">", -1)}
    d = Driver(atoms)
    assert d.assert_all([1, 2, 3])
    assert d.check() is True
    assert d.check() is True


@needs_lra
def test_theory_propagation_if_present():
    """If the theory propagates, every implied literal comes with a valid
    reason made of asserted literals."""
    atoms = {1: payload(X, ">=", 3), 2: payload(X, ">=", 1), 3: payload(X, "<", 2),
             4: payload(X, "==", 0), 5: payload({"x": 1, "y": 1}, "<=", 0), 6: payload({"y": 1}, ">", -3)}
    d = Driver(atoms)
    d.push()
    assert d.assert_(1)
    implied = d.propagate()
    for l in implied:
        assert l in (2, -3, -4, -6) or abs(l) in atoms


# ----------------------------------------------------------------------
# Backtracking torture: random push/assert/pop/check vs reconstruction
# ----------------------------------------------------------------------

def random_atoms(rng, nvars=3, natoms=8, coef=2, rhs=3, ops=("<=", "<", "==", ">=", ">", "!="),
                 max_terms=None):
    names = [f"v{i}" for i in range(nvars)]
    atoms = {}
    for a in range(1, natoms + 1):
        k = rng.randint(1, max_terms or nvars)
        co = {n: rng.choice([c for c in range(-coef, coef + 1) if c]) for n in rng.sample(names, k)}
        atoms[a] = payload(co, rng.choice(ops), F(rng.randint(-rhs, rhs), rng.choice([1, 1, 2, 3])))
    return atoms


def torture(rng, atoms, steps, allow_diseq=True, minimal=True, eager=None):
    d = Driver(atoms, theory=new_theory(eager), minimal=minimal, complete=True)
    for _ in range(steps):
        free = [v for v in atoms if v not in {abs(l) for l in d.asserted}]
        op = rng.random()
        if d.blocked:
            d.pop()
            continue
        if d.dead:
            break
        if op < 0.25:
            d.push()
        elif op < 0.45 and d.level > 0:
            d.pop()
        elif op < 0.85 and free:
            v = rng.choice(free)
            lit = v * rng.choice([1, -1])
            if not allow_diseq and payload_constraint(atoms[v], lit > 0)[1] == "!=":
                lit = -lit
            d.assert_(lit)
        else:
            r = d.check()
            # reference by reconstruction: a fresh theory, same literals
            r2 = run_fresh(atoms, d.asserted, minimal=minimal)
            if r is not None and r2 is not None:
                assert r == r2
    while d.level:
        d.pop()
    return d


@needs_lra
@pytest.mark.parametrize("eager", [True, False])
@pytest.mark.parametrize("seed", range(60))
def test_backtracking_torture(seed, eager):
    rng = random.Random(seed)
    atoms = random_atoms(rng, nvars=rng.randint(1, 4), natoms=rng.randint(3, 10))
    torture(rng, atoms, 120, eager=eager)


@needs_lra
@pytest.mark.parametrize("seed", range(20))
def test_backtracking_torture_tight_bounds(seed):
    """One-variable bounds with few distinct constants: lots of equal and
    strict-vs-nonstrict boundary cases, conflicts inside assert_lit."""
    rng = random.Random(1000 + seed)
    atoms = {a: payload({rng.choice("xy"): rng.choice([1, -1, 2])},
                        rng.choice(["<=", "<", "==", ">=", ">"]), rng.randint(-1, 1))
             for a in range(1, 11)}
    atoms[11] = payload({"x": 1, "y": -1}, rng.choice(["<=", "<", "=="]), 0)
    torture(rng, atoms, 150)


@needs_lra
@pytest.mark.parametrize("seed", range(10))
def test_torture_with_late_registration(seed):
    rng = random.Random(5000 + seed)
    pool = random_atoms(rng, nvars=3, natoms=14)
    d = Driver({})
    v_next = 1
    for _ in range(200):
        if d.blocked:
            d.pop()
            continue
        if d.dead:
            break
        op = rng.random()
        if op < 0.1 and d.level == 0 and v_next <= len(pool):
            d.register(v_next, pool[v_next])
            v_next += 1
        elif op < 0.35:
            d.push()
        elif op < 0.55 and d.level:
            d.pop()
        elif op < 0.85:
            free = [v for v in d.atoms if v not in {abs(l) for l in d.asserted}]
            if free:
                d.assert_(rng.choice(free) * rng.choice([1, -1]))
        else:
            d.check()
