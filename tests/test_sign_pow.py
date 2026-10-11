"""SIGN's ``POW`` map op (issue #149, T1 stage 2): the table against SymPy,
the template rows it replaces, and answers through the engine.

``b**e`` with a symbolic exponent is told to the SIGN theory
(``templates.core.sign_owns_pow``), and the sign rows of ``_POW_RULES`` at
``_POW_SIGN_ROWS`` are left out of its block.  Clause validity of the
reasons (every atom tuple, with pop/restore) is in
``tests/test_class_clauses.py`` (``POW`` is one of SIGN's ops there).
"""
from __future__ import annotations

import pytest
from sympy import I, Pow, Q, Rational, S, nan, oo, pi, sqrt, symbols, zoo

from satassume.engine import Engine
from satassume.knowledge.rules import DEF_LITS
from satassume.knowledge.templates.core import _POW_RULES, _POW_SIGN_ROWS, sign_owns_pow
from satassume.sympy_api import ask
from satassume.theories.sign import sign as sg
from satassume.theories.sign.sign_adapter import SignAdapter, over_cap

F = sg.F
_R = (S(1), S(2), Rational(1, 2), Rational(3, 2), sqrt(2), Rational(1, 7))


def _samples(a):
    if a < 9:
        sr, si = sg._fin(a)
        rs = [S(0)] if sr == 0 else [sr * r for r in _R]
        ims = [S(0)] if si == 0 else [si * r for r in _R[:3]]
        return [r + i * I for r in rs for i in ims]
    return {sg.PI: [oo], sg.NI: [-oo], sg.IN: [zoo, oo * I, -oo * I, oo * (1 + I)]}[a]


def _atom(v):
    """The atom of a SymPy value, ``NAN`` for nan, None if SymPy leaves it
    unevaluated (``(1 + I)**oo``)."""
    if v is nan:
        return sg.NAN
    if v.is_finite:
        try:
            x = complex(v.evalf(30))
        except (TypeError, ValueError):
            return None                 # (``zoo**(-1 - I)``: no number)

        def sgn(t):
            return 0 if abs(t) < 1e-20 else (1 if t > 0 else -1)
        return F(sgn(x.real), sgn(x.imag))
    if v == oo:
        return sg.PI
    if v == -oo:
        return sg.NI
    if v.is_infinite:
        return sg.IN
    return None


@pytest.mark.parametrize("a", range(12))
def test_pow_table_covers_sympy(a):
    """Every value SymPy gives at sample points of the atoms (the end
    points 1 and -1 included) lies in the table's set."""
    for e in range(12):
        tab = sg._pow_atoms(a, e)
        for x in _samples(a):
            for y in _samples(e):
                v = Pow(x, y)
                if v.is_Pow and v.args[1] == y and y.is_infinite:
                    # unevaluated (``(1 + I)**oo``): the cell must not claim
                    assert tab & sg.NANB, (a, e, x, y)
                    continue
                c = _atom(v)
                if c is None:
                    # unevaluated: no claim, or an infinity to a real power
                    # (``(oo*I)**(-sqrt(2))``, ``zoo**sqrt(2)``, which SymPy
                    # keeps): its modulus goes to 0 or oo
                    want = sg.INF if y.is_positive else 1 << sg.ZERO
                    assert tab & sg.NANB or (x.is_infinite and y.is_real
                                             and not tab & ~want), (a, e, x, y, v)
                    continue
                assert tab >> c & 1, (a, e, x, y, v, bin(tab))


def _pmask(p):
    A = SignAdapter
    if p in A.PREDS:
        return A.PRED_MASK[A.PREDS.index(p)]
    if p in DEF_LITS:
        return A.def_mask(DEF_LITS[p])
    return None


