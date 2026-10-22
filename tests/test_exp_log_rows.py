"""The rules of ``exp`` and ``log``, written as ``for_all`` statements
(``templates/exp_log.py``, compiled by ``templates/wiring.py``, #249),
against the generators they replace (``tests/_legacy_exp_log_rules.py``,
verbatim from d149951).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus, though the clauses differ.  Rows of the legacy generators the
rows leave out because the rule base and the other rows imply them:
``exp``'s ``extended_real -> extended_real`` and ``extended_real ->
extended_nonnegative`` (positive on the reals, ``exp(-oo) == 0``,
``exp(oo) == oo``), ``extended_negative -> complex`` (the same, and
complex where finite) and ``zero -> positive`` (positive on the reals);
``log``'s ``extended_positive -> extended_real`` (real on the positive
reals, ``log(oo) == oo``).  :data:`ADDED` are the facts the rows give
that the legacy rules did not, each with its argument; a test checks that
each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_exp_log_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import Q, exp, log  # noqa: E402

from satassume.knowledge.templates import _common  # noqa: E402
from satassume.knowledge.templates._rows import x  # noqa: E402

HEADS = (exp, log)

#: facts the rows give and the legacy rules did not
ADDED = {
    # exp(0) == 1, neither prime nor composite
    exp: (Q.zero(x) >> (~Q.prime(exp(x)) & ~Q.composite(exp(x))),),
}

LEGACY_GEN = {exp: legacy._exp, log: legacy._log}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "exp_log", LEGACY_GEN, ADDED)
    # the corpus reaches exp's I*pi*c*s rules (3 objects) and log's slot
    # x - 1 (3 objects)
    for h in HEADS:
        assert any(len(c.objs) == 3 for e, (cs, _) in new.items() if type(e) is h for c in cs)


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_exp_keeps_its_pattern_keys_and_slot_objects():
    """The template of exp from its rows (``wiring.I_PI_ROOT``) caches its
    patterns under the keys of the legacy ``exp_templates``, over the same
    objects."""
    rows = eq.rows_templates((exp,), "exp_log")[exp]
    try:
        for e in eq.nodes((exp,)):
            seen = []
            for t in (legacy.exp_templates, rows):
                _common._CACHE.clear()
                objs = t(e).objs
                seen.append((tuple(_common._CACHE), objs))
            assert seen[0] == seen[1], e
    finally:
        _common._CACHE.clear()


def test_log_of_two_arguments_gets_no_facts():
    # log(x, b, evaluate=False) is log(x)/log(b), not log(x) (#191)
    t = eq.rows_templates((log,), "exp_log")[log]
    node = log(x, 2, evaluate=False)
    assert len(node.args) == 2
    assert t(node) is None


def test_exp_log_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Q, Symbol, exp, log
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
TRIG = "satassume.knowledge.templates.trig"
EXP_LOG = "satassume.knowledge.templates.exp_log"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.positive(log(x)), Q.positive(x - 1)) is True
assert EXP_LOG in sys.modules and TRIG not in sys.modules
for h in (exp, log):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":exp_log"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
