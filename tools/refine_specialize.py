#!/usr/bin/env python
"""Generate the conditional rules of the identity-based families and verify them.

Usage::

    PYTHONPATH=.:/path/to/sympy .venv/bin/python tools/refine_specialize.py            # the stages to a fixpoint, print
    ... --write                                                                       # ... and write generated/<family>.py
    ... --family log [--write]                                                        # one family, against the committed
                                                                                      # tables of the others (one step)

Families are generated in stage order (``_stages.STAGES``): each with its own
keys on their identity rows and every other key through the tables generated
so far, repeated until no table changes.  Every generated rule is checked
numerically at a sample point of its hypothesis and at the edge points (0, 1,
-1, I, -I and the family's ``EDGE_POINTS``) that satisfy it; only verified
rules are installed and written.  The written modules carry each rule's
derivation record as a comment.  Generation time is printed per family and
round.
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
from satrefine.handlers_identities import _stages  # noqa: E402
from satrefine.handlers_identities._specialize import generated_path, render_module  # noqa: E402


def write(family: str, entry: dict, labels: dict) -> str:
    notes = {rule: _stages.record_lines(rec, labels) for rule, rec in entry["records"].items()}
    path = generated_path(family)
    path.write_text(render_module(family, entry["rules"], entry["keys"], notes))
    return str(path)


def show(family: str, entry: dict) -> None:
    for (lhs, rhs, hyp), v in entry["verdicts"].items():
        mark = "ok   " if v else "WRONG" if v is False else "?    "
        print(f"  {mark} Rule({lhs}, {rhs}, {hyp})")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--family", action="append", help="family module name (repeatable): regenerate only these, "
                   "against the committed tables of the others")
    p.add_argument("--write", action="store_true", help="write satrefine/handlers_identities/generated/<family>.py")
    p.add_argument("--quiet", action="store_true", help="do not list the rules")
    args = p.parse_args()
    t0 = time.time()
    if args.family:
        modules = [m for m in _stages.ordered_families() if _stages.family_name(m) in args.family]
        out = {}
        for module in modules:
            t = time.time()
            rules, keys, verdicts = _stages.generate_one(module)
            from satrefine.handlers_identities import _specialize
            out[_stages.family_name(module)] = {"rules": rules, "keys": keys, "verdicts": verdicts,
                                                "records": {r: _specialize.records.get(r) for r in rules},
                                                "rounds": [1], "seconds": [round(time.time() - t, 1)]}
        import importlib
        others = {}
        for module in _stages.ordered_families():
            fam = _stages.family_name(module)
            try:
                others[fam] = {"rules": importlib.import_module(f"satrefine.handlers_identities.generated.{fam}").RULES}
            except ImportError:
                pass
        labels = _stages.row_labels(others)
    else:
        out = _stages.generate()
        labels = _stages.row_labels(out)
    for family, entry in out.items():
        verdicts = entry["verdicts"]
        print(f"{family}: {len(entry['rules'])} verified rules of {len(verdicts)} generated; "
              f"seconds per round {entry['seconds']}; changed in rounds {entry['rounds']}"
              + (f", written to {write(family, entry, labels)}" if args.write else ""))
        if not args.quiet:
            show(family, entry)
    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
