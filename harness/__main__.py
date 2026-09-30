"""Command line of the history-dependence harness.

    python -m harness fuzz     --seeds 0-9 --config default,tight [--queries N] [--sets K]
                               [--orders ...] [--custom] [--no-relations] [--confirm]
    python -m harness hypo     --examples N --config default [--custom]
    python -m harness replay   queries.jsonl --config default,reuse [--orders ...] [--limit N]
                               [--kinds ask,rec,old] [--chunk N]
    python -m harness refine   --seeds 0-4 --config default [--exprs N]
    python -m harness hashseed --seeds 0-3 --hashseeds 0,1,2,3 --config default
    python -m harness repro    FILE.json [--hashseed N]
    python -m harness exec     STREAM.json [--ref-level L]      (used by subprocesses)
    python -m harness inventory

Every mode prints one JSON line per (source, config) with the counts, and
writes each discrepancy (shrunk to a minimal prefix) to ``--out DIR``
(default ``harness-results/``) as ``.json`` and a standalone ``.py`` repro.
Exit status 1 if any discrepancy was found (``--fail-on unknown``: only
one whose family tag is not a documented one; ``--fail-on never``).

Run with ``PYTHONHASHSEED=0`` unless testing hash-seed variation.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import List

from .checker import (Ask, Checker, Discrepancy, ORDERS, ReferenceLevel, confirm, execute,
                      is_known_family, item_from_json, read_stream, run_in_process, write_repro,
                      write_stream)
from .state import PRESETS, EngineConfig, MODULE_CONFIG, MODULE_CONSTANTS, MODULE_STATE, inventory, preset

DEFAULT_ORDERS = ("forward", "reverse", "shuffle", "grouped", "interleave")


def _seeds(s: str) -> List[int]:
    out: List[int] = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def _configs(s: str) -> List[EngineConfig]:
    if s == "all":
        return list(PRESETS.values())
    return [preset(n) for n in s.split(",")]


def _progress(quiet: bool):
    if quiet:
        return lambda m: None
    return lambda m: print(m, file=sys.stderr, flush=True)


def _report(rep, source, out_dir, args, stem):
    d = rep.to_json()
    d["source"] = source
    print(json.dumps(d), flush=True)
    paths = []
    for i, disc in enumerate(rep.discrepancies):
        if getattr(args, "confirm", False):
            try:
                confirm(disc, hashseeds=_seeds(args.hashseeds))
            except Exception as e:  # noqa: BLE001
                disc.confirmations["error"] = str(e)
        jp, pp = write_repro(disc, out_dir, f"{stem}-{i}")
        paths.append(pp)
        print(f"  discrepancy: {disc.summary()}\n    repro: {pp}", file=sys.stderr, flush=True)
    return paths


def _failing(discs, args, audit: bool = False) -> int:
    """How many of ``discs`` count for the exit status under ``--fail-on``:
    ``any`` (every discrepancy), ``unknown`` (those whose family tag is not
    a documented one, ``checker.is_known_family``), ``never``."""
    mode = getattr(args, "fail_on", "any")
    if mode == "never":
        return 0
    if mode == "unknown":
        return sum(1 for d in discs
                   if not is_known_family(d.confirmations.get("family", "?"), audit=audit))
    return len(discs)


def _ignore(args):
    return [k for k in args.ignore.split(",") if k]


def _common(ap):
    ap.add_argument("--config", default="default", help="comma-separated presets, or 'all'")
    ap.add_argument("--orders", default=",".join(DEFAULT_ORDERS))
    ap.add_argument("--ref-level", type=int, default=1, choices=(1, 2))
    ap.add_argument("--ref-check-every", type=int, default=0,
                    help="every k-th query also gets a module-level reference")
    ap.add_argument("--out", default="harness-results")
    ap.add_argument("--max-discrepancies", type=int, default=5)
    ap.add_argument("--no-shrink", action="store_true")
    ap.add_argument("--confirm", action="store_true", help="re-run each repro in fresh processes")
    ap.add_argument("--hashseeds", default="0,1,2")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--ignore", default="", help="comma-separated kinds not reported, e.g. raise-vs-definite")
    ap.add_argument("--fail-on", default="any", choices=("any", "unknown", "never"),
                    help="exit status 1 on any discrepancy (default), only on one of an "
                         "undocumented family (needs shrinking, which attributes), or never")


def _gen_opts(ap):
    ap.add_argument("--custom", action="store_true", help="custom predicates and register events")
    ap.add_argument("--no-relations", action="store_true")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--lazy", type=float, default=0.0,
                    help="probability of a trigger/observer pair after a base-stream query (harness/lazy.py)")
    ap.add_argument("--profile", default="base",
                    help="stream shape: base, related, focus, deep, relational, declared, mixed, "
                         "or a comma-separated list, or 'all' (see harness/profiles.py)")


def _opts_of(args, profile: str = None) -> dict:
    return dict(relations=not args.no_relations, custom=args.custom, events=args.custom,
                max_depth=args.depth, profile=profile or getattr(args, "profile", "base"),
                lazy=getattr(args, "lazy", 0.0))


def _profiles(args) -> List[str]:
    s = getattr(args, "profile", "base")
    if s == "all":
        from .profiles import PROFILES
        return ["base"] + [p for p in sorted(PROFILES) if p != "mixed"]
    return s.split(",")


def cmd_fuzz(args) -> int:
    from .generators import random_stream
    bad = 0
    for profile in _profiles(args):
        for cfg in _configs(args.config):
            for seed in _seeds(args.seeds):
                items = random_stream(seed, args.queries, args.sets, **_opts_of(args, profile))
                src = f"fuzz profile={profile} seed={seed}"
                chk = Checker(cfg, args.ref_level, args.orders.split(","), seed=seed,
                              ref_check_every=args.ref_check_every,
                              max_discrepancies=args.max_discrepancies,
                              shrink_them=not args.no_shrink, source=src,
                              progress=_progress(args.quiet), ignore_kinds=_ignore(args))
                rep = chk.run(items)
                stem = f"fuzz-{cfg.name}-s{seed}" if profile == "base" else f"fuzz-{profile}-{cfg.name}-s{seed}"
                _report(rep, src, args.out, args, stem)
                bad += _failing(rep.discrepancies, args)
    return 1 if bad else 0


def cmd_hypo(args) -> int:
    from hypothesis import HealthCheck, Phase, given, settings
    from hypothesis.database import DirectoryBasedExampleDatabase
    from .generators import stream_strategy
    bad = []
    # derandomized runs replay the same examples and keep no database
    db = None if args.derandomize else DirectoryBasedExampleDatabase(os.path.join(args.out, ".hypothesis-db"))
    for cfg in _configs(args.config):
        found: List[Discrepancy] = []

        @settings(max_examples=args.examples, deadline=None, database=db,
                  suppress_health_check=list(HealthCheck), derandomize=args.derandomize,
                  phases=(Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink))
        @given(stream_strategy(n_max=args.queries, nsets_max=args.sets, **_opts_of(args)))
        def prop(items):
            for order in args.orders.split(","):
                chk = Checker(cfg, args.ref_level, (order,), shrink_them=False,
                              max_discrepancies=1, source="hypothesis", ignore_kinds=_ignore(args))
                rep = chk.run(items)
                if rep.discrepancies:
                    found[:] = rep.discrepancies
                    raise AssertionError(rep.discrepancies[0].summary())

        t0 = time.perf_counter()
        try:
            prop()
            print(json.dumps({"config": cfg.name, "hypothesis_examples": args.examples,
                              "discrepancies": 0, "seconds": round(time.perf_counter() - t0, 1)}))
        except AssertionError as e:
            print(json.dumps({"config": cfg.name, "hypothesis_examples": args.examples,
                              "discrepancies": 1, "seconds": round(time.perf_counter() - t0, 1),
                              "minimal": str(e)}))
            for d in found:
                from .checker import attribute, shrink
                shrink(d)
                try:
                    attribute(d)
                except Exception as e:  # noqa: BLE001
                    d.confirmations["attribute_error"] = str(e)
                bad.append(d)
                jp, pp = write_repro(d, args.out, f"hypo-{args.profile}-{cfg.name}")
                print(f"  {d.summary()}\n  repro: {pp}", file=sys.stderr)
    return 1 if _failing(bad, args) else 0


def cmd_replay(args) -> int:
    from .corpus import load_corpus, old_records
    kinds = args.kinds.split(",")
    items: List[Ask] = []
    if any(k in ("ask", "rec") for k in kinds):
        items += load_corpus(args.corpus, kinds=[k for k in kinds if k != "old"], limit=args.limit)
    if "old" in kinds:
        items += old_records(args.corpus, limit=args.limit)
    print(f"{len(items)} records", file=sys.stderr)
    bad = 0
    chunk = args.chunk or len(items)
    for cfg in _configs(args.config):
        for start in range(0, len(items), chunk):
            part = items[start:start + chunk]
            chk = Checker(cfg, args.ref_level, args.orders.split(","), seed=start,
                          ref_check_every=args.ref_check_every,
                          max_discrepancies=args.max_discrepancies,
                          shrink_them=not args.no_shrink, source=f"corpus {args.corpus}[{start}:]",
                          progress=_progress(args.quiet), ignore_kinds=_ignore(args))
            rep = chk.run(part)
            _report(rep, f"corpus[{start}:{start + len(part)}]", args.out, args,
                    f"replay-{cfg.name}-{start}")
            bad += _failing(rep.discrepancies, args)
    return 1 if bad else 0


def cmd_refine(args) -> int:
    from .corpus import refine_stream
    bad = 0
    for cfg in _configs(args.config):
        for seed in _seeds(args.seeds):
            items = refine_stream(seed, args.exprs, **_opts_of(args))
            chk = Checker(cfg, args.ref_level, args.orders.split(","), seed=seed,
                          max_discrepancies=args.max_discrepancies,
                          shrink_them=not args.no_shrink, source=f"refine seed={seed}",
                          progress=_progress(args.quiet), ignore_kinds=_ignore(args))
            rep = chk.run(items)
            _report(rep, f"refine seed={seed} ({len(items)} queries)", args.out, args,
                    f"refine-{cfg.name}-s{seed}")
            bad += _failing(rep.discrepancies, args)
    return 1 if bad else 0


def cmd_audit(args) -> int:
    """Cache audit: run a stream, then check every cached fact against a
    fresh engine (``checker.audit_cache``); findings are shrunk, attributed
    and written like the other modes' discrepancies."""
    from .checker import attribute, audit_cache, shrink
    from .generators import random_stream
    bad = 0
    for profile in _profiles(args):
        for cfg in _configs(args.config):
            for seed in _seeds(args.seeds):
                items = random_stream(seed, args.queries, args.sets, **_opts_of(args, profile))
                src = f"audit profile={profile} seed={seed}"
                t0 = time.time()
                found, stats = audit_cache(items, cfg, source=src, progress=_progress(args.quiet),
                                           max_findings=args.max_discrepancies)
                for d in found:
                    if not args.no_shrink:
                        shrink(d, progress=_progress(args.quiet))
                        try:
                            attribute(d)
                        except Exception as e:  # noqa: BLE001
                            d.confirmations["attribute_error"] = str(e)
                print(json.dumps({"config": cfg.name, "source": src, "seconds": round(time.time() - t0, 1),
                                  **stats, "families": sorted({d.confirmations.get("family", "?") for d in found}),
                                  "discrepancies": [d.summary() for d in found]}), flush=True)
                for i, d in enumerate(found):
                    jp, pp = write_repro(d, args.out, f"audit-{profile}-{cfg.name}-s{seed}-{i}")
                    print(f"  discrepancy: {d.summary()}\n    repro: {pp}", file=sys.stderr, flush=True)
                bad += _failing(found, args, audit=True)
    return 1 if bad else 0


