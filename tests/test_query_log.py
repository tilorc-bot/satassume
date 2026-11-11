"""``tools/query_log.py`` replays a stream with its wrappers installed.

Its ``_context_session`` wrapper must take what ``Engine._context_session``
takes: the engine calls ``self._context_session(assumptions, proposition)``,
so a wrapper of one argument raised ``TypeError`` on every contextual query
within the budget.
"""
import importlib.util
import json
from pathlib import Path

import pytest
from sympy import Q, Symbol

from satassume import Engine
from satassume import sympy_api as api
from satassume.engine import Session
from satassume.sat.solver import Solver

TOOL = Path(__file__).resolve().parent.parent / "tools" / "query_log.py"

# every attribute install() replaces, restored after each test
PATCHED = [(api, "_ask"),
           (Engine, "is_"), (Engine, "_is_custom"), (Engine, "ask"),
           (Engine, "_context_session"), (Engine, "_fresh_session"),
           (Session, "query_literal"), (Session, "escalate"),
           (Solver, "entails"), (Solver, "_solve")]


@pytest.fixture
def query_log(monkeypatch):
    for owner, name in PATCHED:
        monkeypatch.setattr(owner, name, getattr(owner, name))
    monkeypatch.setattr(api, "_engine", Engine())
    spec = importlib.util.spec_from_file_location("query_log_under_test", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)            # a fresh module: not installed yet
    return mod


def test_replay_reaches_the_context_session_wrapper(query_log, tmp_path):
    x, y = Symbol("x_qlog"), Symbol("y_qlog")
    stream = [(Q.positive(x + y), Q.positive(x) & Q.positive(y), True)]
    out = tmp_path / "log.jsonl"
    _, bad = query_log.run(stream, str(out))
    assert bad == []
    (rec,) = [json.loads(line) for line in out.read_text().splitlines()]
    assert rec["outcome"] is True
    assert rec["session_new"] == "first"        # recorded by the wrapper
    assert "session_error" not in rec


def test_wrapper_forwards_proposition_by_keyword_or_position(query_log, monkeypatch):
    seen = []
    monkeypatch.setattr(Engine, "_context_session",
                        lambda self, assumptions, proposition=None:
                        seen.append((assumptions, proposition)) or ("s", []))
    query_log.install()
    eng = Engine()
    assert eng._context_session("A", proposition="p") == ("s", [])
    assert eng._context_session("A", "p") == ("s", [])
    assert eng._context_session("A") == ("s", [])
    assert seen == [("A", "p"), ("A", "p"), ("A", None)]
