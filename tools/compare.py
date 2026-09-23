"""Replay recorded SymPy assumption queries against satassume.

    python tools/compare.py queries.jsonl [--in-scope-only] [--time-sympy]
                                          [--limit N] [--show K]

Each new-system record (``kind`` ``ask`` or ``rec``) is classified with
``satassume.sympy_api.out_of_scope``:

* **in scope**: unary scalar predicates on scalar expressions.  These are the
  headline numbers and the only ones that gate anything;
* **out of scope**: ``relation``, ``matrix`` (matrix predicate or non-scalar
  argument), ``custom`` predicate, ``other`` (not a Boolean proposition).
  The engine returns None for these by rule; they are reported for
  information only.

Old-system records (``kind == "old"``, ``expr.is_<fact>`` cache misses) are
replayed through ``Engine.is_`` and reported as "out of scope
(informational)": replacing the old system is the long-term goal, not the
current slice.

Per group the report counts: ``agree`` (same answer, or both raised),
``extra`` (definite answer where SymPy returned None), ``none`` (None where
SymPy answered), ``wrong`` (definite answer contradicting SymPy),
``error`` (the engine raised ValueError where SymPy answered; this is the
documented semantic choice on assumptions contradicting declared facts),
``no_error`` (SymPy raised, the engine answered) and ``unreplayable``.

With ``--time-sympy`` every in-scope record is also timed through
``sympy.ask`` in the same process.  Garbage collection is frozen once and
disabled inside both timed calls, so a collection pause never lands on one
side of a record.  A few rebuilt records make ``sympy.ask`` raise (an
unevaluated ``Or`` of predicates); those are timed again on an evaluated
rebuild and, if SymPy still raises, left out of the comparison and counted.

The exit code is 1 only if an in-scope record is ``wrong``.
"""
from __future__ import annotations

import argparse
import collections
import gc
import json
import sys
import time

from sympy import sympify, srepr  # noqa: F401  (srepr needed by eval below)
from sympy.core.symbol import Symbol  # noqa: F401
import sympy

from satassume import Engine
from satassume.sympy_api import ask as sat_ask, out_of_scope, CATEGORIES
from satassume.engine import DictCache