def cmd_hashseed(args) -> int:
    """The same stream in one fresh interpreter per PYTHONHASHSEED; every
    query's answer must agree across the seeds (and with the in-process
    reference of each run)."""
    from .generators import random_stream
    from .checker import order_stream
    bad = 0
    for cfg in _configs(args.config):
        for seed in _seeds(args.seeds):
            items = order_stream(random_stream(seed, args.queries, args.sets,
                                               **_opts_of(args, _profiles(args)[0])),
                                 args.order, seed)
            runs = {}
            for hs in _seeds(args.hashseeds):
                runs[hs] = run_in_process(items, cfg, hashseed=hs, ref_level=args.ref_level)
            base = next(iter(runs.values()))
            cross = []
            within = {hs: sum(1 for r in rows if r["ref"] is not None and r["warm"] != r["ref"])
                      for hs, rows in runs.items()}
            for i in range(len(base)):
                answers = {hs: rows[i]["warm"] for hs, rows in runs.items()}
                if len(set(answers.values())) > 1:
                    cross.append({"index": i, "item": str(items[base[i]["index"]]), "answers": answers})
            print(json.dumps({"config": cfg.name, "source": f"hashseed seed={seed}",
                              "queries": len(base), "hashseeds": list(runs),
                              "within_process_mismatches": within,
                              "cross_seed_disagreements": len(cross),
                              "examples": cross[:5]}), flush=True)
            # within-process mismatches are not shrunk or attributed here:
            # under --fail-on unknown only a cross-seed disagreement counts
            mode = args.fail_on
            bad += (0 if mode == "never" else len(cross) if mode == "unknown"
                    else len(cross) + sum(within.values()))
            if cross or any(within.values()):
                os.makedirs(args.out, exist_ok=True)
                write_stream(os.path.join(args.out, f"hashseed-{cfg.name}-s{seed}.json"), items,
                             {"config": cfg.to_dict(), "cross": cross, "within": within})
    return 1 if bad else 0


