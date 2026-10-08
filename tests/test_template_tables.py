"""The Mul and Pow templates as tables (issue #97, P6) emit exactly the
clauses of the hand-written functions they replace.

``satassume/templates/core.py`` writes ``_mul_rules``, ``_pow_rules`` and
``ipi_rules`` as the tables ``MUL_TABLE``, ``POW_TABLE`` and ``IPI_TABLE``
(rows of premises over argument facts and conclusion facts, interpreted by
``satassume/templates/table.py`` through the spec builders of
``_common``).  The functions as they were at 876f37d are kept verbatim in
``tests/_legacy_core_rules.py``.  For every node, the compiled clauses of
every template block (and the plain formulas) are computed once with the
tables and once with the legacy functions patched in, each from empty
caches, and compared after canonicalization (literals of a clause sorted,
clauses sorted): over every node of the recorded corpus (``queries.jsonl``,
assumptions and propositions; skipped when it is not recorded) and over
2000 random Mul/Pow terms of the harness's generator (``harness.generators
.QueryGen.term`` with ``RandomDraw``, seeds from 0) and all their
subterms.  A wrong row changes some node's clauses and fails the test.

    PYTHONHASHSEED=0 python -m pytest -q tests/test_template_tables.py -s
"""
import json
import os
import random
import sys

import pytest

