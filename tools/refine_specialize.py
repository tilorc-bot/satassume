#!/usr/bin/env python
"""Generate the conditional rules of the identity-based families and verify them.

Usage::

    PYTHONPATH=.:/path/to/sympy .venv/bin/python tools/refine_specialize.py            # print every family's rules
    ... --family log                                                                  # one family module
    ... --write                                                                       # write generated/<family>.py

Every generated rule is checked numerically at a sample point of its
hypothesis and at the edge points (0, 1, -1, I, -I and the family's
``EDGE_POINTS``) that satisfy it; ``--write`` keeps only the verified rules.
A rule marked WRONG is a wrong answer from ``ask`` reaching the floor
handler, not a wrong identity (the one known case appears under
``SATREFINE_BACKEND=sympy`` only).  Generation always runs the live identity
engine, whatever ``SATREFINE_IDENTITIES`` says.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

os.environ["SATREFINE_HANDLERS"] = "handlers_identities"
os.environ["SATREFINE_IDENTITIES"] = "live"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import satrefine  # noqa: E402,F401  (loads the identity package)
from satrefine.handlers_identities._specialize import family_modules, generate_family, write_family  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--family", action="append", help="family module name (repeatable); default: all")
    p.add_argument("--write", action="store_true", help="write satrefine/handlers_identities/generated/<family>.py")
    args = p.parse_args()
    modules = family_modules()
    if args.family:
        modules = [m for m in modules if m.__name__.rsplit(".", 1)[-1] in args.family]
    for module in modules:
        family = module.__name__.rsplit(".", 1)[-1]
        t0 = time.time()
        if args.write:
            path, rules, verdicts = write_family(module)
        else:
            rules, _keys, verdicts = generate_family(module)
            path = None
        print(f"{family}: {len(rules)} verified rules of {len(verdicts)} generated in {time.time() - t0:.0f}s"
              + (f", written to {path}" if path else ""))
        for (lhs, rhs, hyp), v in verdicts.items():
            mark = "ok   " if v else "WRONG" if v is False else "?    "
            print(f"  {mark} Rule({lhs}, {rhs}, {hyp})")


if __name__ == "__main__":
    main()