def cmd_repro(args) -> int:
    with open(args.file) as fh:
        d = json.load(fh)
    cfg = EngineConfig.from_dict(d["config"])
    items = [item_from_json(i) for i in d["prefix"]] + [item_from_json(d["item"])]
    if args.hashseed is not None and os.environ.get("PYTHONHASHSEED") != str(args.hashseed):
        rows = run_in_process(items, cfg, hashseed=args.hashseed, ref_level=ReferenceLevel.NONE)
        last = rows[-1]
        warm, ref = last["warm"], last["ref"]
    else:
        rows, _ = execute(items, cfg, ReferenceLevel.NONE, ref_for_last=True)
        warm, ref = rows[-1].warm, rows[-1].ref
    print(json.dumps({"file": args.file, "engine_after_prefix": warm, "fresh_engine": ref,
                      "recorded": [d["warm"], d["ref"]], "still_differs": warm != ref}))
    return 1 if warm != ref else 0


def cmd_exec(args) -> int:
    with open(args.file) as fh:
        d = json.load(fh)
    cfg = EngineConfig.from_dict(d["config"])
    items = [item_from_json(i) for i in d["items"]]
    rows, _ = execute(items, cfg, args.ref_level, ref_for_last=True)
    print(json.dumps([{"index": r.index, "warm": r.warm, "ref": r.ref} for r in rows]))
    return 0


