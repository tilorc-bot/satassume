"""CI-sized run of the invariant checkers I1-I7 (``harness/invariants.py``,
``harness/INVARIANTS.md``): about 10 s wall.

* every pinned case in ``harness/repros/invariants`` still violates its
  invariant (strict xfail: a fixed engine makes the test fail, so the
  case moves to ``fixed/``);
* planted defects: a checker must catch an engine patched to break its
  invariant, and must report nothing on an unpatched engine over a small
  stream (no false positive on the CI stream);
* the I1 clause-dropping patch really drops clauses and is undone.

The nightly run is ``python -m harness invariants --nightly --seeds 0-2``
(20 minutes, see ``harness/INVARIANTS.md``); ``INVARIANTS_SLOW=1`` runs a
2-minute slice of it here.
"""
import glob
import json
import os
import random

import pytest

sympy = pytest.importorskip("sympy")

from sympy import Q, Symbol  # noqa: E402

from harness.checker import Ask  # noqa: E402
from harness.generators import random_stream  # noqa: E402
from harness.invariants import (INVARIANTS, Unrelated, check_I1, check_I2, check_I4,  # noqa: E402
                                consistent, dropping_clauses, fresh_outcome, replay, run_stream)
from harness.state import preset  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = sorted(glob.glob(os.path.join(ROOT, "harness", "repros", "invariants", "*.json")))


@pytest.mark.parametrize("path", CASES, ids=[os.path.basename(p)[:-5] for p in CASES])
def test_pinned_case_still_violates(path):
    with open(path) as fh:
        d = json.load(fh)
    sev, base, other = replay(path)
    if sev is None:
        pytest.fail(f"{os.path.basename(path)} no longer violates {d['inv']}: base {base}, "
                    f"variant {other}; move it to harness/repros/invariants/fixed/")
    # engine defects, pinned until fixed
    pytest.xfail(f"{d['inv']} {sev}: base {base}, variant {other}")


def test_ci_stream_reports_only_what_replays():
    """Every checker runs; whatever is reported replays (no flaky report)."""
    from harness.invariants import evaluate
    cfg = preset("default")
    items = random_stream(0, 24, 3, profile="related")
    rep = run_stream(items, cfg, INVARIANTS, seed=0, source="ci", max_violations=3, shrink_them=False)
    assert all(rep.checked.get(i, 0) > 0 for i in INVARIANTS if i != "I3"), rep.checked
    for v in rep.violations:
        assert evaluate(v)[0] is not None, v.summary()


def test_ci_stream_finds_the_pinned_i2_family():
    """The I2 checker on the CI-sized transfer stream reports the pinned
    family (a fact about f(0) under zero(z), asked about f(z), decided only
    once an unrelated relation conjunct is present)."""
    cfg = preset("default")
    items = random_stream(3, 60, 4, profile="transfer")
    rep = run_stream(items, cfg, ("I2",), seed=3060, source="ci", max_violations=2, shrink_them=False)
    assert rep.violations, rep.to_json()
    assert all(v.severity == "depends" and v.base == "None" for v in rep.violations), \
        [v.summary() for v in rep.violations]


def test_drop_patch_drops_and_restores():
    from satassume.solver import Solver
    orig = Solver.add_clause
    x = Symbol("x", positive=True)
    stats = {}
    with dropping_clauses(seed=1, rate=0.5, stats=stats):
        fresh_outcome(Q.positive(x + 1), Q.positive(x), preset("default"))
    assert stats["dropped"] > 0 and stats["kept"] > 0
    assert Solver.add_clause is orig
    # rate 0 drops nothing and answers as the engine does
    with dropping_clauses(seed=1, rate=0.0, stats=stats):
        assert fresh_outcome(Q.positive(x + 1), Q.positive(x), preset("default")) == "True"
    assert stats["dropped"] == 0


def test_unrelated_conjuncts_are_consistent():
    u = Unrelated(random.Random(3), "t")
    cfg = preset("default")
    for n in (1, 3, 6):
        b = u.conjunction(n, depth=2)
        assert consistent(b, cfg) or fresh_outcome(Q.positive(Symbol("x")), b, cfg) != "ValueError", b


def test_planted_defects_are_caught(monkeypatch):
    import satassume.engine as eng_mod
    cfg = preset("default")
    x = Symbol("x", positive=True)
    p, a = Q.positive(x + 1), Q.positive(x)
    rng = random.Random(0)
    base = fresh_outcome(p, a, cfg)
    assert base == "True"
    assert check_I2(p, a, cfg, base, rng)[0] is None
    assert check_I4(p, a, cfg, base, rng)[0] is None

    real_ask = eng_mod.Engine.ask

    # I2: an engine that gives up when the set holds a fresh 'iu' symbol
    def ask_i2(self, proposition, assumptions=None):
        if assumptions is not None and "iu" in str(assumptions):
            return None
        return real_ask(self, proposition, assumptions)
    monkeypatch.setattr(eng_mod.Engine, "ask", ask_i2)
    sev, other, _ = check_I2(p, a, cfg, base, random.Random(0))
    assert sev == "depends" and other == "None"
    monkeypatch.setattr(eng_mod.Engine, "ask", real_ask)

    # I4: an engine that answers True for everything under a set
    def ask_i4(self, proposition, assumptions=None):
        return True
    monkeypatch.setattr(eng_mod.Engine, "ask", ask_i4)
    sev, other, _ = check_I4(p, a, cfg, "True", random.Random(0))
    assert sev == "wrong" and other == "True"
    monkeypatch.setattr(eng_mod.Engine, "ask", real_ask)

    # I1: an engine that answers the opposite while the dropping patch is
    # active (a subset of the clauses must never flip a definite answer)
    from satassume.solver import Solver
    real_int = Solver.add_internal

    def ask_i1(self, proposition, assumptions=None):
        r = real_ask(self, proposition, assumptions)
        return (not r) if Solver.add_internal is not real_int else r
    monkeypatch.setattr(eng_mod.Engine, "ask", ask_i1)
    sev, other, var = check_I1(p, a, cfg, base, random.Random(0), {"kind": "drop", "seed": 1, "rate": 0.0})
    assert sev == "wrong" and other == "False", (sev, other, var)


@pytest.mark.skipif(not os.environ.get("INVARIANTS_SLOW"), reason="INVARIANTS_SLOW=1: a 2-minute slice of the nightly")
def test_nightly_slice():
    from harness.__main__ import main
    rc = main(["invariants", "--nightly", "--minutes", "2", "--seeds", "0", "--fail-on", "unknown",
               "--out", os.path.join(ROOT, "harness-results", "invariants-slow"), "--quiet"])
    assert rc == 0
