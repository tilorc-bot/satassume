# HANDOFF sa-port-358 (20 Nov, ~10:25Z): item 3 (the port of convert.py) finished; items 4, 5, 6 not started

Branch port/measured-next, source commit b580119 (parent 7c376cc; this file is the commit after it), from rust-slice
de88d9b9. Pushed to the clone's origin. Worktree ~/sa-rust-ids-work/sa-port-356/wt in clone ~/dev/sa-port-5.
Nothing is landed. No lease is held. No job is running. No x86-64 .so of this tree exists; nothing ran on a pareto.
orion's .so of b580119: rust-spike/slice/sa_solver.so, aarch64, 4d8921d9c510e99f (untracked).
Write-up: rust-spike/slice/results/measured-next.md (3). Tools and row summary: results/tools358/ (rows358.txt).

## What 358 did
1. The hang in 357's job: `test_convert_walk.py::test_a_deep_formula_is_pythons[700-too-deep]` under run_suite.sh.
   Not this tree: CPython 3.12.14 never returns from a RecursionError raised by a call from a generator-expression
   frame at the recursion limit while a sys.monitoring EXCEPTION_HANDLED callback is registered (handler_count.py has
   one). tools358/repro.py: 14 lines, no satassume. Python's walker on de88d9b9 does the same (tools358/deep.py,
   deep-first.txt). Standalone and in the bar's tests phase (plain pytest, p1/one_test.sh) the test passes.
   Wherever test_convert_walk.py runs with `-p handler_count`: `--deselect` that id, or run it alone under `timeout`
   (tools358/passes.sh does both). No in-process timeout stops it. The test was not edited.
2. The replaced-definition guard, completed (it left 2 ids failing only on the Rust walker, after 12 before the guard):
   off items are called by name (walk.rs:452-482, :877, :919); `Walk.raised` and weak references (walk.rs:315, :1382).
3. Kept tests: 100/101-deep formula with counts and raised against Python's walker (equal; nothing reset);
   replaced `_structural_class` / `_template_name`; test_plant_773_is_caught.
4. Runs, orion only (output ~/sa-rust-ids-work/sa-port-358; `tools358/readrows.sh` prints the comparison):
   test_convert_walk.py standalone 34 passed; the six kept files under run_suite.sh: py 10 failed + 5 errors, rust the
   same 15 ids, 0 only on rust; de88d9b9's Rust walker 18 failed + 5 errors, 8 ids of test_lazy_reads.py that the head
   passes. Plants 768-773 as rows over the six files: each has ids failing only under it (10, 3, 39, 11, 4, 11).
   The k-*.so.txt files say tree 7c376cc0: that was HEAD with b580119's changes uncommitted; the source is b580119's.

## Not done (359)
4. Gate: per query on dev, fuzz 424242, seeds 0/1/2/42 and the 20 workloads: answers, Engine.stats, moved ids and
   counts/raised, Python's walker against SLICE_CONVERT=rust at the head; iv; suite by id. Counters 743, 744, 745, 746
   per workload with a reason (each fires in a kept test, measured-next.md (3)). Needs the x86-64 .so: build on pareto1
   (tools327/build327.sh's docker line; goprof356.sh's tree check must change, HANDOFF-sa-port-356.md map).
5. S1, 12 rounds, Rust at the head against Rust at de88d9b9, quiet lease on pareto1.
6. Bar with the rows of tools358/rows358.sh (CPP358 for PLANTS/SUITE_PLANTS, CONVERT_PLANTS358 for the convdiff phase),
   bar.sh land, guard, PUSH=1, rule [91]. The probe count against 21 of 32.
Not checked by 358, so say so or check: R5 (term_discard.py) with the new items; the quiet-handler counter firing
(0 rows in the six-file passes is not evidence); lazy_reads.py's rows under plant 773 on workloads.

## Rows to know
- 15 ids fail alike on py, rust and de88d9b9 when the six kept files run under `-p rust_plugin -p handler_count`
  (also file by file): 5 errors test_knowledge_lazy.py, 6 failed test_term_ids.py, 4 failed test_term_live.py; by id in
  tools358/rows358.txt. Not diagnosed; the bar runs these files plain.
- run_suite.sh's own exit status is `cat`'s: read exit.txt. A detached script has no `rg` (it is a shell function
  here): use grep. `comm` needs LC_ALL=C on both sides.
- ~/sa-rust-ids-work/sa-port-357/base (worktree of clone -5 at de88d9b9, its aarch64 .so built) is still there for
  comparisons; `git worktree remove` it when no step needs it.

## Open points for the report (the planner ruled on the first four for 358; they stay in every report)
- `formula` past 100 connectives goes to Python's from the top (743), read twice; counts/raised equal (kept test).
- `convert`'s first lines stay Python as the dispatch on WALK[0].
- `_read_own_base`'s Mul(2, t) stays Python (745): the reference's existing construction, under "still Python".
- the `read` item is off for every query under lazy_reads.py (746), P1.
- New with 358: `sa_solver.Walk` gained `raised` and weak references because kept tests read them off
  `tables['reads'].__self__`; no other attribute of `_Walk` is on it (term_shadow.py:719 reads `.raised` too).
- New with 358: the [700-too-deep] case can't run under handler_count; whether it stays as it is (deselected in such
  jobs) or is skipped when an EXCEPTION_HANDLED tool is registered is not ruled.

## File:line map
- rust-spike/slice/convert.py (unchanged by 358): RUST_ITEMS :394, rust_walk :400, _walk_class :450, use_rust :457,
  WALK_PLANTS :465, from_env :470, default_engine_settings :502, formula :523 (the generator expression :551),
  convert :557, _ORIGINAL :606.
- rust-spike/slice/solver_rs/src/term/walk.rs: DEPTH :45, counters :48-:85, plants :115-:126, WalkCtx :140, Walk :315,
  W.owner :412, the by-name dispatch :452-:482, template_name :877, structural_class :919, power_rows_native :935,
  read_value :968, read_native :1028, rel_parts :1076, formula :1091, replaced :1170, formula_top :1186,
  engine_settings :1202, WalkEntry :1237 and its __call__ :1249, Walk.raised :1382, Walk::bare :1391, fresh :1411.
- rust-spike/slice/test_convert_walk.py: ALL_PLANTS :37, PLANTS :43, nested :213, counted :222, the entry and its
  counters :229, the deep formula :264, template names :283, replaced definitions :326 (replaced_checks :333),
  run :387, test_plant_is_caught :403, test_plant_773_is_caught :411, the script mode after it.
- Kept tests that replace `_Walk` methods or read the walker: test_lazy_reads.py:116-122, :313-320, :343, :388;
  test_term_live.py:296, :313; lazy_reads.py:134-142; term_shadow.py:719.
- The bar: p1/bar.sh penv :102 (`convert:NAME`), tests phase :168-:178 (plain pytest), convdiff :228-:236;
  p1/convert_diff.sh; a bar job to copy: results/tools347/job347bar.sh.
- results/tools358: passes.sh (the three passes, detached, end marker passes-end.txt), plantrows.sh, readrows.sh,
  onebyone.sh, deep.py, deep2.py, repro.py, rows358.sh, rows358.txt.
- Everything else: HANDOFF-sa-port-357.md, then HANDOFF-sa-port-356.md "File:line map". Plants from 774, counters from 747.
