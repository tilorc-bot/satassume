"""The rules of ``Abs``, ``re``, ``im``, ``sign`` and ``conjugate``, written
as ``for_all`` statements (``templates/complex_parts.py``, compiled by
``templates/wiring.py``, #249), against the generators they replace
(``tests/_legacy_complex_parts_rules.py``, verbatim from d149951).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus, though the clauses differ.  Rows of the legacy generators the
rows leave out because the rule base and the other rows imply them:
``Abs``'s ``-> extended_real`` (it is extended nonnegative), ``infinite ->
extended_positive`` (nonnegative and not zero) and, on the extended reals,
``integer <-> integer`` (even or odd); ``re``'s ``extended_real ->
extended_real``, ``zero -> zero`` and, on the extended reals, ``zero <->
zero`` and ``integer <-> integer`` (its sign and parity); ``im``'s
``imaginary -> nonzero`` (real where finite, nonzero off the real line);
``sign``'s ``extended_real -> integer`` (odd or 0), ``extended_negative ->
negative`` and ``extended_real & negative -> extended_negative`` (odd, and
positive only for a positive argument), ``extended_nonnegative ->
nonnegative`` and ``extended_nonpositive -> nonpositive``;
``conjugate``'s ``<->`` of ``zero``, ``extended_real`` and ``integer`` (the
sign and the parity), of ``hermitian`` and ``antihermitian`` (the rule
base defines them as ``real`` and ``zero | imaginary``) and of
``commutative`` (always true).  ``Abs``'s ``finite(f) -> finite(x)`` is
written as ``infinite -> infinite``, and ``sign``'s ``extended_positive ->
odd`` and ``extended_negative -> odd`` as one row.  :data:`ADDED` are the
facts the rows give that the legacy rules did not, each with its argument;
a test checks that each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_complex_parts_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import Abs, Q, conjugate, im, re, sign  # noqa: E402

from satassume.knowledge.templates import _common  # noqa: E402
from satassume.knowledge.templates._rows import rules, x  # noqa: E402

HEADS = (Abs, re, im, sign, conjugate)

#: facts the rows give and the legacy rules did not
ADDED = {}

LEGACY_GEN = {Abs: legacy._abs, re: legacy._re, im: legacy._im, sign: legacy._sign,
              conjugate: legacy._conjugate}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    eq.check_rows_entail_exactly(HEADS, "complex_parts", LEGACY_GEN, ADDED)


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_a_row_without_premises_is_its_conclusion():
    R = _common.Rules()
    rules(sign, (Q.complex(sign(x)), Q.zero(sign(x)) | Q.odd(sign(x))), __name__)(R, None)
    assert sorted(R.rules) == [([], [(1, 'complex', True)]),
                               ([], sorted([(1, 'zero', True), (1, 'odd', True)]))]
    # under a condition, it is the conclusion of a row
    R = _common.Rules()
    rules(sign, Q.real(x) >> (Q.complex(sign(x)) & Q.zero(sign(x))), __name__)(R, None)
    assert sorted(R.rules) == [([(0, 'real', True)], [(1, 'complex', True)]),
                               ([(0, 'real', True)], [(1, 'zero', True)])]
    # a conjunction is what a & b >> c parses to
    with pytest.raises(TypeError, match="not an implication"):
        rules(sign, Q.complex(sign(x)) & Q.zero(sign(x)), __name__)


def test_complex_parts_is_compiled_on_its_own_first_use():
    # parts_of_round_templates comes after the rows of re and im, as it did
    # when functions.py registered both
    code = """
import sys
from sympy import Abs, Q, Symbol, conjugate, floor, im, re, sign
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
COMPLEX = "satassume.knowledge.templates.complex_parts"
TRIG = "satassume.knowledge.templates.trig"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.nonnegative(Abs(x)), Q.finite(x)) is True
pending = {m for _, m in registry._lazy}
assert WIRING + ":complex_parts" not in pending and WIRING + ":trig" in pending
# the rows are read compiled: no family module is imported
assert COMPLEX not in sys.modules and TRIG not in sys.modules
for h in (Abs, sign, conjugate):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":complex_parts"]
for h in (re, im):
    assert [(t.__module__, t.__name__) for t in registry._by_class[h]] == [
        (WIRING + ":complex_parts", h.__name__ + "_templates"),
        (WIRING + ":complex_parts", "parts_of_round_templates")]
assert ask(Q.integer(re(floor(x))), Q.finite(x)) is True
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
