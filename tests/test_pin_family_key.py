"""The family key of an invariant finding (``harness/invariants.py``,
``family_key``; ``harness/INVARIANTS.md``, "Families, fingerprints and the
budget"): a pinned case covers only its own family.

Before the ``detail`` component, the key of an I5 case was (invariant,
severity, base, variant answer, variant kind, fingerprint), and one pin
covered unrelated bugs of the same answer shape.  The two reviewers'
examples (PRs #112 and #113) are reproduced here with a patched engine
answer: under the old key (the first six components) the unrelated
finding is the pin's, under the full key it is unknown.  Every pin on
``main`` is recorded (``python -m harness pins --write``) and matches its
own replay.
"""
import glob
import json
import os
import random
import shutil

import pytest

sympy = pytest.importorskip("sympy")

from sympy import Q, S, Symbol  # noqa: E402
from sympy.assumptions.assume import AppliedPredicate  # noqa: E402

import harness.invariants as inv  # noqa: E402
from harness.generators import random_stream  # noqa: E402
from harness.invariants import (Violation, _conjuncts, evaluate, family_key, restate,  # noqa: E402
                                restate_prop, rewrite_of, violation_from_json)
from harness.state import preset  # noqa: E402
from harness.sympy_io import to_srepr  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINS = sorted(glob.glob(os.path.join(ROOT, "harness", "repros", "invariants", "*.json")))


@pytest.fixture
def pin_dir(tmp_path, monkeypatch):
    """An empty pinned-case directory for the matcher (caches reset)."""
    d = tmp_path / "pins"
    d.mkdir()
    monkeypatch.setattr(inv, "PINNED_DIR", str(d))
    monkeypatch.setattr(inv, "_PINNED", {})
    monkeypatch.setattr(inv, "_PIN_META", {})
    monkeypatch.setattr(inv, "_PINNED_LOADED", False)
    return d


def _replayed(v: Violation) -> Violation:
    sev, base, other, var = evaluate(v)
    assert sev is not None, (base, other)
    v.severity, v.base, v.other, v.variant = sev, base, other, {k: x for k, x in var.items() if k != "rewrite"}
    return v


def _pin(d, stem, v: Violation):
    inv.write_case(v, str(d), stem)
    recs = inv.rerecord_pins(str(d), write=True)
    assert all(not r["gone"] for r in recs)
    return [r for r in recs if r["stem"] == stem][0]


# --------------------------------------------------------------------------
# every pin on main
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", PINS, ids=[os.path.basename(p)[:-5] for p in PINS])
def test_pin_is_recorded_and_matches_its_own_replay(path):
    rec = inv.pin_record(path)
    if rec["gone"]:
        pytest.skip("fixed: test_invariants.py::test_pinned_case_still_violates reports it")
    assert rec["recorded"] == {"rewrite": rec["rewrite"], "config_specific": rec["config_specific"]}, \
        f"{rec['stem']} is not recorded for the current family key: run python -m harness pins --write"
    with open(path) as fh:
        v = _replayed(violation_from_json(json.load(fh)))
    assert inv._known(v) == f"pinned:{rec['stem']}", (family_key(v), rec["key"])


def test_an_unrecorded_pin_matches_nothing_until_rerecorded(pin_dir):
    """A pin written before the full key is not matched loosely."""
    src = [p for p in PINS if "evaluated-by-sympy" in p]
    if not src:
        pytest.skip("the pin moved to fixed/")
    with open(src[0]) as fh:
        d = json.load(fh)
    d["variant"].pop("rewrite", None)
    d.pop("config_specific", None)
    with open(pin_dir / "old.json", "w") as fh:
        json.dump(d, fh)
    v = _replayed(violation_from_json(d))
    assert inv._known(v) is None
    inv.rerecord_pins(str(pin_dir), write=True)
    assert inv._known(_replayed(violation_from_json(d))) == "pinned:old"


# --------------------------------------------------------------------------
# the reviewers' examples
# --------------------------------------------------------------------------

