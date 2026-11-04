"""Answers don't depend on the order satassume iterates sets in (issue #325):
the seeded order of harness/set_order.py, at the normal budget and a low one,
on a stream and on queries built to sit near the budget.  This is the small
version; the order shard of harness/campaign.sh runs the large one."""
import argparse
import builtins
import json
import os
import subprocess
import sys

import pytest

from harness import set_order

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def hook(monkeypatch):
    monkeypatch.setattr(builtins, "__set_order__", set_order._order, raising=False)
    monkeypatch.setattr(builtins, "__set_pop__", set_order._pop, raising=False)
    monkeypatch.setattr(set_order, "CENSUS", {})

    def run(source, seed):
        monkeypatch.setattr(set_order, "SEED", seed)
        env = {"s": set(range(20)), "nope": [3, 1, 2]}
        exec(set_order.rewrite(source, "<t>", "t"), env)
        return env["out"]
    return run


@pytest.mark.parametrize("source", [
    "out = []\nfor x in s:\n    out.append(x)",
    "out = [x for x in s]",
    "out = list(s)",
    "out = [*s]",
    "out = list(map(int, s))",
    "out = []\nt = set(s)\nwhile t:\n    out.append(t.pop())",
])
def test_every_way_of_reading_a_set(hook, source):
    orders = [hook(source, seed) for seed in (1, 2, 3)]
    assert all(sorted(o) == list(range(20)) for o in orders)
    assert len({tuple(o) for o in orders}) == 3
    assert hook(source, 1) == orders[0]     # the order is a function of seed and contents
    assert hook(source, None) == hook(source, None)


def test_only_sets_are_touched(hook):
    assert hook("out = [x for x in nope]", 1) == [3, 1, 2]
    assert hook("out = sorted(s)", 1) == list(range(20))
    assert list(set_order.CENSUS) == ["t:1"]


def _run(tmp_path, name, *args):
    out = tmp_path / f"{name}.json"
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONPATH=ROOT)
    subprocess.run([sys.executable, "-m", "harness.set_order", "run", str(out), *args],
                   check=True, cwd=ROOT, env=env, timeout=300)
    return json.loads(out.read_text())


@pytest.mark.parametrize("what", [
    ("--pairs", "harness.set_order:strips:0:30"),
    ("--pairs", "harness.set_order:strips:0:30", "--branch-budget", "4"),
    ("--stream", "0:40:3:related"),
    ("--stream", "0:40:3:related", "--discovery-budget", "5"),
])
def test_answers_do_not_move(tmp_path, what):
    base = _run(tmp_path, "off", *what)
    other = _run(tmp_path, "1", "--seed", "1", *what)
    assert set_order.moved(base, other)[0] == []
    assert other["reordered"] > 0
    assert any(not r[0].startswith("Error") for r in base["rows"])
    assert base["reordered"] == 0           # no seed, no change
    if what[1].startswith("harness"):       # and the comparison was not vacuous
        assert any(r[2] for r in base["rows"])
        assert {r[0] for r in base["rows"]} >= {"True", "None"}
        assert any(k.startswith("theories/lra/lra.py:") and c[1] for k, c in base["census"].items())


def test_the_comparison_can_fail(tmp_path):
    what = ("--pairs", "harness.set_order:strips:0:100", "--plant-bug")
    base, other = _run(tmp_path, "off", *what), _run(tmp_path, "1", "--seed", "1", *what)
    assert set_order.moved(base, other)[0]
    assert "plant:4" in base["census"]


def _rows(answer="True", clauses="c", ran_out=1, path="p"):
    return [[answer, clauses, ran_out, path], ["None", clauses, ran_out, path]]


_NO_QUERIES = {"rows": [], "generator": "TypeError()"}      # issue #326
_LEGS = ("off", "s2", "s3", "s2.h2")
_ALL_LEGS = {f"strips-1.bb2.{leg}": _NO_QUERIES for leg in _LEGS}


def _nightly(tmp_path, fault, profiles=""):
    def leg(out, name, hashseed, args):
        if name in fault:
            return fault[name]
        answer = "False" if name == "control.s2" else "True"
        return {"rows": _rows(answer), "reordered": 0 if name.endswith(".off") else 1}
    args = argparse.Namespace(seeds="1-1", queries=2, profiles=profiles, out=str(tmp_path), jobs=1, plant_bug=False)
    return set_order.nightly(args, leg=leg)


@pytest.mark.parametrize("fault, status", [
    ({}, 0),
    ({"strips-1.bb2.s2": {"rows": _rows("False"), "reordered": 1}}, 1),     # a moved answer
    ({"strips-1.normal.s2.h2": {"rows": _rows("None"), "reordered": 1}}, 1),
    ({"strips-1.db5.s2": None}, 1),                                        # a crashed leg
    ({"strips-1.bb2.off": None}, 1),
    ({"strips-1.normal.s2": {"rows": _rows(), "reordered": 0}}, 1),         # no reordering
    ({"strips-1.normal.off": {"rows": _rows(ran_out=0), "reordered": 0}}, 1),   # no budget hit
    ({"control.s2": {"rows": _rows(), "reordered": 1}}, 1),                 # the control moved nothing
    ({"control.off": None}, 1),
    ({"strips-1.bb2.s2": {"rows": _rows(clauses="d", path="q"), "reordered": 1}}, 0),   # the search only
    (_ALL_LEGS, 0),                                                         # issue #326 in every leg
    ({"strips-1.bb2.off": _NO_QUERIES}, 1),                                 # in the base only
    ({"strips-1.bb2.s3": _NO_QUERIES}, 1),                                  # in another leg only
    ({**_ALL_LEGS, "strips-1.bb2.s3": None}, 1),                            # and another crash beside it
])
def test_what_fails_the_nightly(tmp_path, fault, status):
    assert _nightly(tmp_path, fault) == status


def test_the_summary_counts_skipped_streams(tmp_path, capsys):
    fault = {f"declared-1.{budget}.{leg}": _NO_QUERIES for budget in set_order.BUDGETS for leg in _LEGS}
    assert _nightly(tmp_path, fault, profiles="declared") == 0
    assert "; 1 stream skipped for a generator crash; ok" in capsys.readouterr().err
