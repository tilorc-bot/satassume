"""The table of values at infinities, nan and poles (docs/special-values.md).

Each row has examples; the table decides their value, not SymPy (#247).
Where SymPy's evaluation differs, the example is listed in
``DISAGREES`` with the argument for the table's value.  A new
disagreement (another SymPy version, a new row) fails
``test_row_examples`` until it is triaged with an argument: the row is
fixed, or the example joins ``DISAGREES``.  Never by taking SymPy's value
as right.
"""
import pytest

sympy = pytest.importorskip("sympy")
from sympy import (Abs, Float, I, Pow, Q, Rational, S, Symbol, exp, log, nan, oo,  # noqa: E402
                   sin, sqrt, symbols, zoo)

from satassume.sympy_api import ask  # noqa: E402

from _special_values import directed, evaluate, facts, kind, same_value  # noqa: E402

x, y, z = symbols("x y z")
h = S.Half

# (row, expression, point, the table's value)
ROWS = [
    ("N1", sin(x), {x: nan}, nan),
    ("N1", x + 1, {x: nan}, nan),
    ("A1", x + 1, {x: oo}, oo),
    ("A1", x + I, {x: oo}, oo),
    ("A1", x + I, {x: -oo}, -oo),
    ("A2", x + y, {x: oo, y: oo}, oo),
    ("A2", x + y, {x: oo, y: -oo}, nan),
    ("A2", I*x + I*y + z, {x: oo, y: -oo, z: oo}, nan),
    ("A2", I*x + y + z, {x: oo, y: oo, z: -oo}, nan),
    ("A3", x + 1, {x: zoo}, zoo),
    ("A3", x + y, {x: zoo, y: oo}, nan),
    ("A3", x + y, {x: zoo, y: zoo}, nan),
    ("M1", x*y, {x: 0, y: oo}, nan),
    ("M1", x*y, {x: 0, y: zoo}, nan),
    ("M2", x*y, {x: -2, y: oo}, -oo),
    ("M2", x*y, {x: -oo, y: -oo}, oo),
    ("M2", x*y, {x: I, y: oo}, directed(I)),
    ("M2", x*y, {x: 1 + I, y: oo}, directed(1 + I)),
    ("M3", x*y, {x: zoo, y: oo}, zoo),
    ("M3", x*y, {x: 2, y: zoo}, zoo),
    ("P1", 1/x, {x: 0}, zoo),
    ("P1", x**Rational(-1, 2), {x: 0}, zoo),
    ("P2", x**y, {x: oo, y: 0}, 1),
    ("P2", x**y, {x: zoo, y: 0}, 1),
    ("P2", x**y, {x: zoo, y: Float(0)}, 1),
    ("P3", x**2, {x: -oo}, oo),
    ("P3", x**3, {x: -oo}, -oo),
    ("P3", sqrt(x), {x: -oo}, directed(I)),
    ("P3", 1/x, {x: oo}, 0),
    ("P3", x**2, {x: zoo}, zoo),
    ("P4", 2**y, {y: oo}, oo),
    ("P4", 2**y, {y: -oo}, 0),
    ("P4", h**y, {y: -oo}, oo),
    ("P4", (-2)**y, {y: oo}, zoo),
    ("P4", (-2)**y, {y: -oo}, 0),
    ("P4", Rational(-3, 2)**y, {y: -oo}, 0),
    ("P4", (-h)**y, {y: oo}, 0),
    ("P4", (-h)**y, {y: -oo}, zoo),
    ("P4", (2*I)**y, {y: oo}, zoo),
    ("P4", x**y, {x: 0, y: oo}, 0),
    ("P4", x**y, {x: 0, y: -oo}, zoo),
    ("P5", Pow(1, y, evaluate=False), {y: oo}, nan),
    ("P5", (-1)**y, {y: oo}, nan),
    ("P5", I**y, {y: oo}, nan),
    ("P5", x**y, {x: Float(1), y: oo}, nan),
    ("P5", x**y, {x: Float(-1), y: -oo}, nan),
    ("P6", x**y, {x: oo, y: oo}, oo),
    ("P6", x**y, {x: oo, y: -oo}, 0),
    ("P6", x**y, {x: -oo, y: oo}, zoo),
    ("P6", x**y, {x: zoo, y: oo}, zoo),
    ("P6", x**y, {x: zoo, y: -oo}, 0),
    ("F1", exp(x), {x: oo}, oo),
    ("F1", exp(x), {x: -oo}, 0),
    ("F1", exp(x), {x: zoo}, nan),
    ("F1", exp(I*x), {x: oo}, nan),
    ("F1", exp((1 + I)*x), {x: oo}, zoo),
    ("F1", exp((-1 + I)*x), {x: oo}, 0),
    ("F2", log(x), {x: 0}, zoo),
    ("F2", log(x), {x: oo}, oo),
    ("F2", log(x), {x: -oo}, oo),
    ("F2", log(x), {x: zoo}, zoo),
    ("F3", Abs(x), {x: -oo}, oo),
    ("F3", Abs(x), {x: zoo}, oo),
    ("F3", Abs(I*x), {x: oo}, oo),
]

