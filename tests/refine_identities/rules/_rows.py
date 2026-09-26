"""Shared driver for the family row tests (``same``/``different``/``extra``/``neither``/``miss``)."""
from __future__ import annotations

import pytest
from sympy import simplify

from satrefine import refine
from satrefine.testing.harness import assert_refinement_valid


def ids(rows):
    return [f"{expr}|{assum}" for expr, assum, _, _ in rows]


def check_valid(expr, assumptions, values=None, relation=""):
    if relation.startswith("wrong"):
        pytest.xfail(relation)                # a documented engine defect; see needs/
    refined = refine(expr, assumptions)
    if refined != expr:
        assert_refinement_valid(expr, assumptions, refined, values=values)


def check_relation(expr, assumptions, team, relation):
    if relation.startswith("wrong"):          # a documented engine defect; see needs/
        try:
            refined = refine(expr, assumptions)
        except RecursionError:
            pytest.xfail(relation)
        if refined != expr and refined != team:
            pytest.xfail(relation)
    refined = refine(expr, assumptions)
    if relation.startswith("miss"):
        if refined == expr:
            pytest.xfail(relation)
        assert refined == team or simplify(refined - team) == 0, "the miss was fixed; update the row"
    elif relation == "same":
        assert refined == team or simplify(refined - team) == 0, refined
    elif relation == "different":
        assert refined != expr and refined != team, refined
    elif relation.startswith("extra"):
        assert refined != expr
    else:
        assert refined == expr, refined
