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

from sympy import And, Not, Q, S, Symbol  # noqa: E402

from harness.checker import Ask  # noqa: E402
from harness.generators import random_stream  # noqa: E402
from harness.sympy_io import to_srepr
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
    # both directions of the family: None -> definite, and definite -> None;
    # since round 4 also the Undecided crash (an unsettled constant in a relation)
    assert all(v.severity in ("depends", "crash") for v in rep.violations), [v.summary() for v in rep.violations]
    assert any(v.severity == "depends" for v in rep.violations), [v.summary() for v in rep.violations]


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
    # a fixed unrelated conjunct (the generator's own variants reach the
    # engine's real I2 families, e.g. a closed relation in the set)
    fixed = {"kind": "unrelated", "extra": to_srepr(Q.positive(Symbol("iuu1")))}
    assert check_I2(p, a, cfg, base, rng, dict(fixed))[0] is None
    assert check_I4(p, a, cfg, base, rng)[0] is None

    real_ask = eng_mod.Engine.ask

    # I2: an engine that gives up when anything is added to the set (the
    # unrelated material may be a closed fact with no fresh symbol in it)
    def ask_i2(self, proposition, assumptions=None):
        if assumptions is not None and assumptions != a:
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


def test_negation_is_not_sympys_rewrite():
    """Round-1 false positives: ``Not(x >= a)`` is rewritten by SymPy to
    ``x < a``, which is not the negation when ``x`` can be non-real.  The
    checkers negate with ``evaluate=False`` and the negation survives the
    srepr round trip, renaming and restatement."""
    from sympy import Ge, Gt, Not, Rational, S, oo
    from harness.invariants import negate, rename, restate
    from harness.sympy_io import from_srepr, to_srepr
    nP = Symbol("nP", positive=False)
    z = Symbol("z")
    for p in (Ge(-nP, Rational(-1, 3)), Gt(z / 2, oo), Ge(z, oo)):
        n = negate(p)
        assert isinstance(n, Not) and n.args[0] == p
        assert from_srepr(to_srepr(n)) == n
        (r,), _, _ = rename([n], random.Random(0))
        assert isinstance(r, Not)
        assert isinstance(restate(n, random.Random(0), 1.0), Not)
    assert negate(negate(Q.positive(z))) == Q.positive(z)
    assert negate(S.true) is S.false
    # the round-1 cases: consistent, and no I4 report
    cfg = preset("default")
    for p, a in ((Ge(-nP, Rational(-1, 3)), Q.complex(nP)), (Ge(z, oo), Q.negative_infinite(z**2 * (z + 1)))):
        base = fresh_outcome(p, a, cfg)
        assert check_I4(p, a, cfg, base, random.Random(0))[0] is None, (p, a, base)


def test_syntax_form_keeps_the_models():
    from sympy import And
    from harness.invariants import syntax_form

    def _leaves(e):
        return [x for a in e.args for x in _leaves(a)] if isinstance(e, And) else [e]
    from harness.sympy_io import from_srepr, to_srepr
    x, y = Symbol("x"), Symbol("y")
    cs = [Q.positive(x), Q.real(y), Q.zero(y - 1)]
    for seed in range(6):
        f = syntax_form(cs, random.Random(seed))
        assert set(_leaves(f)) == set(cs)                   # the same conjuncts, whatever the nesting
        assert from_srepr(to_srepr(f)) == f                 # the spelling survives srepr


def test_restatements_agree_on_values():
    """Every restatement of a predicate or relation conjunct has the truth
    of the original at sample values (SymPy's own ``ask`` on closed terms:
    integers, rationals, floats, irrationals, imaginary, infinities)."""
    from sympy import I as _I, Rational, Float, S, pi as _pi, sqrt as _sqrt, oo, zoo, ask as sask
    from sympy.logic.boolalg import BooleanAtom
    from harness.invariants import restate, VALUE_PREDS
    x, y = Symbol("x"), Symbol("y")
    values = [S(0), S(1), S(-2), S(3), S(4), S(7), Rational(1, 2), Rational(-3, 2), Float(2.5),
              _sqrt(2), -_pi, _I, 1 + _I, 2 * _I, oo, -oo, zoo]
    rng = random.Random(5)
    rels = [Q.lt(x, y), Q.le(x, y), Q.gt(x, y), Q.ge(x, y), Q.eq(x, y), Q.ne(x, y), Q.lt(x, 2), Q.eq(x, 0)]
    preds = [getattr(Q, n)(x) for n in VALUE_PREDS]
    checked = 0
    for conj in rels + preds:
        for _ in range(5):
            other = restate(conj, rng, p=0.9)
            if other == conj:
                continue
            for _ in range(6):
                vx, vy = rng.choice(values), rng.choice(values)
                try:
                    a = sask(conj.xreplace({x: vx, y: vy}))
                    b = sask(other.xreplace({x: vx, y: vy}))
                except Exception:  # noqa: BLE001 - SymPy refused the value (nan, ...)
                    continue
                if a is None or b is None:
                    continue
                assert a == b, (conj, other, vx, vy, a, b)
                checked += 1
    assert checked > 80


