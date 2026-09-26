"""Regression test (formerly ``needs/test_checker_ask_poisons_plain_symbols.py``):
after one ``refine`` whose ``ask`` went through
satassume, later ``refine`` calls in the same process must not change.

The satassume side (SymPy's cached ``(0**n).is_finite`` read as a fact, and
a derived fact written into the ``_assumptions`` shared by every plain
symbol) is fixed on ``main`` (PR #2) and tested there in
``tests/test_shared_facts.py``.  What stays here is the refine-level
regression check.  The SymPy root cause, ``(0**n).is_finite is True`` for a
plain ``n`` (``Pow._eval_is_algebraic`` ignores the exponent), is an
upstream issue candidate and is not tested here, since this repository does
not patch SymPy.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

SCRIPT = textwrap.dedent("""
    import os
    os.environ["SATREFINE_HANDLERS"] = "handlers_identities"
    from sympy import Q, Symbol, sqrt, log
    from satrefine import refine
    x, n = Symbol('x'), Symbol('n')
    refine(log(x**n), Q.negative(n) & Q.nonnegative(x))
    print(Symbol('fresh').is_negative)
    print(refine(sqrt(x**2), Q.even(x)))
""")


def test_refine_is_independent_of_earlier_calls():
    env = {**os.environ, "SATREFINE_BACKEND": "combined"}
    out = subprocess.run([sys.executable, "-c", SCRIPT], capture_output=True, text=True, env=env, check=True)
    assert out.stdout.split()[-2:] == ["None", "Abs(x)"]
