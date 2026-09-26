#!/usr/bin/env python
"""Numeric fuzzer for the refine handlers.

Builds random expressions over the handler families, draws random consistent
assumption sets (unary predicates plus an occasional relation), refines under
the combined backend (or ``SATREFINE_BACKEND``), and checks every rewrite at random numeric points that
satisfy the assumptions, evaluated at 20 digits in the complex plane.  SymPy's
own refine runs on the same inputs, so inherited upstream bugs can be told
apart from the handlers' own.  Reported categories: unsound rewrites (with the
counterexample), non-SymPy return values, crashes, and inputs where both fire
with different results.

Usage::

    PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satrefine.tools.refine_fuzz [seed] [cases] [--handlers handlers_v2]
    ... --ext [seed] [cases]         # the extended family: infinities, Piecewise, inverse pairs
    ... --matrices [seed] [cases]    # matrix expressions at explicit sample matrices

The case streams, samplers and checkers are in ``satrefine.tools.lib``
(``grammar``, ``assumptions``, ``points``, ``numeric``, ``matrices``); the
differential uses the same ones.

A mismatch is evidence, not proof: a value that agrees to 7 digits passes, and
poles or removable singularities of the original can show up as spurious
mismatches, so read the counterexample before calling a rule wrong.
"""
from __future__ import annotations

import argparse
import random
import time
from collections import Counter

from sympy import sympify
from sympy.assumptions.refine import refine as sympy_refine
from sympy.core.basic import Basic

import satrefine
from satrefine import refine as sat_refine
from satrefine.tools.lib.grammar import case_rng, ext_generate, scalar_case
from satrefine.tools.lib.matrices import MatrixRowCoverage, mat_compare, mat_generate, mat_points, short
from satrefine.tools.lib.numeric import check, ext_compare
from satrefine.tools.lib.points import ext_points
from satrefine.tools.lib.select import backend_from_env, select


def main(seed=0, cases=3000):
    fired = Counter(); tried = Counter(); unsound = []; crashes = []; sympy_unsound = []; nonbasic = []
    sat_only = Counter(); sympy_only = Counter(); differ = []
    checked_cases = unchecked = 0  # fired cases checked at >= 1 point / at none
    t0 = time.time()
    for case in range(cases):
        rng = case_rng(seed, case)
        g = scalar_case(rng)
        if g is None:
            continue
        head, e, assumptions, combos, rel = g
        tried[head] += 1
        try:
            r = sat_refine(e, assumptions)
            if not isinstance(r, Basic):
                nonbasic.append((head, e, assumptions, repr(r)))
                r = sympify(r)
        except ValueError as ex:
            if "nconsistent" in str(ex): continue
            crashes.append((head, e, assumptions, f"{type(ex).__name__}: {ex}")); continue
        except Exception as ex:
            crashes.append((head, e, assumptions, f"{type(ex).__name__}: {str(ex)[:80]}")); continue
        try:
            rs = sympify(sympy_refine(e, assumptions))
        except Exception:
            rs = None
        if r != e:
            fired[head] += 1
            n_ok, ce = check(e, r, assumptions, combos, rel, rng)
            if ce: unsound.append((head, e, assumptions, r, ce))
            elif n_ok: checked_cases += 1
            else: unchecked += 1
        if rs is not None and rs != e:
            n_ok, ce = check(e, rs, assumptions, combos, rel, rng)
            if ce: sympy_unsound.append((head, e, assumptions, rs, ce))
        if rs is not None:
            if r != e and rs == e: sat_only[head] += 1
            if r == e and rs != e: sympy_only[head] += 1
            if r != e and rs != e and r != rs: differ.append((head, e, assumptions, r, rs))
    dt = time.time() - t0
    print(f"seed={seed} cases={cases} time={dt:.0f}s tried={sum(tried.values())} fired={sum(fired.values())} "
          f"checked={checked_cases} unchecked={unchecked} unsound={len(unsound)}")
    print("\n== fires by head (fired/tried; satrefine-only fires; sympy-only fires) ==")
    for h in sorted(tried, key=lambda h: -tried[h]):
        print(f"  {h:15} {fired[h]:4}/{tried[h]:<4} sat_only={sat_only[h]:<3} sympy_only={sympy_only[h]:<3}")
    print(f"\n== satrefine UNSOUND rewrites: {len(unsound)} ==")
    seen = set()
    for head, e, a, r, (sample, va, vb) in unsound:
        key = (head, str(e)[:40])
        if key in seen: continue
        seen.add(key)
        print(f"  [{head}] refine({e}, {a}) -> {r}\n      at {sample}: orig={va} refined={vb}")
    print(f"\n== SymPy's own refine unsound on the same inputs: {len(sympy_unsound)} ==")
    seen = set()
    for head, e, a, r, (sample, va, vb) in sympy_unsound[:15]:
        key = (head, str(e)[:40])
        if key in seen: continue
        seen.add(key)
        print(f"  [{head}] sympy.refine({e}, {a}) -> {r}\n      at {sample}: orig={va} refined={vb}")
    print(f"\n== satrefine returned a non-SymPy object: {len(nonbasic)} ==")
    for head, e, a, r in nonbasic[:5]:
        print(f"  [{head}] refine({e}, {a}) -> {r}")
    print(f"\n== crashes: {len(crashes)} ==")
    seen = Counter()
    for head, e, a, msg in crashes:
        seen[(head, msg.split(':')[0])] += 1
    for (head, msg), c in seen.most_common(20):
        ex = next(cr for cr in crashes if cr[0] == head and cr[3].startswith(msg))
        print(f"  {c:3}x [{head}] {ex[3][:100]}\n        e.g. refine({ex[1]}, {ex[2]})")
    print(f"\n== both fire, different results: {len(differ)} (first 12) ==")
    for head, e, a, r, rs in differ[:12]:
        print(f"  [{head}] {e} | {a}\n      satrefine: {r}\n      sympy:     {rs}")


