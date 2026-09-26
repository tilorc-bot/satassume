#!/usr/bin/env python
"""Row ablation for the ``handlers_identities`` rule tables: which rows can go.

For a family module (``integer_funcs``, ``combinatorial``, ``minmax_deltas``,
``matrices``, ...), every row of its ``RULES`` is removed in turn, in
process and without editing files, and the family is measured against three
gates:

1. **battery**: the family's cases of ``tests/refine_identities/battery_v3.py``,
   classified exactly as ``tools/refine_identity_scoreboard.py`` does.  A
   case that was "same" or "other form" must stay one of the two, a "quiet"
   case (unchanged as v3 expects) must stay quiet, and no case may become
   "wrong" or "crash";
2. **tests**: ``tests/refine_identities/test_<family>.py`` and
   ``test_engine_<family>.py``; every test that passed must still pass.
   Run only for rows gate 1 does not already keep (``--full``: for every
   row, to list the tests each row is responsible for).
   Tests that only assert the table size (``test_table_size*``, see
   ``--ignore-test``) are reported, not counted;
3. **soundness**: ``tools/refine_differential.py``'s inputs (``--seed``,
   ``--cases``) restricted to the inputs containing one of the family's
   heads, checked numerically with its edge points; no input may become
   unsound, crash or time out that did not before.  Slow, so run only on
   rows that pass gates 1 and 2.

A row is removed from every table of the module that holds it (shared rows,
such as a generic-head row serving several keys, go everywhere at once) and
from the module's own lists, so a test reading ``mod.RULES`` sees the
ablated table.  Each measurement runs in a fresh subprocess (``--worker``),
one at a time.

After the single-row pass, droppable rows are removed greedily in table
order, each re-checked against all accepted removals (rows interact: two
rows may each be redundant only because of the other).  The final set is
checked with gate 3.

Usage::

    PYTHONPATH=.:/path/to/sympy python tools/refine_ablate.py integer_funcs
    ... --no-soundness                    # gates 1 and 2 only
    ... --seed 2 --cases 400              # the soundness sample (default)
    ... --save-baseline b.json            # measure the working tree as is and save it
    ... --compare-to b.json               # measure the working tree against a saved baseline
                                          # (for hand-made merges: edit the module, compare, revert)

The exit status is always 0: this is a measurement.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests" / "refine_identities"
GOOD = ("same", "other")
SHORT = {"fired, same as v3": "same", "fired, other form": "other",
         "did not fire, v3 expects a result": "miss", "unchanged as expected": "quiet",
         "fired where v3 expects unchanged": "extra", "fired, numerically wrong": "wrong", "crash": "crash"}


# ---------------------------------------------------------------------------
# worker: ablate in process, measure, write JSON
# ---------------------------------------------------------------------------

def family_file(family: str) -> Path:
    """The family's module file (``satrefine/identities/rules/`` or, for the matrices, ``compat/``)."""
    package = ROOT / "satrefine" / "identities"
    return next((p for p in (package / "rules" / f"{family}.py", package / "compat" / f"{family}.py") if p.exists()),
                package / "rules" / f"{family}.py")


def family_module(family: str) -> str:
    """The family's module name (see :func:`family_file`)."""
    return ".".join(family_file(family).relative_to(ROOT).with_suffix("").parts)


def family_keys(family: str) -> list[str]:
    """The keys the module registers (its literal ``handlers_dict['key'] = ...`` lines)."""
    src = family_file(family).read_text()
    return re.findall(r"handlers_dict\[['\"](\w+)['\"]\]\s*=", src)


def _norm(row) -> tuple:
    return tuple(row) + (None,) * (4 - len(row))


def _table_parts(handler) -> list:
    """The table handlers (with ``rows``) of a key: the handler itself, or the parts of a ``chain``."""
    if hasattr(handler, "rows"):
        return [handler]
    return [t for part in getattr(handler, "parts", ()) for t in _table_parts(part)]


def ablate(family: str, drop: list[int]) -> list[str]:
    """Remove ``RULES[i]`` for ``i`` in ``drop`` from every table of the module; describe what was removed."""
    from satrefine._upstream import handlers_dict
    mod = importlib.import_module(family_module(family))
    rules = list(mod.RULES)
    gone = [_norm(rules[i]) for i in drop]
    for key in family_keys(family):
        for h in _table_parts(handlers_dict[key]):
            h.rows[:] = [r for r in h.rows if _norm(r) not in gone]     # the closure's own list
    for name, value in vars(mod).items():
        if isinstance(value, list) and value and all(isinstance(r, tuple) for r in value):
            value[:] = [r for r in value if _norm(r) not in gone]
    return [str(rules[i]) for i in drop]