# the examples where SymPy's evaluation differs from the table, and why
# the table's value is taken (docs/special-values.md)
DISAGREES = {
    (str(x + I), "{x: oo}"): "A1: a finite summand does not move an infinity "
        "(directed infinities); SymPy keeps oo + I, which it calls no extended real",
    (str(x + I), "{x: -oo}"): "A1, as oo + I",
    (str(x**y), "{x: zoo, y: 0.0}"): "P2: b**0 = 1; 0.0 is the number 0 (SymPy: "
        "zoo**0 = 1 but zoo**0.0 = nan)",
    (str(Rational(-3, 2)**y), "{y: -oo}"): "P4: |(-3/2)**t| = (3/2)**t -> 0 as "
        "t -> -oo; SymPy gives (-2)**(-oo) = 0 but (-3/2)**(-oo) = nan (#240)",
    (str((-h)**y), "{y: -oo}"): "P4: |(-1/2)**t| = 2**(-t) -> oo as t -> -oo, the "
        "argument turns: zoo; SymPy gives (-2)**oo = zoo but (-1/2)**(-oo) = nan "
        "(#97 P6)",
    (str((2*I)**y), "{y: oo}"): "P4: |(2I)**t| = 2**t -> oo, the argument turns: zoo "
        "(SymPy leaves it unevaluated)",
    (str(I**y), "{y: oo}"): "P5: I**t turns on the unit circle, no limit (SymPy "
        "leaves it unevaluated)",
    (str(x**y), "{x: -oo, y: oo}"): "P6: |(-s)**t| = s**t -> oo, the argument "
        "turns: zoo, as (-2)**oo = zoo in SymPy; SymPy gives nan",
    (str(x**y), "{x: zoo, y: oo}"): "P6: |b**t| -> oo for |b| -> oo, t -> oo: zoo; "
        "SymPy gives zoo**oo = 0, but zoo**2 = zoo and 2**oo = oo",
}


def _key(expr, point):
    return str(expr), str(point)


def _agree(t, s):
    kt, ks = kind(t), kind(s)
    if kt == "nan" or ks == "nan":
        return kt == ks
    return ks is not None and kt == ks and same_value(t, s) is True


@pytest.mark.parametrize("row, expr, point, value", ROWS,
                         ids=[f"{r[0]}-{r[1]}-{r[2]}" for r in ROWS])
def test_row_examples(row, expr, point, value):
    v, source = evaluate(expr, point)
    assert source == "table", (v, source)
    assert _agree(v, S(value)), (v, value)
    sympy_value = expr.xreplace(point)
    key = _key(expr, point)
    if _agree(v, sympy_value):
        assert key not in DISAGREES, f"SymPy now agrees: {sympy_value}"
    else:
        assert key in DISAGREES, (
            f"SymPy gives {sympy_value}, the table {v} (row {row}): a "
            f"candidate; triage it with an argument (#247)")


