"""Checker finding, not in handlers_identities: one ``ask`` through the default
``combined`` backend can rewrite the old-style assumptions of *every* plain
symbol in the process, after which later ``refine`` calls return wrong
results.  The tests under this directory are a request for the satassume
owner.

The chain:

1. SymPy's old assumptions call ``0**n`` finite for a plain ``n``
   (``(0**n).is_finite is True``), although ``0**-1`` is ``zoo``; the value
   is cached on the ``Pow``;
2. satassume's ``ObjectCache`` reads a node's cached facts as facts that hold
   without any assumptions, so under ``Q.negative(n)`` the query is
   inconsistent at root and the solver derives ``n`` not negative;
3. ``writeback`` stores that into ``n._assumptions``, which (in this SymPy)
   is the one ``StdFactKB`` shared by every symbol created with the same
   assumptions: from then on ``Symbol('anything').is_negative`` is ``False``.

Seen in the checker's fuzz: after ``refine(log(x**n), Q.negative(n) &
Q.nonnegative(x))`` in the same process, ``refine(sqrt(x**2), Q.even(x))``
returns ``x`` (wrong at ``x = -2``) instead of ``Abs(x)``.  Long-running
tools (``refine_differential.py``, ``refine_fuzz.py``, the scoreboard) run
many cases per process, so their later results can be affected; with
``SATREFINE_BACKEND=sympy`` the effect is absent.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap

SCRIPT = textwrap.dedent("""
    import os
    os.environ["SATREFINE_HANDLERS"] = "handlers_identities"
    from sympy import Q, Symbol, sqrt, log, Abs
    from satrefine import refine
    from satrefine.backend import ask
    x, n = Symbol('x'), Symbol('n')
    step = os.environ["STEP"]
    if step == "ask":
        (0**n).is_finite
        ask(Q.positive(0**n), Q.negative(n) & Q.nonnegative(x))
        print(Symbol('fresh').is_negative)
    else:
        refine(log(x**n), Q.negative(n) & Q.nonnegative(x))
        print(refine(sqrt(x**2), Q.even(x)))
""")


def _run(step: str) -> str:
    import os
    env = {**os.environ, "STEP": step, "SATREFINE_BACKEND": "combined"}
    out = subprocess.run([sys.executable, "-c", SCRIPT], capture_output=True, text=True, env=env, check=True)
    return out.stdout.strip().splitlines()[-1]


def test_zero_power_is_not_finite_for_a_plain_exponent():
    from sympy import Symbol
    assert (0**Symbol('n')).is_finite is not True


def test_one_ask_does_not_change_other_symbols():
    assert _run("ask") == "None"


def test_refine_is_independent_of_earlier_calls():
    assert _run("refine") == "Abs(x)"