_EXTRA_MODULES = (
    "sympy.core.symbol", "sympy.assumptions", "sympy.assumptions.assume",
    "sympy.assumptions.relation.binrel",
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


def rebuild(s, timeout=2, evaluated=False):
    """Rebuild an ``srepr`` string.  ``srepr`` loses ``evaluate=False``, so
    the tree is rebuilt without evaluation (it was canonical already) and a
    hard timeout guards against constructions that SymPy would grind on."""
    import signal
    from sympy import evaluate
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(timeout)
    try:
        if evaluated:
            return eval(s, namespace())
        with evaluate(False):
            return eval(s, namespace())
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def time_sympy(prop, assum, rec):
    """Seconds ``sympy.ask`` takes on the record, or None if it raises on
    both the unevaluated and the evaluated rebuild."""
    for attempt in (0, 1):
        if attempt:
            try:
                prop, assum = rebuild(rec["prop"], evaluated=True), rebuild(rec["assum"], evaluated=True)
            except Exception:
                return None
        gc.disable()
        t = time.perf_counter()
        try:
            sympy.ask(prop, assum)
        except Exception:
            continue
        else:
            return time.perf_counter() - t
        finally:
            gc.enable()
    return None


IN_SCOPE = "in-scope"
OLD = "old"
GROUPS = (IN_SCOPE,) + tuple("out:" + c for c in CATEGORIES) + (OLD,)
LABELS = {
    IN_SCOPE: "in scope: unary scalar predicates (ask + rec)",
    "out:relation": "out of scope (informational): relations",
    "out:matrix": "out of scope (informational): matrix predicates / non-scalar arguments",
    "out:custom": "out of scope (informational): custom predicates",
    "out:other": "out of scope (informational): not a Boolean proposition",
    OLD: "out of scope (informational): old-system expr.is_* records",
}
COLUMNS = ("agree", "extra", "none", "wrong", "error", "no_error", "unreplayable")


def classify(got, want) -> str:
    if isinstance(want, str) and want.startswith("error"):
        return "agree" if isinstance(got, str) else "no_error"
    if isinstance(got, str):
        return "error"
    if got == want:
        return "agree"
    if got is None:
        return "none"
    if want is None:
        return "extra"
    return "wrong"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("file")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip", type=int, default=0, help="skip the first N records")
    ap.add_argument("--show", type=int, default=15, help="print up to K records per reported category")
    ap.add_argument("--slow-ms", type=float, default=100.0, help="print records slower than this")
    ap.add_argument("--in-scope-only", action="store_true",
                    help="replay only in-scope new-system records")
    ap.add_argument("--time-sympy", action="store_true",
                    help="also time sympy.ask on every in-scope record")
    ap.add_argument("--fresh-cache", action="store_true",
                    help="use a private cache instead of the objects' _assumptions dicts")
    ap.add_argument("--dump-times", metavar="FILE",
                    help="write per-record timings (satassume ms, sympy ms, query) to FILE")
    args = ap.parse_args(argv)
    dump = open(args.dump_times, "w") if args.dump_times else None

    eng = Engine(cache=DictCache() if args.fresh_cache else None)
    stats = {g: collections.Counter() for g in GROUPS}
    shown = collections.Counter()
    t_sat = collections.Counter()
    t_sympy = 0.0
    sat_slower = 0
    sympy_raised = 0
    timed = 0
    if args.time_sympy:
        gc.freeze()
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
            want = rec["value"]
            if kind == "old":
                if args.in_scope_only:
                    continue
                group = OLD
                try:
                    expr = rebuild(rec["expr"])
                except Exception:
                    stats[group]["unreplayable"] += 1
                    continue
                desc = f"{rec['fact']}({expr})"
                t = time.perf_counter()
                try:
                    got = eng.is_(expr, rec["fact"])
                except ValueError:
                    got = "error:ValueError"
                dt = time.perf_counter() - t
            else:
                try:
                    prop = rebuild(rec["prop"])
                    assum = rebuild(rec["assum"])
                    cat = out_of_scope(prop, assum)
                except Exception:
                    stats[IN_SCOPE]["unreplayable"] += 1
                    continue
                group = IN_SCOPE if cat is None else "out:" + cat
                if args.in_scope_only and group != IN_SCOPE:
                    continue
                desc = f"{prop} | {assum}"
                if args.time_sympy:
                    gc.disable()
                t = time.perf_counter()
                try:
                    got = sat_ask(prop, assum, engine=eng)
                except ValueError:
                    got = "error:ValueError"
                dt = time.perf_counter() - t
                if args.time_sympy:
                    gc.enable()
                if args.time_sympy and group == IN_SCOPE:
                    ds = time_sympy(prop, assum, rec)
                    if ds is None:
                        sympy_raised += 1
                    else:
                        timed += 1
                        t_sympy += ds
                        if dt > ds:
                            sat_slower += 1
                        if dump is not None:
                            dump.write(f"{dt*1000:.3f}\t{ds*1000:.3f}\t{desc}\n")
            t_sat[group] += dt
            if dt * 1000 > args.slow_ms:
                print(f"[slow {dt*1000:.0f} ms] {group}: {desc[:200]}", flush=True)
            cat = classify(got, want)
            stats[group][cat] += 1
            key = (group, cat)
            if cat in ("wrong", "none", "error", "no_error") and group == IN_SCOPE \
                    and shown[key] < args.show:
                shown[key] += 1
                print(f"[{cat}] {group}: {desc}  sympy={want} satassume={got}")
    print()
    for g in GROUPS:
        c = stats[g]
        tot = sum(c.values())
        if tot == 0:
            continue
        cells = " ".join(f"{k}={c[k]}" for k in COLUMNS if c[k])
        answered = tot - c["unreplayable"]
        pct = 100.0 * c["agree"] / answered if answered else 0.0
        print(f"{LABELS[g]}\n    n={tot} {cells}  ({pct:.1f}% agree, {t_sat[g]:.2f}s)")
    if args.time_sympy:
        print(f"sympy.ask on {timed} in-scope records: {t_sympy:.2f}s; satassume slower on "
              f"{sat_slower} records; sympy.ask raised on {sympy_raised} (not compared)")
    sizes = sorted((len(sess.base) for sess, _ in eng._context_sessions.values()), reverse=True)
    print(f"engine stats: {eng.stats}; kept context sessions (nodes): {sizes}")
    if dump is not None:
        dump.close()
    return 1 if stats[IN_SCOPE]["wrong"] else 0


if __name__ == "__main__":
    sys.exit(main())
