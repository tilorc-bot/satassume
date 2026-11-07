# HANDOFF sa-port-108: 5c2a bar read; 5c2 bar, loop workload and 5c3 bar running; test_query_core.py done (issue 323)

Clone /home/tilo/dev/sa-port-7 (checked out on port/5c3). port/5c 7a14725 (pushed, unchanged). port/5c3 3ffccb1 = 3491f6b +
test_query_core.py; this handoff sits on top of it. rust-slice still d2d3234 at 23:30Z (6e not landed). port/5c is 10 ahead of
rust-slice and still a fast-forward, so a 5c2 landing adds only docs under port/5c3.

## Jobs (all detached on pareto1; read their files, don't wait in a shell; stop only by these PIDs)
- **5c2 bar** (sa-port-106's, tested 7adb61e): `~/sp19/sa-rust-ids-work/sa-port-106/`. At 23:28Z build/tests/suite/live/plants done
  (tests 438 passed), suiteplants running; sum.txt + done.txt at the end.
- **Loop workload** (mine, tested 7a14725): launched 23:29Z by orion `~/sa-rust-ids-work/sa-port-108/launch-loop.sh` (machine run
  PID 558763, log `loop-launch.log`). Its own tree `~/sp19/dev/sa-port-108-5c2`, phases `build extra sum`, WLS=loop, the 11
  `_LOOP_PLANTS`. OUT pareto1 `~/sp19/sa-rust-ids-work/sa-port-108/loop-5c2/` (extra/summary.txt, extra/plant-loop-*.cmp, sum.txt).
  drop-compile-demand must fire there and DIFFER (orion at 53adc14: 3,286 fired, DIFFER).
- **5c3 bar** (mine, tested 3ffccb1): launched 23:28Z by `launch-5c3.sh` (PID 557916, log `bar-5c3-launch.log`), tree
  `~/sp19/dev/sa-port-108`, the 12 `_QUERY_PLANTS`, WLS=loop, SUITE_PLANTS=zero, TESTS + test_query_core.py, BASE sa-port-99's
  rows. OUT `~/sp19/sa-rust-ids-work/sa-port-108/bar-5c3/`. Script: `~/sp19/bar-sa-port-108.sh` (bar.sh from 7a14725).

## 5c2a rerun, read (sa-port-103a/sum.txt, tested afcc6eb, base sa-port-99)
1. Suite: 5,959 passed, 125 failed, 23 skipped, 18 xfailed, 6,125 ids. New 0, gone 0, changed 0. Passed 5,958 with no firing,
   1 with a firing (test_ci_stream_reports_only_what_replays).
2. dev and fuzz: the four comparisons each MATCH, control MATCH. Answers dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6. 0 Python solvers on Rust.
3. Plants: drop-emit-ment, drop-flush-custom, drop-pat-demand, drop-split-later, want-empty DIFFER on dev and fuzz. **Void (fired 0
   on both): drop-compile-demand, drop-pend-compile.** Suite plants: drop-pend-compile fired 474 and changed 57 outcomes (182
   failed), so it's caught there. drop-compile-demand **fired in the suite (26,753) with 0 changed outcomes**: not caught by the
   suite. It's caught by test_compile_loop_core.py, and on the loop workload if that run DIFFERs.
4. Handlers: 39 rows in 2 tests, same multiset as base (`_consistent` 34 `_ok` + 4 `_rb_clauses`; `_build_context` "Already
   mutably borrowed" 1 in test_protocol_on_fuzz). **Quiet catches at engine.py:1906: 1** (that `_build_context` row), suite only;
   dev and fuzz handler files 0 rows (12), plant files 0 rows (14). TermFault 0.
5. Known differences: none. tests 434 passed, relations_direct exit 0. Not run: seed1.

## 5c3 so far
- test_query_core.py (3ffccb1): 13 cases. It needed an `AppliedUndef` (`f(x - y)`) for zero twins (`relations._under_apps`) and
  a forged aux `d` with `[-d, q]` to make `mention` change an answer (a block implication is written above root only for a
  mentioned variable, solver.py:1243). 14 passed on orion: matches Python, all 12 plants fire and each moves a case.
- Reach: fuzz's first 600 on orion reach all 9 moved methods (literal_of 393, _relations 1,130, ensure_twins 1,142, query_all 224).
  So no workload is needed for reach unless the full bar shows a 0. Plants likely void on dev/fuzz: ql-skip-consistent,
  drop-twins-var, drop-prep-twins (they need inconsistency that propagation misses, or an `AppliedUndef`). Read the bar.
- Formula callbacks (planner's 5c2 note): compile_loop.rs reads `.pred`/`.expr`/`.args` and calls `atoms_of`/`compile_formula`
  back (compile_loop.rs:152-391); query.rs reads `.pred`/`.expr` and calls `atoms_of`/`formula_literal`/`basis_lits`/
  `_glue_of` back (query.rs:6, 83-292). Kept as counted callbacks; the boundary conversion stays with the formula step.

## Next
1. Read the 5c2 bar's sum.txt and the loop's sum.txt/extra/summary.txt. State the five items.
2. Write results/port-5c2a.md and results/port-5c2.md (port-5c1.md's form) on port/5c. Check `git log origin/rust-slice`; if 6e
   landed, rebase and rerun the full bar with WLS=loop. Otherwise `PUSH=1 sh rust-spike/slice/p1/bar.sh land 7a14725`.
3. Rebase port/5c3 on it (docs only, so no rerun), read bar-5c3/sum.txt, write results/port-5c3.md, land.
Moved methods, 5c2: want_of, _split, _emit_pattern, _flush, _compile, _compile_pending, _compile_patterns (5c2a); _custom,
_visit, core visit, Session._link (5c2b). Plants: want-empty, drop-split-later, drop-emit-ment, drop-flush-custom,
drop-compile-demand, drop-pend-compile, drop-pat-demand; drop-custom-rel, drop-custom-facts, drop-visit-items, drop-dv-link.
Still owed in every report: see the brief's MUST STAY list (S's standing, _n_conflicts shim 64 tests, test_incremental_matches_fresh
at the test-only step before 5c7, test_equality_sharing re-pointed at 5c4 via skip-share; no module newly counts whole).

## 5c2 bar, finished (sa-port-106/sum.txt, tested 7adb61e; grep only, read sum.txt yourself)
tests 438 passed, direct exit 0. Suite 5,959/125/23/18, new/gone/changed 0, passed 5,958 + 1 firing, handler multiset same as
base (39). dev and fuzz: 8 MATCH. Plants DIFFER on dev and fuzz: drop-custom-rel, drop-emit-ment, drop-flush-custom,
drop-pat-demand, drop-split-later, want-empty. **Void on both (fired 0):** drop-compile-demand, drop-custom-facts, drop-dv-link,
drop-pend-compile, drop-visit-items. In the suite, each fired: drop-custom-facts 316 (11 changed), drop-dv-link 1,528,434
(25 changed), drop-pend-compile 474 (57), drop-visit-items 459 (58), drop-compile-demand 26,753 (**0 changed**: only the
direct test and the loop workload). Not run: seed1. Still to grep: quiet catches at engine.py:1906 in this run.