def classify_battery(family: str) -> dict:
    """``case id -> (short key, result)`` for the family's battery cases, as the scoreboard classifies them."""
    from sympy import MatrixSymbol, sympify

    from satrefine import refine
    from satrefine.testing.harness import assert_refinement_valid
    sys.path.insert(0, str(ROOT / "tools"))
    sb = importlib.import_module("refine_identity_scoreboard")
    cases, _ = sb.load_battery(str(TESTS / "battery_v3.py"))
    known_limit = sb._known_oracle_limit()
    out = {}
    for index, (expr, assumptions, expected, source) in enumerate(cases):
        if sb._family(source) != family:
            continue
        cid = f"{index}:{source}"
        try:
            got = sympify(refine(expr, assumptions))
        except Exception as e:  # noqa: BLE001
            out[cid] = ("crash", f"{type(e).__name__}: {str(e)[:120]}")
            continue
        fired = got != expr
        valid = True
        if fired and not (expr.has(MatrixSymbol) or got.has(MatrixSymbol)):
            try:
                assert_refinement_valid(expr, assumptions, got)
            except AssertionError as e:
                if not (str(e).startswith("no satisfying sample") or known_limit(expr, assumptions, got, source)):
                    valid = False
            except Exception:  # noqa: BLE001  (unsampled: unchecked, not wrong)
                pass
        if not valid:
            key = "wrong"
        elif expected is None:
            key = "extra" if fired else "quiet"
        elif not fired:
            key = "miss"
        else:
            key = "same" if sb._same(got, expected) else "other"
        out[cid] = (key, str(got))
    return out


class _Collector:
    def __init__(self):
        self.outcomes: dict[str, str] = {}

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            outcome = "xfailed" if hasattr(report, "wasxfail") and report.skipped else report.outcome
            if report.nodeid not in self.outcomes or outcome != "passed":
                self.outcomes[report.nodeid] = outcome


def run_tests(family: str) -> dict:
    import pytest
    paths = [str(p) for p in (TESTS / f"test_{family}.py", TESTS / f"test_engine_{family}.py") if p.exists()]
    col = _Collector()
    pytest.main(["-q", "-p", "no:cacheprovider", "--no-header", "-rN", *paths], plugins=[col])
    return col.outcomes


class _Timeout(Exception):
    pass


def soundness(family: str, seed: int, cases: int, timeout: int) -> dict:
    """``case -> record`` for ``refine_differential``'s inputs that contain one of the family's heads."""
    from sympy import Basic, preorder_traversal, srepr, sympify
    sys.path.insert(0, str(ROOT / "tools"))
    rd = importlib.import_module("refine_differential")
    f = rd.fz()
    keys = set(family_keys(family))

    def on_alarm(signum, frame):
        raise _Timeout

    signal.signal(signal.SIGALRM, on_alarm)
    out = {}
    for case in range(cases):
        g = rd.generate(seed, case)
        if g is None:
            continue
        head, e, assumptions, combos, rel = g
        if not any(type(n).__name__ in keys for n in preorder_traversal(e)):
            continue
        rec = {"head": head, "expr": str(e), "assumptions": str(assumptions)}
        signal.alarm(timeout)
        try:
            try:
                r = f.sat_refine(e, assumptions)
                if not isinstance(r, Basic):
                    r = sympify(r)
            except ValueError as ex:
                if "nconsistent" in str(ex):
                    rec["status"] = "inconsistent"
                    out[str(case)] = rec
                    continue
                raise
            if r == e:
                rec["status"] = "unchanged"
            else:
                rec["status"] = "fired"
                rec["result"] = srepr(r)
                rec["result_str"] = str(r)
                points = rd.check_points([e, r], combos, rel, random.Random(seed * 7919 + case))
                _, ce = rd.compare(e, r, points)
                if ce:
                    pt, a, b = ce
                    rec["unsound"] = {"point": {str(k): str(v) for k, v in pt.items()},
                                      "orig": rd._fmt(a), "refined": rd._fmt(b)}
        except _Timeout:
            rec["status"] = "timeout"
        except Exception as ex:  # noqa: BLE001
            rec["status"] = "crash"
            rec["error"] = f"{type(ex).__name__}: {str(ex)[:160]}"
        finally:
            signal.alarm(0)
        out[str(case)] = rec
    return out