def test_pr112_zero_eq_pin_does_not_cover_a_symbol(pin_dir, monkeypatch):
    """#112's pin ``I5-nan-zero-is-none-eq-zero-is-false``: ``zero(nan)``
    None, ``eq(nan, 0)`` False (key ``(I5, depends, None, False, prop,
    norel)``).  The reviewer injected an unsound fold of ``Q.eq(y, 0)`` to
    False for a symbol ``y``: the ``zero(y)`` / ``eq(y, 0)`` finding had
    the same key.  Both are simulated here (the relation folded unless
    relations are off, so that the ``norel`` probe makes it vanish)."""
    x, y = Symbol("x"), Symbol("y")
    orig = inv.fresh_outcome

    def patched(prop, assum, config):
        if config.relations != "none" and isinstance(prop, AppliedPredicate) and prop.function == Q.eq \
                and prop.arguments[1] == S.Zero and prop.arguments[0] in (S.NaN, y):
            return "False"
        return orig(prop, assum, config)
    monkeypatch.setattr(inv, "fresh_outcome", patched)
    cfg = preset("default")
    pin = Violation("I5", "depends", cfg, Q.zero(S.NaN), Q.positive(x),
                    {"kind": "prop", "prop": to_srepr(Q.eq(S.NaN, S.Zero))}, "None", "False")
    rec = _pin(pin_dir, "I5-nan-zero-is-none-eq-zero-is-false", _replayed(pin))
    assert rec["old_key"] == ("I5", "depends", "None", "False", ("prop",), "norel")
    assert rec["rewrite"] == ["zero-eq(zero)[nan]"] and rec["config_specific"] is False

    bug = _replayed(Violation("I5", "depends", cfg, Q.zero(y), Q.positive(x),
                              {"kind": "prop", "prop": to_srepr(Q.eq(y, S.Zero))}, "None", "False"))
    assert inv._known(bug) is None
    key = family_key(bug)
    assert key[:6] == rec["old_key"]                 # the old key: tagged as the pin
    assert key[6] == ("zero-eq(zero)[symbol]",)       # the term class tells them apart
    # the pin's own family is still recognised
    assert inv._known(_replayed(Violation("I5", "depends", cfg, Q.zero(S.NaN), Q.positive(x),
                                          {"kind": "prop", "prop": to_srepr(Q.eq(S.NaN, S.Zero))},
                                          "None", "False"))) == "pinned:I5-nan-zero-is-none-eq-zero-is-false"


def test_pr113_shift_pin_does_not_cover_a_term_form(pin_dir, monkeypatch):
    """#113's pin ``I5-shifted-equality-notransfer``: ``eq(x + 1, 1)``
    restated ``eq(x + 3/2, 3/2)`` loses True under ``notransfer`` (key
    ``(I5, depends, True, None, restate, -)``, the most common I5 shape).
    In a run it absorbed a ``zero(t)`` / ``zero(-t)`` finding of another
    cause; simulated here by an engine that loses ``zero(-t)``."""
    x, t = Symbol("x"), Symbol("t")
    orig = inv.fresh_outcome

    def patched(prop, assum, config):
        if assum == Q.zero(-t):
            return "None"
        return orig(prop, assum, config)
    monkeypatch.setattr(inv, "fresh_outcome", patched)
    cfg = preset("notransfer")
    e = Q.eq(x + 1, 1)
    pin = Violation("I5", "depends", cfg, e, e,
                    {"kind": "restate", "parts": [to_srepr(Q.eq(x + S(3) / 2, S(3) / 2))],
                     "assum": to_srepr(Q.eq(x + S(3) / 2, S(3) / 2))}, "True", "None")
    rec = _pin(pin_dir, "I5-shifted-equality-notransfer", _replayed(pin))
    assert rec["old_key"] == ("I5", "depends", "True", "None", ("restate",), "-")
    assert rec["rewrite"] == ["shift-relation(eq)[expr,number]"]
    assert rec["config_specific"] is True            # transfer supplies real(x) under default

    other = _replayed(Violation("I5", "depends", cfg, Q.zero(t), Q.zero(t),
                                {"kind": "restate", "parts": [to_srepr(Q.zero(-t))],
                                 "assum": to_srepr(Q.zero(-t))}, "True", "None"))
    assert family_key(other)[:6] == rec["old_key"]
    assert family_key(other)[6] == ("term-form:neg(zero)[symbol]",)
    assert inv._known(other) is None
    assert inv._known(_replayed(Violation("I5", "depends", cfg, e, e, dict(pin.variant), "True", "None"))) \
        == "pinned:I5-shifted-equality-notransfer"
    # the same rewrite under another configuration is not the config-specific pin
    elsewhere = _replayed(Violation("I5", "depends", preset("lean"), Q.zero(t), Q.zero(t),
                                    dict(other.variant), "True", "None"))
    assert inv._known(elsewhere) is None