def _derives(prem, concl) -> bool:
    ms = [sg.ALL, sg.ALL, sg.ALL]
    for l in prem:
        if l[1] == 'commutative':       # (non-commutative queries are out of scope)
            continue
        m = _pmask(l[1])
        if m is None:
            return False
        ms[l[0]] &= m if len(l) == 2 else sg.ALL & ~m
    cm = _pmask(concl[1])
    if cm is None:
        return False
    if len(concl) == 3:
        cm = sg.ALL & ~cm
    newn, out = sg.SIGN.map_masks(sg.POW, ms[2], [ms[0], ms[1]])
    got = {2: newn, 0: out[0], 1: out[1]}[concl[0]]
    return bool(got) and not got & ~cm


def test_pow_sign_rows_are_derived():
    """The rows the templates leave out for a symbolic exponent are exactly
    the rows of ``_POW_RULES`` the map op derives from their premises."""
    derived = {i for i, (p, c) in enumerate(_POW_RULES) if _derives(p, c)}
    assert derived == set(_POW_SIGN_ROWS)


def test_ownership():
    x, y = symbols('x y')
    assert sign_owns_pow(x, y) and sign_owns_pow(x + 1, y)
    assert not sign_owns_pow(S(2), y) and not sign_owns_pow(x, sqrt(2))
    assert over_cap(x**y) and not over_cap(2**y) and not over_cap(x**2) and not over_cap(x**pi)
    assert SignAdapter.selects(x**y) and not SignAdapter.selects(x**3)


a, b, e = symbols('a b e')


def _ask(q, A=True):
    return ask(q, A, engine=Engine())


@pytest.mark.parametrize("q, A, want", [
    # the rows the theory now decides (base answers kept)
    (Q.positive(b**e), Q.positive(b) & Q.real(e), True),
    (Q.zero(b**e), Q.zero(b) & Q.positive(e), True),
    (Q.infinite(b**e), Q.zero(b) & Q.negative(e), True),
    (Q.positive(b**e), Q.zero(e), True),
    (Q.finite(b**e), Q.finite(b) & Q.finite(e) & Q.nonzero(b), True),
    (Q.zero(b**e), Q.infinite(b) & Q.negative(e), True),
    (Q.zero(b**e), Q.finite(b) & Q.negative(e), False),
    (Q.positive(a**2 * b**e), Q.positive(a) & Q.positive(b) & Q.real(e), True),
    (Q.positive(2**e), Q.real(e), True),
    # parity rows stay template rows
    (Q.positive(b**e), Q.negative(b) & Q.even(e), True),
    (Q.negative(b**e), Q.negative(b) & Q.odd(e), True),
    # backward through the map op
    (Q.negative(b), Q.negative(b**e) & Q.real(b) & Q.real(e), True),
    (Q.zero(b), Q.zero(b**e) & Q.finite(e) & Q.finite(b), True),
    (Q.nonzero(b), Q.nonzero(b**e) & Q.positive(e) & Q.real(b), True),
    (Q.finite(b), Q.infinite(b**e) & Q.positive(e), False),
    # no claim where a value may be nan (1**oo, 0**I)
    (Q.extended_real(b**e), Q.positive(b) & Q.positive_infinite(e), None),
    (Q.zero(b**e), Q.zero(b) & Q.imaginary(e), None),
    # integer bases, negative integer exponents (no b - 1, b + 1 nodes)
    (Q.integer(b**e), Q.even(b) & Q.integer(e) & Q.negative(e), False),
    (Q.integer(b**e), Q.prime(b) & Q.integer(e) & Q.negative(e), False),
    (Q.integer(b**e), Q.composite(b) & Q.integer(e) & Q.negative(e), False),
    (Q.integer(1/b), Q.prime(b), False),
    (Q.integer(b**-2), Q.composite(b), False),
    (Q.integer(b**-3), Q.even(b), False),
    (Q.prime(b**b), Q.negative(b), False),
    (Q.composite(b**e), Q.integer(b) & Q.integer(e) & Q.negative(e), False),
    (Q.odd(b), Q.integer(b**e) & Q.integer(b) & Q.integer(e) & Q.negative(e), True),
    (Q.integer(b**e), Q.odd(b) & Q.integer(e) & Q.negative(e), None),
])
def test_answers(q, A, want):
    assert _ask(q, A) is want
