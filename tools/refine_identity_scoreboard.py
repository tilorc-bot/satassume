#!/usr/bin/env python
"""Scoreboard for the identity-based handlers: rows per family, battery, fuzz.

Usage::

    PYTHONPATH=.:/path/to/sympy .venv/bin/python tools/refine_identity_scoreboard.py
    ... --handlers handlers_v3            # run the battery with another package
    ... --battery tests/refine_identities/battery_v3.py
    ... --family power_exp_log            # only the battery cases from that v3 test module
    ... --fuzz                            # also a fuzz smoke run (seed 2, 200 cases)
    ... --fuzz 2 1500                     # a full fuzz run (seed, cases)

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
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--handlers", default="handlers_identities")
    p.add_argument("--battery", default=str(ROOT / "tests/refine_identities/battery_v3.py"))
    p.add_argument("--fuzz", nargs="*", metavar="SEED CASES",
                   help="also run tools/refine_fuzz.py; with no values a smoke run (seed 2, 200 cases)")
    p.add_argument("--show", action="store_true", help="print every case that is not a clean pass")
    p.add_argument("--family", action="append", help="battery families to run (by test module name), repeatable")
    return p.parse_args()


def count_rows() -> None:
    """Rows per family module; ``generated`` is the size of ``generated/<family>.py`` if present."""
    import satrefine.handlers_identities as package
    print(f"rows per family (handlers_identities, SATREFINE_IDENTITIES={os.environ.get('SATREFINE_IDENTITIES', 'generated')})")
    print(f"  {'module':18s} {'facts':>6s} {'exp':>6s} {'rules':>6s} {'simple':>6s} {'generated':>10s}")
    total = Counter()
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_") or info.ispkg:
            continue
        mod = importlib.import_module(f"{package.__name__}.{info.name}")
        def n(m, name: str) -> int:
            v = getattr(m, name, None)
            return v if isinstance(v, int) else len(v) if v is not None else 0
        counts = {k: n(mod, k) for k in ("FACTS", "EXP_FORMS", "RULES", "SIMPLE_RULES")}
        try:
            gen = importlib.import_module(f"{package.__name__}.generated.{info.name}")
            counts["GENERATED"] = n(gen, "RULES")
        except ModuleNotFoundError:
            counts["GENERATED"] = 0
        total.update(counts)
        print(f"  {info.name:18s} {counts['FACTS']:6d} {counts['EXP_FORMS']:6d} {counts['RULES']:6d} "
              f"{counts['SIMPLE_RULES']:6d} {counts['GENERATED']:10d}")
    print(f"  {'total':18s} {total['FACTS']:6d} {total['EXP_FORMS']:6d} {total['RULES']:6d} "
          f"{total['SIMPLE_RULES']:6d} {total['GENERATED']:10d}")


def load_battery(path: str) -> tuple[list, int]:
    spec = importlib.util.spec_from_file_location("battery", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return list(mod.BATTERY), len(getattr(mod, "SKIPPED", ()))


KEYS = ("fired, same as v3", "fired, other form", "did not fire, v3 expects a result",
        "unchanged as expected", "fired where v3 expects unchanged", "fired, numerically wrong", "crash")
UNCHECKED = "numerically unchecked (matrix symbols, no sample, or the sampler raised)"


def _family(source: str) -> str:
    name = source.split("::", 1)[0]
    return name[len("test_"):-len(".py")] if name.startswith("test_") and name.endswith(".py") else name


def _same(got, expected) -> bool:
    from sympy import simplify
    if got == expected:
        return True
    try:
        return simplify(got - expected) == 0
    except Exception:  # noqa: BLE001
        return False


def _known_oracle_limit():
    """``test_battery._known_oracle_limit``: mismatches the numeric oracle is known to report wrongly."""
    tests_dir = str(ROOT / "tests" / "refine_identities")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    try:
        return importlib.import_module("test_battery")._known_oracle_limit
    except Exception as e:  # noqa: BLE001  (test_battery needs pytest; without it every mismatch counts as wrong)
        print(f"  (known oracle limits unavailable: {type(e).__name__}: {e}; run with pytest installed)")
        return lambda expr, assumptions, expected, source: None


def run_battery(cases: list, show: bool, families: list | None = None) -> None:
    """Classify each case; the numeric check follows ``test_battery.py``'s conventions:
    matrix symbols, unsampleable assumptions, a raising sampler and the oracle's
    known limits are unchecked, not wrong."""
    from sympy import MatrixSymbol
    from satrefine import refine
    from satrefine.harness import assert_refinement_valid
    known_limit = _known_oracle_limit()
    counts: Counter = Counter()
    per_family: dict = defaultdict(Counter)
    unchecked = 0
    for expr, assumptions, expected, source in cases:
        family = _family(source)
        if families and family not in families:
            continue
        try:
            got = refine(expr, assumptions)
        except Exception as e:  # noqa: BLE001
            counts["crash"] += 1
            per_family[family]["crash"] += 1
            if show:
                print(f"  crash        {source}: {expr} | {assumptions}: {type(e).__name__}: {e}")
            continue
        fired = got != expr
        valid = True
        if fired:
            if expr.has(MatrixSymbol) or got.has(MatrixSymbol):
                unchecked += 1
            else:
                try:
                    assert_refinement_valid(expr, assumptions, got)
                except AssertionError as e:
                    limit = None if str(e).startswith("no satisfying sample") else known_limit(expr, assumptions, got, source)
                    if str(e).startswith("no satisfying sample") or limit:
                        unchecked += 1
                        if show and limit:
                            print(f"  oracle limit {source}: {limit}")
                    else:
                        valid = False
                except Exception as e:  # noqa: BLE001  (e.g. the oracle's sampler asking about a relation at a complex point)
                    unchecked += 1
                    if show:
                        print(f"  unsampled    {source}: {expr} | {assumptions}: {type(e).__name__}: {e}")
        if not valid:
            key = "fired, numerically wrong"
        elif expected is None:
            key = "unchanged as expected" if not fired else "fired where v3 expects unchanged"
        elif not fired:
            key = "did not fire, v3 expects a result"
        else:
            key = "fired, same as v3" if _same(got, expected) else "fired, other form"
        counts[key] += 1
        per_family[family][key] += 1
        if show and key not in ("unchanged as expected", "fired, same as v3"):
            print(f"  {key:38s} {source}: {expr} | {assumptions} -> {got}  (v3: {expected})")
    total = sum(counts.values())
    print(f"\nbattery: {total} cases, handlers={os.environ.get('SATREFINE_HANDLERS', 'handlers')}, "
          f"identities={os.environ.get('SATREFINE_IDENTITIES', 'generated')}")
    for key in KEYS:
        if counts[key]:
            print(f"  {counts[key]:5d}  {key}")
    if unchecked:
        print(f"  {unchecked:5d}  {UNCHECKED}")
    short = {"fired, same as v3": "same", "fired, other form": "other", "did not fire, v3 expects a result": "miss",
             "unchanged as expected": "quiet", "fired where v3 expects unchanged": "extra",
             "fired, numerically wrong": "wrong", "crash": "crash"}
    print(f"\n  {'family':16s}" + "".join(f"{short[k]:>7s}" for k in KEYS))
    for family in sorted(per_family):
        c = per_family[family]
        print(f"  {family:16s}" + "".join(f"{c[k]:7d}" for k in KEYS))


def main() -> None:
    args = parse()
    os.environ["SATREFINE_HANDLERS"] = args.handlers
    import satrefine  # noqa: F401
    if args.handlers == "handlers_identities":
        count_rows()
        sys.stdout.flush()
    cases, skipped = load_battery(args.battery)
    if skipped:
        print(f"\n({skipped} battery cases under a patched ask are in SKIPPED and not run)")
    if cases:
        run_battery(cases, args.show, args.family)
    else:
        print(f"\nbattery {args.battery} is empty")
    if args.fuzz is not None:
        seed, n = (args.fuzz + ["2", "200"])[:2]
        print(f"\nfuzz seed {seed}, {n} cases, handlers={args.handlers}")
        subprocess.run([sys.executable, str(ROOT / "tools/refine_fuzz.py"), seed, n, "--handlers", args.handlers],
                       cwd=ROOT, env=dict(os.environ))


if __name__ == "__main__":
    main()
