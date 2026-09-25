#!/usr/bin/env python
"""Differential fuzzer: two refine handler packages on the same random inputs.

The inputs are exactly those of ``tools/refine_fuzz.py`` (its expression
grammar, assumption vocabulary, per-case random stream and consistency
filter are imported from it, so ``--seed S --cases C`` here generates the same
expressions and assumption sets as ``refine_fuzz.py S C``).  Each package runs
in its own subprocess, since the package is fixed per process; the parent
compares the two result streams and reports:

* inputs where exactly one package fires;
* inputs where both fire with different results, marked numerically equal,
  different (with the distinguishing point) or undecided (no point checked);
* unsound outputs per package, with the counterexample;
* crashes and timeouts per package.

Numeric check.  Every rewrite is compared with its input at ``refine_fuzz``'s
random satisfying points and, in addition, at edge points: 0, 1, -1, I, -I and
points on the branch cuts of log, sqrt (any non-integer power), asin, acos,
atan, acoth, asech and acsch, used both as values of each symbol and, where
such a function's argument is linear in a single symbol, as that argument
(the symbol value that puts the argument on the cut).  A point is used only if
it satisfies the symbol's sampled predicates and the relation, if any.
Relation assumptions are decided numerically at each point (``refine_fuzz``
cannot decide them, so it never checks a case that has one).  Values are
compared at 20 digits with ``refine_fuzz``'s tolerance; a point
where both sides are non-finite or unevaluable is skipped.  A mismatch is
evidence, not proof: a removable singularity or pole of the input can show up
as a mismatch, so read the counterexample.

Usage::

    PYTHONPATH=.:/path/to/sympy python tools/refine_differential.py \\
        [--a handlers_v3] [--b handlers_identities] [--seed 2] [--cases 1500] [--summary]

``--summary`` prints only the counts.  ``--show N`` caps the examples listed
per category (default 15).  ``--timeout T`` bounds one refine call plus its
checks in a worker (seconds, default 60).
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import signal
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# shared: case generation (refine_fuzz's) and the numeric check with edge points
# ---------------------------------------------------------------------------

_FZ = None


def fz():
    """``tools/refine_fuzz.py`` as a module (imports satrefine: set the package first)."""
    global _FZ
    if _FZ is None:
        sys.path.insert(0, str(HERE))
        saved = sys.argv
        sys.argv = [saved[0]]            # refine_fuzz reads --handlers from argv at import
        try:
            _FZ = importlib.import_module("refine_fuzz")
        finally:
            sys.argv = saved
    return _FZ


def generate(seed, case):
    """Case ``case`` of ``refine_fuzz.main(seed, ...)``: (head, expr, assumptions, combos, rel) or None."""
    import functools

    from sympy import S
    from sympy.core.expr import Expr
    f = fz()
    rng = random.Random(seed * 1000003 + case)
    head = rng.choice(list(f.OUTER))
    try:
        e = f.OUTER[head](f.inner(rng), rng)
    except Exception:  # noqa: BLE001 -- the generator's own policy
        return None
    if not isinstance(e, Expr):
        return None
    syms = sorted(e.free_symbols, key=str)
    if not syms:
        return None
    combos = {s: rng.choice(f.COMBOS) for s in syms}
    if any(f.draw(c, rng) is None for c in combos.values()):
        return None
    facts = [f.PREDS[p][0](s) for s, c in combos.items() for p in c]
    rel = f.relations(rng, syms)
    if rel is not None:
        facts.append(rel)
    assumptions = S.true if not facts else functools.reduce(lambda a, b: a & b, facts)
    return head, e, assumptions, combos, rel


def _cut_points():
    from sympy import I, Rational, S
    half = Rational(1, 2)
    neg_real = [S.Zero, S.NegativeOne, S(-2), -half]
    return {
        "log": neg_real,
        "pow": neg_real,                 # sqrt and every non-integer power: principal log cut
        "asin": [S.One, S.NegativeOne, S(2), S(-2), 3 * half, -3 * half],
        "acos": [S.One, S.NegativeOne, S(2), S(-2), 3 * half, -3 * half],
        "atan": [I, -I, 2 * I, -2 * I],
        "acoth": [S.Zero, S.One, S.NegativeOne, half, -half],
        "asech": [S.Zero, S.One, S.NegativeOne, S(2), -half],
        "acsch": [S.Zero, I, -I, I / 2, -I / 2],
    }


def edge_values():
    """0, 1, -1, I, -I and every branch-cut point, as symbol values."""
    from sympy import I, S
    seen, out = set(), []
    for v in [S.Zero, S.One, S.NegativeOne, I, -I] + [p for ps in _cut_points().values() for p in ps]:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _cut_arguments(exprs):
    """(argument, cut points) for every branch-cut function occurring in ``exprs``."""
    from sympy import Pow, acos, acoth, acsch, asech, asin, atan, log
    cuts = _cut_points()
    kinds = [(log, "log"), (asin, "asin"), (acos, "acos"), (atan, "atan"),
             (acoth, "acoth"), (asech, "asech"), (acsch, "acsch")]
    out = []
    for expr in exprs:
        for sub in expr.atoms(log, asin, acos, atan, acoth, asech, acsch, Pow):
            if isinstance(sub, Pow):
                if sub.exp.is_integer is not True:
                    out.append((sub.base, cuts["pow"]))
                continue
            for cls, name in kinds:
                if isinstance(sub, cls):
                    out.append((sub.args[0], cuts[name]))
    return out


def edge_candidates(exprs, syms, combos):
    """Per symbol: edge values and cut pre-images that satisfy its predicates."""
    f = fz()
    cand = {s: list(edge_values()) for s in syms}
    for arg, points in _cut_arguments(exprs):
        free = arg.free_symbols
        if len(free) != 1:
            continue
        (s,) = free
        if s not in cand:
            continue
        slope = arg.diff(s)
        if slope.free_symbols or slope == 0 or arg.subs(s, 0).free_symbols:
            continue              # only arguments linear in the one symbol
        for p in points:
            v = (p - arg.subs(s, 0)) / slope
            if v not in cand[s]:
                cand[s].append(v)

    def ok(s, v):
        try:
            return all(f.PREDS[p][1](v) for p in combos.get(s, ()))
        except (TypeError, ValueError):
            return False
    return {s: [v for v in vs if ok(s, v)] for s, vs in cand.items()}


def rel_holds(rel, point):
    """Decide a relation at a numeric point.

    ``refine_fuzz.rel_holds`` relies on ``Q.lt(-3, 0).doit()``, which SymPy
    leaves unevaluated, so it never answers True and ``refine_fuzz`` checks no
    case that carries a relation.  Here both sides are evaluated numerically;
    an order relation needs both sides real.
    """
    from sympy import N, Q
    try:
        lhs, rhs = (complex(N(side.subs(point), 20)) for side in rel.arguments)
    except (TypeError, ValueError, AttributeError):
        return None
    tol = 1e-12 * max(1.0, abs(lhs), abs(rhs))
    if rel.function == Q.eq:
        return abs(lhs - rhs) <= tol
    if rel.function == Q.ne:
        return abs(lhs - rhs) > tol
    if abs(lhs.imag) > tol or abs(rhs.imag) > tol:
        return False
    a, b = lhs.real, rhs.real
    return {Q.gt: a > b + tol, Q.ge: a >= b - tol, Q.lt: a < b - tol, Q.le: a <= b + tol}.get(rel.function)


def check_points(exprs, combos, rel, rng, random_points=12, cap=160):
    """Sample points satisfying the assumptions: random draws plus edge points."""
    f = fz()
    syms = sorted(set().union(*(e.free_symbols for e in exprs)), key=str)
    points = []

    def rand_value(s):
        return f.draw(combos.get(s, ()), rng)

    for _ in range(random_points * 4):
        if len(points) >= random_points:
            break
        pt = {s: rand_value(s) for s in syms}
        if any(v is None for v in pt.values()):
            break
        points.append(pt)
    cand = edge_candidates(exprs, syms, combos)
    # the full product of edge candidates when small, else each edge value with random others
    total = 1
    for s in syms:
        total *= max(1, len(cand[s]))
    if syms and total <= cap:
        import itertools
        for combo in itertools.product(*[cand[s] or [None] for s in syms]):
            pt = {s: (v if v is not None else rand_value(s)) for s, v in zip(syms, combo)}
            if all(v is not None for v in pt.values()):
                points.append(pt)
    else:
        for s in syms:
            for v in cand[s]:
                pt = {t: (v if t == s else rand_value(t)) for t in syms}
                if all(w is not None for w in pt.values()):
                    points.append(pt)
    if rel is not None:
        points = [p for p in points if rel_holds(rel, p) is True]
    return points


def compare(left, right, points):
    """(n_checked, counterexample or None) comparing two expressions at ``points``."""
    f = fz()
    bad = ("error", "unevaluated", "nan", "inf")
    checked = 0
    for pt in points:
        try:
            a, b = f.numeric(left.subs(pt)), f.numeric(right.subs(pt))
        except Exception:  # noqa: BLE001, S112 -- a point SymPy cannot substitute is skipped
            continue
        if a in bad and b in bad:
            continue
        if not f.agree(a, b):
            return checked, (pt, a, b)
        checked += 1
    return checked, None


def _fmt(v):
    if isinstance(v, tuple):            # a matrix value from refine_fuzz.mat_value
        return f"{v[1][0]}x{v[1][1]} matrix [" + ", ".join(_fmt(x) for x in v[2]) + "]"
    return v if isinstance(v, str) else f"{v.real:.12g}{v.imag:+.12g}j"


# ---------------------------------------------------------------------------
# worker: one package, every case
# ---------------------------------------------------------------------------

class _Timeout(Exception):
    pass


def worker(package, seed, cases, out, timeout, matrices=False):
    os.environ["SATREFINE_HANDLERS"] = package
    f = fz()
    from sympy import Basic, srepr, sympify
    mod = sys.modules.get("satrefine." + package)
    assert mod is not None, f"satrefine.{package} was not loaded"

    def on_alarm(signum, frame):
        raise _Timeout

    signal.signal(signal.SIGALRM, on_alarm)
    records = []
    t0 = time.time()
    for case in range(cases):
        g = f.mat_generate(seed, case) if matrices else generate(seed, case)
        if g is None:
            continue
        head, e, assumptions, combos, rel = g
        rec = {"case": case, "head": head}
        signal.alarm(timeout)
        try:
            try:
                r = f.sat_refine(e, assumptions)
                if not isinstance(r, Basic):
                    rec["nonbasic"] = repr(r)
                    r = sympify(r)
            except ValueError as ex:
                if "nconsistent" in str(ex):
                    rec["status"] = "inconsistent"
                    records.append(rec)
                    continue
                raise
            if r == e:
                rec["status"] = "unchanged"
            else:
                rec["status"] = "fired"
                rec["result"] = srepr(r)
                rec["result_str"] = str(r)
                rng = random.Random(seed * 7919 + case)
                if matrices:
                    n_ok, ce = f.mat_compare(e, r, f.mat_points(combos, rel, rng))
                else:
                    points = check_points([e, r], combos, rel, rng)
                    n_ok, ce = compare(e, r, points)
                rec["checked"] = n_ok
                if ce:
                    pt, a, b = ce
                    rec["unsound"] = {"point": {str(k): str(v).replace("\n", "") for k, v in pt.items()},
                                      "orig": _fmt(a), "refined": _fmt(b)}
        except _Timeout:
            rec["status"] = "timeout"
        except Exception as ex:  # noqa: BLE001 -- a crash is a finding, recorded
            rec["status"] = "crash"
            rec["error"] = f"{type(ex).__name__}: {str(ex)[:160]}"
        finally:
            signal.alarm(0)
        records.append(rec)
    with open(out, "w") as fh:
        json.dump({"package": package, "seconds": time.time() - t0, "records": records}, fh)


# ---------------------------------------------------------------------------
# parent: run both, compare
# ---------------------------------------------------------------------------

def run_worker(package, args, out):
    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", package, "--seed", str(args.seed),
           "--cases", str(args.cases), "--out", out, "--timeout", str(args.timeout)]
    if args.matrices:
        cmd.append("--matrices")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"worker for {package} failed ({proc.returncode})")
    with open(out) as fh:
        return json.load(fh)


def _load(s):
    import sympy
    from sympy import srepr
    from sympy.core.parameters import evaluate
    ns = {k: getattr(sympy, k) for k in dir(sympy) if not k.startswith("_")}
    from sympy.assumptions.relation.binrel import AppliedBinaryRelation
    from sympy.core.symbol import Str
    ns.update(AppliedBinaryRelation=AppliedBinaryRelation, Str=Str)
    import sympy.matrices.expressions as mexpr
    from sympy.matrices.expressions.matexpr import MatrixElement
    ns.update({k: getattr(mexpr, k) for k in dir(mexpr) if not k.startswith("_")}, MatrixElement=MatrixElement)
    v = eval(s, dict(ns))
    if srepr(v) != s:
        with evaluate(False):
            w = eval(s, dict(ns))
        if srepr(w) == s:
            v = w
    return v


def _singular(record):
    """The counterexample's input side is nan or infinite."""
    return record["unsound"]["orig"] in ("nan", "inf")


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
                    help="matrix expressions (refine_fuzz.mat_generate) checked at explicit sample matrices")
    ap.add_argument("--worker", help=argparse.SUPPRESS)
    ap.add_argument("--out", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.worker:
        worker(args.worker, args.seed, args.cases, args.out, args.timeout, args.matrices)
        return

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        res = {}
        for label, pkg in (("a", args.a), ("b", args.b)):     # sequential: shared machine
            res[label] = run_worker(pkg, args, os.path.join(tmp, f"{label}.json"))
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
    gen = fz().mat_generate if args.matrices else generate
    for c in differ:
        g = gen(args.seed, c)
        _, e, _, combos, rel = g
        la, lb = _load(A[c]["result"]), _load(B[c]["result"])
        rng = random.Random(args.seed * 104729 + c)
        if args.matrices:
            n, ce = fz().mat_compare(la, lb, fz().mat_points(combos, rel, rng), ref=e)
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
    print(f"{'matrices ' if args.matrices else ''}seed={args.seed} cases={args.cases} compared={len(common)} time={time.time() - t0:.0f}s "
          f"(a={args.a} {res['a']['seconds']:.0f}s, b={args.b} {res['b']['seconds']:.0f}s)")
    for lab in ("a", "b"):
        print(f"  {lab}={name[lab]}: fired={stat(res[lab], 'fired')} unchanged={stat(res[lab], 'unchanged')} "
              f"inconsistent={stat(res[lab], 'inconsistent')} crash={stat(res[lab], 'crash')} "
              f"timeout={stat(res[lab], 'timeout')} checked={stat(res[lab], 'fired') - len(unsound[lab]) - len(unchecked[lab])} "
              f"unchecked={len(unchecked[lab])} unsound={len(unsound[lab])} "
              f"(input finite at the point: {sum(1 for r in unsound[lab] if not _singular(r))}) "
              f"non-SymPy={len(nonbasic[lab])}")
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
            print(f"      NUMERICALLY DIFFERENT at {pt}: a={_fmt(va)} b={_fmt(vb)}")
        else:
            print(f"      {verdict}" + (f" at {info} points" if verdict == "equal" else ""))
    for lab in ("a", "b"):
        recs = A if lab == "a" else B
        print(f"\n== {lab}={name[lab]} UNSOUND rewrites: {len(unsound[lab])} ==")
        for r in unsound[lab][:args.show]:
            u = r["unsound"]
            note = "  (input non-finite there: pole or removable singularity?)" if _singular(r) else ""
            print(f"  {case_line(r['case'], recs[r['case']])} -> {r['result_str']}\n"
                  f"      at {u['point']}: orig={u['orig']} refined={u['refined']}{note}")
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
