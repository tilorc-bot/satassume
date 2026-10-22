"""The rules of ``sinh``, ``cosh``, ``tanh``, ``coth``, ``sech`` and
``csch``, written as ``for_all`` statements (``templates/hyperbolic.py``,
compiled by ``templates/wiring.py``, #249), against the generators they
replace (``tests/_legacy_hyperbolic_rules.py``, verbatim from f9291ab).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus, though the clauses differ.  Rows of the legacy generators the
rows leave out because the rule base and the other rows imply them:
``sinh``'s ``real -> real`` and ``extended_real -> extended_real`` (its
sign follows that of the argument), ``coth``'s and ``csch``'s
``extended_real & ~zero -> real`` (their signs, and ``csch(+-oo) == 0``),
``sech``'s ``extended_real -> real`` and ``-> nonnegative`` (positive on
the reals, 0 at ``+-oo``), ``cosh``'s ``real -> positive`` (finite and
extended positive), ``extended_real -> ~imaginary`` of ``coth`` and
``csch``, ``extended_positive -> nonnegative`` of ``csch``,
``imaginary -> ~imaginary`` of ``sech`` and ``imaginary -> imaginary |
zero`` of ``sinh`` (finite there).  :data:`ADDED` are the facts the rows
give that the legacy rules did not, each with its argument; a test checks
that each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_hyperbolic_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import Q, cosh, coth, csch, sech, sinh, tanh  # noqa: E402

from satassume.knowledge.templates._rows import x  # noqa: E402

HEADS = (sinh, cosh, tanh, coth, sech, csch)

#: facts the rows give and the legacy rules did not
ADDED = {
    tanh: (
        # tanh is meromorphic: where it is finite its value is a number
        (Q.complex(x) & Q.finite(tanh(x))) >> Q.complex(tanh(x)),
        # tanh(I*t) == I*tan(t), and tan(t) is real or zoo for real t
        (Q.imaginary(x) & Q.finite(tanh(x))) >> (Q.imaginary(tanh(x)) | Q.zero(tanh(x))),
        Q.imaginary(x) >> (~Q.extended_real(tanh(x)) | Q.zero(tanh(x))),
    ),
    # cosh(0) == 1, neither prime nor composite
    cosh: (Q.zero(x) >> (~Q.prime(cosh(x)) & ~Q.composite(cosh(x))),),
    # sech(0) == 1, neither prime nor composite
    sech: (Q.zero(x) >> (~Q.prime(sech(x)) & ~Q.composite(sech(x))),),
}

LEGACY_GEN = {sinh: legacy._sinh, cosh: legacy._cosh, tanh: legacy._tanh, coth: legacy._coth,
              sech: legacy._sech, csch: legacy._csch}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "hyperbolic", LEGACY_GEN, ADDED)
    # the corpus reaches cosh's I*pi*c*s rules (3 objects) and its
    # r + I*pi*c*s rules (3 or 4)
    shapes = {len(c.objs) for e, (cs, _) in new.items() if type(e) is cosh for c in cs}
    assert {2, 3, 4} <= shapes


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_hyperbolic_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Q, Symbol, cosh, coth, csch, sech, sinh, tanh
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
TRIG = "satassume.knowledge.templates.trig"
HYPERBOLIC = "satassume.knowledge.templates.hyperbolic"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.positive(cosh(x)), Q.real(x)) is True
assert HYPERBOLIC in sys.modules and TRIG not in sys.modules
for h in (sinh, cosh, tanh, coth, sech, csch):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":hyperbolic"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