def test_given_restatements_agree_on_declared_values():
    """Every equivalence of ``_GIVEN`` (and the relation complement under
    real sides) agrees with the original at every pool value admissible
    for the declared symbol, under SymPy's own ``ask`` and the harness's
    conservative evaluator."""
    from sympy import ask as sask
    from harness.invariants import _GIVEN, restate_given
    from harness.models import POOL, admissible, evaluate_at
    checked = 0
    for kw in ({"real": True}, {"integer": True}, {"finite": True}, {"extended_real": True},
               {"positive": True}, {"integer": True, "nonnegative": True}):
        x, y = Symbol("x", **kw), Symbol("y", **kw)
        vals = [v for v in POOL if admissible(x, v)]
        assert vals, kw
        conjs = [f(x) for f in _GIVEN] + [Not(r(x, y), evaluate=False) for r in (Q.lt, Q.le, Q.gt, Q.ge)]
        for conj in conjs:
            seen = set()
            for _ in range(8):
                other = restate_given(conj, random.Random(len(seen)))
                if other is None or other in seen:
                    continue
                seen.add(other)
                unary = y not in conj.free_symbols
                for vx in vals:
                    for vy in (vals if not unary else [S.Zero]):
                        subs = {x: vx, y: vy}
                        a, b = evaluate_at(conj, subs), evaluate_at(other, subs)
                        if a is not None and b is not None:
                            assert a == b, (conj, other, vx, vy, a, b)
                            checked += 1
                        if not unary:
                            continue          # SymPy's ask on every pair is slow; the evaluator covers them
                        try:
                            sa, sb = sask(conj.xreplace(subs)), sask(other.xreplace(subs))
                        except Exception:  # noqa: BLE001
                            continue
                        if sa is not None and sb is not None:
                            assert sa == sb, (conj, other, vx, vy, sa, sb)
                            checked += 1
    assert checked > 200


def test_blocks_carry_a_verified_witness():
    """Every unrelated block evaluates True at its witness, and the
    witness respects the declarations of the block's symbols."""
    from harness.invariants import Unrelated
    from harness.models import admissible, evaluate_at
    n = 0
    for seed in range(40):
        u = Unrelated(random.Random(seed), "t", random.Random(seed).choice(["any", "norel", "rel"]))
        blk = u.block([S(7)])
        if blk is None:
            continue
        w = u.last_witness
        assert evaluate_at(And(*blk), w) is True, (blk, w)
        assert all(admissible(s, v) for s, v in w.items())
        assert len(blk) >= 2 and len({s for c in blk for s in c.free_symbols}) >= 2
        n += 1
    assert n >= 25


def test_model_guard_and_scope_tag():
    """The guard's second path finds a concrete model where the engine
    cannot read the set (a Float relation under an unregistered
    predicate), and out-of-scope material is a tag on the I2 case, never
    a veto: the oracle is the same."""
    from sympy import Float
    from harness.invariants import check_I2, consistent_by, scope_of
    from harness.sympy_io import custom_predicate
    x, u = Symbol("x"), Symbol("u")
    cfg = preset("default")
    a = Q.gt(x, Float(2.5)) & Q.lt(x, 7)
    assert consistent_by(a, cfg) in ("engine", "model")
    assert consistent_by(Q.gt(x, 7) & Q.lt(x, Float(2.5)), cfg) is None
    extra = custom_predicate("tscope", 1)(u)
    assert scope_of(Q.positive(x), extra) == "custom"
    variant = {"kind": "unrelated", "extra": to_srepr(extra), "mode": "any"}
    sev, other, var = check_I2(Q.positive(x), Q.positive(x), cfg, "True", random.Random(0), variant)
    assert var["scope"] == "custom"
    assert sev == ("depends" if other == "None" else None), (sev, other)
