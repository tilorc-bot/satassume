# Step 5c10d: query entry and counters in Rust; `Engine.stats`, `Engine.last_budget_limited` Rust-owned (issue 323)

## What moved
Inventory part 5's 5c10d row (sa-port-147, INVENTORY-state.md :293-299), the last 5c10 part, under the planner's go (8 Nov
23:50). Work by sa-port-192 (WIP 2faa09e); the five remaining plants, the live/memo_check view checks, the bar, the rows and
landing by sa-port-193.
- **Rows in entry.rs**, step for step as engine.py: `is_` (:567), `is_many` (:618), `_decide` (:479), `_put_result` (:508),
  `_is_custom` (:709), `ask` (:743), `_ask` (:798), `_check_version` (:391), `_settings_changed` (:436), `_drop_set_memos`
  (:417), `_fresh_session` (:452); pyfunctions `ent_*` bound over Engine in session_live's `_ENTRY_METHODS` (:840, install
  :867). **From port/5c7:** `_over_budget` and `_note_budget` (budget.rs :554, :570), now wired and writing the Rust state.
  `entry_native()` (session_live.py :854; `SLICE_ENTRY=py` is the control).
- **Moved to Rust-owned state:** `Engine.stats` (12 counters in Python's key order) and `Engine.last_budget_limited`, as
  entry.rs `EngineStats` (:64-205) in the engine's `__dict__`, behind `StatsSlot` data descriptors (:227-280) on both
  attributes. Readers get a **read-only view**: `[k]`, `get`, `in`, `keys`/`values`/`items`, `==`, `dict()`, `len`, iteration,
  `repr`; `[k]=v` raises TypeError. `Engine.__init__`'s dict and flag writes convert once (`st:slot_set`, `st:flag_set`).
  Test-only export: `sa_solver.st_snapshot(eng)` (:836).
- **Write path, the planner's ruling (2):** narrow named record methods, each a single counted entry point, for the writers
  outside the rows: `_record_cache_hit`, `_record_relevant`, `_record_consistency_check`, `_record_scope_miss`,
  `_clear_budget_flag`, `_keep_budget_flag(limited)` (engine.py :1420-1436 hold Python's bodies; Rust's `ent_record_*` are
  installed over them). Callers changed: sympy_api.py :469 :478 :571 :583 :588 :589 :1099 :1114, relations.py :907, and
  Session `_custom`'s scope miss. Rust writers write natively: relevance.rs `consistent`, context.rs `build_context`
  (set_checks), compile_loop.rs and relations_core.rs scope misses (`entry::scope_miss`). **The answer memo stays
  conversion** (input layer), as ruled.
- **`_Mark`** (term_live.py :155-158, :186-192) snapshots and restores the stats through `_st_mark`/`_st_rollback` (`st:mark`).
- **Callbacks into Python left, counted:** `ent:cb_noncomm` (`_noncommutative*`, `noncommutative_false`), `ent:cb_gave_up`
  (`_gave_up`), `ent:cb_scope` (`theory_scope`), `ent:cb_basis` (`basis_lits`/`basis_formula`); Session methods and
  `s.truncated`/`s.solver`/`s.n_hold` are read through the session (the state step).
- **Counters** (session.rs :401-426): 301-326 (NAMES is 327): `ent:*`, `st:*`. **Plants** (relations_core.rs): 231-250 plus
  the two budget plants, `_ENTRY_PLANTS` (session_live.py :847).
- **New test:** test_entry_core.py, Python against Rust, each mode in its own process: cert_wl and budget_wl per query (answer,
  `list(stats.items())`, flag), `is_many`, settings, epoch, a split set (`consistency_checks`), a custom predicate
  (`custom_cache` hits), a contextual query whose LRA gives up (`theory_gave_up`), one DictCache shared by two engines with
  different settings (`_check_version`'s sync), `Engine.ask` called directly over the budget and then on a non-commutative
  atom (`ask`'s own flag clear before the early return), Python's 400-step write sequence through the record methods, and the
  view forms; `st_snapshot` equals the view after every query. **23 passed: all 21 plants fire and move a case; `ELSEWHERE`
  is empty.**
- **live.py** records `[list(stats.items()), last_budget_limited]` of `sympy_api.default_engine()` after each query;
  **livecmp.py** compares it (`stats_diff`). This is the read-only view pinned equal to Python's value after each query on
  every bar workload, budget included.
- **memo_check.py** puts `stats` and the flag into the compared fields, and on Rust checks the view against `st_snapshot`
  (`st_view_bad`); it still runs on base trees.

## SHAs
**Tested: 8ff9116** (port/5c10d on rust-slice b384ec1). Bar 00:29Z-02:31Z on pareto1 (every phase exit 0 but seed1, not run; machine run released the lease exit 0), rows `~/sp19/sa-rust-ids-work/sa-port-193/bar-5c10d-r2/` (a first launch at 00:26 had literal quotes in its PLANTS/TESTS/WLS/DIRECT, so its tests phase found no files; stopped after 1 minute, rows discarded)
(summary copied to `~/sa-rust-ids-work/sa-port-193/machine-run.log`); `.so` sha256 53fe77a5…. Run beside sa-port-191's 6g(c6) bar, both under shared leases.
Base suite rows: 5c10c's landing bar (`sa-port-189/bar-5c10c/suite`).
**Incoming diff before the bar:** none (b384ec1 was rust-slice's head at launch).
**Landed:** TBD.

## The bar (sa-port-193/bar-5c10d-r2 on 8ff9116)
1. **Suite by id against 5c10c's rows:** 5,991 passed, 127 failed, 23 skipped, 18 xfailed, 6,159 ids. New 0, gone 0,
   **changed outcome 0.** Passed splits as 5,990 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`).
   `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` failed, as on base: the
   known id()-reuse test artifact (sa-port-185, report a28c548), unedited. S's standing: S's gate is met except for the 46
   named stub failures, one cause.
2. **Fresh dev and fuzz, plus loop, zero, cert, scope and budget:** answers and state MATCH, **`stats_diff` 0 everywhere** (the
   stats view and flag after each query), and every control MATCHes. Answers: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6,
   loop 09238b2537e54383, zero d9ed3534a2093027 (all equal to 5c10c's), budget 35bc2c4a937bebc0 (28 q). Rust made 0 Python
   solvers, reentry 0. Snapshot digest equal at the switch on all seven (below).
3. **Plants:** 20 of 21 caught (table below); void on the bar: `st-keep-flag-drop` (fires 0 on every workload and the suite),
   caught by test_entry_core.py. **Both budget plants are caught on budget:** `over-budget-no-flag` (15 fires) and
   `note-budget-count` (13), by `stats_diff` alone (answers unchanged). In sa-port-193's orion preview `note-budget-count`
   gave `stats_diff` 14 on budget with answers equal: the view comparison catches what the answer comparison can't.
4. **Quiet handlers in the suite:** 39 rows in 2 tests, the same multiset as base: `_consistent` AttributeError 34 (`_ok`) and
   4 (`_rb_clauses`), the named needs-internals case; `Engine._build_context` "Already mutably borrowed" 1 in
   `test_protocol_on_fuzz` (the 46-stub cause). **engine.py:1906's catches (`ctx:caught`):** 1 in the suite (that row), 0 on
   all seven workloads; caught rows per id equal base (0 ids differ). TermFault 0. Every live, extra and plant handler file
   has 0 rows; the 8 suite-plant runs give the same 39-row multiset.
5. **Known differences in answers or read state:** none. Tests: 661 passed, 3 skipped (5c10c's 19 files plus
   test_entry_core.py's 23); `relations_direct.py` exited 0.

## Plants
Caught by: L = the bar's live comparison (workloads where it DIFFERs, mostly `stats_diff`), U = the suite (SUITE_PLANTS=`zero`:
the 8 that fired 0 on dev and fuzz; changed outcomes), T = test_entry_core.py (all 21).

| plant | caught by |
|---|---|
| ent-is-no-hit-count, ent-put-result-no-put | L dev, fuzz, cert; T |
| ent-is-many-queries-short | L dev, fuzz, scope, zero; T |
| ent-decide-no-escalate | L dev, fuzz, loop, scope, zero; T |
| ent-fresh-no-count, note-budget-count, st-view-order | L all seven; T |
| st-cache-hit-drop | L dev, fuzz, loop; T |
| st-relevant-drop, st-consistency-drop | L dev, fuzz; T |
| over-budget-no-flag | L budget; U 16 tests; T |
| st-flag-view-stale | L budget; U 16 tests; T |
| ent-ask-no-gave-up | U 1 (`test_lra_constant_coefficients.py::test_hidden_algebraic_equality_gives_up_but_other_theories_answer`); T |
| ent-drop-memos-keep-answers | U 34 (test_registry_versioning.py, test_history.py, ...); T |
| ent-settings-no-clear | U 8; T |
| ent-is-custom-no-hit | U 2; T |
| st-scope-miss-double | U 1; T |
| ent-ask-no-clear-flag, ent-check-version-no-sync, st-clear-flag-skip | fire on every workload but MATCH (sympy_api clears the flag itself; one engine, so the sync never empties); T only (`flag`, `shared`, `writes` cases) |
| st-keep-flag-drop | **void on the bar** (0 fires everywhere, suite too); T only (`writes`) |

## The switch digest (planner's state ruling, item 3)
`memo_check.py WL rust` at PYTHONHASHSEED=0 on base Rust (b384ec1, a worktree with its own build, `~/sa-rust-ids-work/sa-port-193/base`)
and on 5c10d Rust (8ff9116's source), on orion, both from this step's memo_check.py (`sa-port-193/bin/`). On base `stats` is
a Python dict; on 5c10d it is the `EngineStats` view. **`memo_check --cmp` gives MATCH on all seven workloads**
(`~/sa-rust-ids-work/sa-port-193/mc/cmp-base-new.txt`): answers, registry digest, the engine memos and fact stores, **the
12 stats counters in order and `last_budget_limited`**, and the 200-query rerun. The view equals `st_snapshot` on every
workload (`st_view_bad` empty).

| workload | queries | answers | digest | `stats["queries"]` | flag at end |
|---|--:|---|---|--:|---|
| dev | 1,985 | c9cf2db177fb842d | fa58cc766d98d539 | 883 | False |
| fuzz | 3,000 | 7b70c27d5415d320 | c322be409740fe5e | 3,031 | False |
| loop | 420 | 157ced0aa6f9823f | c8fa633c2526d52e | 384 | False |
| zero | 854 | 1c3f3090a3f172c6 | f409711365f18111 | 714 | False |
| cert | 61 | c8e58c56d2ac2beb | 124879cd9aca401c | 87 | False |
| scope | 169 | f2fd056234f29d49 | 170d770cf3b65109 | 197 | False |
| budget | 28 | ecf2048fa4c9e38c | ac1d909b55a445c1 | 26 | True |

Base and 5c10d give the same row on every workload; the six earlier workloads' answers and digests equal 5c10c's table.

## Reached, and the record-method counts (memo_check's unplanted 5c10d pass, one pass)
| workload | `ask` | `ask_inner` | `is` | `is_many` | `is_custom` | `decide`/`put_result` | `fresh_session` | `over_budget` | `note_budget` | `cb_gave_up` | `cb_noncomm` | `cb_scope` | `cb_basis` | `st:mark` | `st:py_read` |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| dev | 776 | 776 | 433 | 2 | 2 | 107 | 918 | 0 | 776 | 776 | 1,209 | 2 | 1 | 1,221 | 1,675 |
| fuzz | 2,812 | 2,605 | 783 | 6 | 45 | 219 | 3,133 | 0 | 2,605 | 2,565 | 3,556 | 85 | 11 | 2,998 | 3,979 |
| loop | 244 | 244 | 140 | 0 | 0 | 140 | 384 | 0 | 244 | 244 | 384 | 0 | 0 | 384 | 386 |
| zero | 699 | 643 | 1 | 1 | 1 | 15 | 667 | 0 | 625 | 625 | 700 | 1 | 0 | 740 | 710 |
| cert | 61 | 61 | 121 | 0 | 0 | 26 | 87 | 0 | 61 | 61 | 182 | 0 | 0 | 61 | 63 |
| scope | 166 | 166 | 3 | 2 | 2 | 31 | 171 | 0 | 166 | 166 | 169 | 2 | 0 | 169 | 171 |
| budget | 26 | 13 | 2 | 0 | 0 | 0 | 17 | **15** | 13 | 12 | 28 | 1 | 0 | 28 | 30 |

`check_version` 1 on every workload (memo_check's one clear); `settings_changed` and `drop_set_memos` 0 on the workloads
(reached by test_entry_core.py's `settings` and `epoch` cases and by the suite).

**Record methods per workload** (Python callers into the named entry points):

| workload | `_record_cache_hit` | `_record_relevant` | `_record_consistency_check` | `_record_scope_miss` | `_clear_budget_flag` | `_keep_budget_flag` |
|---|--:|--:|--:|--:|--:|--:|
| dev | 895 | 583 | 0 | 0 | 3,206 | 0 |
| fuzz | 19 | 1,203 | 0 | 0 | 5,998 | 0 |
| loop | 36 | 0 | 0 | 0 | 804 | 0 |
| zero | 154 | 84 | 0 | 0 | 1,594 | 0 |
| cert | 0 | 0 | 0 | 0 | 122 | 0 |
| scope | 0 | 0 | 0 | 0 | 338 | 0 |
| budget | 0 | 0 | 0 | 0 | 56 | 0 |

`_record_consistency_check` and `_record_scope_miss` are 0 because their Rust callers write natively (relevance.rs
`consistent`, `entry::scope_miss`); `_keep_budget_flag` (sympy_api :588-589) is reached by test_entry_core.py's `writes`
case only: plant `st-keep-flag-drop` fired 0 in the suite too.

**Which moved items are reached, and by what:** every row and both containers by every workload (above), except
`_settings_changed`/`_drop_set_memos` (test_entry_core.py, suite) and `_over_budget` (budget only, 15 of 28 queries; the
flag is True after those and False after the rest, pinned by the live comparison and test_entry_core.py).

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Out-of-scope: dev 24/1,985 (1.21%), every other workload 0; refused 0 everywhere; no other named exception. Equal to
5c10c's bar on dev, fuzz, loop, zero, cert, scope; budget has no base row (first time on a bar), 0 and 0. **No share rose.**

## State: each container 5c10d's rows touch (planner's state ruling, 8 Nov)
| container | decision | readers past 5c10d | inventory row |
|---|---|---|---|
| `Engine.stats` | **moved to Rust-owned** (entry.rs `EngineStats`), read-only view plus the named record methods | public API and tests read through the view (`st:py_read`); sympy_api :469 :478 :571 :583 :1099 :1114, relations.py :907, Session `_custom` write through the record methods | INVENTORY-state.md :293-299 (5c10d row); tsv "state: Engine.stats" |
| `Engine.last_budget_limited` | **moved to Rust-owned** (`EngineStats.limited`), read-only view | sympy_api `ask`/`_ask`/`_ask_general`/`_engine_ask` read it (conversion); sympy_api :588-589 write through `_clear_budget_flag`/`_keep_budget_flag` | the same; tsv "state: Engine.last_budget_limited" |
| `Engine.answers` (AnswerMemo) | **kept: conversion** (input layer), as the planner's ruling (2) says | sympy_api `_ask_general` | the same |
| `Engine.cache.store`, `custom_cache.store` | Rust-native since 5c10a; `is_`/`is_many`/`_is_custom`/`_put_result`/`_settings_changed` now reach them from Rust (TSV callers relabelled 5c10c -> 5c10d) | as 5c10a's rows | tsv rows 10-15, "state: Engine.cache.store", "custom_cache.store" |
| Session.solver, Session.xfer, Session.truncated | **kept Python to the named state step** (state rule; planner's go, item 4) | entry.rs :511 and budget.rs :573 read `s.truncated`; entry.rs :801-803 read `s.solver`/`s.n_hold`; the three relations.py sites in INVENTORY-state.md :302-312 | :302-312; tsv "state: Session.*" |

**Snapshot digest at the switch: equal on all seven workloads** (above).

## Module count: what keeps engine.py out
**14 of 32, unchanged** (checked against STATUS "Counted modules", 14 of 32). engine.py doesn't count whole at 5c10d, because
Python state that the state step owns is still read per query (planner's go, item 4). By line, at 8ff9116:
- entry.rs :511 (`_put_result`) and budget.rs :573 (`_note_budget`) read `s.truncated` from the Python Session;
- entry.rs :801-803 (`_ask`) reads `s.solver` and `s.n_hold` and calls `s.solver.release`; :806-812 call the Session's
  `prepare_query`, `assumption_lits`, `query_literal`, `incomplete`, `escalate` (and :729-730 `literal_of`/`assumption_lits`
  in `_is_custom`);
- `_gave_up` (engine.py :2292, `s.solver.theories()`), called back per contextual query (`ent:cb_gave_up`, entry.rs :821);
- the module helpers called back: `_noncommutative_atoms` (engine.py :170, entry.rs :759), `_noncommutative` (:140, entry.rs
  :529), `theory_scope` (entry.rs :706), `basis_lits`/`basis_formula` (entry.rs :554, :781);
- INVENTORY-state.md :302-312's five sites: relations.py :1689 `_engage_transfer` (writes `s.xfer`), :1812 `sync_transfer`,
  :1851 `_xswitch`; engine.py `_put_result` and `_note_budget` (now the Rust reads above);
- the Session class itself (engine.py :304): its containers and methods are Python (`_custom` :707 among them), bridged by
  session_live and `_Mark`.
Engine.__init__ (engine.py :1313) runs once per engine, not per query. So the state step's list is: the Session containers
and handles, the three relations.py transfer sites, and the callbacks above.

## Owed-list additions
- `_keep_budget_flag` fires 0 on every workload (sympy_api :588-589); test_entry_core.py's `writes` case catches its plant.
- `ent:cb_*`: the per-query callbacks above, removed by the state step with session_live.

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
- the full suite under the 13 plants that fire on dev or fuzz (SUITE_PLANTS was `zero`);
- memo_check's plant pass (the bar's live comparison and test_entry_core.py cover all 21).

Other notes:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
- `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`: the known id()-reuse test
  artifact (sa-port-185, report a28c548), unedited.
