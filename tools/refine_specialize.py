#!/usr/bin/env python
"""Generate the conditional ``log`` rules from the identity rows and verify them.

Usage::

    PYTHONPATH=.:/path/to/sympy .venv/bin/python tools/refine_specialize.py

Prints every generated rule with the result of a numeric check at a point
satisfying its hypothesis.  A rule marked WRONG is a wrong answer from
``ask`` reaching the floor handler, not a wrong identity; the report
explains the one known case, which appears under ``SATREFINE_BACKEND=sympy``
only (``SATREFINE_BACKEND`` selects the backend as everywhere else).
"""
from __future__ import annotations

import os
import sys
import time

os.environ["SATREFINE_HANDLERS"] = "handlers_identities"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import satrefine  # noqa: E402,F401  (loads the identity package)
from satrefine.handlers_identities._specialize import specialize_table, verify  # noqa: E402
from satrefine.handlers_identities.power_exp_log import IDENTITIES  # noqa: E402


def main() -> None:
    t0 = time.time()
    rules = specialize_table(IDENTITIES)
    print(f"generated {len(rules)} rules from {len(IDENTITIES)} identity rows in {time.time() - t0:.0f}s\n")
    for lhs, rhs, hyp in rules:
        v = verify(lhs, rhs, hyp)
        mark = "ok   " if v else "WRONG" if v is False else "?    "
        print(f"  {mark} Rule({lhs}, {rhs}, {hyp})")


if __name__ == "__main__":
    main()
