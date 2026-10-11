"""The Add and Mul rows deleted as redundant (issue #149, R1a) stay
redundant.

``tools/minimise.py`` found rows of ``core._add_rules`` and ``MUL_TABLE``
whose clauses the other rows and the rule base (``rules.RULE_INSTANTIATED``,
instantiated on every object of a block) imply in every pattern; they were
deleted by hand.  The rows are kept here as they were, and for every
pattern of ``minimise.shapes()`` (Add and Mul of 1 to 5 arguments, with no,
one or two constants of every kind the guards and ``const_value`` tell
apart: integers, halves, thirds, floats, pi, E, I, the infinities, nan, ...)
each clause they gave is proved (z3) to follow from the clauses the
templates give now plus the rule base.  So each pattern is logically
equivalent to what it was before the deletion, and no answer can change; a
later edit that removes what a deleted row relied on fails here.

    PYTHONHASHSEED=0 python -m pytest -q tests/test_template_minimal.py
"""
import os
import sys

import pytest

pytest.importorskip("sympy")
pytest.importorskip("z3")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import minimise  # noqa: E402
from sympy import S  # noqa: E402

from satassume.knowledge.templates import core  # noqa: E402
from satassume.knowledge.templates._common import SIGN_FLIP, Rules, lits  # noqa: E402


def deleted_add_rows(n, consts):
    """The deleted rows of ``_add_rules``, as they were."""
    R = Rules()
    rule = R.rule
    N, A = n, range(n)
    sign = not core.sign_owns(False, n)
    closure = not core.closure_owns(False, n)
    if sign:
        # _ADD_CLOSED: extended_positive, extended_negative
        for pred in ('extended_positive', 'extended_negative'):
            rule(lits(A, pred), (N, pred, True))
        # sum of imaginaries is imaginary or zero
        rule(lits(A, 'imaginary'), [(N, 'imaginary', True), (N, 'zero', True)])
    for k in A:
        rest = [j for j in A if j != k]
        if sign:
            # imaginary term plus finite reals is not real
            rule([(k, 'imaginary', True), *lits(rest, 'real')], (N, 'extended_real', False))
            # _ADD_SUBTRACT: real
            if closure:
                rule([(N, 'real', True), *lits(rest, 'real')], (k, 'real', True))
            # a constant +oo (-oo) plus terms >= 0 (<= 0) or finite real
            if k in consts:
                for strict, nonstrict in core._STRICT:
                    signed = strict.replace('extended_', '') + '_infinite'
                    for cond in (nonstrict, 'real'):
                        rule([(k, signed, True), *lits(rest, cond)], (N, strict, True))
    return R.rules


def deleted_mul_rows(n, consts):
    """The deleted rows of ``MUL_TABLE``, as they were."""
    R = Rules()
    rule = R.rule
    N, A = n, range(n)
    sign = not core.sign_owns(True, n)
    closure = not core.closure_owns(True, n)
    if closure:     # closed: integer
        rule(lits(A, 'integer'), (N, 'integer', True))
    if sign:
        rule(lits(A, 'nonnegative'), (N, 'nonnegative', True))       # closed.sign
        rule([*lits(A, 'extended_real'), *lits(A, 'finite')], (N, 'extended_real', True))
        rule([*lits(A, 'extended_real'), *lits(A, 'zero', False)], (N, 'extended_real', True))
        if n % 2 == 0:  # all_nonpos.even
            rule(lits(A, 'nonpositive'), (N, 'nonnegative', True))
        if n <= core.MAX_ONEOUT:
            for k in A:
                rest = [j for j in A if j != k]
                rule([(k, 'nonpositive', True), *lits(rest, 'nonnegative')], (N, 'nonpositive', True))
                rule([(k, 'imaginary', True), *lits(rest, 'real'), *lits(rest, 'zero', False)],
                     (N, 'imaginary', True))
    if core._coeff({'n': n, 'consts': consts}):
        c = consts[0]
        for p in ('positive', 'negative', 'nonnegative', 'nonpositive', 'extended_positive',
                  'extended_negative', 'real', 'extended_real', 'finite'):
            rule([(N, p, True)], (1, SIGN_FLIP.get(p, p) if c.is_negative else p, True))
        if c is S.NegativeOne:
            for p in ('even', 'odd'):
                rule([(N, p, True)], (1, p, True))
    return R.rules


DELETED = {'add': deleted_add_rows, 'mul': deleted_mul_rows}


def unimplied(shape, extra=()):
    """The clauses of the deleted rows that the current pattern of
    ``shape`` (less the rows tagged ``extra``) and the rule base do not
    imply."""
    kind, n, consts = shape
    try:
        goals = minimise.basis_clauses(DELETED[kind](n, consts), consts)
        kept = minimise.basis_clauses([(p, c) for t, p, c in minimise.tagged_rules(kind, n, consts)
                                       if t[0] not in extra], consts)
    except ValueError:      # a constant contradicts a rule: no such node
        return []
    return minimise.checker(n + 1).unimplied(kept, goals)


def test_shapes_cover_the_constant_kinds():
    shapes = minimise.shapes()
    assert len(shapes) > 800
    assert {type(c).__name__ for s in shapes for c in s[2].values()} >= {
        'Zero', 'One', 'NegativeOne', 'Integer', 'Half', 'Rational', 'Float', 'Pi', 'Exp1',
        'ImaginaryUnit', 'Infinity', 'NegativeInfinity', 'ComplexInfinity', 'NaN'}


@pytest.mark.parametrize("kind", ["add", "mul"])
def test_deleted_rows_stay_implied(kind):
    bad = [(s, cl) for s in minimise.shapes() if s[0] == kind for cl in unimplied(s)]
    assert not bad, bad[:3]


def test_a_needed_row_is_seen():
    """Mutation check: without ``one_neg`` the deleted sign rows of
    ``x*y`` no longer follow."""
    assert unimplied(('mul', 2, {}), extra={'mul:one_neg'})
    assert unimplied(('add', 2, {}), extra={'add:%d' % line for line, v in minimise.LOOP_VARS.items()
                                            if v == ('strict', 'nonstrict')})
