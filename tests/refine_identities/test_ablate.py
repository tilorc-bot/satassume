"""``satrefine/tools/refine_ablate.py``: in-process row removal and the gate comparison.

The ablation mutates the loaded tables, so every test restores them.
"""
from __future__ import annotations

import importlib

import pytest
from sympy import DiracDelta, Q, symbols

from satrefine import refine
from satrefine._upstream import handlers_dict

ablate_tool = importlib.import_module("satrefine.tools.refine_ablate")

x, y = symbols("x y")


@pytest.fixture
def restore_minmax():
    mod = importlib.import_module("satrefine.identities.rules.minmax_deltas")
    lists = {name: list(v) for name, v in vars(mod).items()
             if isinstance(v, list) and v and all(isinstance(r, tuple) for r in v)}
    tables = [t for key in ablate_tool.family_keys("minmax_deltas")
              for t in ablate_tool._table_parts(handlers_dict[key])]
    rows = [(t, list(t.rows)) for t in tables]
    yield mod
    for name, saved in lists.items():
        getattr(mod, name)[:] = saved
    for table, saved in rows:
        table.rows[:] = saved


def test_family_keys():
    assert ablate_tool.family_keys("minmax_deltas") == ["Max", "Min", "KroneckerDelta", "Heaviside", "DiracDelta"]
    assert set(ablate_tool.family_keys("integer_funcs")) == {"floor", "ceiling", "frac", "Mod", "Rem"}


def test_ablate_removes_the_row_from_handler_and_module(restore_minmax):
    mod = restore_minmax
    assert refine(DiracDelta(x), Q.positive(x)) == 0
    removed = ablate_tool.ablate("minmax_deltas", [0])       # DiracDelta off the origin
    assert "DiracDelta(x)" in removed[0]
    assert len(mod.RULES) == 6 and len(mod.DIRAC) == 2
    assert len(handlers_dict["DiracDelta"].rows) == 2
    assert refine(DiracDelta(x), Q.positive(x)) == DiracDelta(x)


def test_ablate_shared_row_goes_from_every_table():
    mod = importlib.import_module("satrefine.identities.rules.integer_funcs")
    saved = {name: list(getattr(mod, name)) for name in ("RULES", "FLOOR", "CEILING", "ROUNDING")}
    saved_rows = {key: list(handlers_dict[key].rows) for key in ("floor", "ceiling")}
    try:
        ablate_tool.ablate("integer_funcs", [0])              # the generic-head F(x) row
        assert len(handlers_dict["floor"].rows) == len(saved_rows["floor"]) - 1
        assert len(handlers_dict["ceiling"].rows) == len(saved_rows["ceiling"]) - 1
        assert len(mod.ROUNDING) == 0
    finally:
        for name, rows in saved.items():
            getattr(mod, name)[:] = rows
        for key, rows in saved_rows.items():
            handlers_dict[key].rows[:] = rows


def test_regressions():
    base = {"battery": {"1": ("same", "x"), "2": ("quiet", "y"), "3": ("miss", "z"), "4": ("other", "w")},
            "tests": {"t::a": "passed", "t::test_table_size": "passed", "t::b": "failed"},
            "soundness": {"7": {"head": "floor", "status": "fired", "result": "r", "expr": "e", "assumptions": "True"}}}
    same = {k: dict(v) for k, v in base.items()}
    assert ablate_tool.regressions(base, same, ["test_table_size"]) == {}
    now = {"battery": {"1": ("other", "x2"), "2": ("extra", "y2"), "3": ("quiet", "z"), "4": ("miss", "w")},
           "tests": {"t::a": "passed", "t::test_table_size": "failed", "t::b": "failed"},
           "soundness": {"7": {"head": "floor", "status": "fired", "result": "r2", "result_str": "r2",
                               "expr": "e", "assumptions": "True", "unsound": {}}}}
    lost = ablate_tool.regressions(base, now, ["test_table_size"])
    assert [s.split(":")[0] for s in lost["battery"]] == ["2", "4"]   # same -> other is fine
    assert "tests" not in lost and lost["_exempt_tests"] == ["t::test_table_size"]
    assert len(lost["soundness"]) == 1
    assert ablate_tool.fails(lost)
    assert not ablate_tool.fails({"_exempt_tests": ["t::test_table_size"]})