def mat_main(seed=0, cases=1000):
    """The matrix fuzz: refine every case, check each rewrite at sampled explicit matrices."""
    fired, tried, checked_cases, unchecked, unsound, crashes, nopoint, sympy_unsound = (
        Counter(), Counter(), Counter(), [], [], [], 0, [])
    t0 = time.time()
    coverage = MatrixRowCoverage() if satrefine.HANDLERS_PACKAGE == "handlers_identities" else None
    if coverage:
        coverage.__enter__()
    for case in range(cases):
        g = mat_generate(seed, case)
        if g is None:
            continue
        head, e, assumptions, combos, rel = g
        tried[head] += 1
        try:
            r = sat_refine(e, assumptions)
        except ValueError as ex:
            if "nconsistent" in str(ex):
                continue
            crashes.append((f"{head} #{case}", e, assumptions, f"{type(ex).__name__}: {ex}"))
            continue
        except Exception as ex:
            crashes.append((f"{head} #{case}", e, assumptions, f"{type(ex).__name__}: {str(ex)[:80]}"))
            continue
        rng = random.Random(f"matrix-points-{seed}-{case}")
        points = mat_points(combos, rel, rng)
        if not points:
            nopoint += 1
        if r != e:
            fired[head] += 1
            n_ok, ce = mat_compare(e, r, points)
            if ce:
                unsound.append((f"{head} #{case}", e, assumptions, r, ce))
            elif n_ok:
                checked_cases[head] += 1
            else:
                unchecked.append((f"{head} #{case}", e, assumptions, r))
        try:
            rs = sympy_refine(e, assumptions)
        except Exception:
            rs = e
        if rs != e:
            n_ok, ce = mat_compare(e, rs, points)
            if ce:
                sympy_unsound.append((head, e, assumptions, rs, ce))
    print(f"matrices seed={seed} cases={cases} time={time.time() - t0:.0f}s tried={sum(tried.values())} "
          f"fired={sum(fired.values())} checked={sum(checked_cases.values())} unchecked={len(unchecked)} "
          f"unsound={len(unsound)} crash={len(crashes)} (no satisfying point: {nopoint} cases)")
    for h in sorted(tried, key=lambda h: -tried[h]):
        print(f"  {h:14} fired {fired[h]:4}/{tried[h]:<4} checked {checked_cases[h]}")
    if coverage:
        coverage.__exit__(None, None, None)
        unfired = [row for row in coverage.all_rows if not coverage.counts[row]]
        print(f"\n== matrices rows fired: {len(coverage.all_rows) - len(unfired)} of {len(coverage.all_rows)} ==")
        for row in coverage.all_rows:
            print(f"  {coverage.counts[row]:4}  {short(row[0], 40):40} -> {short(row[1], 30):30} if {short(row[2], 80)}"
                  + (f" unless {row[3]}" if len(row) > 3 else ""))
    print(f"\n== satrefine UNSOUND matrix rewrites: {len(unsound)} ==")
    for head, e, a, r, (pt, va, vb) in unsound[:20]:
        print(f"  [{head}] refine({short(e)}, {a}) -> {short(r)}\n      at {short(pt)}: orig={short(va)} refined={short(vb)}")
    print(f"\n== fired but unchecked (no point with a finite input value): {len(unchecked)} ==")
    for head, e, a, r in unchecked[:20]:
        print(f"  [{head}] refine({short(e)}, {a}) -> {short(r)}")
    print(f"\n== SymPy's own refine unsound on the same inputs: {len(sympy_unsound)} ==")
    for head, e, a, r, (pt, va, vb) in sympy_unsound[:10]:
        print(f"  [{head}] sympy.refine({short(e)}, {a}) -> {short(r)}\n      at {short(pt)}: orig={short(va)} refined={short(vb)}")
    print(f"\n== crashes: {len(crashes)} ==")
    for head, e, a, msg in crashes[:10]:
        print(f"  [{head}] refine({short(e)}, {a}): {msg}")


