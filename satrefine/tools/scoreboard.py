#!/usr/bin/env python
"""The refine scoreboard: the battery, family sizes and fuzz, or a test suite under each ask backend.

Usage::

    PYTHONPATH=.:/path/to/sympy python -m satrefine.tools.scoreboard [battery] [options]
    ... battery                           # rows and code lines, then the battery (the default subcommand)
    ... battery --handlers handlers_v3    # the battery with another package (no rows or lines)
    ... battery --battery tests/refine_identities/battery_v3.py
    ... battery --family power_exp_log    # only the battery cases from that v3 test module (repeatable)
    ... battery --show                    # print every case that is not a clean pass
    ... battery --fuzz [SEED CASES]       # also refine_fuzz (default: a smoke run, seed 2, 200 cases)
    ... lines                             # only rows and code lines (same as battery --lines)

    ... suite                             # tests/refine under the sympy, satassume and combined backends
    ... suite --backends sympy,satassume  # a subset
    ... suite --junit-dir out/            # keep the junit files
    ... suite --reuse out/                # do not run, read junit-<backend>.xml
    ... suite --show-failures satassume   # print each failure's message
    ... suite --handlers handlers_v2 --suite tests/refine_v2   # another handler package and its suite
    ... suite -- -k pow                   # extra pytest arguments

``battery``: rows per family module (``satrefine.tools.lib.sizes``), code
lines of the engine (online and offline) and per family, then every case of
the battery classified (``satrefine.tools.lib.battery``): same as v3, other
form, miss, quiet, extra, numerically wrong, crash, plus the cases it could
not check numerically; totals and a per-family table.

``suite``: each backend runs the suite in its own pytest subprocess with
``SATREFINE_BACKEND`` set, and the outcomes are compared:

* a test that passes under ``sympy`` and fails under ``satassume`` is a
  satassume gap (a template or rule the engine lacks, or an out-of-scope
  query);
* a test that passes under ``satassume`` and fails under ``sympy`` is a
  satassume win;
* a test that passes under ``combined`` only is a simplification neither
  engine alone justifies;
* a test that fails under all three is a refine-handler gap, not an engine
  gap.

``refine_identity_scoreboard`` (= ``battery``) and ``refine_scoreboard``
(= ``suite``) are the old names of the two halves.  The exit status is 0 (1
for ``suite`` when no junit file could be read): this is a measurement.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from satrefine.tools.lib import battery as bat
from satrefine.tools.lib import sizes
from satrefine.tools.lib import suite as st
from satrefine.tools.lib.report import table
from satrefine.tools.lib.select import select

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ("battery", "lines", "suite")


# ---------------------------------------------------------------------------
# battery, rows, code lines
# ---------------------------------------------------------------------------

def print_rows() -> None:
    print(f"rows per family (handlers_identities, SATREFINE_IDENTITIES={os.environ.get('SATREFINE_IDENTITIES', 'generated')})")
    print(f"  {'module':18s} {'facts':>6s} {'exp':>6s} {'rules':>6s} {'simple':>6s} {'ranges':>6s} {'stage0':>6s} "
          f"{'generated':>10s}")
    total = Counter()

    def line(name, c):
        print(f"  {name:18s} {c['FACTS']:6d} {c['EXP_FORMS']:6d} {c['RULES']:6d} "
              f"{c['SIMPLE_RULES']:6d} {c['RANGES']:6d} {c['STAGE0']:6d} {c['GENERATED']:10d}")
    for name, counts in sizes.family_rows():
        total.update(counts)
        line(name, counts)
    line("total", total)


def print_code_lines() -> None:
    online, offline = sizes.engine_paths()
    print("code lines (no blanks, comments, docstrings)")

    def listed(paths: list[Path]) -> tuple[int, str]:
        counts = {str(p.relative_to(ROOT / "satrefine").with_suffix("")): sizes.code_lines(p) for p in paths}
        return sum(counts.values()), ", ".join(f"{k} {v}" for k, v in counts.items())
    (n_on, on), (n_off, off) = listed(online), listed(offline)
    print(f"  {'engine':10s} {n_on + n_off:5d}  online {n_on}: {on}; offline {n_off}: {off}")
    counts = {f: sizes.code_lines(p) for f, p in sizes.family_paths().items()}
    print(f"  {'families':10s} {sum(counts.values()):5d}  " + ", ".join(f"{k} {v}" for k, v in counts.items()))


def run_battery(cases: list, show: bool, families: list | None = None) -> None:
    """Classify each case (``lib.battery.classify``) and print the totals and the per-family table."""
    known_limit = bat.known_oracle_limit()
    counts: Counter = Counter()
    per_family: dict = defaultdict(Counter)
    unchecked = 0
    for expr, assumptions, expected, source in cases:
        family = bat.family_of(source)
        if families and family not in families:
            continue
        out = bat.classify(expr, assumptions, expected, source, known_limit)
        counts[out.key] += 1
        per_family[family][out.key] += 1
        if out.error is not None:
            if show:
                print(f"  crash        {source}: {expr} | {assumptions}: {type(out.error).__name__}: {out.error}")
            continue
        unchecked += out.unchecked
        if show and out.limit:
            print(f"  oracle limit {source}: {out.limit}")
        if show and out.unsampled is not None:
            print(f"  unsampled    {source}: {expr} | {assumptions}: {type(out.unsampled).__name__}: {out.unsampled}")
        if show and out.key not in ("unchanged as expected", "fired, same as v3"):
            print(f"  {out.key:38s} {source}: {expr} | {assumptions} -> {out.got}  (v3: {expected})")
    total = sum(counts.values())
    try:
        from satrefine.identities.core.driver import non_basic_returns
    except ImportError:
        non_basic_returns = {}
    if non_basic_returns:
        n = sum(non_basic_returns.values())
        print(f"\n  {n} handler results were not SymPy objects (sympified by the dispatcher):")
        for (key, handler), count in sorted(non_basic_returns.items()):
            print(f"    {count:5d}  {key}: {handler}")
    print(f"\nbattery: {total} cases, handlers={os.environ.get('SATREFINE_HANDLERS', 'handlers')}, "
          f"identities={os.environ.get('SATREFINE_IDENTITIES', 'generated')}")
    for key in bat.KEYS:
        if counts[key]:
            print(f"  {counts[key]:5d}  {key}")
    if unchecked:
        print(f"  {unchecked:5d}  {bat.UNCHECKED}")
    print(f"\n  {'family':16s}" + "".join(f"{bat.SHORT[k]:>7s}" for k in bat.KEYS))
    for family in sorted(per_family):
        c = per_family[family]
        print(f"  {family:16s}" + "".join(f"{c[k]:7d}" for k in bat.KEYS))


def battery(args) -> int:
    select(handlers=args.handlers)
    os.environ.setdefault("SATREFINE_STRICT_LOOPS", "1")   # a tripped loop guard is a crash here
    import satrefine  # noqa: F401
    if args.handlers == "handlers_identities":
        print_rows()
        print_code_lines()
        sys.stdout.flush()
    if args.lines:
        return 0
    cases, skipped = bat.load_battery(args.battery)
    if skipped:
        print(f"\n({skipped} battery cases under a patched ask are in SKIPPED and not run)")
    if cases:
        run_battery(cases, args.show, args.family)
    else:
        print(f"\nbattery {args.battery} is empty")
    if args.fuzz is not None:
        seed, n = (args.fuzz + ["2", "200"])[:2]
        print(f"\nfuzz seed {seed}, {n} cases, handlers={args.handlers}")
        subprocess.run([sys.executable, "-m", "satrefine.tools.refine_fuzz", seed, n, "--handlers", args.handlers],
                       cwd=ROOT, env=dict(os.environ))
    return 0


# ---------------------------------------------------------------------------
# a test suite under each backend
# ---------------------------------------------------------------------------

def suite(args, error) -> int:
    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    unknown = [b for b in backends if b not in st.BACKENDS]
    if unknown:
        error(f"unknown backends {unknown}; choose from {st.BACKENDS}")

    junit_dir = args.reuse or args.junit_dir or Path(tempfile.mkdtemp(prefix="refine-scoreboard-"))
    junit_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict[str, str]] = {}
    messages: dict[str, dict[str, str]] = {}
    counts: dict[str, dict[str, dict[str, int]]] = {}
    wall: dict[str, float] = {}
    for backend in backends:
        junit = junit_dir / f"junit-{backend}.xml"
        if args.reuse is None:
            wall[backend] = st.run_backend(backend, args.suite, junit, args.pytest_args, args.handlers)
        if not junit.exists():
            print(f"{backend}: no junit file at {junit}", file=sys.stderr)
            continue
        results[backend], messages[backend], counts[backend], test_time = st.parse_junit(junit)
        wall.setdefault(backend, test_time)

    if not results:
        return 1

    print(f"# Refine scoreboard: {args.suite} under each ask backend"
          f"{' (handlers: ' + args.handlers + ')' if args.handlers else ''}\n")
    rows = []
    for backend in backends:
        if backend not in results:
            continue
        c = Counter(results[backend].values())
        rows.append([backend, sum(c[o] for o in st.PASSING), c["failed"] + c["error"],
                     c["xfailed"], c["skipped"], len(results[backend]), f"{wall[backend]:.1f}s"])
    table(rows, ["backend", "passed", "failed", "xfailed", "skipped", "total", "time"])

    print("\n## Passed / total by test module\n")
    modules = sorted({st.module_of(t) for r in results.values() for t in r})
    rows = []
    for module in modules:
        row = [module]
        for backend in backends:
            if backend not in results:
                continue
            ids = [t for t in results[backend] if st.module_of(t) == module]
            ok = sum(results[backend][t] in st.PASSING for t in ids)
            row.append(f"{ok}/{len(ids)}" if ids else "-")
        rows.append(row)
    table(rows, ["module", *[b for b in backends if b in results]])

    all_ids = sorted(set().union(*(set(r) for r in results.values())))

    def ok(backend: str, test_id: str) -> bool:
        return results.get(backend, {}).get(test_id) in st.PASSING

    def scope_note(test_id: str) -> str:
        c = counts.get("satassume", {}).get(test_id, {})
        out = {k: v for k, v in c.items() if k in st.OUT_OF_SCOPE and v}
        parts = [f"{k} x{v}" for k, v in sorted(out.items())]
        if c.get("undecided"):
            parts.append(f"undecided in-scope x{c['undecided']}")
        return f"  [{', '.join(parts)}]" if parts else ""

    def section(title: str, ids: list[str], notes: bool = False) -> None:
        print(f"\n## {title} ({len(ids)})\n")
        for t in ids:
            print(f"- {t}{scope_note(t) if notes else ''}")

    def out_of_scope(test_id: str) -> bool:
        c = counts.get("satassume", {}).get(test_id, {})
        return any(c.get(k) for k in st.OUT_OF_SCOPE)

    def xfailed_everywhere(test_id: str) -> bool:
        return all(results[b].get(test_id) == "xfailed" for b in results)

    have = set(results)
    if {"sympy", "satassume"} <= have:
        gaps = [t for t in all_ids if ok("sympy", t) and not ok("satassume", t)]
        section("satassume in-scope gaps: pass under sympy, fail under satassume, "
                "only in-scope queries asked", [t for t in gaps if not out_of_scope(t)], notes=True)
        section("satassume out of scope: pass under sympy, fail under satassume, "
                "relations or matrix predicates asked", [t for t in gaps if out_of_scope(t)], notes=True)
        wins = [t for t in all_ids if ok("satassume", t) and not ok("sympy", t)]
        section("satassume wins: pass under satassume, fail under sympy, "
                "only in-scope queries asked", [t for t in wins if not out_of_scope(t)], notes=True)
        section("pass under satassume only because a handler did not fire: "
                "fail under sympy, out-of-scope queries asked", [t for t in wins if out_of_scope(t)], notes=True)
    if have == set(st.BACKENDS):
        section("combination wins: pass under combined only",
                [t for t in all_ids if ok("combined", t) and not ok("sympy", t) and not ok("satassume", t)])
    everywhere = [t for t in all_ids if not any(ok(b, t) for b in have)]
    section("refine gaps: fail under every backend", [t for t in everywhere if not xfailed_everywhere(t)])
    section("expected failures under every backend (xfail)", [t for t in everywhere if xfailed_everywhere(t)])

    if args.show_failures:
        b = args.show_failures
        print(f"\n## Failures under {b}\n")
        for t in all_ids:
            if results.get(b, {}).get(t) in ("failed", "error"):
                print(f"- {t}\n    {messages[b].get(t, '')}")

    if args.reuse is None and args.junit_dir is None:
        print(f"\n(junit files in {junit_dir})")
    return 0


# ---------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------

def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m satrefine.tools.scoreboard", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command")
    for name in ("battery", "lines"):
        p = sub.add_parser(name, help="rows, code lines and the battery" if name == "battery"
                           else "only rows and code lines")
        p.add_argument("--handlers", default="handlers_identities")
        p.add_argument("--battery", default=str(bat.DEFAULT))
        p.add_argument("--fuzz", nargs="*", metavar="SEED CASES",
                       help="also run refine_fuzz; with no values a smoke run (seed 2, 200 cases)")
        p.add_argument("--show", action="store_true", help="print every case that is not a clean pass")
        p.add_argument("--lines", action="store_true", help="only count code lines and rows")
        p.add_argument("--family", action="append", help="battery families to run (by test module name), repeatable")
    p = sub.add_parser("suite", help="a test suite under each ask backend")
    p.add_argument("--backends", default=",".join(st.BACKENDS))
    p.add_argument("--suite", default="tests/refine")
    p.add_argument("--handlers", help="handler package to load (SATREFINE_HANDLERS), e.g. handlers_v2")
    p.add_argument("--junit-dir", type=Path, help="directory to keep junit-<backend>.xml in")
    p.add_argument("--reuse", type=Path, help="read junit-<backend>.xml from this directory instead of running")
    p.add_argument("--show-failures", metavar="BACKEND", help="print every failing test of this backend with its message")
    p.add_argument("pytest_args", nargs="*", help="extra pytest arguments after --")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in (*COMMANDS, "-h", "--help"):
        argv = ["battery", *argv]                  # the default subcommand
    ap = parser()
    args = ap.parse_args(argv)
    if args.command == "suite":
        return suite(args, ap.error)
    if args.command == "lines":
        args.lines = True
    return battery(args)


if __name__ == "__main__":
    sys.exit(main())
