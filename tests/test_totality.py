"""The totality gate: every node block of the templates is a conservative
extension of its children (``tools/totality.py``; issue #53, invariant I2).

A block is *total* if, for every assignment of its children that the rule
base and the children's own blocks (one level down, ``depth=1``) allow,
the node's clauses are satisfiable.  A non-total block is either unsound
(the ``Mul``/``Pow`` rules of issue #47, ``commutative(x*A) ->
commutative(A)`` against ``0*A == 0``; the generic ``commutative(f(x)) ->
commutative(x)`` against the scalar facts of ``Abs``, ``re``, ``im`` and
``sign``) or a gap that lets one node's block decide facts its children's
blocks cannot (a transcendental product, the coefficient-free product of
a ``Mul``).  Both make the answer of a query depend on which other nodes a
session holds, so the gate keeps the set of non-total blocks at
``ALLOWLIST`` (empty: every entry must be justified here with the issue
that tracks it).

The check runs over the synthetic expression list of the checker (the
node shapes of the templates and every family found so far, about 1 s);
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


def _non_total(depth=1):
    models = totality.rule_models()
    exprs = totality.load_exprs(os.environ.get("TOTALITY_CORPUS"), os.environ.get("TOTALITY_STREAM"))
    pats, _ = totality.collect_patterns(exprs, False)
    out = []
    for key, (e, compiled) in pats.items():
        pat = totality._Union(e, compiled)
        comp = totality._Comp(tuple(pat.objs), pat)
        r = totality.check_pattern(pat, models, totality.derived_constraints(comp, depth))
        if r is not None:
            assign, fired = r
            out.append((repr(e), {str(k): sorted(totality.PREDICATES[i] for i in t) for k, t in assign.items()},
                        [totality.clause_str(l, pat.node) for l, _, _ in fired]))
    return out


def test_rule_base_has_48_models():
    assert len(totality.rule_models()) == 48


def test_every_node_block_is_total_at_depth_1():
    bad = [(e, a, f) for e, a, f in _non_total(1) if e not in ALLOWLIST]
    assert not bad, "non-total blocks (unsound or a template gap):\n" + "\n".join(
        f"{e}: children {a}; fired {f[:6]}" for e, a, f in bad)


def test_allowlist_entries_are_still_needed():
    """An entry whose block became total must be dropped."""
    if not ALLOWLIST:
        return
    still = {e for e, _, _ in _non_total(1)}
    assert set(ALLOWLIST) <= still, set(ALLOWLIST) - still
