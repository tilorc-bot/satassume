# Step 5c2: Session's compile loop in Rust, carrying 5c2a (issue 323)

## What moved
- **5c2a** (results/port-5c2a.md): `want_of`, `_split` (engine.py:2311-2350), and `Session._emit_pattern`, `_flush`, `_compile`, `_compile_pending`, `_compile_patterns` (engine.py:614-771).
- **5c2b:** `Session._custom` (:707-733), `_visit` (:572-613), the core visit (session_live `_core_visit`'s census and `engine._constructing`, now `compile_loop::core_visit`, called from session.rs `visit_id`), and `Session._link` (:481-505). `_link` was already Rust from 5a (session.rs `link`), and it's now also on the class as `link_py`.

All of it is in `solver_rs/src/compile_loop.rs` (516 lines). It's wrapped by `session_live.py` `_LOOP_METHODS`, and `SLICE_LOOP=py` keeps Python's. `core_visit` and `_flush` call `_visit` and `_custom` by name, so instance and class patches are still honoured (test_session_limits.py:241 and :266, and the offline tools-rust/coarse.py:143). Counters: `ses:want_of` .. `ses:link` (session.rs NAMES).

No module newly counts whole: relations.py at 5c5, Session at 5c6, engine.py at 5c10. **Formula callbacks:** compile_loop.rs reads `.pred`/`.expr`/`.args` and calls `atoms_of`/`compile_formula` back. These stay counted callbacks; the boundary conversion stays with the formula step after 5c (planner's 5c2 note).

## SHAs
Tested 26460b5: port/5c rebased on rust-slice 2540ca7 (6e). 6e changes code the default Rust path runs (knowledge_live.py, term/tcore.rs), so the full bar was rerun with WLS=loop. Rows are on pareto1 at `~/sp19/sa-rust-ids-work/sa-port-109/bar-5c2/` (`sum.txt`, `commands.txt`), `.so` sha256 f178a3d7…, base 6e's suite rows (sa-port-104). The earlier runs before 6e (sa-port-106, tested 7adb61e; loop sa-port-108, tested 7a14725; base sa-port-99) gave the same numbers. Landed: see the report; the commits after 26460b5 are these two results files only.

## The bar (sa-port-109/bar-5c2)
1. **Suite by id against 6e's rows:** 5,958 passed, 126 failed, 23 skipped, 18 xfailed, 6,125 ids. New 0, gone 0, changed outcome 0. Passed: 5,957 with no firing, 1 with a firing (`test_ci_stream_reports_only_what_replays`). The 126th failure is 6e's `test_comparison_detects_a_wrong_row` (needs internals; see port-6e.md). S's standing: its gate is met except for the 46 named stub failures, one cause. `test_equality_sharing_is_needed_and_works` stays failing and unedited.
2. **Fresh dev, fuzz and loop:** answers and state MATCH. Dev and fuzz each have four comparisons, and loop has Python against Rust; every control MATCHes. Answers: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6, loop 09238b2537e54383, the same as before 6e. Rust runs made 0 Python solvers.
3. **Plants:** below. Each moved method has a plant that a workload catches.
4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as base: `_consistent` AttributeError 34 `_ok` + 4 `_rb_clauses` (named needs-internals case), and `Engine._build_context` "Already mutably borrowed" 1 in `test_protocol_on_fuzz` (the 46-stub cause). `caught` rows per id are the same as base. **Quiet catches at engine.py:1906: 1**, in the suite, as on base. 0 on dev, fuzz and loop: the 13 handler files have 0 rows, and so do 22 plant files. TermFault 0, here and in all 5 suite-plant runs.
5. **Known differences in answers or read state:** none. Tests: 459 passed (the 5c TESTS + 6e's three); `relations_direct.py` exit 0.

## Plants (fired; caught by)
| plant | method | dev | fuzz | loop | suite (fired / changed) |
|---|---|--:|--:|--:|---|
| want-empty | want_of | 5,348 D | 51,089 D | 3,666 D | |
| drop-split-later | _split | 291 D | 455 D | 86 D | |
| drop-emit-ment | _emit_pattern | 3,346 D | 33,238 D | 2,802 D | |
| drop-flush-custom | _flush | 506 D | 10,086 D | 0 | |
| drop-pat-demand | _compile_patterns | 2,119 D | 18,498 D | 1,732 D | |
| drop-pend-compile | _compile_pending | 0 | 0 | 452 D | 474 / 57 |
| drop-compile-demand | _compile | 0 | 0 | 3,286 D | 26,753 / **0** |
| drop-custom-rel | _custom | 1,187 D | 21,333 D | 0 | |
| drop-custom-facts | _custom | 0 | 0 | 0 | 316 / 11 |
| drop-visit-items | _visit, core visit | 0 | 0 | 760 D | 459 / 58 |
| drop-dv-link | _link | 0 | 0 | 0 | 1,528,440 / 25 |

D = DIFFER. Suite plants ran for the five that fired 0 on dev and fuzz.

**Void (fired 0, so the MATCH means nothing):**
- On dev and fuzz: drop-compile-demand, drop-pend-compile, drop-visit-items, drop-custom-facts and drop-dv-link.
- On loop: drop-flush-custom, drop-custom-rel, drop-custom-facts and drop-dv-link.

What catches them instead:
- drop-compile-demand, drop-pend-compile and drop-visit-items: the loop workload.
- drop-custom-facts and drop-dv-link: the suite (11 and 25 changed outcomes).
- All 11: `test_compile_loop_core.py` (each fires and moves a case).

drop-compile-demand fires in the suite but changes no outcome. So by the gaps ruling, the loop workload (`loop_wl.py`, `live.py loop`, 420 queries, four vocabulary functions true of SymPy's meaning, in the repo) is what makes `_compile`'s demand path count as reached. It fires there 3,286 times and DIFFERs (end state and stream).

## Reached (ses: counters; dev / fuzz / loop / suite)
| method | dev | fuzz | loop | suite |
|---|--:|--:|--:|--:|
| want_of | 5,257 | 51,089 | 3,766 | 2,128,540 |
| _split | 8,127 | 79,164 | 5,713 | 2,914,144 |
| _emit_pattern | 3,298 | 33,176 | 2,798 | 1,219,323 |
| _flush | 3,259 | 58,720 | 1,403 | 559,730 |
| _compile | **0** | **0** | 1,159 | 991 |
| _compile_pending | 597 | 18,059 | 598 | 193,243 |
| _compile_patterns | 2,461 | 16,537 | 2,284 | 985,209 |
| _custom | 1,507 | 36,397 | 0 | 349,896 |
| _visit | 2,482 | 16,537 | 2,284 | 1,000,169 |
| core visit | 2,482 | 16,537 | 2,284 | 1,000,169 |
| _link | 2,299 | 5,525 | 560 | 902,158 |

Every method is reached by dev or fuzz except `_compile`, which only loop and the suite reach. The direct test reaches all 11.

## Direct test
`test_compile_loop_core.py` runs forged state, Python against Rust in separate processes. Cases cover want/split, patterns under a demand, `_flush` with custom atoms, `_compile` with vocabulary formulas mentioning another node's atom, `_compile_pending`, `custom:rel:*`, `custom:facts:name`, `custom:no-ext`, `link:*`, and `visit:`/`visit-mine:`/`visit-own:*`. Everything matches Python, and all 11 plants fire and move a case.

## Not run
Moved to "before any backend PR", none quoted as met:
- the mutant 2, 5, 6, 7, 9 rerun and mutlive's control;
- the boundary rescore and suite column;
- the final drop score and its lost rows;
- the suite split with Python's counter;
- `order:_rows`' evidence (not caught meanwhile);
- the `_forms` guard test;
- history and seed reruns (seed1 not run);
- forced moves;
- the native path;
- timing.

Other notes:
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- The public-API `test_incremental_matches_fresh` family is still owed. Planner's go: a test-only step before 5c7 (pure Python first, adds only, a Python failure is a finding against main).
- `test_equality_sharing_is_needed_and_works` gets re-pointed at 5c4, through `_share`: a `skip-share` plant plus a test in test_relations_core.py; the Python test stays unedited. 5c2 doesn't touch `_share`.
