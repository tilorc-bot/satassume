"""The rules of the inverse trigonometric and hyperbolic functions, written
as ``for_all`` statements (``templates/inverse.py``, compiled by
``templates/wiring.py``, #249), against the generators they replace
(``tests/_legacy_inverse_rules.py``, verbatim from d149951).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus, though the clauses differ.  Rows of the legacy generators the
rows leave out because the rule base and the other rows imply them:
``asin``'s ``real(f) -> real(x)`` (its sign where real); ``asinh``'s
``real -> real`` and ``extended_real -> extended_real`` (the sign of the
argument); ``atan``'s and ``acot``'s ``extended_real -> real`` (their
signs, and ``acot(+-oo) == 0``); ``acot``'s ``extended_nonnegative ->
nonnegative``, ``extended_negative -> nonpositive`` and ``real -> ~zero``
(its sign on the reals and ``acot(+-oo) == 0``), and its ``real &
algebraic -> transcendental`` (``algebraic -> ~algebraic``); ``acosh``'s
``real & nonnegative(x - 1) -> nonnegative`` (positive beyond 1, 0 at 1);
``asech``'s ``positive & nonpositive(x - 1) -> nonnegative`` (positive on
(0, 1), 0 at 1); ``acsch``'s ``extended_real & ~zero -> real`` and
``extended_real -> ~imaginary`` (its sign, 0 at the infinities, ``zoo`` at
0).  :data:`ADDED` are the facts the rows give that the legacy rules did
not, each with its argument; a test checks that each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_inverse_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import (  # noqa: E402
    Q, acos, acosh, acot, acoth, acsc, acsch, asec, asech, asin, asinh, atan, atanh,
)

from satassume.knowledge.templates._rows import x  # noqa: E402

HEADS = (asin, acos, asinh, acosh, atanh, acoth, asech, acsch, asec, acsc, atan, acot)

#: facts the rows give and the legacy rules did not
ADDED = {
    # Lindemann for every algebraic argument where the value is a number
    # b != 0: tan(atan(a)) == a, tanh(atanh(a)) == a and coth(acoth(a)) == a,
    # and tan, tanh, coth are transcendental at an algebraic b != 0
    # (Lindemann-Weierstrass); the legacy rules needed a real argument
    # (atan) or one other than +-1 (atanh, acoth)
    h: ((Q.algebraic(x) & Q.complex(h(x)) & ~Q.zero(h(x))) >> Q.transcendental(h(x)),)
    for h in (atan, atanh, acoth)
}

LEGACY_GEN = {asin: legacy._asin, acos: legacy._acos, atan: legacy._atan, acot: legacy._acot,
              asec: legacy._asec, acsc: legacy._acsc, asinh: legacy._asinh,
              acosh: legacy._acosh, atanh: legacy._atanh, acoth: legacy._acoth,
              asech: legacy._asech, acsch: legacy._acsch}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    new = eq.check_rows_entail_exactly(HEADS, "inverse", LEGACY_GEN, ADDED)
    # the corpus reaches the derived slots x - 1 and x + 1 (4 objects) and
    # the facts of a constant argument of asin and acos
    assert any(len(c.objs) == 4 for cs, _ in new.values() for c in cs)
    assert any(fs for e, (_, fs) in new.items() if type(e) in (asin, acos))


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_inverse_is_compiled_on_its_own_first_use():
    code = """
import sys
from sympy import Q, Symbol, acos, acosh, acot, acoth, acsc, acsch, asec, asech, asin, asinh, atan, atanh
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
TRIG = "satassume.knowledge.templates.trig"
INVERSE = "satassume.knowledge.templates.inverse"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.real(atanh(x)), Q.negative(x - 1) & Q.positive(x + 1)) is True
assert INVERSE in sys.modules and TRIG not in sys.modules
for h in (asin, acos, atan, acot, asec, acsc, asinh, acosh, atanh, acoth, asech, acsch):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":inverse"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
