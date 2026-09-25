#!/usr/bin/env python
"""Numeric check of the ``ask`` answers the combined backend takes from SymPy.

For random scalar expressions (``refine_fuzz``'s inner grammar, one level
deeper with its outer heads) under random assumption sets (``refine_fuzz``'s
vocabulary), asks a unary predicate of the expression.  Where satassume has no
answer and SymPy has one (the answers the ``combined`` backend passes
through), the answer is checked at random points satisfying the assumptions:
a ``True`` must hold, a ``False`` must fail, at every point.  Reported: the
wrong answers, with the point, per predicate and expression head, both for raw
SymPy and for the guarded SymPy call the combined backend makes.

Usage::

    PYTHONPATH=.:/path/to/sympy python tools/ask_fuzz.py [--seed 0] [--cases 2000]

A contradiction is evidence, not proof (floating tolerance 1e-9; a point where
the value is not finite is skipped for every predicate but ``finite``).
"""
from __future__ import annotations

import argparse
import functools
import random
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
_argv, sys.argv = sys.argv, sys.argv[:1]
import refine_fuzz as f  # noqa: E402
sys.argv = _argv

from sympy import Q, S  # noqa: E402

from satrefine import backend  # noqa: E402

CHECK = {name: (f.PREDS[name][0], f.PREDS[name][1]) for name in
         ("real", "positive", "negative", "nonnegative", "nonpositive", "nonzero", "zero", "integer", "even",
          "odd", "imaginary")}
CHECK["finite"] = (Q.finite, None)


def holds(name, value):
    """The predicate at a numeric value; None where it cannot be decided."""
    if name == "finite":
        return False if value == "inf" else None if isinstance(value, str) else True
    if isinstance(value, str):
        return None
    return CHECK[name][1](value)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--cases", type=int, default=2000)
    ap.add_argument("--show", type=int, default=40)
    ap.add_argument("--relation", action="store_true",
                    help="always add a relation between two symbols (satassume then often has no answer)")
    args = ap.parse_args(argv)
    t0 = time.time()
    asked = passed = unchecked = 0
    wrong = {"sympy": [], "guarded": []}
    for case in range(args.cases):
        rng = random.Random(f"ask-{args.seed}-{case}")
        head = rng.choice(list(f.OUTER))
        try:
            e = f.OUTER[head](f.inner(rng), rng) if rng.random() < 0.6 else f.inner(rng)
        except Exception:  # noqa: BLE001
            continue
        syms = sorted(getattr(e, "free_symbols", ()), key=str)
        if not syms or e.is_number:
            continue
        combos = {s: rng.choice(f.COMBOS) for s in syms}
        facts = [f.PREDS[p][0](s) for s, c in combos.items() for p in c]
        rel = f.relations(rng, syms)
        if args.relation and rel is None:
            a_ = rng.choice(syms)
            rel = rng.choice([Q.ne, Q.gt, Q.lt, Q.ge, Q.le])(a_, rng.choice([s for s in syms if s != a_] + [S.Zero, S.One]))
        if rel is not None:
            facts.append(rel)
        assumptions = S.true if not facts else functools.reduce(lambda a, b: a & b, facts)
        name = rng.choice(list(CHECK))
        prop = CHECK[name][0](e)
        try:
            sat = backend._satassume_ask(prop, assumptions)
        except Exception:  # noqa: BLE001 -- inconsistent or unsupported: SymPy decides
            sat = None
        if sat is not None:
            continue
        try:
            raw = backend._sympy_ask(prop, assumptions)
            guarded = backend._guarded_sympy_ask(prop, assumptions)
        except Exception:  # noqa: BLE001
            continue
        if raw is None and guarded is None:
            continue
        asked += 1
        pts = []
        for _ in range(60):
            if len(pts) >= 8:
                break
            pt = {s: f.draw(combos[s], rng) for s in syms}
            if any(v is None for v in pt.values()):
                break
            if rel is not None and f.rel_holds(rel, pt) is not True:
                continue
            pts.append(pt)
        verdicts = {}
        for label, ans in (("sympy", raw), ("guarded", guarded)):
            if ans is None:
                continue
            for pt in pts:
                try:
                    v = f.numeric(e.subs(pt))
                except Exception:  # noqa: BLE001
                    continue
                if name != "finite" and isinstance(v, str):
                    continue
                h = holds(name, v)
                if h is not None and h != ans:
                    verdicts[label] = (pt, v)
                    break
        for label, ans in (("sympy", raw), ("guarded", guarded)):
            if label in verdicts:
                wrong[label].append((head, prop, assumptions, ans, verdicts[label]))
        if not verdicts:
            passed += 1 if pts else 0
            unchecked += 0 if pts else 1
    print(f"seed={args.seed} cases={args.cases} time={time.time() - t0:.0f}s "
          f"answered by SymPy only={asked} checked-consistent={passed} unchecked={unchecked} "
          f"wrong: sympy={len(wrong['sympy'])} guarded={len(wrong['guarded'])}")
    for label in ("sympy", "guarded"):
        by = Counter(str(p.function) for _, p, *_ in wrong[label])
        print(f"\n== {label} wrong answers: {len(wrong[label])} ({', '.join(f'{k} {v}' for k, v in by.most_common())}) ==")
        for head, p, a, ans, (pt, v) in wrong[label][:args.show]:
            print(f"  ask({p}, {a}) = {ans}\n      at {pt}: value {v}")


if __name__ == "__main__":
    main()
