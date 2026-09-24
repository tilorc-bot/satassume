#!/usr/bin/env python
"""Scoreboard for the identity-based handlers: rows per family, battery, fuzz.

Usage::

    PYTHONPATH=.:/path/to/sympy .venv/bin/python tools/refine_identity_scoreboard.py
    ... --handlers handlers_v3            # run the battery with another package
    ... --battery tests/refine_identities/battery_v3.py
    ... --fuzz 2 1500                     # also run tools/refine_fuzz.py (seed, cases)

Rows are counted from the family modules of ``handlers_identities``
(``FACTS``, ``EXP_FORMS``, ``RULES``, ``SIMPLE_RULES``).  The battery is a
list of ``(expr, assumptions, expected, source)`` (see the battery module):
for each case the dispatcher's output is compared with ``expected`` by
``simplify`` of the difference, checked numerically with the harness
oracle, and classified.  The exit status is always 0: this is a
measurement.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import pkgutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--handlers", default="handlers_identities")
    p.add_argument("--battery", default=str(ROOT / "tests/refine_identities/battery_v3.py"))
    p.add_argument("--fuzz", nargs=2, metavar=("SEED", "CASES"))
    p.add_argument("--show", action="store_true", help="print every case that is not a clean pass")
    return p.parse_args()


def count_rows() -> None:
    import satrefine.handlers_identities as package
    print("rows per family (handlers_identities)")
    print(f"  {'module':18s} {'facts':>6s} {'exp':>6s} {'rules':>6s} {'simple':>6s}")
    total = Counter()
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{package.__name__}.{info.name}")
        def n(name: str) -> int:
            v = getattr(mod, name, None)
            return v if isinstance(v, int) else len(v) if v is not None else 0
        counts = {k: n(k) for k in ("FACTS", "EXP_FORMS", "RULES", "SIMPLE_RULES")}
        total.update(counts)
        print(f"  {info.name:18s} {counts['FACTS']:6d} {counts['EXP_FORMS']:6d} {counts['RULES']:6d} {counts['SIMPLE_RULES']:6d}")
    print(f"  {'total':18s} {total['FACTS']:6d} {total['EXP_FORMS']:6d} {total['RULES']:6d} {total['SIMPLE_RULES']:6d}")


def load_battery(path: str) -> list:
    spec = importlib.util.spec_from_file_location("battery", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return list(mod.BATTERY)


def run_battery(cases: list, show: bool) -> None:
    from sympy import simplify
    from satrefine import refine
    from satrefine.harness import assert_refinement_valid
    counts: Counter = Counter()
    for expr, assumptions, expected, source in cases:
        try:
            got = refine(expr, assumptions)
        except Exception as e:  # noqa: BLE001
            counts["crash"] += 1
            if show:
                print(f"  crash        {source}: {expr} | {assumptions}: {type(e).__name__}: {e}")
            continue
        fired = got != expr
        valid = True
        if fired:
            try:
                assert_refinement_valid(expr, assumptions, got)
            except AssertionError:
                valid = False
        if not valid:
            key = "fired, numerically wrong"
        elif expected is None:
            key = "unchanged as expected" if not fired else "fired where v3 test expects unchanged"
        elif not fired:
            key = "did not fire, v3 expects a result"
        else:
            same = False
            try:
                same = simplify(got - expected) == 0
            except Exception:  # noqa: BLE001
                same = got == expected
            key = "fired, same as v3" if same else "fired, other form"
        counts[key] += 1
        if show and key not in ("unchanged as expected", "fired, same as v3"):
            print(f"  {key:38s} {source}: {expr} | {assumptions} -> {got}  (v3: {expected})")
    print(f"\nbattery: {len(cases)} cases, handlers={os.environ.get('SATREFINE_HANDLERS', 'handlers')}")
    for key in ("fired, same as v3", "fired, other form", "did not fire, v3 expects a result",
                "unchanged as expected", "fired where v3 test expects unchanged", "fired, numerically wrong", "crash"):
        if counts[key]:
            print(f"  {counts[key]:5d}  {key}")


def main() -> None:
    args = parse()
    os.environ["SATREFINE_HANDLERS"] = args.handlers
    import satrefine  # noqa: F401
    if args.handlers == "handlers_identities":
        count_rows()
    cases = load_battery(args.battery)
    if cases:
        run_battery(cases, args.show)
    else:
        print(f"\nbattery {args.battery} is empty")
    if args.fuzz:
        seed, n = args.fuzz
        print(f"\nfuzz seed {seed}, {n} cases, handlers={args.handlers}")
        subprocess.run([sys.executable, str(ROOT / "tools/refine_fuzz.py"), seed, n, "--handlers", args.handlers],
                       cwd=ROOT, env=dict(os.environ))


if __name__ == "__main__":
    main()
