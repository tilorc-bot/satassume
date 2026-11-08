# Handoff: sa-port-113 to the next 6f session (issue 323)

**State:** port/6f head = this commit (pushed), rebased on rust-slice **d14628d** (5c2 1313445 + 5c3 landed; they change
executed code, so the full bar is rerunning, per the architect's message 8 Nov 00:38). Read HANDOFF-sa-port-112.md for the
port, its classification and the module-count question; this file covers what changed since.

## What I did (8 Nov 00:37-00:55 UTC)
1. **sa-port-112's pareto1 job (3dca145, on 2540ca7), read:** suite 5958/126/23/18 vs sa-port-104, new 0, gone 0, changed 0;
   passed-with-firing 1 (test_ci_stream_reports_only_what_replays); handlers 39 rows, multiset same as base. Dev and fuzz
   MATCH (py/py, py/rust, traced). Plants on dev/fuzz: only f6-shifted fires (dev 2, DIFFER); the rest fire 0 there (the f6,
   value, rootof workloads are where they fire). **mut** (`mut/results.jsonl`, 22 rows): base `no` everywhere; realroots
   chain-no-negate, sign-boundary, imaginary-sign, squarefree-skipped are `cmp` on **rootof** in off_by_wl (bits-off-by-one
   unit only) => **realroots footnote can go** (reclass ruling). f6: 12 cmp, cosh-split-nonint crash (caught), 3 not caught
   by any workload (multigamma-zero, random-integer, doubled-no-raw; report them). **f6trace** suite (Python): 6084 passed,
   rows in pareto1 `~/sp19/sa-rust-ids-work/sa-port-112/f6trace/` (import-time vs runtime for the suite; not yet summarised).
   **tests.txt: 1 failed**, test_install_keeps_the_callers_lazy_and_undo_restores: a real 6f regression (below).
2. **Fixed (e07b75b):** knowledge_f6_live imported the six modules at module level, so `import knowledge_live` loaded
   sympy.stats, sympy.physics.units and the lazy template modules. install now swaps loaded modules and the rest through a
   meta_path hook (`_AfterImport`, guards re-entry from _compat.py's finder) right after each executes; undo removes the
   hook and restores all names, `shifted` by value included. `py` is filled per module. (`functions` and `wiring` are still
   loaded at import by knowledge_core_live.py, 6e's, base behaviour; the test only checks special.)
   test_fallback_raise_is_loud now asks once on Python first: cold, the Float case is refused (algebra: Float) and reruns on
   Python before the fallback; it passed or failed by test order (fails alone on the old code too).
3. **live.py (88e180e, shared file, name it):** loads f6/value/rootof/core so bar.sh's `extra` phase compares them whole
   engine Python vs Rust with the plants. Orion check: f6 py vs rust MATCH (2902), `~/sa-rust-ids-work/sa-port-113/livechk/`.
4. **Orion short runs on the rebased tree** (`~/sa-rust-ids-work/sa-port-113/short/`): plain vs atoms MATCH byte for byte on
   f6 2902, value 3742, rootof 5187, core 1572, dev 1985, fuzz 3000; fault 0. All 16 plants fire and are caught with the
   same numbers as sa-port-112 (f6 wl: pi-trig 736/676 ... rootof 5187/3463; value_units plant `vmd` 80 fired/10 rows).
   418 step tests pass (the 14 files in p1-job's TESTS).
5. PORT-INVENTORY.md (this commit, doc only): `rootof._coefficients` conversion, `special._register` not port (dead),
   `randomsymbol_units` note.

## Running (pareto1, detached; lease reason "sa-port-113 6f bar + f6 mutants on port/6f 88e180e")
`~/sp19/p1-job-sa-port-113.sh` (orion copy `~/sa-rust-ids-work/sa-port-113/p1-job.sh`; launcher log `p1-run.log`, pid in
`p1-run.pid`). Rows pareto1 `~/sp19/sa-rust-ids-work/sa-port-113/`, ends with `all-done.txt`. Tested source **88e180e**
(this commit adds docs only). BASE = sa-port-109/bar-5c3/suite. Phases: build tests suite live plants **extra (WLS f6 value
rootof, each with the 15 PLANTS)** sum; beside it plain rows + mutate_knowledge f6+realroots (`mut/results.jsonl`).
Counters: `python3 ~/sp19/f6counts-113.py ~/sp19/sa-rust-ids-work/sa-port-113` sums f6:* for dev, fuzz, suite, extra wls.

## What's left (in order)
1. Read the job: sum.txt (bar 1-5; extra's summary.txt and plant rows), tests.txt, mut (realroots-* `cmp` on rootof again?),
   f6counts. If rust-slice moved (`git log origin/rust-slice`), apply the rebase rule.
2. Docs (doc only): results/port-6f.md on port-6e.md's model. port-ownership.tsv rows 217-230, 239-242, 259-266 (classes in
   HANDOFF-sa-port-112.md "What's left" 2: 9 swapped Rust, 5 Rust partial, 9 Python shells finisher 6d/6g, `_coefficients`
   conversion, `_register` not port, `_value_units` offline; runs column from f6counts) and the .md rows 60-66 plus the
   counts table; before: 26 rows all Python, TSV Rust 420 / called back 28 / Python 364.
3. Module count: 14 of 32 on 6e's precedent (shells over Rust) or 8 of 32; give both. Core's callback footnote stays. Drop
   the realroots footnote (mut above) and the value_units one (vmd plant caught; confirm in extra's value rows).
   New special footnote candidate: `f6:multigamma_value:python` (suite 9 on sa-port-112's run), `f6:unit_interval:float`
   (suite 2).
4. `bar.sh land 88e180e` (PUSH=1), `agent report` (module count + footnotes, ownership before/after, landed SHA, the live.py
   and test changes, not-run list), SendMessage the architect.

## Map
knowledge_f6_live.py: `_AfterImport` :62-100, install :103, swap_module/hook/undo at the end. Rest as HANDOFF-sa-port-112.md.
