"""The rules of ``erf``, ``erfc``, ``erfi``, ``Ei``, ``Si``, ``Shi``,
``Ci``, ``Chi``, ``fresnels`` and ``fresnelc``, written as ``for_all``
statements (``templates/error_functions.py``, compiled by
``templates/wiring.py``, #249), against the generators they replace
(``tests/_legacy_error_functions_rules.py``, verbatim from d149951).

The comparison is ``tests/_rows_equivalence.py``'s: the rows and the
legacy generators plus :data:`ADDED` entail each other on every node of
its corpus, though the clauses differ.  Rows of the legacy generators the
rows leave out because the rule base and the other rows imply them:
``zero -> zero`` of ``erf``, ``erfi``, ``Si``, ``Shi``, ``fresnels`` and
``fresnelc`` (0 is extended real, and their sign is the argument's),
``erfi``'s and ``Shi``'s ``real -> real`` and ``extended_real ->
extended_real`` (entire, and of the sign of the argument),
``extended_real -> real`` of ``erf`` (odd at a real infinity), ``erfc``
(positive on the reals, 0 at ``oo``, 2 at ``-oo``) and the Fresnel
integrals (rational at a real infinity), and ``erfc``'s ``extended_real
-> nonnegative`` (the same three facts).  Rows the rows state in another
form: ``Ei``'s ``negative -> negative`` and ``zero -> extended_negative``
are ``nonpositive -> extended_negative`` (finite off 0), ``erf``'s
``infinite & extended_positive -> odd`` and ``infinite &
extended_negative -> odd`` are one row with ``extended_real``, and the
Fresnel integrals' ``extended_real & ~zero -> ~integer`` is ``real &
~zero -> ~integer`` and ``~integer`` at a real infinity.  :data:`ADDED`
are the facts the rows give that the legacy rules did not, each with its
argument; a test checks that each is new.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _legacy_error_functions_rules as legacy  # noqa: E402
import _rows_equivalence as eq  # noqa: E402
from sympy import Chi, Ci, Ei, Q, Shi, Si, erf, erfc, erfi, fresnelc, fresnels  # noqa: E402

from satassume.knowledge.templates._rows import x  # noqa: E402

HEADS = (erf, erfc, erfi, Si, Shi, fresnels, fresnelc, Ei, Ci, Chi)

#: facts the rows give and the legacy rules did not
ADDED = {
    # erfc(0) == 1, neither prime nor composite
    erfc: (Q.zero(x) >> (~Q.prime(erfc(x)) & ~Q.composite(erfc(x))),),
}

LEGACY_GEN = {
    erf: legacy._erf, erfc: legacy._erfc, erfi: legacy._erfi, Ei: legacy._ei, Si: legacy._si,
    Shi: legacy._shi, Ci: lambda R, c: legacy._ci_chi(R, True),
    Chi: lambda R, c: legacy._ci_chi(R, False), fresnels: legacy._fresnel,
    fresnelc: legacy._fresnel,
}


def test_rows_entail_exactly_the_legacy_rules_and_the_added_facts():
    eq.check_rows_entail_exactly(HEADS, "error_functions", LEGACY_GEN, ADDED)


def test_each_added_fact_is_new():
    eq.check_added_are_new(LEGACY_GEN, ADDED)


def test_error_functions_are_compiled_on_their_own_first_use():
    code = """
import sys
from sympy import Chi, Ci, Ei, Q, Shi, Si, Symbol, erf, erfc, erfi, fresnelc, fresnels
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
ROWS = "satassume.knowledge.templates.error_functions"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.positive(erfc(x)), Q.real(x)) is True
for other in ("trig", "hyperbolic", "special"):
    assert "satassume.knowledge.templates." + other not in sys.modules, other
assert ROWS in sys.modules
for h in (erf, erfc, erfi, Ei, Si, Shi, Ci, Chi, fresnels, fresnelc):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":error_functions"]
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
