"""Replay recorded SymPy assumption queries against satassume.

    python tools/compare.py queries.jsonl [--limit N] [--show K]

Reports, per record kind, how often satassume agrees with SymPy, answers
where SymPy did not, returns None where SymPy answered, or disagrees (the
only category that must be zero), plus the time taken by each side.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time

from sympy import sympify, srepr  # noqa: F401  (srepr needed by eval below)
from sympy.core.symbol import Symbol  # noqa: F401
import sympy

from satassume import Engine
from satassume.sympy_api import ask as sat_ask, to_formula, Unsupported
from satassume.engine import DictCache


_EXTRA_MODULES = (
    "sympy.core.symbol", "sympy.assumptions", "sympy.assumptions.assume",
    "sympy.matrices.expressions", "sympy.matrices.expressions.matexpr",
    "sympy.matrices.expressions.slice", "sympy.matrices.expressions.blockmatrix",
    "sympy.matrices.expressions.diagonal", "sympy.matrices.expressions.fourier",
    "sympy.matrices.expressions.factorizations", "sympy.matrices.expressions.special",
    "sympy.functions", "sympy.core.numbers", "sympy.core.relational", "sympy.logic.boolalg",
)


class _Namespace(dict):
    """srepr output names classes from all over SymPy; resolve them lazily."""

    def __missing__(self, name):
        import importlib
        for mod in ("sympy",) + _EXTRA_MODULES:
            try:
                obj = getattr(importlib.import_module(mod), name)
            except (AttributeError, ImportError):
                continue
            self[name] = obj
            return obj
        raise NameError(name)


_NS = None


def namespace():
    global _NS
    if _NS is None:
        _NS = _Namespace(vars(sympy))
    return _NS


class Unreplayable(Exception):
    pass


def _alarm(signum, frame):
    raise Unreplayable("rebuild timed out")


def rebuild(s, timeout=2):
    """Rebuild an ``srepr`` string.  ``srepr`` loses ``evaluate=False``, so
    the tree is rebuilt without evaluation (it was canonical already) and a
    hard timeout guards against constructions that SymPy would grind on."""
    import signal
    from sympy import evaluate
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(timeout)
    try:
        with evaluate(False):
            return eval(s, namespace())
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip", type=int, default=0, help="skip the first N records")
    ap.add_argument("--show", type=int, default=15, help="print up to K disagreements/misses")
    ap.add_argument("--slow-ms", type=float, default=100.0, help="print records slower than this")
    ap.add_argument("--fresh-cache", action="store_true",
                    help="use a private cache instead of the objects' _assumptions dicts")
    args = ap.parse_args(argv)

    eng = Engine(cache=DictCache() if args.fresh_cache else None)
    stats = collections.defaultdict(collections.Counter)
    shown = collections.Counter()
    t_sat = 0.0
    n = 0
    with open(args.file) as f:
        for line in f:
            n += 1
            if n <= args.skip:
                continue
            if args.limit and n > args.skip + args.limit:
                break
            rec = json.loads(line)
            kind = rec["kind"]
            try:
                if kind == "old":
                    expr = rebuild(rec["expr"])
                    want = rec["value"]
                    t = time.perf_counter()
                    got = eng.is_(expr, rec["fact"])
                    t_sat += time.perf_counter() - t
                    desc = f"{rec['fact']}({expr})"
                else:
                    prop = rebuild(rec["prop"]); assum = rebuild(rec["assum"])
                    want = rec["value"]
                    t = time.perf_counter()
                    try:
                        got = sat_ask(prop, assum, engine=eng)
                    except ValueError:
                        got = "error:ValueError"
                    t_sat += time.perf_counter() - t
                    desc = f"{prop} | {assum}"
            except Exception as e:  # rebuild failures etc.
                stats[kind]["unreplayable"] += 1
                continue
            dt = time.perf_counter() - t
            if dt * 1000 > args.slow_ms:
                print(f"[slow {dt*1000:.0f} ms] {kind}: {desc[:200]}", flush=True)
            if isinstance(want, str) and want.startswith("error"):
                cat = "agree" if isinstance(got, str) else "sat_no_error"
            elif got == want:
                cat = "agree"
            elif got is None:
                cat = "sat_none"
            elif want is None:
                cat = "sat_answers"
            else:
                cat = "DISAGREE"
            stats[kind][cat] += 1
            if cat in ("DISAGREE", "sat_none") and shown[cat] < args.show:
                shown[cat] += 1
                print(f"[{cat}] {kind}: {desc}  sympy={want} satassume={got}")
    print()
    for kind, c in stats.items():
        tot = sum(c.values())
        print(f"{kind:4s} n={tot:5d} " + " ".join(f"{k}={v}" for k, v in sorted(c.items())))
    print(f"satassume time: {t_sat:.2f}s  engine stats: {eng.stats}")
    return 1 if any(c["DISAGREE"] for c in stats.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