def worker(args) -> None:
    os.environ["SATREFINE_HANDLERS"] = "handlers_identities"
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(TESTS))
    import satrefine  # noqa: F401
    drop = [int(i) for i in args.drop.split(",") if i != ""] if args.drop else []
    t0 = time.time()
    result = {"family": args.family, "drop": drop, "removed": ablate(args.family, drop)}
    if "battery" in args.gates:
        result["battery"] = classify_battery(args.family)
    if "tests" in args.gates:
        result["tests"] = run_tests(args.family)
    if "soundness" in args.gates:
        result["soundness"] = soundness(args.family, args.seed, args.cases, args.timeout)
    result["seconds"] = time.time() - t0
    with open(args.out, "w") as fh:
        json.dump(result, fh)


# ---------------------------------------------------------------------------
# parent: one subprocess per measurement, compare with the baseline
# ---------------------------------------------------------------------------

def measure(args, drop: list[int], gates: tuple[str, ...]) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "m.json")
        cmd = [sys.executable, str(Path(__file__).resolve()), args.family, "--worker", "--out", out,
               "--drop", ",".join(map(str, drop)), "--gates", ",".join(gates),
               "--seed", str(args.seed), "--cases", str(args.cases), "--timeout", str(args.timeout)]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=ROOT)
        if proc.returncode != 0 or not os.path.exists(out):
            sys.stderr.write(proc.stdout[-3000:] + proc.stderr[-3000:])
            raise SystemExit(f"worker failed for drop={drop} ({proc.returncode})")
        with open(out) as fh:
            return json.load(fh)


def regressions(base: dict, now: dict, ignore: list[str]) -> dict:
    """What ``now`` loses against ``base``, per gate; an empty dict is a pass."""
    lost: dict = {}
    if "battery" in now:
        bad = []
        for cid, (key, got) in now["battery"].items():
            was = base["battery"].get(cid, (None, None))[0]
            if key in ("wrong", "crash") or (was in GOOD and key not in GOOD) or (was == "quiet" and key != "quiet"):
                bad.append(f"{cid}: {was} -> {key} ({got[:80]})")
        if bad:
            lost["battery"] = bad
    if "tests" in now:
        bad, exempt = [], []
        for nodeid, outcome in base["tests"].items():
            if outcome == "passed" and now["tests"].get(nodeid) != "passed":
                (exempt if any(s in nodeid for s in ignore) else bad).append(nodeid)
        if bad:
            lost["tests"] = bad
        if exempt:
            lost["_exempt_tests"] = exempt
    if "soundness" in now:
        bad = []
        for case, rec in now["soundness"].items():
            was = base["soundness"].get(case, {})
            new_unsound = "unsound" in rec and ("unsound" not in was or was.get("result") != rec.get("result"))
            new_crash = rec.get("status") in ("crash", "timeout") and was.get("status") not in ("crash", "timeout")
            if new_unsound or new_crash:
                bad.append(f"case {case} [{rec['head']}] refine({rec['expr']}, {rec['assumptions']}) -> "
                           f"{rec.get('result_str', rec.get('error', rec['status']))}")
        if bad:
            lost["soundness"] = bad
    return lost


def fails(lost: dict) -> bool:
    return any(k for k in lost if not k.startswith("_"))


def summary(m: dict) -> str:
    from collections import Counter
    parts = []
    if "battery" in m:
        c = Counter(k for k, _ in m["battery"].values())
        parts.append("battery " + " ".join(f"{k}={c[k]}" for k in SHORT.values() if c[k]))
    if "tests" in m:
        c = Counter(m["tests"].values())
        parts.append("tests " + " ".join(f"{k}={v}" for k, v in sorted(c.items())))
    if "soundness" in m:
        recs = m["soundness"].values()
        parts.append(f"soundness inputs={len(m['soundness'])} fired={sum(r.get('status') == 'fired' for r in recs)} "
                     f"unsound={sum('unsound' in r for r in recs)} "
                     f"crash/timeout={sum(r.get('status') in ('crash', 'timeout') for r in recs)}")
    return "; ".join(parts)


def changed_outputs(base: dict, now: dict) -> list[str]:
    """Battery cases that stay acceptable but come out different (informative)."""
    return [f"{cid}: {base['battery'][cid][1][:60]} -> {got[:60]}"
            for cid, (key, got) in now.get("battery", {}).items()
            if cid in base["battery"] and base["battery"][cid][1] != got]