def ext_main(seed=0, cases=1000):
    """The extended fuzz for the selected package: refine, check at finite and infinite points."""
    tried, fired = Counter(), Counter()
    unsound, crashes, unchecked, conv_cases = [], [], 0, Counter()
    stats = Counter()
    dropped = checked_cases = 0
    t0 = time.time()
    for case in range(cases):
        g = ext_generate(seed, case)
        if g is None:
            dropped += 1
            continue
        head, e, assumptions, combos, rels = g
        tried[head] += 1
        try:
            r = sat_refine(e, assumptions)
            if not isinstance(r, Basic):
                r = sympify(r)
        except ValueError as ex:
            if "nconsistent" in str(ex):
                continue
            crashes.append((head, e, assumptions, f"{type(ex).__name__}: {ex}"))
            continue
        except Exception as ex:  # noqa: BLE001
            crashes.append((head, e, assumptions, f"{type(ex).__name__}: {str(ex)[:80]}"))
            continue
        if r == e:
            continue
        fired[head] += 1
        n_ok, ce, st = ext_compare(e, r, ext_points([e, r], combos, rels, random.Random(f"ext-pts-{seed}-{case}")))
        stats.update(st)
        for lab in st:
            if lab.startswith("convention"):
                conv_cases[lab] += 1
        if ce:
            unsound.append((head, case, e, assumptions, r, ce))
        elif n_ok:
            checked_cases += 1
        else:
            unchecked += 1
    kinds = Counter(u[5][3] for u in unsound)
    print(f"ext seed={seed} cases={cases} time={time.time() - t0:.0f}s dropped={dropped} tried={sum(tried.values())} "
          f"fired={sum(fired.values())} checked={checked_cases} unchecked={unchecked} unsound={len(unsound)} "
          f"({', '.join(f'{k} {v}' for k, v in sorted(kinds.items())) or 'none'}) crash={len(crashes)}")
    print("  points: " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())))
    print("  cases with a convention-excused point: " + (", ".join(f"{k[12:]} {v}" for k, v in sorted(conv_cases.items())) or "0"))
    print("\n== fires by head (fired/tried) ==")
    for h in sorted(tried, key=lambda h: -tried[h]):
        print(f"  {h:22} {fired[h]:4}/{tried[h]}")
    print(f"\n== UNSOUND: {len(unsound)} ==")
    for head, case, e, a, r, (pt, va, vb, kind) in unsound[:40]:
        print(f"  [{head} #{case}] refine({e}, {a}) -> {r}\n      {kind} {pt}: orig={va} refined={vb}")
    print(f"\n== crashes: {len(crashes)} ==")
    for head, e, a, msg in crashes[:20]:
        print(f"  [{head}] refine({e}, {a}): {msg}")


def cli(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("seed", nargs="?", type=int, default=0)
    ap.add_argument("cases", nargs="?", type=int, help="default 3000 (--ext, --matrices: 1000)")
    ap.add_argument("--handlers", help="handler package (SATREFINE_HANDLERS)")
    ap.add_argument("--ext", action="store_true", help="the extended family")
    ap.add_argument("--matrices", action="store_true", help="the matrix family")
    args = ap.parse_args(argv)
    if args.handlers:
        select(handlers=args.handlers)
    backend_from_env()                 # SATREFINE_BACKEND, default combined
    if args.ext:
        ext_main(args.seed, 1000 if args.cases is None else args.cases)
    elif args.matrices:
        mat_main(args.seed, 1000 if args.cases is None else args.cases)
    else:
        main(args.seed, 3000 if args.cases is None else args.cases)


if __name__ == "__main__":
    cli()