# --------------------------------------------------------------------------
# the rewrite classifier
# --------------------------------------------------------------------------

def test_rewrite_names():
    x, y = Symbol("x"), Symbol("y")
    r = Symbol("r", real=True)
    assert rewrite_of(Q.zero(x), Q.eq(x, 0)) == ["zero-eq(zero)[symbol]"]
    assert rewrite_of(Q.eq(x + 1, 1), Q.eq(x + 3, 3)) == ["?(eq)"]          # not a restate rule
    assert rewrite_of(Q.eq(x + 1, 1), Q.eq(x + S(3) / 2, S(3) / 2)) == ["shift-relation(eq)[expr,number]"]
    assert rewrite_of(Q.zero(x), Q.zero(-x)) == ["term-form:neg(zero)[symbol]"]
    assert rewrite_of(Q.positive(x), Q.negative(-x)) == ["sign-flip(positive)[symbol]"]
    assert rewrite_of(Q.lt(x, y), Q.gt(y, x)) == ["swap(lt)[symbol]"]
    assert rewrite_of(Q.positive(r), Q.gt(r, 0)) == ["given(positive)[symbol]"]
    assert rewrite_of(Q.nonnegative(x), Q.zero(x) | Q.positive(x)) == ["split(nonnegative)[symbol]"]
    assert sorted(rewrite_of(~(Q.zero(x) & Q.lt(x, y)), ~Q.eq(x, 0) | ~Q.gt(y, x))) == \
        ["de-morgan", "swap(lt)[symbol]", "zero-eq(zero)[symbol]"]


@pytest.mark.parametrize("profile", ["base", "related", "relational", "transfer", "deep"])
def test_every_restatement_is_recognised(profile):
    """``restate`` and ``restate_prop`` over a generated stream: the
    outputs are named by ``rewrite_of``, so the key is the rule that
    produced the variant.  A compound restatement SymPy flattens or
    evaluates beyond the structure of ``restate`` is ``?(<head>)`` (still a
    function of the case, so a key; 23 of 6,314 over every profile, 3
    seeds): at most 1 %."""
    from harness.checker import Ask
    rng = random.Random(7)
    asks = [it for it in random_stream(5, 40, 4, profile=profile) if isinstance(it, Ask)]
    seen = bad = 0
    for a in asks:
        for c in _conjuncts(a.assum):
            for _ in range(3):
                n = restate(c, random.Random(rng.randrange(1 << 30)))
                if n == c:
                    continue
                seen += 1
                if any(d.startswith("?") for d in rewrite_of(c, n)):
                    bad += 1
                    print("unrecognised", c, "->", n)
        q = restate_prop(a.prop, random.Random(rng.randrange(1 << 30)))
        if q != a.prop:
            seen += 1
            if any(d.startswith("?") for d in rewrite_of(a.prop, q)):
                bad += 1
                print("unrecognised", a.prop, "->", q)
    assert seen > 20
    assert bad <= seen // 100, (bad, seen)
