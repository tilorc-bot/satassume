# HANDOFF sa-port-103: 5c2 ported whole on port/5c; the 5c2a rerun is running (issue 323)

port/5c at 53adc14 (pushed), rebased on rust-slice d2d3234 (wiring, sa-port-99, landed). Clone /home/tilo/dev/sa-port-7.

## 5c2a (first part, sa-port-100's): first bar read, rerun running
- sa-port-100's bar (tested 3246bb4, base sa-port-96, pareto1 `~/sp19/sa-rust-ids-work/sa-port-100/sum.txt`) held: suite 5,959 passed / 125 failed / 23 skipped / 18 xfailed, 6,125 ids. New 0, gone 0, changed outcome 0. Passed: 5,958 with no firing, 1 with a firing (`test_ci_stream_reports_only_what_replays`). Handler multiset same as base (34 `_ok` + 4 `_rb_clauses` in `_consistent`, 1 `_build_context` "Already mutably borrowed"). Dev and fuzz: all 8 comparisons MATCH, shas dev 31cd0945c07f02a6 and fuzz 173502b6ef285ad6. Tests 428 passed. Not run: seed1.
- Plants: 5 DIFFER on dev and fuzz. **Void on the workloads (fired 0): drop-compile-demand and drop-pend-compile.** On the suite, drop-pend-compile changed 57 outcomes (caught). drop-compile-demand changed none, and that run didn't record whether it fired, so it's caught only by test_compile_loop_core.py's plant test. Per the gaps ruling, `_compile`'s demand path counts as **not reached** until a workload makes it fire. The suite-plant run now records firing (plant_count.py, afcc6eb), so the rerun answers it.
- The rebase brought the wiring step (knowledge_live.py, live.py, rust_plugin.py), which is code the runs execute, so the full rerun is required. **Running:** launched 22:54Z from orion (`~/sa-rust-ids-work/sa-port-103/launch-a.sh`, launcher PID 534666, log `~/sa-rust-ids-work/sa-port-103/bar-a-launch.log`). Tested source afcc6eb; rows at pareto1 `~/sp19/sa-rust-ids-work/sa-port-103a/` (sum.txt, done.txt). BASE is sa-port-99's suite rows. PLANTS are the 7, SUITE_PLANTS=zero, TESTS add test_knowledge_wire.py, DIRECT "relations_direct.py 300 0". It was in the live phase at 22:59Z, about 20 minutes in all.
- Quiet catches at engine.py:1906 (`complete_check`, the `_build_context` row): 1 in the suite, as on base; 0 on dev and fuzz.

## 5c2 second part: done, committed in 53adc14, bar not run
- compile_loop.rs: `custom` (`_custom`), `visit` (`_visit`), `core_visit` (session_live `_core_visit`'s census and `engine._constructing`, now Rust; session.rs `visit_id` calls it). `Session._link` was already Rust (session.rs `link`, 5a; the engine's calls come from Rust var/dvar). It is now exposed as `link_py` and put on the class. `core_visit` and `_flush` call `_visit` and `_custom` **by name**, as Python does: the class methods are the Rust wrappers, and an instance override is honoured (test_session_limits.py `_object_case` patches `s._visit`; it failed with a direct call).
- Counters ses:custom, ses:visit, ses:core_visit, ses:link (session.rs NAMES, now 69). Plants 45-48: drop-custom-rel, drop-custom-facts, drop-visit-items, drop-dv-link (relations_core.rs; `_LOOP_PLANTS`).
- test_compile_loop_core.py adds custom:rel:* (no Relations, then made and counted in scope_misses; assumption formula noted), custom:facts:name, custom:no-ext, link:* (forged defs by name, derived preds via compile), and visit:/visit-mine:/visit-own:* through `Session.node` (node facts, parked under a demand, constants). All match Python. All 11 plants fire and move a case. On orion the bar's TESTS (+ test_knowledge_wire.py) gave **438 passed**.
- Offline tool tools-rust/coarse.py patches `Session._custom` at class level. It's offline and not ported, and the by-name call still honours it.

## Next
1. Read pareto1 `~/sp19/sa-rust-ids-work/sa-port-103a/sum.txt` (the head, then the suite-plants tail by rg; never pipe a detached launcher into tail/head). State the five items. If the bar holds, land 5c2a: `git log origin/rust-slice` first (sa-port-98's 6e may land), then `bar.sh land afcc6eb` (PUSH=1) from a branch at afcc6eb, **not** port/5c's head 53adc14. Or skip the separate 5c2a landing, run the 5c2 bar on 53adc14 and land both as 5c2 with port-5c2a.md + port-5c2.md. That's simpler: one landing.
2. 5c2 bar on 53adc14: `scp rust-spike/slice/p1/bar.sh pareto1:sp19/bar-NAME.sh`, then as in launch-a.sh with OUT=.../NAME, PLANTS = the 11, SUITE_PLANTS=zero, same TESTS, and BASE = the last landing's suite rows. Write results/port-5c2.md in port-5c1.md's form. Name which methods are reached and by which workload (gaps ruling). drop-custom-facts will likely fire 0 on dev and fuzz, since no extension facts are registered there. It's caught by the direct test; check the suite-plant firing count.
3. Then 5c3 per HANDOFF-sa-port-93.md's split table.

## Map
- compile_loop.rs: want_of, split, emit_pattern, flush, compile, compile_pending, compile_patterns, custom, visit, core_visit; ses_* pyfunctions; register.
- session.rs: `link` (+ DROP_DV_LINK, SES_LINK), `link_py`, `visit_id` → `compile_loop::core_visit`.
- session_live.py: `_ses_custom`, `_ses_visit`, `_ses_link`, `_LOOP_METHODS`, `_LOOP_PLANTS`, `_install_compile_loop`; `_core_visit` removed.
- plant_count.py (new; `-p plant_count` in bar.sh's suite runs) → counts.PID.json; bar_sum.py prints "plant fired in the suite".
- engine.py: `_link` :481, `_visit` :572, `_custom` :707.
