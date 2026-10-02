"""Relations between numbers, and ``nan`` (nightly I5, package NA).

A relation whose two sides are numbers is the Boolean SymPy's own
``Relational`` gives it when that evaluates (``Eq(nan, 0)`` is False,
``Lt(0.5, 1)`` True; ``sympy_api._closed_relation``), so ``Q.lt(0.5, 1)``,
``Lt(0.5, 1)`` and ``True`` are one statement, as the I5 restatements
assume.  ``nan`` is no number and no extended real
(``templates.atoms._NAN_FACTS``), so ``Q.zero(nan)`` agrees with
``Q.eq(nan, 0)``.  The pinned repros are
``harness/repros/invariants/fixed/I5-nan-*`` and ``I5-float-*``.
"""
import pytest

sympy = pytest.importorskip("sympy")

from sympy import (E, Eq, Float, Ge, Gt, I, Le, Lt, Ne, Q, Rational, S, Symbol,  # noqa: E402
                   nan, oo, pi, sqrt, zoo)

from satassume.engine import Engine  # noqa: E402
from satassume.ref import ask_ref  # noqa: E402
from satassume.sympy_api import ask  # noqa: E402

r = Symbol("r", rational=True)
x = Symbol("x")

# (proposition, assumptions, answer); sympy.ask at the pin gives the same
# answer, except None for Q.zero(nan) (it leaves every fact of nan open)
CASES = [
    # the nightly findings (I5, seed 201)
    (Q.eq(nan, 0), True, False),
    (Q.eq(nan, 0), ~Q.antihermitian(nan), False),
    (Q.zero(nan), ~Q.antihermitian(nan), False),
    (Q.eq(nan, -1), True, False),
    (Q.lt(Float(0.5), 1), True, True),
    (Q.lt(Float(0.5), 1), Q.eq(r + 1, -1), True),
    # nan equals nothing, itself included
    (Q.eq(nan, nan), True, False),
    (Q.ne(nan, nan), True, True),
    (Q.ne(nan, 0), True, True),
    (Q.eq(nan, zoo), True, False),
    (Q.eq(nan, oo), True, False),
    # Floats compare by value, as SymPy's relationals do
    (Q.eq(Float(0.5), S.Half), True, True),
    (Q.le(Float(0.5), S.Half), True, True),
    (Q.ge(Float(2), 2), True, True),
    (Q.gt(Float(0.5), 1), True, False),
    # already decided before, unchanged
    (Q.eq(zoo, 1), True, False),
    (Q.eq(zoo, zoo), True, True),
    (Q.eq(oo, oo), True, True),
    (Q.lt(oo, 1), True, False),
    (Q.lt(-oo, oo), True, True),
    (Q.eq(I, 0), True, False),
    (Q.eq(pi + E, 6), True, False),
    (Q.lt(pi + E, 6), True, True),
]


@pytest.mark.parametrize("p, a, want", CASES, ids=[f"{p}|{a}" for p, a, _ in CASES])
def test_constant_relation_answers(p, a, want):
    assert ask(p, a, engine=Engine()) is want
    assert ask_ref(p, a) is want
    assert sympy.ask(p, a) in (want, None)       # None only for Q.zero(nan)


@pytest.mark.parametrize("p", [Q.eq(nan, 0), Q.lt(Float(0.5), 1), Q.eq(nan, -1),
                               Q.ne(nan, nan), Q.le(Float(0.5), S.Half)])
def test_predicate_form_agrees_with_sympy_relational(p):
    """``Q.rel(a, b)`` and the ``Relational`` SymPy folds it to answer alike,
    in the proposition and as an assumption."""
    rel = {"eq": Eq, "ne": Ne, "lt": Lt, "le": Le, "gt": Gt, "ge": Ge}[p.function.name](*p.arguments)
    assert rel in (S.true, S.false)
    assert ask(p, engine=Engine()) is bool(rel)
    q = Q.positive(x)
    if rel is S.true:
        assert ask(q, p & Q.positive(x), engine=Engine()) is True
    else:
        with pytest.raises(ValueError):
            ask(q, p, engine=Engine())


def test_other_numbers_are_left_to_the_engine():
    """Only ``Number`` atoms and ``nan`` sides are folded: SymPy compares
    other numbers by ``evalf``, which can be wrong (``atan(tan(r)**3)`` for
    ``r`` just past pi/2 is about -pi/2, but ``Lt(c, 0)`` is False;
    tests/test_lra_constants.py).  ``Eq(sqrt(2), 1.4142135623730951)`` is
    False in SymPy and stays None here (not in this package)."""
    from sympy import atan, tan
    rr = Rational(157079632679489661923132169163975144209858469968755291049, 10**56)
    c = atan(tan(rr)**3)
    assert Lt(c, 0) is S.false
    assert ask(Q.lt(c, 0), engine=Engine()) is not False
    assert ask(Q.eq(sqrt(2), Float(1.4142135623730951)), engine=Engine()) is None


def test_invalid_comparison_keeps_the_relation_atom():
    """``Lt(nan, 1)`` and ``Lt(I, 1)`` raise in SymPy; the atom stays and the
    order glue decides it (a side that is no extended real: False)."""
    assert ask(Q.lt(nan, 1), engine=Engine()) is False
    assert ask(Q.lt(I, 1), engine=Engine()) is False
    assert ask(Q.le(nan, 1), engine=Engine()) is False


NO_NUMBER = ["zero", "nonzero", "positive", "negative", "nonnegative", "nonpositive",
             "real", "extended_real", "complex", "rational", "integer", "even", "odd",
             "imaginary", "algebraic", "transcendental", "irrational", "noninteger",
             "extended_positive", "extended_negative", "extended_nonzero",
             "extended_nonnegative", "extended_nonpositive", "positive_infinite",
             "negative_infinite", "prime", "composite"]


@pytest.mark.parametrize("pred", NO_NUMBER)
def test_nan_is_no_number(pred):
    """Every predicate that implies a number or an extended real is False
    for ``nan`` (SymPy: None), as the relation glue already reads it."""
    p = getattr(Q, pred)(nan)
    assert ask(p, engine=Engine()) is False
    assert ask_ref(p) is False


@pytest.mark.parametrize("pred", ["finite", "infinite"])
def test_nan_finiteness_stays_open(pred):
    assert ask(getattr(Q, pred)(nan), engine=Engine()) is None
    assert ask(Q.commutative(nan), engine=Engine()) is True


def test_zero_and_eq_zero_agree_on_constants():
    """``zero(c)`` <-> ``eq(c, 0)`` (an I5 restatement) for the constants the
    harness pools use."""
    for c in [nan, zoo, oo, -oo, I, S.Zero, S.One, Rational(-1, 3), pi, E, Float(0.5),
              Float(0), sqrt(2), pi - pi, 1 + I]:
        assert ask(Q.zero(c), engine=Engine()) is ask(Q.eq(c, 0), engine=Engine()), c