def test_disagreements_are_row_examples():
    assert set(DISAGREES) <= {_key(e, p) for _, e, p, _ in ROWS}


VOCAB = ['algebraic', 'antihermitian', 'complex', 'composite', 'even',
         'extended_negative', 'extended_nonnegative', 'extended_nonpositive',
         'extended_nonzero', 'extended_positive', 'extended_real', 'finite',
         'hermitian', 'imaginary', 'infinite', 'integer', 'irrational', 'negative',
         'noninteger', 'nonnegative', 'nonpositive', 'nonzero', 'odd', 'positive',
         'prime', 'rational', 'real', 'transcendental', 'zero']


@pytest.mark.parametrize("v", [oo, -oo, zoo, directed(I), directed(1 - I), -oo*I], ids=str)
def test_facts_agree_with_sympy_where_it_decides(v):
    """V1-V3: the oracles that read ``is_*`` of a table value
    (``point_value``) get the table's facts."""
    for p in VOCAB:
        mine, theirs = facts(v, p), getattr(v, "is_" + p)
        assert mine is not None
        assert theirs is None or theirs == mine, (v, p, mine, theirs)


def test_nan_facts():
    assert facts(nan, "finite") is None and facts(nan, "infinite") is None
    assert not any(facts(nan, p) for p in VOCAB)


def test_candidate_where_no_row():
    v, source = evaluate(sin(x), {x: oo})
    assert source == "candidate"            # SymPy's AccumBounds(-1, 1)
    v, source = evaluate(x + y, {x: oo, y: oo*I})
    assert source == "candidate"            # two directions: no row


def test_issue_220_eq_of_minus_oo_and_oo_plus_I():
    """#205/#220: at x = -oo, y = I the term -x + y is oo (A1), which is
    not -oo, so the oracle no longer leaves eq(-oo, -x + y) free."""
    from test_verify_soundness import X, Y, _eq, _value, refute, VALUES_2
    a, _ = _value(-X + Y, {X: -oo, Y: I})
    assert a is oo and _eq(-oo, a) is False
    prop = ("r", "gt", X, Y, "Q")
    assum = ("and", ("r", "lt", X, -X, "Q"), ("r", "eq", X, -X + Y, "Q"))
    assert refute(prop, assum, True, {X: VALUES_2, Y: VALUES_2}) is None
    assert ask(Q.gt(X, Y), Q.lt(X, -X) & Q.eq(X, -X + Y)) is True


def test_issue_209_lt_is_irreflexive():
    """#209: a < a is false for every value: an extended real is not below
    itself, and an order relation is false where a side is no extended
    real (relations.py, "Meaning")."""
    from test_verify_soundness import _lt, refute
    c = Symbol("c")
    assert _lt((1 + I)**2, (1 + I)**2) is False
    prop, assum = ("r", "lt", c**2, c**2, "Q"), ("not", ("r", "lt", c, c, "Q"))
    assert refute(prop, assum, False, {c: [S.Zero, S.One, I, 1 + I, S(-1)]}) is None
    assert ask(Q.lt(c**2, c**2), ~Q.lt(c, c)) is False


def test_issue_240_negative_base_to_minus_infinity():
    """#240 and #97 P6: (-3/2)**(-oo) is 0 and (-1/2)**(-oo) is zoo (P4),
    as satassume answers; SymPy's nan is not the value."""
    assert evaluate(Rational(-3, 2)**y, {y: -oo})[0] == 0
    assert evaluate((-h)**y, {y: -oo})[0] is zoo
    assert ask(Q.zero(Rational(-3, 2)**y), Q.negative_infinite(y)) is True
    assert ask(Q.finite(Rational(-3, 2)**y), Q.negative_infinite(y)) is True
    assert ask(Q.infinite((-h)**y), Q.negative_infinite(y)) is True
