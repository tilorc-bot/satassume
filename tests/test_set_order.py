"""Answers don't depend on the order satassume iterates sets in (issue #325):
the seeded order of harness/set_order.py, at the normal budget and a low one,
on a stream and on queries built to sit near the budget."""
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
    for seed in ("1", "2"):
        other = _run(tmp_path, seed, "--seed", seed, *what)
        assert set_order.moved(base, other)[0] == []
    assert base["census"]                   # the hook saw sets
    if what[1].startswith("harness"):       # and the comparison was not vacuous
        assert any(r[2] for r in base["rows"])
        assert {r[0] for r in base["rows"]} >= {"True", "None"}
        assert any(k.startswith("theories/lra/lra.py:") and c[1] for k, c in base["census"].items())