def cmd_inventory(args) -> int:
    from .state import MODULE_INTERNED, import_all
    import_all()
    known = set(MODULE_STATE) | set(MODULE_CONSTANTS) | set(MODULE_CONFIG) | set(MODULE_INTERNED)
    unknown = []
    for mod, attr, tp in inventory():
        tag = ("state" if (mod, attr) in set(MODULE_STATE) else
               "constant" if (mod, attr) in MODULE_CONSTANTS else
               "config" if (mod, attr) in MODULE_CONFIG else
               "interned" if (mod, attr) in MODULE_INTERNED else "UNKNOWN")
        if tag == "UNKNOWN":
            unknown.append((mod, attr))
        print(f"{tag:9} {mod}.{attr} ({tp})")
    print(f"{len(unknown)} unclassified", file=sys.stderr)
    return 1 if unknown else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m harness", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("fuzz")
    p.add_argument("--seeds", default="0-3")
    p.add_argument("--queries", type=int, default=300)
    p.add_argument("--sets", type=int, default=6)
    _common(p)
    _gen_opts(p)
    p.set_defaults(fn=cmd_fuzz)

    p = sub.add_parser("hypo")
    p.add_argument("--examples", type=int, default=100)
    p.add_argument("--queries", type=int, default=40)
    p.add_argument("--sets", type=int, default=4)
    p.add_argument("--derandomize", action="store_true",
                   help="the same examples every run (no example database)")
    _common(p)
    _gen_opts(p)
    p.set_defaults(fn=cmd_hypo)

    p = sub.add_parser("replay")
    p.add_argument("corpus")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--kinds", default="ask,rec")
    p.add_argument("--chunk", type=int, default=0, help="split the corpus into streams of N")
    _common(p)
    p.set_defaults(fn=cmd_replay)

    p = sub.add_parser("refine")
    p.add_argument("--seeds", default="0-3")
    p.add_argument("--exprs", type=int, default=40)
    _common(p)
    _gen_opts(p)
    p.set_defaults(fn=cmd_refine)

    p = sub.add_parser("audit")
    p.add_argument("--seeds", default="0-3")
    p.add_argument("--queries", type=int, default=150)
    p.add_argument("--sets", type=int, default=4)
    _common(p)
    _gen_opts(p)
    p.set_defaults(fn=cmd_audit)

    p = sub.add_parser("hashseed")
    p.add_argument("--seeds", default="0-1")
    p.add_argument("--queries", type=int, default=200)
    p.add_argument("--sets", type=int, default=6)
    p.add_argument("--order", default="forward")
    _common(p)
    _gen_opts(p)
    p.set_defaults(fn=cmd_hashseed)

    p = sub.add_parser("repro")
    p.add_argument("file")
    p.add_argument("--hashseed", type=int)
    p.set_defaults(fn=cmd_repro)

    p = sub.add_parser("exec")
    p.add_argument("file")
    p.add_argument("--ref-level", type=int, default=1)
    p.set_defaults(fn=cmd_exec)

    p = sub.add_parser("inventory")
    p.set_defaults(fn=cmd_inventory)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
