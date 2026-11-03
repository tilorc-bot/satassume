"""Lazy relation links (prototype, ``relations.LAZY``): a link
``extended_positive(e) <-> gt(e, 0)`` etc. is built only when the model
disagrees with it (``Relations.unbuilt_disagree``), so every answer must
equal the eager build's.

Cause "lra_inf" (fuzz seed 424242, 12 queries; REPORT-lzr-exact.md): with a
term of ``e`` infinite in the model, the LRA check was skipped, and clauses 2
of the link atoms (``Relations._order_infinite``) went unchecked.  In #2210
the model took ``x = oo``, ``y = -oo`` and ``x + y - 3/2`` extended negative,
which ``e < 0`` with an up push from ``x`` excludes.

The suite under SA_LAZY=1 (REPORT-lzr-exact2.md) found four more causes,
each tested below: the reference (``ask_ref``) deferred links but never ran
the check (it now builds every link); an order adapter with no
``integer_form`` crashed the check (test_relations' dummy theory); an atom
LRA does not interpret (an ``oo`` summand) skipped clauses 2; and LRA's
point need not satisfy the integrality literals (lra.py, "Integrality").
"""
from __future__ import annotations

import pytest

sympy = pytest.importorskip("sympy")
from sympy import Dummy, Q, Rational, oo, pi, symbols

from satassume import DictCache, Engine
from satassume import relations as R
from satassume.ref import ask_ref
from satassume.sympy_api import ask

x, y = symbols("x y")
h = Rational(1, 2)

# fuzz 424242 query number, query, assumptions
CASES = [
    (52, Q.ne(3*x + 2*y, x + 2*y + 1), Q.gt(y, -1) & Q.lt(x, -1) & Q.ge(1 - y, -2*x - y)),
    (227, Q.ne(-y - 1, -x + y), Q.finite(x) & Q.gt(y, 1) & Q.eq(-2*x - 1, x + 1)),
    (509, Q.ge(x - y + 1, x + y + h), Q.ge(y, 1) & Q.le(x, pi/2) & Q.extended_positive(x + 2*y)),
    (646, Q.le(2*x + y - 1, -x + 2*y - 1), Q.ge(y, h) & Q.gt(x, 2) & Q.eq(x + h, 3*x + 1)),
    (1442, Q.ne(-2*x, 2*x + 2*y - 3*h), Q.ge(x, pi/2) & Q.gt(x + 2*y + 2, -2*x - y + 1)),
    (1742, Q.finite(-x - y), Q.finite(y) & Q.le(x, -1) & Q.eq(-2*x, 2*x - y - 1)),
    (1891, Q.ge(2*x + 2*y + 1, x + 2*y + 1), Q.gt(y, 0) & Q.lt(x, 0) & Q.eq(-x, 3*x + 2*y + 2)),
    (2010, Q.eq(2*y + h, 2 - x), Q.lt(y, h) & Q.gt(x, pi/2) & Q.eq(3*x - y, -2*x - y)),
    (2166, Q.ne(-x - y + 1, 3*x + 2*y - 3*h), Q.ge(y, 1) & Q.extended_positive(x - y + h)),
    (2210, Q.nonzero(x + h), Q.gt(x, 1) & Q.lt(y, 1) & Q.le(x + y - 3*h, h - y)),
    (2403, Q.finite(-x + y), Q.extended_real(y) & Q.ge(x, 0) & Q.ge(y, h) & Q.eq(x, -x + y)),
    (2866, Q.le(-3*h, 3*x + y), Q.le(y, -1) & Q.gt(x, h) & Q.extended_positive(x + y - 1)),
]


def _ask(prop, assum, lazy, monkeypatch):
    monkeypatch.setattr(R, "LAZY", lazy)
    return ask(prop, assum, Engine(cache=DictCache()))


@pytest.mark.parametrize("n,prop,assum", CASES, ids=[str(c[0]) for c in CASES])
def test_lazy_infinite_terms_match_eager(n, prop, assum, monkeypatch):
    eager = _ask(prop, assum, False, monkeypatch)
    assert eager is not None
    assert _ask(prop, assum, True, monkeypatch) is eager


def test_2210_by_hand(monkeypatch):
    # x = oo needs x + 2*y <= 2, so y = -oo, and then x + y - 3/2 is nan,
    # which no order atom holds: x is a finite real > 1, x + 1/2 > 3/2
    R.LSTATS.clear()
    assert _ask(Q.nonzero(x + h), Q.gt(x, 1) & Q.lt(y, 1) & Q.le(x + y - 3*h, h - y),
                True, monkeypatch) is True
    assert R.LSTATS.get("why lra_inf")


def test_reference_builds_every_link(monkeypatch):
    # ask_ref is the spec: it runs no lazy check, so it defers nothing
    monkeypatch.setattr(R, "LAZY", True)
    assert ask_ref(Q.negative(1 - x), Q.positive(x - 1)) is True


def test_integrality_point_is_no_model(monkeypatch):
    # LRA's point x = 1 ignores ~integer(x); with it, 2*x = 2 looked
    # integral.  3/4 < x < 5/4 and 2*x integral give x = 1.
    R.LSTATS.clear()
    p, a = Q.integer(x), Q.gt(x, Rational(3, 4)) & Q.lt(x, Rational(5, 4)) & Q.integer(2*x)
    assert _ask(p, a, False, monkeypatch) is True
    assert _ask(p, a, True, monkeypatch) is True


@pytest.mark.parametrize("lazy", [False, True])
def test_uninterpreted_atom_keeps_clauses_2(lazy, monkeypatch):
    # 0 < y - oo is refuted by clause 2 (-oo pushes the side down) though
    # LRA does not interpret it; a > b only starts the glue
    a, b = Dummy("a"), Dummy("b")
    A = Q.extended_nonnegative(y - oo) & Q.extended_positive(y - oo) & (a > b)
    R.LSTATS.clear()
    with pytest.raises(ValueError):
        _ask(Q.positive(y), A, lazy, monkeypatch)
    assert not lazy or R.LSTATS.get("why lra_inf")
