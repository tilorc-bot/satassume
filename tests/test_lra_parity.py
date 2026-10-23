"""The parity check of LRA (``satassume/theories/lra/parity.py``, #315)
against brute force, and the parity links end to end.

Fuzz: small systems of integrality literals ``f in Z`` / ``f not in Z``
over variables ``x0..x3`` with coefficients and offsets in ``Z/2``.  The
oracle enumerates integer values of the variables in ``-2..2`` (both
parities of each, so any parity pattern is reached) and evaluates each
literal with Fractions; it never computes a parity.  Checked:

* :func:`parity.conflict` gives a conflict iff the oracle finds no point
  (every variable declared integral, so every row is used), and its
  clause names only asserted literals whose own system is infeasible;
* ``LRATheory.check`` over the same atoms (no bounds) reports a conflict
  for every infeasible system and never for a feasible one, with a clause
  of asserted literals that is infeasible by the oracle.

Seeds: ``PARITY_FUZZ_SEEDS`` (default 300) from ``PARITY_FUZZ_SEED0``.
"""
from __future__ import annotations

import itertools
import os
import random
from fractions import Fraction as F

import pytest

from satassume.theories.lra import lra
from satassume.theories.lra import parity
from satassume.theories.lra.lra import Integral

SEEDS = int(os.environ.get("PARITY_FUZZ_SEEDS", "300"))
SEED0 = int(os.environ.get("PARITY_FUZZ_SEED0", "0"))
VALUES = range(-2, 3)


def _system(rng):
    """``(nvars, atoms, lits)``: ``atoms`` literal -> (lin, offset), the
    first ``nvars`` the units ``x_i in Z`` (asserted true), the rest random
    forms, each asserted true or false (``lits``)."""
    n = rng.randint(1, 4)
    atoms = {i + 1: ({f"x{i}": F(1)}, F(0)) for i in range(n)}
    lits = list(atoms)
    for j in range(rng.randint(1, 5)):
        lin = {}
        for i in range(n):
            if rng.random() < 0.6:
                c = F(rng.randint(-3, 3), 2)
                if c:
                    lin[f"x{i}"] = c
        if not lin:
            lin[f"x{rng.randrange(n)}"] = F(1, 2)
        a = n + j + 1
        atoms[a] = (lin, F(rng.randint(-2, 2), 2))
        lits.append(a if rng.random() < 0.5 else -a)
    return n, atoms, lits


def _feasible(n, atoms, lits) -> bool:
    for xs in itertools.product(VALUES, repeat=n):
        val = {f"x{i}": x for i, x in enumerate(xs)}
        if all((sum(c * val[t] for t, c in atoms[abs(l)][0].items())
                + atoms[abs(l)][1]).denominator == 1 for l in lits if l > 0) \
           and all((sum(c * val[t] for t, c in atoms[abs(l)][0].items())
                    + atoms[abs(l)][1]).denominator != 1 for l in lits if l < 0):
            return True
    return False


def _rows(n, atoms, lits):
    var = {f"x{i}": i for i in range(n)}.__getitem__
    units, rows = {}, []
    for l in lits:
        lin, k = atoms[abs(l)]
        u = parity.unit_of(lin, var, k)
        if l > 0 and u is not None:
            units.setdefault(u, l)
            continue
        vs, mask, kappa = parity.row_of(lin, var, k)
        rows.append((vs, mask, kappa, l))
    return units, rows


