#!/usr/bin/env python
"""Run the refine suite under each ask backend and compare the outcomes.

The refine handlers in ``satrefine`` ask their predicate questions through
one seam, ``satrefine.identities.compat.backend``, which can be SymPy's ``ask``, satassume's
``ask``, or the two combined.  Running ``tests/refine`` under each backend
measures how much of the refine work each engine can justify:

* a test that passes under ``sympy`` and fails under ``satassume`` is a
  satassume gap (a template or rule the engine lacks, or an out-of-scope
  query);
* a test that passes under ``satassume`` and fails under ``sympy`` is a
  satassume win;
* a test that passes under ``combined`` only is a simplification neither
  engine alone justifies;
* a test that fails under all three is a refine-handler gap, not an engine
  gap.

Usage::

    PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satrefine.tools.refine_scoreboard
    ... --backends sympy,satassume        # a subset
    ... --junit-dir out/                  # keep the junit files
    ... --reuse out/                      # do not run, read junit-<backend>.xml
    ... --show-failures satassume         # print each failure's message
    ... --handlers handlers_v2 --suite tests/refine_v2   # another handler package and its suite
    ... -- -k pow                         # extra pytest arguments

Each backend runs in its own pytest subprocess with ``SATREFINE_BACKEND``
set, so the environment of the calling shell (``PYTHONPATH`` in particular)
is what the runs see.  The exit status is always 0: this is a measurement.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
BACKENDS = ("sympy", "satassume", "combined")
PASSING = ("passed", "xpassed")


def run_backend(backend: str, suite: str, junit: Path, pytest_args: list[str], handlers: str | None = None) -> float:
    env = dict(os.environ, SATREFINE_BACKEND=backend)
    if handlers:
        env["SATREFINE_HANDLERS"] = handlers
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
           "--junitxml", str(junit), suite, *pytest_args]
    start = perf_counter()
    subprocess.run(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return perf_counter() - start


OUT_OF_SCOPE = ("relation", "matrix", "custom", "other")


def parse_junit(path: Path) -> tuple[dict[str, str], dict[str, str], dict[str, dict[str, int]], float]:
    """Return {test id: outcome}, {test id: failure message}, {test id: ask counts}, total time."""
    outcomes: dict[str, str] = {}
    messages: dict[str, str] = {}
    counts: dict[str, dict[str, int]] = {}
    total = 0.0
    for case in ET.parse(path).getroot().iter("testcase"):
        test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
        total += float(case.get("time", 0) or 0)
        outcome = "passed"
        counts[test_id] = {}
        for child in case:
            tag = child.tag
            if tag == "properties":
                for prop in child:
                    name = prop.get("name", "")
                    if name.startswith("ask_"):
                        counts[test_id][name[4:]] = int(prop.get("value", 0))
                continue
            if tag == "failure":
                outcome = "failed"
            elif tag == "error":
                outcome = "error"
            elif tag == "skipped":
                outcome = "xfailed" if child.get("type") == "pytest.xfail" else "skipped"
            else:
                continue
            messages[test_id] = (child.get("message") or "").strip().splitlines()[0][:160] if child.get("message") else (child.text or "").strip().splitlines()[-1][:160] if child.text else ""
        outcomes[test_id] = outcome
    return outcomes, messages, counts, total


def module_of(test_id: str) -> str:
    return test_id.split("::")[0].rsplit(".", 1)[-1]


def print_table(rows: list[list[str]], header: list[str]) -> None:
    widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
    line = "  ".join(str(h).ljust(w) for h, w in zip(header, widths))
    print(line)
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(r, widths)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--backends", default=",".join(BACKENDS))
    ap.add_argument("--suite", default="tests/refine")
    ap.add_argument("--handlers", help="handler package to load (SATREFINE_HANDLERS), e.g. handlers_v2")
    ap.add_argument("--junit-dir", type=Path, help="directory to keep junit-<backend>.xml in")
    ap.add_argument("--reuse", type=Path, help="read junit-<backend>.xml from this directory instead of running")
    ap.add_argument("--show-failures", metavar="BACKEND", help="print every failing test of this backend with its message")
    ap.add_argument("pytest_args", nargs="*", help="extra pytest arguments after --")
    args = ap.parse_args(argv)

    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    unknown = [b for b in backends if b not in BACKENDS]
    if unknown:
        ap.error(f"unknown backends {unknown}; choose from {BACKENDS}")

    junit_dir = args.reuse or args.junit_dir or Path(tempfile.mkdtemp(prefix="refine-scoreboard-"))
    junit_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict[str, str]] = {}
    messages: dict[str, dict[str, str]] = {}
    counts: dict[str, dict[str, dict[str, int]]] = {}
    wall: dict[str, float] = {}
    for backend in backends:
        junit = junit_dir / f"junit-{backend}.xml"
        if args.reuse is None:
            wall[backend] = run_backend(backend, args.suite, junit, args.pytest_args, args.handlers)
        if not junit.exists():
            print(f"{backend}: no junit file at {junit}", file=sys.stderr)
            continue
        results[backend], messages[backend], counts[backend], test_time = parse_junit(junit)
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
        rows.append([backend, sum(c[o] for o in PASSING), c["failed"] + c["error"],
                     c["xfailed"], c["skipped"], len(results[backend]), f"{wall[backend]:.1f}s"])
    print_table(rows, ["backend", "passed", "failed", "xfailed", "skipped", "total", "time"])

    print("\n## Passed / total by test module\n")
    modules = sorted({module_of(t) for r in results.values() for t in r})
    rows = []
    for module in modules:
        row = [module]
        for backend in backends:
            if backend not in results:
                continue
            ids = [t for t in results[backend] if module_of(t) == module]
            ok = sum(results[backend][t] in PASSING for t in ids)
            row.append(f"{ok}/{len(ids)}" if ids else "-")
        rows.append(row)
    print_table(rows, ["module", *[b for b in backends if b in results]])

    all_ids = sorted(set().union(*(set(r) for r in results.values())))

    def ok(backend: str, test_id: str) -> bool:
        return results.get(backend, {}).get(test_id) in PASSING

    def scope_note(test_id: str) -> str:
        c = counts.get("satassume", {}).get(test_id, {})
        out = {k: v for k, v in c.items() if k in OUT_OF_SCOPE and v}
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
        return any(c.get(k) for k in OUT_OF_SCOPE)

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
    if have == set(BACKENDS):
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


if __name__ == "__main__":
    sys.exit(main())
