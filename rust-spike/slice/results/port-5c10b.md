# Step 5c10b: context sessions and verdicts in Rust; `_failed`, `_verdict`, `_context_sessions` Rust-native (issue 323)

## What moved
Inventory part 5's 5c10b row (sa-port-147, INVENTORY-state.md :288-290): containers `_context_sessions`, `_failed`, `_verdict`,
Session.solver and Session.xfer handles, Session.truncated; rows `_context_session`, `_build_context_memoized`,
`_build_context`, `verdict`, `_complete_check` (engine.py :1835-1983); the quiet catch at engine.py:1906 is part of this bar.
Work by sa-port-184 (27873ac); bar, ownership rows and landing by sa-port-186.
- **The five rows run in context.rs**, step for step as engine.py:1835-1983: the epoch test and `_check_version`, the memo of
  `INCONSISTENT`, `_failed`'s bound 10,000 and `_verdict`'s 20,000 (emptied when full, as Python), the complete check, its
  fallback to a plain session, `link_set`. session_live `_install_context` (:824, installed at :1071; `SLICE_CONTEXT=py` is
  the control) binds thin Python wrappers over `sa_solver.ctx_*`. Calls among the five are direct Rust calls unless a patch
  replaced the class attribute (catch_count, `mock.patch.object`): the patch is then called by name, counted `ctx:cb_patched`.
