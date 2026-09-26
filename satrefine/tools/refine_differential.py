#!/usr/bin/env python
"""Differential fuzzer: two refine handler packages on the same random inputs.

The inputs are exactly those of ``refine_fuzz`` (``satrefine.tools.lib.grammar``:
the expression grammar, assumption vocabulary, per-case random stream and
consistency filter, so ``--seed S --cases C`` here generates the same
expressions and assumption sets as ``refine_fuzz S C``).  Each package runs
in its own subprocess, since the package is fixed per process; the parent
compares the two result streams and reports:

* inputs where exactly one package fires;
* inputs where both fire with different results, marked numerically equal,
  different (with the distinguishing point) or undecided (no point checked);
* unsound outputs per package, with the counterexample;
* crashes and timeouts per package.

Numeric check (``lib.points.check_points``, ``lib.numeric.compare``).  Every
rewrite is compared with its input at random satisfying points and, in
addition, at edge points: 0, 1, -1, I, -I and
points on the branch cuts of log, sqrt (any non-integer power), asin, acos,
atan, acoth, asech and acsch, used both as values of each symbol and, where
such a function's argument is linear in a single symbol, as that argument
(the symbol value that puts the argument on the cut).  A point is used only if
it satisfies the symbol's sampled predicates and the relation, if any.
Relation assumptions are decided numerically at each point.  Values are
compared at 20 digits with a relative tolerance of 1e-7; a point
where both sides are non-finite or unevaluable is skipped.  A mismatch is
evidence, not proof: a removable singularity or pole of the input can show up
as a mismatch, so read the counterexample.

Usage::

    PYTHONPATH=.:/path/to/sympy python -m satrefine.tools.refine_differential \\
        [--a handlers_v3] [--b handlers_identities] [--seed 2] [--cases 1500] [--summary]

``--ext`` uses the extended family instead (``lib.grammar.ext_generate``:
``Q.infinite``/``Q.finite``/``extended_*`` facts, relations with infinite
bounds, Piecewise, the inverse pairs acot(cot) etc.), checked at finite and
infinite points (``lib.points.ext_points``/``lib.numeric.ext_compare``, which
classify SymPy's conventions at infinity instead of reporting them); its own
seed stream, so the default sections are unchanged.  ``--matrices`` uses the
matrix family (``lib.matrices``).

``--summary`` prints only the counts.  ``--show N`` caps the examples listed
per category (default 15).  ``--timeout T`` bounds one refine call plus its
checks in a worker (seconds, default 60).
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
import time
from collections import Counter

from satrefine.tools.lib import matrices as M
from satrefine.tools.lib.grammar import ext_generate, generate
from satrefine.tools.lib.numeric import compare, ext_compare, fmt
from satrefine.tools.lib.points import check_points, ext_points
from satrefine.tools.lib.select import backend_from_env
from satrefine.tools.lib.workers import install_case_alarm, load_srepr, refine_case, run_json_worker

# ---------------------------------------------------------------------------
# worker: one package, every case
# ---------------------------------------------------------------------------


def _generator(matrices=False, ext=False):
    return M.mat_generate if matrices else ext_generate if ext else generate


def worker(package, seed, cases, out, timeout, matrices=False, ext=False):
    """Refine every case with ``package`` (the one this process loaded), check each rewrite, write JSON."""
    import json

    os.environ.setdefault("SATREFINE_STRICT_LOOPS", "1")   # a tripped loop guard is a crash here
    assert sys.modules.get("satrefine." + package) is not None, f"satrefine.{package} was not loaded"
    backend_from_env()
    install_case_alarm()
    gen = _generator(matrices, ext)
    records = []
    t0 = time.time()
    for case in range(cases):
        g = gen(seed, case)
        if g is None:
            continue
        head, e, assumptions, combos, rel = g

        def check(r, rec, e=e, combos=combos, rel=rel, case=case):
            rng = random.Random(seed * 7919 + case)
            if matrices:
                return M.mat_compare(e, r, M.mat_points(combos, rel, rng))
            if ext:
                n_ok, ce, st = ext_compare(e, r, ext_points([e, r], combos, rel, rng))
                rec["stats"] = dict(st)
                if ce:
                    rec["kind"] = ce[3]
                    ce = ce[:3]
                return n_ok, ce
            return compare(e, r, check_points([e, r], combos, rel, rng))

        records.append({"case": case, "head": head, **refine_case(e, assumptions, timeout, check)})
    with open(out, "w") as fh:
        json.dump({"package": package, "seconds": time.time() - t0, "records": records}, fh)


# ---------------------------------------------------------------------------
# parent: run both, compare
# ---------------------------------------------------------------------------

def run_worker(package, args, out):
    """The worker's records for ``package``, run in a fresh process that loads it."""
    cmd = ["--worker", package, "--seed", str(args.seed), "--cases", str(args.cases), "--out", out,
           "--timeout", str(args.timeout)] + (["--matrices"] if args.matrices else []) + (["--ext"] if args.ext else [])
    return run_json_worker("satrefine.tools.refine_differential", cmd, out, env={"SATREFINE_HANDLERS": package},
                           failure=f"worker for {package} failed")