@pytest.mark.parametrize("seed", range(SEED0, SEED0 + SEEDS))
def test_conflict_against_brute_force(seed):
    rng = random.Random(seed)
    n, atoms, lits = _system(rng)
    feasible = _feasible(n, atoms, lits)
    c = parity.conflict(*_rows(n, atoms, lits))
    assert (c is None) == feasible, (atoms, lits, c)
    if c is not None:
        sub = [-l for l in c]
        assert set(sub) <= set(lits)
        assert not _feasible(n, atoms, sub)
    # the theory: same atoms, asserted in a random order, no bounds
    t = lra.LRATheory()
    for a, (lin, k) in atoms.items():
        t.register_atom(a, Integral(lin, k))
    order = lits[:]
    rng.shuffle(order)
    for l in order:
        r = t.assert_lit(l)
        if r is not None:
            break
    else:
        r = t.check()
    if feasible:
        assert r is None or r[0] is True, (atoms, lits, r)
    else:
        assert r is not None and r[0] is False, (atoms, lits, r)
        sub = [-l for l in r[1]]
        assert set(sub) <= set(lits)
        assert not _feasible(n, atoms, sub)


def test_row_of_skips_other_denominators():
    var = {"x": 0, "y": 1}.__getitem__
    assert parity.row_of({"x": F(1, 2), "y": F(1)}, var, F(1, 2)) == ((0, 1), 1, 1)
    assert parity.row_of({"x": F(1, 4)}, var, F(0)) is None
    assert parity.row_of({"x": F(1, 2)}, var, F(1, 3)) is None
    assert parity.unit_of({"x": F(-1)}, var, F(3)) == 0
    assert parity.unit_of({"x": F(2)}, var, F(0)) is None


def test_a_row_over_a_variable_not_integral_is_left_out():
    var = {"x": 0, "y": 1}.__getitem__
    # x/2 + y/2 in Z and x/2 + y/2 + 1/2 in Z contradict each other for
    # any y, but with y not asserted integral the rows are not parity
    # equations, and the check leaves them out (incomplete, never wrong)
    rows = [((0, 1), 3, 0, 5), ((0, 1), 3, 1, 6)]
    assert parity.conflict({0: 1}, rows) is None
    assert parity.conflict({0: 1, 1: 2}, rows) == [-6, -5, -2, -1]


# -- end to end: the links and the trigger (relations.PARITY) -------------

sympy = pytest.importorskip("sympy")
from sympy import Q, Rational, Symbol, symbols  # noqa: E402

from satassume import DictCache, Engine  # noqa: E402
from satassume.sympy_api import ask  # noqa: E402

k, m, n, x, y, z, w = symbols("k m n x y z w")
half = Rational(1, 2)


@pytest.mark.parametrize("query, assumptions, expected", [
    # the hook's stream shapes (#315 step 1)
    (Q.integer(k/2 + half), Q.odd(k), True),
    (Q.integer(-k/2 - 3*half), Q.odd(k), True),
    (Q.integer(half - k/2), Q.odd(k), True),
    (Q.integer(k/2 + half), Q.even(k), False),
    # gate2's: (-1)**x is odd by the Pow rows, a term of the half sum
    (Q.integer((-1)**x/2 - half), Q.integer(x), True),
    (Q.integer((-1)**x/2 + 5*half), Q.integer(x), True),
    # several terms; no 2**k limit (the hook stopped at 4 odd terms)
    (Q.integer(x/2 + y/2 + z/2), Q.odd(x) & Q.odd(y) & Q.odd(z), False),
    (Q.integer(x/2 + y/2 + z/2 + w/2 + n/2),
     Q.odd(x) & Q.odd(y) & Q.odd(z) & Q.odd(w) & Q.odd(n), False),
    (Q.integer(x/2 + y/2 + z/2 + w/2),
     Q.odd(x) & Q.odd(y) & Q.odd(z) & Q.odd(w), True),
    # parities not known: no answer
    (Q.integer(k/2 + half), Q.integer(k), None),
    (Q.integer(x/2 + y/2), Q.odd(x) & Q.integer(y), None),
])
def test_half_sums(query, assumptions, expected):
    assert ask(query, assumptions, engine=Engine(cache=DictCache())) is expected


def test_declared_integer_symbols():
    j = Symbol("j", odd=True)
    assert ask(Q.integer(j/2 + half)) is True
    assert ask(Q.integer(j/2)) is False