sympy = pytest.importorskip("sympy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_core_rules as legacy  # noqa: E402
import totality  # noqa: E402
from sympy import Mul, Pow  # noqa: E402

from satassume.templates import _common, core, functions, registry  # noqa: E402
from satassume.templates.table import count_rows, iter_rows  # noqa: E402

CORPUS = os.path.join(ROOT, "queries.jsonl")
N_RANDOM = 2000


def _subexprs(exprs):
    out = {}
    for e in exprs:
        stack = [e]
        while stack:
            x = stack.pop()
            if x in out:
                continue
            out[x] = None
            stack.extend(getattr(x, "args", ()))
    return list(out)


def corpus_nodes():
    ns = {}
    exec("from sympy import *\nfrom sympy.assumptions import Q\nfrom sympy.core.symbol import Symbol", ns)
    exprs = []
    with open(CORPUS) as fh:
        for line in fh:
            d = json.loads(line)
            for key in ("prop", "assum", "expr"):
                v = d.get(key)
                if not v or v in ("true", "True"):
                    continue
                try:
                    obj = eval(v, ns)
                except Exception:  # noqa: BLE001  (unreplayable record, as compare.py)
                    continue
                exprs.extend(totality._expressions_of(obj))
    return _subexprs(exprs)


def random_terms(n=N_RANDOM):
    """``n`` distinct random Mul/Pow terms of the fuzz generator."""
    from harness.generators import GenOptions, QueryGen, RandomDraw
    out = {}
    seed = 0
    while len(out) < n:
        gen = QueryGen(RandomDraw(random.Random(seed)), GenOptions())
        for _ in range(200):
            try:
                t = gen.term()
            except Exception:  # noqa: BLE001  (a term SymPy cannot build)
                continue
            if isinstance(t, (Mul, Pow)) and t not in out:
                out[t] = None
                if len(out) == n:
                    break
        seed += 1
    return list(out)


def synthetic_nodes():
    """The node shapes of the totality checker, plus unevaluated nodes that
    SymPy would otherwise rewrite before any template sees them (issue #97,
    P6 review nit 2): ``Pow(E, x)`` becomes ``exp(x)`` and ``Pow(x, 1)``
    becomes ``x``, so the ``pow.E.*`` and ``one`` rows of ``POW_TABLE`` are
    reached only through these."""
    from sympy import E, symbols
    x = symbols("x")
    extra = [Pow(E, x, evaluate=False), Pow(x, 1, evaluate=False)]
    return _subexprs(list(totality.load_exprs()) + extra)


def _clear():
    _common._CACHE.clear()
    registry._clauses_cache.clear()


def _canonical(e):
    """The node's compiled blocks and formulas, canonicalized."""
    compiled, formulas = registry.clauses_for(e)
    blocks = []
    for c in compiled:
        clauses = tuple(sorted(tuple(sorted(lits)) for lits, _, _ in c.pattern.clauses))
        blocks.append((tuple(map(str, c.objs)), c.pattern.node, clauses))
    return tuple(sorted(blocks)), tuple(sorted(map(str, formulas)))


def _run(nodes):
    _clear()
    out = {}
    for e in nodes:
        try:
            out[e] = _canonical(e)
        except Exception as exc:  # noqa: BLE001  (compared like a result)
            out[e] = ("raises", type(exc).__name__, str(exc))
    return out


def _with_legacy(monkeypatch, nodes):
    with monkeypatch.context() as m:
        m.setattr(core, "_mul_rules", legacy.mul_rules)
        m.setattr(core, "_pow_rules", legacy.pow_rules)
        m.setattr(core, "ipi_rules", legacy.ipi_rules)
        m.setattr(functions, "ipi_rules", legacy.ipi_rules)
        try:
            return _run(nodes)
        finally:
            _clear()


def _compare(monkeypatch, nodes, label):
    new = _run(nodes)
    old = _with_legacy(monkeypatch, nodes)
    _clear()
    diff = [e for e in nodes if new[e] != old[e]]
    nclauses = sum(len(b[2]) for v in new.values() if v[0] != "raises" for b in v[0])
    nmulpow = sum(1 for e in nodes if isinstance(e, (Mul, Pow)))
    print(f"{label}: {len(nodes)} nodes ({nmulpow} Mul/Pow), {nclauses} clauses compared, "
          f"{len(diff)} differ")
    assert not diff, f"{label}: clauses differ for {diff[:5]}"
    return nclauses


@pytest.mark.skipif(not os.path.exists(CORPUS),
                    reason="queries.jsonl not recorded (tools/record_queries.py)")
def test_corpus_clauses_identical(monkeypatch):
    _compare(monkeypatch, corpus_nodes(), "corpus")


def test_random_clauses_identical(monkeypatch):
    terms = random_terms()
    assert len(terms) == N_RANDOM
    _compare(monkeypatch, _subexprs(terms), f"random ({N_RANDOM} Mul/Pow terms and subterms)")


def test_synthetic_clauses_identical(monkeypatch):
    # the node shapes of the totality checker (no corpus needed), plus the
    # unevaluated Pow nodes of synthetic_nodes()
    _compare(monkeypatch, synthetic_nodes(), "synthetic")


def test_comparison_detects_a_wrong_row(monkeypatch):
    """Mutation check of the comparison itself: one changed row is seen."""
    from sympy import symbols
    x, y = symbols("x y")
    nodes = _subexprs([x * y, x**y, x**2])
    row = next(r for r in iter_rows(core.MUL_TABLE) if r.name == 'one_neg')
    new = _run(nodes)
    try:
        with monkeypatch.context() as m:
            m.setattr(row, "concl", (('N', 'extended_positive'),))
            row._compile()
            mutated = _run(nodes)
    finally:
        row._compile()
        _clear()
    assert new[x * y] != mutated[x * y]


def test_table_sizes_and_names():
    for table in (core.MUL_TABLE, core.POW_TABLE, core.IPI_TABLE):
        names = [r.name for r in iter_rows(table)]
        assert len(names) == len(set(names)), "row names are unique per table"
        for r in iter_rows(table):
            for lit in (*r.prem, *r.concl):
                assert lit[1] in _common.VOCAB or lit[1] in ('$p', 'flip:$p', 'int>=2'), r.text()
    print("rows:", {"mul": count_rows(core.MUL_TABLE), "pow": count_rows(core.POW_TABLE),
                    "ipi": count_rows(core.IPI_TABLE)})


def test_provenance_covers_every_table_clause():
    """Every clause of a Mul/Pow table block is named by some row
    (``core.table_provenance``, used by ``tools/totality.py``)."""
    from satassume.rules import BASIS
    missing = []
    for e in _subexprs(totality.load_exprs()):
        if not isinstance(e, (Mul, Pow)):
            continue
        prov = {}
        for name, clause in core.table_provenance(e):
            prov.setdefault(clause, []).append(name)
        compiled, _ = registry.clauses_for(e)
        for c in compiled:
            for lits, _, _ in c.pattern.clauses:
                cl = frozenset((c.objs[k], BASIS[i], not neg) for k, i, neg in lits)
                if cl not in prov:
                    missing.append((e, cl))
    assert not missing, missing[:5]