def _singular(record):
    """The counterexample's input side is nan or infinite."""
    return record["unsound"]["orig"] in ("nan", "inf", "zoo") or record["unsound"]["orig"].startswith("oo*")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--a", default="handlers_v3")
    ap.add_argument("--b", default="handlers_identities")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--cases", type=int, default=3000)
    ap.add_argument("--summary", action="store_true", help="print only the counts")
    ap.add_argument("--show", type=int, default=15, help="examples listed per category")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--matrices", action="store_true",
                    help="matrix expressions (lib.matrices.mat_generate) checked at explicit sample matrices")
    ap.add_argument("--ext", action="store_true",
                    help="the extended family (lib.grammar.ext_generate): infinities, Piecewise, inverse pairs")
    ap.add_argument("--keep", help="keep the workers' JSON results in this directory")
    ap.add_argument("--worker", help=argparse.SUPPRESS)
    ap.add_argument("--out", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.worker:
        worker(args.worker, args.seed, args.cases, args.out, args.timeout, args.matrices, args.ext)
        return

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        res = {}
        keep = args.keep or tmp
        os.makedirs(keep, exist_ok=True)
        for label, pkg in (("a", args.a), ("b", args.b)):     # sequential: shared machine
            res[label] = run_worker(pkg, args, os.path.join(keep, f"{label}-{pkg}-{args.seed}.json"))
    A = {r["case"]: r for r in res["a"]["records"]}
    B = {r["case"]: r for r in res["b"]["records"]}
    common = sorted(set(A) & set(B))

    only_a, only_b, differ, same = [], [], [], 0
    for c in common:
        ra, rb = A[c], B[c]
        if "inconsistent" in (ra.get("status"), rb.get("status")):
            continue
        fa, fb = ra.get("status") == "fired", rb.get("status") == "fired"
        if fa and not fb and rb.get("status") == "unchanged":
            only_a.append(c)
        elif fb and not fa and ra.get("status") == "unchanged":
            only_b.append(c)
        elif fa and fb:
            if ra["result"] == rb["result"]:
                same += 1
            else:
                differ.append(c)

    # numeric equality of the differing pairs, at the same kind of points
    verdicts = {}
    gen = _generator(args.matrices, args.ext)
    for c in differ:
        g = gen(args.seed, c)
        _, e, _, combos, rel = g
        try:
            la, lb = load_srepr(A[c]["result"]), load_srepr(B[c]["result"])
        except Exception:  # noqa: BLE001 -- a result this parser cannot rebuild stays undecided
            verdicts[c] = ("undecided", None)
            continue
        rng = random.Random(args.seed * 104729 + c)
        if args.matrices:
            n, ce = M.mat_compare(la, lb, M.mat_points(combos, rel, rng), ref=e)
        elif args.ext:
            n, ce, _ = ext_compare(la, lb, ext_points([e, la, lb], combos, rel, rng), ref=e)
            ce = ce[:3] if ce else None
        else:
            points = check_points([e, la, lb], combos, rel, rng)
            n, ce = compare(la, lb, points)
        verdicts[c] = ("different", ce) if ce else (("equal", n) if n else ("undecided", None))

    def stat(res_, key):
        return sum(1 for r in res_["records"] if r.get("status") == key)

    unsound = {lab: [r for r in res[lab]["records"] if "unsound" in r] for lab in ("a", "b")}
    # fired, no counterexample, and not a single point checked: reported, never silently passed
    unchecked = {lab: [r for r in res[lab]["records"]
                       if r.get("status") == "fired" and "unsound" not in r and not r.get("checked")]
                 for lab in ("a", "b")}
    crashes = {lab: [r for r in res[lab]["records"] if r.get("status") in ("crash", "timeout")] for lab in ("a", "b")}
    nonbasic = {lab: [r for r in res[lab]["records"] if "nonbasic" in r] for lab in ("a", "b")}
    vcount = Counter(v[0] for v in verdicts.values())

    name = {"a": args.a, "b": args.b}
    print(f"{'matrices ' if args.matrices else 'ext ' if args.ext else ''}seed={args.seed} cases={args.cases} compared={len(common)} time={time.time() - t0:.0f}s "
          f"(a={args.a} {res['a']['seconds']:.0f}s, b={args.b} {res['b']['seconds']:.0f}s)")
    for lab in ("a", "b"):
        print(f"  {lab}={name[lab]}: fired={stat(res[lab], 'fired')} unchanged={stat(res[lab], 'unchanged')} "
              f"inconsistent={stat(res[lab], 'inconsistent')} crash={stat(res[lab], 'crash')} "
              f"timeout={stat(res[lab], 'timeout')} checked={stat(res[lab], 'fired') - len(unsound[lab]) - len(unchecked[lab])} "
              f"unchecked={len(unchecked[lab])} unsound={len(unsound[lab])} "
              f"(input finite at the point: {sum(1 for r in unsound[lab] if not _singular(r))}) "
              f"non-SymPy={len(nonbasic[lab])}")
    if args.ext:
        for lab in ("a", "b"):
            recs = res[lab]["records"]
            st, conv = Counter(), Counter()
            for r in recs:
                st.update(r.get("stats", {}))
                conv.update(k[12:] for k in r.get("stats", {}) if k.startswith("convention: "))
            kinds = Counter(r["kind"] for r in unsound[lab] if "kind" in r)
            print(f"  {lab} ext: unsound by kind: {', '.join(f'{k} {v}' for k, v in sorted(kinds.items())) or 'none'}; "
                  f"cases with an infinite point checked: {sum(1 for r in recs if r.get('stats', {}).get('checked at an infinity'))}")
            print(f"  {lab} ext points: " + ", ".join(f"{k} {v}" for k, v in sorted(st.items()) if not k.startswith("convention")))
            print(f"  {lab} ext cases with a convention-excused point: "
                  + (", ".join(f"{k} {v}" for k, v in sorted(conv.items())) or "0"))
    print(f"  only a fires: {len(only_a)}   only b fires: {len(only_b)}   both fire, same result: {same}")
    print(f"  both fire, different results: {len(differ)} (numerically equal {vcount['equal']}, "
          f"different {vcount['different']}, undecided {vcount['undecided']})")
    if args.summary:
        return

    def case_line(c, rec):
        g = gen(args.seed, c)
        return f"[{rec['head']}] refine({g[1]}, {g[2]})"

    def heads(cs, recs):
        return ", ".join(f"{h} {n}" for h, n in Counter(recs[c]["head"] for c in cs).most_common())

    for lab, cs, recs, other in (("a", only_a, A, "b"), ("b", only_b, B, "a")):
        print(f"\n== only {lab}={name[lab]} fires: {len(cs)} ==")
        if cs:
            print(f"  by head: {heads(cs, recs)}")
        for c in cs[:args.show]:
            print(f"  {case_line(c, recs[c])}\n      {name[lab]}: {recs[c]['result_str']}")
    print(f"\n== both fire, different results: {len(differ)} ==")
    order = sorted(differ, key=lambda c: {"different": 0, "undecided": 1, "equal": 2}[verdicts[c][0]])
    for c in order[:args.show if args.show else None]:
        verdict, info = verdicts[c]
        print(f"  {case_line(c, A[c])}\n      a: {A[c]['result_str']}\n      b: {B[c]['result_str']}")
        if verdict == "different":
            pt, va, vb = info
            print(f"      NUMERICALLY DIFFERENT at {pt}: a={fmt(va)} b={fmt(vb)}")
        else:
            print(f"      {verdict}" + (f" at {info} points" if verdict == "equal" else ""))
    for lab in ("a", "b"):
        recs = A if lab == "a" else B
        print(f"\n== {lab}={name[lab]} UNSOUND rewrites: {len(unsound[lab])} ==")
        for r in unsound[lab][:args.show]:
            u = r["unsound"]
            note = "  (input non-finite there: pole or removable singularity?)" if _singular(r) else ""
            kind = f" [{r['kind']}]" if "kind" in r else ""
            print(f"  {case_line(r['case'], recs[r['case']])} -> {r['result_str']}\n"
                  f"      at {u['point']}{kind}: orig={u['orig']} refined={u['refined']}{note}")
    for lab in ("a", "b"):
        recs = A if lab == "a" else B
        print(f"\n== {lab}={name[lab]} crashes/timeouts: {len(crashes[lab])} ==")
        for r in crashes[lab][:args.show]:
            print(f"  {case_line(r['case'], recs[r['case']])}: {r.get('error', 'timeout')}")
        print(f"\n== {lab}={name[lab]} fired but unchecked (no point checked): {len(unchecked[lab])} ==")
        for r in unchecked[lab][:args.show]:
            print(f"  {case_line(r['case'], recs[r['case']])} -> {r['result_str']}")
        if nonbasic[lab]:
            print(f"  non-SymPy returns: {len(nonbasic[lab])}, e.g. {nonbasic[lab][0]['nonbasic']}")


if __name__ == "__main__":
    main()
