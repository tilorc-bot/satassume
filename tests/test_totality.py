"""The totality gate: every node block of the templates is a conservative
extension of its children (``tools/totality.py``; issue #53, invariant I2).

A block is *total* if, for every assignment of its children that the rule
base and the children's own blocks (one level down, ``depth=1``) allow,
the node's clauses are satisfiable.  A non-total block is either unsound
(the downward ``commutative`` rules of #47 and #59: ``Abs(A)`` of a
non-commutative ``A`` was inconsistent in a fresh engine) or a gap that
lets one node's block decide facts its children's blocks cannot (a
transcendental product, a product a ``Mul`` derives).  Both make the
answer of a query depend on which other nodes a session holds, so the
gate keeps the set of non-total blocks at ``ALLOWLIST`` (empty: every
entry must be justified here with the issue that tracks it).  Totality is
not soundness: a sound block is total, a total block need not be sound
(the old Mul rule of #47 passed the gate once its counterpart was
weakened), so a rule change needs its own argument.

The check runs over the synthetic expression list of the checker (the
node shapes of the templates and every family found so far, about 2 s);
``TOTALITY_CORPUS`` / ``TOTALITY_STREAM`` (paths) add the recorded corpus
and the refine stream (the long mode, about 6 s), to be run on every
template change.
"""
import os
import sys

import pytest

sympy = pytest.importorskip("sympy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import totality  # noqa: E402

#: repr of the expressions whose block is allowed to be non-total, with
#: the reason and the issue; must be empty or justified per entry
ALLOWLIST: dict = {}


def _non_total():
    exprs = totality.load_exprs(os.environ.get("TOTALITY_CORPUS"), os.environ.get("TOTALITY_STREAM"))
    failures, checked, _ = totality.run(exprs, depth=1)
    assert checked >= 100, checked                      # the list did not shrink
    return {repr(e): totality.describe(e, pat, assign, fired) for e, pat, assign, fired in failures}


def test_rule_base_has_48_models():
    assert len(totality.rule_models()) == 48


def test_every_node_block_is_total_at_depth_1():
    bad = {e: d for e, d in _non_total().items() if e not in ALLOWLIST}
    assert not bad, "non-total blocks (unsound or a template gap):\n" + "\n".join(
        f"{e}: children {d['assignment']}; fired {d['fired'][:6]}" for e, d in bad.items())


def test_allowlist_entries_are_still_needed():
    """An entry whose block became total must be dropped."""
    if not ALLOWLIST:
        return
    still = set(_non_total())
    assert set(ALLOWLIST) <= still, set(ALLOWLIST) - still


def test_canary_a_non_total_block_is_reported():
    """The checker itself: a block with the old downward rule of #47 next
    to an unconditional scalar fact must be reported for a non-commutative
    argument, and the same block without the downward rule must pass."""
    from sympy import Function, Symbol

    from satassume.templates._common import Rules, facts

    A = Symbol('A', commutative=False)
    node = Function('canary')(A)
    models = totality.rule_models()

    def block(downward):
        R = Rules()
        R.rule([], (1, 'extended_real', True))
        if downward:
            R.rule([(1, 'commutative', True)], (0, 'commutative', True))
        return [facts(('canary', downward), lambda: R.rules, {}, (A, node), 1)]

    r = totality.check_block(node, block(True), models, depth=1)
    assert r is not None
    pat, assign, fired = r
    d = totality.describe(node, pat, assign, fired)
    assert 'commutative' not in d['assignment']['0']      # the counterexample: A non-commutative
    assert any('commutative' in c for c in d['fired'])
    assert totality.check_block(node, block(False), models, depth=1) is None


def test_a_template_that_raises_fails_the_gate(monkeypatch):
    """A block that cannot be compiled is an error, not a skipped block."""
    from sympy import Symbol

    from satassume.templates import registry

    def boom(expr):
        raise RuntimeError("canary")
    monkeypatch.setattr(registry, "clauses_for", boom)
    with pytest.raises(RuntimeError, match="canary"):
        totality.run([Symbol('x') + 1], depth=1, models=totality.rule_models())
