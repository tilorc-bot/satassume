"""Failing tests from the P5b review (reports/p5b-review.md); each names
its finding.  They fail at 75ccc97 and must pass once the finding is fixed."""
from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stdout

import pytest
from sympy import Float, I, Symbol, sqrt
from sympy.assumptions import Q

from satassume.ref import ask_ref
from satassume.sympy_api import out_of_scope

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))


def test_ask_ref_raising_is_independent_of_p():
    """Finding 1 (spec 1.4, 7, 10 rule 1: raising is decided by ``A``'s
    verdict alone).  With ``uninterpreted="none"`` an uninterpreted relation
    in ``p`` must not turn an inconsistent set's ``ValueError`` into None:
    ``ask_ref`` catches ``Uninterpreted`` before deciding the set."""
    z = Symbol("z")
    a = Q.rational(sqrt(3) / 2 + I)          # inconsistent on its own
    with pytest.raises(ValueError):
        ask_ref(Q.positive(z), a, uninterpreted="none")
    for p in (z > Float(0.5), Q.positive(z) | (z > Float(0.5))):
        with pytest.raises(ValueError):
            ask_ref(p, a, uninterpreted="none")


def test_ref_corpus_counts_every_record(tmp_path):
    """Finding 2 (docs/agents.md Gating rule 5; plan P5b item 4: "none are
    silently excluded").  ``tools/ref_corpus.py`` must print how many
    records it read and how many it did not replay, by reason (``old``
    records and each out-of-scope category), next to ``n``."""
    import ref_corpus
    x = Symbol("x")
    oos = [p for p in (Q.invertible(x), Q.prime(x) & Q.is_true(x))
           if out_of_scope(p, True) is not None]
    assert oos, "no out-of-scope candidate; adjust the test"
    from sympy import srepr
    recs = [
        {"kind": "old", "expr": "Integer(2)", "fact": "nonnegative", "value": True},
        {"kind": "ask", "prop": srepr(Q.integer(x)), "assum": "true", "value": None},
        {"kind": "ask", "prop": srepr(oos[0]), "assum": "true", "value": None},
    ]
    path = tmp_path / "c.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in recs))
    buf = io.StringIO()
    with redirect_stdout(buf):
        ref_corpus.main([str(path)])
    out = buf.getvalue()
    assert "n=1" in out, out
    # every record accounted for: 3 read = 1 replayed + 1 old + 1 out of scope
    assert "records=3" in out and "old=1" in out, out
    assert "out_of_scope=1" in out or f"{out_of_scope(oos[0], True)}=1" in out, out