- **engine.py:1906's handler is in `build_context`** (context.rs :169-218): an `Exception` from the complete check becomes a
  plain session as in Python, counted `ctx:caught`, with a row to handler_count under Python's site name
  `Engine._build_context` (handler_count.py :44-49 takes Python's code object from `session_live.PY_CONTEXT`).
- **Moved to Rust-native state:** `_failed`, `_verdict`, `_context_sessions` are engmemo.rs slots 5-7, with 5c9c's
  `EngineMemo` view at the same Engine attributes (`native`, `moved`; `_Mark` skips them; the registry digest counts them).
- **Kept Python, by the state rule:** Session.solver, Session.xfer, Session.truncated (below, "State").
- **Callbacks into Python left, counted, each removed by 5c10d:** `_check_version` (`ctx:cb_check_version`), `_fresh_session`
  (`ctx:cb_fresh_session`), `_gave_up`/`_exhausted`/`_noncommutative_atoms` (`ctx:cb_helpers`), the `stats["set_checks"]`
  write (`ctx:py_stats`). Python's `_drop_set_memos` (engine.py :1590-1600) clears the three through the view (5c10d).
- **Counters** (session.rs :350-372): 271-287 (NAMES is 288). **Plants** (relations_core.rs :288-310): 211-222,
  `_CTX_PLANTS` in session_live.py.
- **New test:** test_context_core.py, Python against Rust in separate processes: 12 passed, 3 skipped (plants void there:
  214, 216, 217; VOID_HERE names why).
- **memo_check.py** records the three in `em_sizes`/`em_content`/`em_order` and checks their views against `em_snapshot`.

## SHAs
**Tested: 27873ac** (port/5c10b on rust-slice 67d108d), all bar phases but seed1. Rows on pareto1:
`~/sp19/sa-rust-ids-work/sa-port-186/bar-5c10b/` (end marker `done.txt`; summary copied to `~/sa-rust-ids-work/sa-port-186/bar/`);
`.so` sha256 2d9f6109…. Base suite rows: 5c10a's (`sa-port-182/bar-5c10a/suite`).
**Landed:** the commit carrying this file, on rust-slice, rebased on 67d108d (unchanged since the bar started). **Incoming
diff: none** (67d108d..67d108d). Between 27873ac and the landed commit there is only this report and port-ownership.md/.tsv
(results/); the landing guard saw no source difference.

## The bar (sa-port-186/bar-5c10b on 27873ac)
1. **Suite by id against 5c10a's rows:** 5,991 passed, 127 failed, 23 skipped, 18 xfailed, 6,159 ids. New 0, gone 0,
   **changed outcome 0.** Passed splits as 5,990 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`).
   `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` failed, as on base: the
   known id()-reuse test artifact (sa-port-185, report a28c548; 50 of 50 fail under Rust at 67d108d), unedited. Under plant 211
   it passed: the same id()-reuse luck, not the plant.
   S's standing: S's gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz, plus loop, zero, cert and scope:** answers and state MATCH, and every control MATCHes. Answers
   unchanged: dev 31cd0945c07f02a6 (1,985 q), fuzz 173502b6ef285ad6 (3,000 q), loop 09238b2537e54383 (420 q), zero
   d9ed3534a2093027 (854 q), cert 6a09c059eb266747 (61 q), scope 12e06b0586faee40 (169 q), all equal to 5c10a's. The Rust runs
   made 0 Python solvers, reentry 0. The snapshot digest is equal at the switch on all six (below).
3. **Plants:** 11 of 12 caught (table below), counting the bar's live comparison, the suite, memo_check and
   test_context_core.py. **The inventory's planted bug, 211 (`_verdict` kept across a settings change), is caught by the
   suite in 6 tests**, among them `test_set_verdict.py::test_setting_change_drops_the_verdict_memo`. **Void: 214**
   (`_verdict` never emptied at 20,000): no workload, test or suite case has 20,000 distinct sets on one engine.
4. **Quiet handlers in the suite:** 39 rows in 2 tests, the same multiset as 5c10a's:
   - `_consistent` AttributeError: 34 on `_ok` and 4 on `_rb_clauses` (the named needs-internals case);
   - `Engine._build_context` "Already mutably borrowed": 1, in `test_protocol_on_fuzz` (the 46-stub cause).

   **engine.py:1906's catches, now `ctx:caught` in context.rs:** 1 in the suite (that row), 0 on all six workloads unplanted;
   shown to fire under plant 221 (dev 833, fuzz 2,980; the bar's plant handler files have those rows). The `caught` rows per
   id match base (0 ids differ). TermFault 0. The 12 live handler files and the extra-workload handler files have 0 rows, and so
   do 22 of the 24 plant handler files (the other two are 221's). The 4 suite-plant runs give the same 39-row multiset.
5. **Known differences in answers or read state:** none. Tests: 616 passed, 3 skipped (5c10a's 17 files plus
   test_context_core.py; the skips are its 3 plants void there). `relations_direct.py` exited 0.

## Plants
Fired = `rel:plant_fired`. Caught by: L = the bar's live comparison (answers and state; dev, fuzz and extra on loop, zero,
cert, scope), M = memo_check against the unplanted 5c10b run (S registry digest, E memo sizes/contents/order, C not empty
after clear), U = the suite (SUITE_PLANTS=`zero`: the four that fired 0 in live.py on dev and fuzz), T = test_context_core.py.
Counts per workload are memo_check's (dev / fuzz / loop / zero / cert / scope). Rows: `~/sa-rust-ids-work/sa-port-186/mc/pl-*`,
`mc/plants-table.txt`; the bar's `bar-5c10b/{live,extra,suite-ctx-*}`.

| plant | row | fired | caught by |
|---|---|---|---|
| ctx-verdict-clear-skip (211, **the inventory's planted bug: `_verdict` kept across a settings change**) | the view's `clear` | 1 each (memo_check's clear); 0 in live.py | **U: 6 tests** (`test_set_verdict.py::test_setting_change_drops_the_verdict_memo`, `::test_verdict_keeps_no_session`, `test_invariant_repros.py::test_k3_setting_change_after_queries`, `test_registry_versioning.py::test_setting_change_after_queries_answers_as_fresh[uninterpreted]`, `::test_splits_are_keyed_on_the_registry`, `test_memos.py::test_two_engines_do_not_share_memos`), M (C on all six), T |
| ctx-failed-clear-skip (212) | `_failed`'s clear | 1 each (on an empty map) | U (`test_memos.py::test_uninterpreted_assumptions_are_remembered`), T; nothing read changes on any workload (`_failed` empty) |
| ctx-failed-no-memo (213) | record an `Uninterpreted` | 0 everywhere | U (the same test), T; void on every workload (no set raises `Uninterpreted`) |
| ctx-verdict-no-bound (214) | `_verdict` at 20,000 | 833 / 2,952 / 244 / 665 / 61 / 166 (the bound test) | **void**: nothing reaches 20,000 sets (largest: fuzz 1,802); T skips it with that reason |
| ctx-session-inconsistent-pass (215) | `_context_session` on INCONSISTENT | 0 / 167 / 0 / 3 / 0 / 0 | L fuzz, zero; M fuzz (S); T |
| ctx-build-no-fallback (216) | gave-up session kept | 0 everywhere | **U: 2 tests** (`test_lra_constant_coefficients.py::test_integer_valued_offset_does_not_silence_the_theory[log8/log2]`, `[sqrt2]`); void on every workload (`ctx:fallback` 0 there, 37 in the suite) |
| ctx-build-no-link (217) | `link_set` skipped | 839 / 2,758 / 244 / 694 / 61 / 166 | **L dev, fuzz, zero, scope (answers: an AssertionError at Session.link_set)**, M same four (answers, S); fires without effect on loop and cert |
| ctx-verdict-skip-budget (218) | `verdict` over the budget | 64 / 315 / 0 / 25 / 0 / 0 | M dev, fuzz, zero (S, E); T; live.py doesn't read `_verdict`, so L MATCHes |
| ctx-check-no-escalate (219) | no escalate | 175 / 1,077 / 169 / 615 / 61 / 41 | L all six (state, stream), M all six (E, S), T |
| ctx-check-no-truncated (220) | truncated/gave-up as consistent | 833 / 2,758 / 244 / 661 / 61 / 166 | L all six (stream), M dev, fuzz (E), T |
| ctx-check-raise (221) | ValueError in the check | 833 / 2,980 / 244 / 718 / 61 / 166 | L all six (session count, stream; fuzz answers), M all six, T; `ctx:caught` = fired |
| ctx-sessions-store (222) | session kept in `_context_sessions` | 776 / 2,565 / 244 / 643 / 61 / 166 | M all six (E: `_context_sessions` not empty), T; live.py doesn't read it |

**Void overall: 214.** Void on every workload but caught elsewhere: 211 (suite), 212 and 213 (suite), 216 (suite). The
handoff's "216/217 void here" is settled: 216 is caught by the suite, and 217 by the live comparison on four workloads.

## The switch digest (planner's state ruling, item 3)
`memo_check.py WL rust` at PYTHONHASHSEED=0 on base Rust (67d108d, a worktree with its own build,
`~/sa-rust-ids-work/sa-port-186/base`) and on 5c10b Rust (27873ac, this clone's build), on orion, from a copy of this step's
memo_check.py (`sa-port-186/bin/`) that differs only in keeping `ctx:*` counters in `counts` and in skipping the view check
and the cleared check for a map that isn't an `EngineMemo` (base's three are dicts). On base the three containers are Python
dicts; on 5c10b they are `EngineMemo` views. **`memo_check --cmp` gives MATCH on all six workloads**: answers, registry
digest, the 5c9c memos, the fact stores, and `_failed`, `_verdict`, `_context_sessions`' sizes, contents and insertion order.
Views equal `em_snapshot` on every workload (`em_view_bad` empty), every memo is empty after clear, and the 200-query rerun
gives the same answers.

| workload | queries | answers | digest | `_failed` | `_verdict` | `_context_sessions` |
|---|--:|---|---|--:|--:|--:|
| dev | 1,985 | c9cf2db177fb842d | fa58cc766d98d539 | 0 | 108 | 0 |
| fuzz | 3,000 | 7b70c27d5415d320 | c322be409740fe5e | 0 | 1,802 | 0 |
| loop | 420 | 157ced0aa6f9823f | c8fa633c2526d52e | 0 | 10 | 0 |
| zero | 854 | 1c3f3090a3f172c6 | f409711365f18111 | 0 | 77 | 0 |
| cert | 61 | c8e58c56d2ac2beb | 124879cd9aca401c | 0 | 31 | 0 |
| scope | 169 | f2fd056234f29d49 | 170d770cf3b65109 | 0 | 27 | 0 |

Base and 5c10b give the same row on every workload. dev's answers and digest equal 5c10a's memo_check rows
(`sa-port-182/mc/base/dev.json`). Rows: `~/sa-rust-ids-work/sa-port-186/mc/{base,new}`.

## Reached (counters on the unplanted 5c10b run, memo_check: one full pass plus the 200-query rerun)
| workload | `context_session` | `build_memoized` = `build_context` = `complete_check` | `verdict` | `verdict_hit` | `failed_hit` | `fallback` | `caught` | `cb_helpers` | `cb_check_version` | `cb_patched` |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| dev | 776 | 833 | 64 | 7 | 0 | 0 | 0 | 2,563 | 0 | 0 |
| fuzz | 2,772 | 2,952 | 315 | 135 | 0 | 0 | 0 | 8,589 | 0 | 0 |
| loop | 244 | 244 | 0 | 0 | 0 | 0 | 0 | 732 | 0 | 0 |
| zero | 699 | 665 | 25 | 59 | 0 | 0 | 0 | 2,008 | 0 | 0 |
| cert | 61 | 61 | 0 | 0 | 0 | 0 | 0 | 183 | 0 | 0 |
| scope | 166 | 166 | 0 | 0 | 0 | 0 | 0 | 498 | 0 | 0 |
| suite | 39,272 | 41,032 / 41,607 / 41,487 | | | 10 | 37 | 1 | 122,676 | 330 | 41,487 |

`cb_fresh_session` and `py_stats` equal `build_context` on every workload. In the suite, `cb_patched` is rust_plugin's
catch_count (catch_count.py :21-41), which wraps `_complete_check` and `verdict` on both backends: context.rs calls the
wrapper by name, and the wrapper calls session_live's Rust row. Rows: `~/sa-rust-ids-work/sa-port-186/mc/new`; suite counts
in `bar-5c10b/suite/counts.*.json`.

**Which moved items are reached, and by what:** `_context_session`, `_build_context_memoized`, `_build_context` and
`_complete_check` by every workload; `verdict` by dev, fuzz and zero; `_verdict` filled by every workload (sizes above) and hit
on dev, fuzz, zero. `_failed` is empty on every workload (no set raises `Uninterpreted`); the suite reaches it (`failed_hit` 10;
plants 212 and 213 caught there). `_context_sessions` stays empty, as in Python; only plant 222 writes it. The plain-session
fallback (`fallback`), `_check_version` (an epoch change) and engine.py:1906's catch are reached only by the suite and
test_context_core.py (and the catch by plant 221). Counters shown to fire before their zero is quoted: `ctx:caught` (plant 221),
`ctx:fallback`, `ctx:failed_hit`, `ctx:cb_check_version` and `ctx:cb_patched` (suite, above), and every `ctx:*` in
test_context_core.py's Rust run.

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Share of all queries kept per reason, on the Rust run, against 5c10a's bar.

| workload | queries | out-of-scope | refused | other named exceptions | base |
|---|--:|--:|--:|--:|---|
| dev | 1,985 | 24 (1.21%) | 0 | 0 | the same |
| fuzz | 3,000 | 0 | 0 | 0 | the same |
| zero | 854 | 0 | 0 | 0 | the same |
| cert | 61 | 0 | 0 | 0 | the same |
| loop | 420 | 0 | 0 | 0 | the same |
| scope | 169 | 0 | 0 | 0 | the same |

**No share rose.**

## State: each container 5c10b's rows touch (planner's state ruling, 8 Nov)
| container | decision | readers past 5c10b | inventory row |
|---|---|---|---|
| `Engine._failed` | **moved to Rust-native** (engmemo.rs slot 5, bound 10,000 as Python) | `_drop_set_memos` clears it through the view, `Engine.__init__` assigns it (5c10d); the registry's `Engine.memos` (view, public); `tests/test_memos.py` reads it through the view | INVENTORY-state.md :288-290; tsv "state: Engine._failed" |
| `Engine._verdict` | **moved to Rust-native** (slot 6, bound 20,000 as Python) | as `_failed`; tests in test_set_verdict.py, test_memos.py, test_registry_versioning.py and others read it through the view, unedited | :288-290; tsv "state: Engine._verdict" |
| `Engine._context_sessions` | **moved to Rust-native** (slot 7; always empty, as Python since issue 97) | as `_failed`; wiring: term_discard.py:95 (`len`, through the view) | :288-290; tsv "state: Engine._context_sessions" |
| Session.solver | **kept Python to the named state step after 5c10** (state rule: its last non-test Python reader stays) | relations.py `_xsync` :1812, `_xswitch` :1851 (Python `Relations`); Rust reads it through the shell (context.rs, query.rs :109, compile_loop.rs :98/:385); tests (test_solver_incremental, test_euf_adapter, theory_harness, ...) | :288-290, :296 (Session containers move with session_live); tsv "state: Session.solver" |
| Session.xfer | **kept Python, same step** | relations.py :1689 sets it; ref.py :454 (reference); context.rs and query.rs :111 read it | the same; tsv "state: Session.xfer" |
| Session.truncated | **kept Python, same step** | engine.py `_put_result` :2145 and `_note_budget` :2248 (5c10d); budget.rs :315; set by discovery.rs :220 | the same; tsv "state: Session.truncated" |

The three Session attributes: the brief left this open ("move them or ask the architect"). The state rule decides it: no
step before the state step removes their last non-test Python reader (Python `Relations` and 5c10d's rows read them), and
Session is still a Python shell whose other containers move with session_live in the state step. Moving three attributes onto
SessionCore now would add a crossing back for each Python reader. If the planner wants them moved in 5c10d instead, it's a
small change: SessionCore fields with a data descriptor on Session.

**Snapshot digest at the switch: equal on all six workloads** (above). `em_snapshot` (engmemo.rs, test-only) reads each map
itself; the views equal it on every workload (`em_view_bad` empty).

## Module count
**14 of 32, unchanged** (STATUS "Counted modules"). engine.py doesn't count whole; 5c10c and 5c10d remain.

## Owed-list additions
- `_failed`, the plain-session fallback, `_check_version` and engine.py:1906's catch are reached by the suite and
  test_context_core.py, not by any workload. Plants 212, 213 and 216 are void on every workload and caught by the suite.
- Plant 214 (`_verdict`'s 20,000 bound) is void everywhere. A test that fills one engine with 20,000 distinct sets would
  catch it.
- `ctx:cb_patched` in the suite: catch_count's wrappers make every `_complete_check`/`verdict` call a by-name call there. It
  isn't a crossing on the default backend (0 on every workload), but the suite runs the Rust rows through one Python hop.
- Session.solver/xfer/truncated go to the state step (above), with Rust's reads of the shell attributes counted as crossings
  until then (not counted separately yet: they're `getattr`s on the Python Session).

## Not run
Moved to "before any backend PR", and none quoted as met:
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

Also not run:
- the switch digest on budget (memo_check ran dev, fuzz, loop, zero, cert, scope);
- the full suite under plants 211-222 other than 211, 212, 213 and 216 (SUITE_PLANTS was `zero`: the four that fire 0 in
  live.py on dev and fuzz);
- a workload reaching `_failed`, the fallback, an epoch change or `_verdict`'s bound.

Other notes:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals
  (failed on this bar as on base). This step doesn't touch it.
- `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`: failed, as on base. It's
  the known id()-reuse test artifact (sa-port-185, report a28c548), unedited.
- `test_performance_smoke_300_vars`: not among the changed outcomes (same as base).
