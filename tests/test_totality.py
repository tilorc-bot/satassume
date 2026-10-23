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


def test_rule_base_has_44_models():
    # the 48 of the full rule base with ``commutative`` true (rules.DEFINITIONS)
    assert len(totality.rule_models()) == 44


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
    """The checker itself: a block with a downward rule (the shape of the
    old rule of #47, there ``commutative(x*A) -> commutative(A)``) next to
    an unconditional fact about the node must be reported for an argument
    the rule does not hold of, and the same block without the downward
    rule must pass."""
    from sympy import Function, Symbol

    from satassume.knowledge.templates._common import Rules, facts

    x = Symbol('x')
    node = Function('canary')(x)
    models = totality.rule_models()

    def block(downward):
        R = Rules()
        R.rule([], (1, 'extended_positive', True))
        if downward:
            R.rule([(1, 'extended_positive', True)], (0, 'extended_positive', True))
        return [facts(('canary', downward), lambda: R.rules, {}, (x, node), 1)]

    r = totality.check_block(node, block(True), models, depth=1)
    assert r is not None
    pat, assign, fired = r
    d = totality.describe(node, pat, assign, fired)
    assert 'extended_positive' not in d['assignment']['0']   # the counterexample: x not positive
    assert any('extended_positive' in c for c in d['fired'])
    assert totality.check_block(node, block(False), models, depth=1) is None


def test_a_template_that_raises_fails_the_gate(monkeypatch):
    """A block that cannot be compiled is an error, not a skipped block."""
    from sympy import Symbol

    from satassume.knowledge.templates import registry

    def boom(expr):
        raise RuntimeError("canary")
    monkeypatch.setattr(registry, "clauses_for", boom)
    with pytest.raises(RuntimeError, match="canary"):
        totality.run([Symbol('x') + 1], depth=1, models=totality.rule_models())


def test_provenance_covers_every_clause_of_the_mul_rows():
    """Every clause of a Mul block of rows is named by some row
    (``totality.row_provenance``, printed with a non-total block), as
    ``tools/show_rows.py Mul`` prints it."""
    from sympy import Mul

    from satassume.knowledge.rules import BASIS
    from satassume.knowledge.templates import registry
    from satassume.knowledge.templates.core import _mul_factor_sets

    missing, named = [], set()
    for e in totality.load_exprs():
        for m in sympy.preorder_traversal(e):
            if not isinstance(m, Mul):
                continue
            prov = {}
            for name, clause in totality.row_provenance(m):
                prov.setdefault(clause, []).append(name)
            compiled, _ = registry.clauses_for(m)
            sets = {tuple(f) + (m,) for f in _mul_factor_sets(m)}
            for c in compiled:
                if tuple(o for o in c.objs if o is not None) not in sets:
                    continue    # a block of no rows (core._quotient_templates)
                for lits, _, _ in c.pattern.clauses:
                    cl = frozenset((c.objs[k], BASIS[i], not neg) for k, i, neg in lits)
                    if cl not in prov:
                        missing.append((m, cl))
                    named.update(prov.get(cl, ()))
    assert not missing, missing[:5]
    assert len(named) > 40 and all(": " in n for n in named)


def test_provenance_covers_every_clause_of_the_add_rows():
    """Every clause of the Add block of rows is named by some row
    (``totality.row_provenance``), as ``tools/show_rows.py Add`` prints
    it; the blocks of the sums of a special shape are not rows."""
    from sympy import Add

    from satassume.knowledge.rules import BASIS
    from satassume.knowledge.templates import registry

    missing, named, blocks = [], set(), 0
    for e in totality.load_exprs():
        for a in sympy.preorder_traversal(e):
            if not isinstance(a, Add):
                continue
            prov = {}
            for name, clause in totality.row_provenance(a):
                prov.setdefault(clause, []).append(name)
            compiled, _ = registry.clauses_for(a)
            for c in compiled:
                if tuple(c.objs) != a.args + (a,):
                    continue    # a sum of a special shape (core._imag_templates)
                blocks += 1
                for lits, _, _ in c.pattern.clauses:
                    cl = frozenset((c.objs[k], BASIS[i], not neg) for k, i, neg in lits)
                    if cl not in prov:
                        missing.append((a, cl))
                    named.update(prov.get(cl, ()))
    assert not missing, missing[:5]
    assert blocks > 20 and len(named) > 25 and all(": " in n for n in named)
