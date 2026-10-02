"""Run ``satassume.ref.ask_ref`` over the recorded corpus.

    python tools/ref_corpus.py queries.jsonl [--relations-only] [--skip N] [--limit N] [--lines a,b,c]

Replays the in-scope records exactly as ``tools/compare.py --in-scope-only``
selects them (with ``--relations-only``, the ``out:relation`` records as
``compare.py --relations-only`` does) (its loader, ``rebuild`` and ``out_of_scope``, is imported, not
copied) and answers each three ways: the recorded answer, the engine
(``sympy_api.ask`` on one ``Engine``, as ``compare.py``) and ``ask_ref``.

Counts, in ``compare.py``'s columns, of ``ask_ref`` against the record
(``agree``, ``extra`` = more definite, ``none`` = less definite, ``wrong`` =
contradiction, ``error``, ``no_error``, ``unreplayable``) and of ``ask_ref``
against the engine (``agree``, ``ref_more``, ``eng_more``, ``contradict``,
``error``).

Every difference between ``ask_ref`` and the engine is listed with one of
three classifications (issue #97 plan, P5b item 4):

* ``budget``: the engine answered None with ``last_budget_limited`` set
  where ``ask_ref`` is definite;
* ``engine defect``: the engine is None (not budget limited) or raised
  where ``ask_ref`` is definite, or the two contradict with ``ask_ref``
  agreeing with the record;
* ``spec defect``: ``ask_ref`` is None or raised where the engine is
  definite, or the two contradict with the engine agreeing with the record,
  or ``ask_ref`` raised an exception other than ``ValueError``.

Every difference between ``ask_ref`` and the record is listed too (a
``none`` there with the engine also None is a corpus miss the baseline
counts).  Each record is wrapped so one exception is counted, not fatal;
partial totals are printed every 500 records.  Nothing is excluded: the
summary line and the partial totals count every line read (``records``),
the ``old`` records and each out-of-scope category (``out_of_scope``'s
name; ``in_scope`` for records ``--relations-only`` leaves out) next to
``n``, so ``n`` + ``old`` + the categories + ``unreplayable`` = ``records``.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare import IN_SCOPE, classify, rebuild  # noqa: E402

from satassume.engine import Engine  # noqa: E402
from satassume.ref import RefInfo, ask_ref  # noqa: E402
from satassume.sympy_api import ask as sat_ask, out_of_scope  # noqa: E402

REC_COLUMNS = ("agree", "extra", "none", "wrong", "error", "no_error", "unreplayable")
ENG_COLUMNS = ("agree", "ref_more", "eng_more", "contradict", "error")


def _vs_engine(ref, eng) -> str:
    if isinstance(ref, str) and ref.startswith("exc:"):
        return "error"
    if ref == eng:
        return "agree"
    if isinstance(ref, str) or isinstance(eng, str):
        # one raised ValueError, the other did not
        return "error"
    if ref is None:
        return "eng_more"
    if eng is None:
        return "ref_more"
    return "contradict"


def _classify(kind: str, ref, eng, want, budget: bool) -> str:
    if kind == "ref_more":
        return "budget" if budget else "engine defect"
    if kind == "eng_more":
        return "spec defect"
    if kind == "contradict":
        if ref == want:
            return "engine defect"
        if eng == want:
            return "spec defect"
        return "spec defect (neither matches the record)"
    if kind == "error":
        if isinstance(ref, str) and ref.startswith("exc:"):
            return "spec defect (exception)"
        if isinstance(ref, str):
            return "spec defect (ask_ref raised, engine did not)"
        return "engine defect (engine raised, ask_ref did not)"
    return ""


def _fmt(v) -> str:
    return v if isinstance(v, str) else repr(v)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("file")
    ap.add_argument("--relations-only", action="store_true",
                    help="replay the relational records instead (compare.py --relations-only)")
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--lines", default="", help="comma-separated line numbers only")
    ap.add_argument("--every", type=int, default=500, help="print partial totals every N records")
    args = ap.parse_args(argv)
    only = {int(s) for s in args.lines.split(",") if s} if args.lines else None

    eng = Engine()
    rec_stats = collections.Counter()
    eng_stats = collections.Counter()
    classes = collections.Counter()
    diffs_eng = []      # (line, desc, ref, eng, want, class)
    diffs_rec = []      # (line, desc, ref, eng, want, column)
    t_ref = t_eng = 0.0
    t_max = (0.0, 0, "")
    n = seen = records = 0
    skipped = collections.Counter()     # old, and each out-of-scope category

    def _skipped():
        return (f"records={records} old={skipped['old']} " +
                " ".join(f"{c}={v}" for c, v in sorted(skipped.items()) if c != "old"))

    with open(args.file) as f:
        for line in f:
            n += 1
            if n <= args.skip or (only is not None and n not in only):
                continue
            if args.limit and n > args.skip + args.limit:
                break
            records += 1
            rec = json.loads(line)
            if rec["kind"] == "old":
                skipped["old"] += 1
                continue
            want = rec["value"]
            try:
                prop = rebuild(rec["prop"])
                assum = rebuild(rec["assum"])
                cat = out_of_scope(prop, assum)
            except Exception:   # noqa: BLE001 - as compare.py
                rec_stats["unreplayable"] += 1
                continue
            if (cat != "relation") if args.relations_only else (cat is not None):
                skipped[cat if cat is not None else "in_scope"] += 1
                continue
            seen += 1
            desc = f"{prop} | {assum}"
            t = time.perf_counter()
            try:
                got_eng = sat_ask(prop, assum, engine=eng)
            except ValueError:
                got_eng = "error:ValueError"
            except Exception as e:   # noqa: BLE001 - counted, not fatal
                got_eng = f"exc:{type(e).__name__}"
            budget = bool(eng.last_budget_limited)
            t_eng += time.perf_counter() - t
            info = RefInfo()
            t = time.perf_counter()
            try:
                got_ref = ask_ref(prop, assum, info=info)
            except ValueError:
                got_ref = "error:ValueError"
            except Exception as e:   # noqa: BLE001 - counted, not fatal
                got_ref = f"exc:{type(e).__name__}: {e}"[:160]
            dt = time.perf_counter() - t
            t_ref += dt
            if dt > t_max[0]:
                t_max = (dt, n, desc)
            col = classify(got_ref, want)
            rec_stats[col] += 1
            if col != "agree":
                diffs_rec.append((n, desc, got_ref, got_eng, want, col, info))
            kind = _vs_engine(got_ref, got_eng)
            eng_stats[kind] += 1
            if kind != "agree":
                cls = _classify(kind, got_ref, got_eng, want, budget)
                classes[cls] += 1
                diffs_eng.append((n, desc, got_ref, got_eng, want, kind, cls, budget, info))
            if seen % args.every == 0:
                print(f"[partial] line {n}: n={seen} {_skipped()} vs record "
                      f"{dict((c, rec_stats[c]) for c in REC_COLUMNS if rec_stats[c])} "
                      f"vs engine {dict((c, eng_stats[c]) for c in ENG_COLUMNS if eng_stats[c])} "
                      f"ref {t_ref:.1f}s eng {t_eng:.1f}s", flush=True)

    print(f"\nask_ref vs record: n={seen} {_skipped()} " +
          " ".join(f"{c}={rec_stats[c]}" for c in REC_COLUMNS))
    print(f"ask_ref vs engine: n={seen} " +
          " ".join(f"{c}={eng_stats[c]}" for c in ENG_COLUMNS))
    print("classification of ask_ref/engine differences: " +
          (", ".join(f"{k}={v}" for k, v in sorted(classes.items())) or "none"))
    print(f"time: ask_ref {t_ref:.2f}s ({1000 * t_ref / max(seen, 1):.2f} ms/query), "
          f"engine {t_eng:.2f}s ({1000 * t_eng / max(seen, 1):.2f} ms/query); "
          f"slowest ask_ref {1000 * t_max[0]:.0f} ms at line {t_max[1]}: {t_max[2]}")
    print(f"\n{len(diffs_eng)} differences ask_ref vs engine (line | query | ref | engine | "
          f"record | kind | class | budget_limited | info):")
    for n, desc, r, e, w, kind, cls, budget, info in diffs_eng:
        print(f"  {n} | {desc} | {_fmt(r)} | {_fmt(e)} | {w!r} | {kind} | {cls} | {budget} | {info}")
    print(f"\n{len(diffs_rec)} differences ask_ref vs record (line | query | ref | engine | "
          f"record | column | info):")
    for n, desc, r, e, w, col, info in diffs_rec:
        print(f"  {n} | {desc} | {_fmt(r)} | {_fmt(e)} | {w!r} | {col} | {info}")
    return 1 if rec_stats["wrong"] or eng_stats["contradict"] else 0


if __name__ == "__main__":
    sys.exit(main())