def show_lost(lost: dict, indent: str = "      ", cap: int = 8) -> None:
    for gate, items in lost.items():
        label = "exempt tests (table size)" if gate == "_exempt_tests" else gate
        print(f"{indent}{label}: {len(items)}")
        for it in items[:cap]:
            print(f"{indent}  {it}")
        if len(items) > cap:
            print(f"{indent}  ... {len(items) - cap} more")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("family")
    ap.add_argument("--seed", type=int, default=2)
    ap.add_argument("--cases", type=int, default=400)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--no-soundness", action="store_true", help="skip gate 3")
    ap.add_argument("--ignore-test", action="append", default=["test_table_size"],
                    help="substring of test ids whose failure is reported, not counted (repeatable)")
    ap.add_argument("--full", action="store_true",
                    help="run the tests for every row (default: only for rows the battery does not need)")
    ap.add_argument("--rows", help="comma-separated row indices to try (default: all)")
    ap.add_argument("--save-baseline", metavar="JSON", help="measure the working tree, save, exit")
    ap.add_argument("--keep-baseline", metavar="JSON", help="also save the baseline of a full run (for --compare-to)")
    ap.add_argument("--compare-to", metavar="JSON", help="measure the working tree against a saved baseline, exit")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--drop", default="", help=argparse.SUPPRESS)
    ap.add_argument("--gates", default="battery,tests,soundness", help=argparse.SUPPRESS)
    ap.add_argument("--out", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)      # progress is visible when redirected to a file
    if args.worker:
        worker(args)
        return

    all_gates = ("battery", "tests") if args.no_soundness else ("battery", "tests", "soundness")
    t0 = time.time()
    if args.save_baseline:
        m = measure(args, [], all_gates)
        Path(args.save_baseline).write_text(json.dumps(m))
        print(f"baseline {args.family}: {summary(m)} ({m['seconds']:.0f}s) -> {args.save_baseline}")
        return
    if args.compare_to:
        base = json.loads(Path(args.compare_to).read_text())
        gates = tuple(g for g in all_gates if g in base)
        m = measure(args, [], gates)
        lost = regressions(base, m, args.ignore_test)
        print(f"baseline: {summary(base)}\nnow:      {summary(m)}")
        print("PASS" if not fails(lost) else "FAIL")
        show_lost(lost, "  ", cap=50)
        for line in changed_outputs(base, m):
            print(f"  changed output (still acceptable) {line}")
        return

    base = measure(args, [], all_gates)
    if args.keep_baseline:
        Path(args.keep_baseline).write_text(json.dumps(base))
    import satrefine  # noqa: F401  (only to read the rows for printing, in the parent)
    rules = importlib.import_module(family_module(args.family)).RULES
    print(f"family {args.family}: {len(rules)} rows, keys {', '.join(family_keys(args.family))}")
    print(f"baseline: {summary(base)} ({base['seconds']:.0f}s)")
    rows = [int(i) for i in args.rows.split(",")] if args.rows else list(range(len(rules)))

    print("\n== single-row removal (gates 1 and 2) ==")
    single = []
    for i in rows:
        m = measure(args, [i], ("battery",) if not args.full else ("battery", "tests"))
        lost = regressions(base, m, args.ignore_test)
        if not fails(lost) and not args.full:          # tests only when the battery alone does not decide
            m = measure(args, [i], ("battery", "tests"))
            lost = regressions(base, m, args.ignore_test)
        verdict = "droppable" if not fails(lost) else "needed"
        print(f"  row {i:2d} {verdict:9s} {m['removed'][0][:110]}")
        show_lost(lost)
        for line in changed_outputs(base, m)[:4]:
            print(f"      changed output: {line}")
        if not fails(lost):
            single.append(i)
    print(f"\nsingle droppable (gates 1, 2): {single}")

    if not args.no_soundness and single:
        print("\n== soundness of each single droppable row (gate 3) ==")
        kept = []
        for i in single:
            m = measure(args, [i], ("soundness",))
            lost = regressions(base, m, args.ignore_test)
            print(f"  row {i:2d} {'sound' if not fails(lost) else 'NEW UNSOUND'}")
            show_lost(lost)
            if not fails(lost):
                kept.append(i)
        single = kept

    print("\n== greedy removal ==")
    chosen: list[int] = []
    for i in single:
        trial = chosen + [i]
        m = measure(args, trial, ("battery", "tests"))
        lost = regressions(base, m, args.ignore_test)
        if fails(lost):
            print(f"  + row {i:2d}: rejected together with {chosen}")
            show_lost(lost)
        else:
            chosen = trial
            print(f"  + row {i:2d}: accepted -> {chosen}")
    if chosen and not args.no_soundness:
        m = measure(args, chosen, ("soundness",))
        lost = regressions(base, m, args.ignore_test)
        print(f"  soundness of {chosen}: {'sound' if not fails(lost) else 'NEW UNSOUND'}")
        show_lost(lost)
        if fails(lost):
            chosen = []
    print(f"\nlargest removable set found: {chosen} ({len(rules)} -> {len(rules) - len(chosen)} rows)")
    print(f"time {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
