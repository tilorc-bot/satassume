"""The generated rule tables are up to date and used by the dispatcher."""
from __future__ import annotations

import importlib
import os

import pytest
from sympy import I, Q, log, pi, srepr, symbols, sympify

from satrefine.handlers_identities import _dispatch, _stages
from satrefine.handlers_identities._specialize import family_modules, generated_path

x = symbols("x")

GENERATED_GAPS: dict = {}   # rows where the live engine fires and generated mode does not, and why
# None: a generated table is a fast path, and the live rows run when it declines (the
# catalog has no rational-exponent, extended-sign or literal-4 profile, so the table
# alone misses log(x**(1/3)), log(1/x) for an extended-positive x and log(x**4) for an
# imaginary x; the dispatcher covers them).


def test_generated_table_covers_the_live_rows(monkeypatch):
    """Every row the live engine fires on, generated mode fires on with a
    numerically valid result, except the listed gaps."""
    from satrefine import refine
    from satrefine.harness import assert_refinement_valid
    from test_power_exp_log import IDS, ROWS  # same directory; pytest prepends it to sys.path
    misses, unexpected = [], []
    for (expr, assumptions, _team, _rel), rid in zip(ROWS, IDS):
        monkeypatch.setenv(_dispatch.MODE_ENV_VAR, "live")
        live = refine(expr, assumptions)
        monkeypatch.setenv(_dispatch.MODE_ENV_VAR, "generated")
        gen = refine(expr, assumptions)
        if gen != expr:
            assert_refinement_valid(expr, assumptions, gen)
        if live != expr and gen == expr:
            (unexpected if rid not in GENERATED_GAPS else misses).append(rid)
    assert not unexpected, unexpected
    assert set(misses) == set(GENERATED_GAPS), "update GENERATED_GAPS"


def test_generated_tables_are_registered_and_preferred(monkeypatch):
    from satrefine import refine
    assert "log" in _dispatch.generated_handlers
    monkeypatch.setenv(_dispatch.MODE_ENV_VAR, "generated")
    assert refine(log(x), Q.negative(x)) == log(-x) + I*pi
    monkeypatch.setenv(_dispatch.MODE_ENV_VAR, "live")
    assert refine(log(x), Q.negative(x)) == log(-x) + I*pi
    monkeypatch.setenv(_dispatch.MODE_ENV_VAR, "bogus")
    with pytest.raises(ValueError):
        refine(log(x), Q.negative(x))


@pytest.mark.slow
@pytest.mark.parametrize("module", family_modules(), ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_generated_module_is_up_to_date(module, monkeypatch):
    monkeypatch.setenv(_dispatch.MODE_ENV_VAR, "live")
    family = module.__name__.rsplit(".", 1)[-1]
    path = generated_path(family)
    assert path.exists(), f"run tools/refine_specialize.py --write --family {family}"
    committed = importlib.import_module(f"satrefine.handlers_identities.generated.{family}")
    # the fixpoint property: regenerating the family against the committed tables of
    # the others (its own keys live) gives its committed table (see _stages)
    rules, _keys, _verdicts = _stages.generate_one(module)
    # Compare as the module reads back: importing it evaluates each row, and
    # some generated left sides auto-evaluate (Abs(exp(z)) -> exp(re(z))).
    loaded = {tuple(sympify(srepr(part)) for part in rule) for rule in rules}
    assert set(committed.RULES) == loaded, "regenerate with tools/refine_specialize.py --write"


def test_stage_manifest_covers_every_generating_family():
    assert {_stages.family_name(m) for m in _stages.ordered_families()} == \
        {m.__name__.rsplit(".", 1)[-1] for m in family_modules()}
