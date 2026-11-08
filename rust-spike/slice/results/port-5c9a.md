# Step 5c9a: the memo registry, able to hold Rust-native tables; Engine settings and restamp read in Rust (issue 323)

## What moved
Inventory part 5's 5c9a rows (sa-port-147, INVENTORY-state.md :265-280): state/memos.py (22 rows), `engine_memos`,
`epoch.bump` and the Engine settings properties (`extensions` .. `templates`, 16 getters and setters). Classified by
tracing (`memo_trace.py`, sa-port-173), then:
- **Moved to Rust, the callbacks gone:** Rust's reads of `Engine.extensions`, `relation_specs`, `transfer` and `uninterpreted`
  (memos.rs `setting`: the field when the engine's type is exactly `Engine`, else the property, counted
  `memo:setting_prop`), and Rust's `Table.restamp` on `_KEYS`/`_CONST` (memos.rs `restamp`). Per pass, called back from
  Rust before: dev 989 / 122 / 35 / 393 and restamp 2; fuzz 2,938 / 315 / 911 / 5,564 and restamp 2. **After: 0 on both**
  (memo_trace on 5c9a; the only `<-C` row left is one `memos.__getattr__` via `_compat`, at import).
- **The registry container** (`memos.PROCESS`, `Memos`) stays a Python object and is made able to hold Rust-native tables:
  `Memos.attach/detach` and `_native` (memos.py :101-130); `items`, `names`, `sizes`, `clear` and `__repr__` include them.
  It now lists Rust's two native process memos, which Python never saw: relations_core `SPEC_ROWS` and constfield
  `ENCLOSURES`, as read-only `NativeTable` views (memos.rs). Empty on the Python backend.
- **Stay, with reason:** the Python getters (conversion callers: convert.py `convert` and `default_engine_settings`,
  `_engine_ask`, `_ask_general`; and the public API); the setters (public configuration writes; `_settings_changed` is
  5c10's); `Table.restamp` for `_formula` (`_FORMULAS`, conversion layer); import-time, harness and test rows
  (`adopt`, `_module_attr`, `owner_memos`, `engine_memos`, `load_owners`, `module_locations`, `__getattr__`, `epoch.bump`:
  0 per query); `_Mark`'s `Memos.items` per query (slice wiring, parked for the conversion pass by the state ruling;
  `_Mark._note` now skips native views, term_live.py:145).
- **Bounds:** `SPEC_ROWS_SIZE` (relations_core.rs, the literal 4096 named). `ENCLOSURES_SIZE` 100,000 (constfield.rs):
  ENCLOSURES had no bound. **A behaviour change for a memo only:** past 100,000 constants it empties, as Python's tables do.
- **Counters** (session.rs): `memo:*` 230-235; 200-229 are reserved fillers (skipped by `session_counts`). **Plants**
  (relations_core.rs): 170-177, `_MEMO_PLANTS` in session_live.py.

## SHAs
**Tested: 5122f71** (port/5c9a on rust-slice 3611952), all bar phases but seed1. Rows on pareto1:
`~/sp19/sa-rust-ids-work/sa-port-174/bar-5c9a/`; `.so` sha256 43441f03…. Base suite rows: 5c8's (`sa-port-170/bar-5c8/suite`).
**Landed:** the commit carrying this file, on rust-slice, rebased on 3611952 (unchanged since the bar started). **Incoming
diff: none** (3611952..3611952). Between 5122f71 and the landed commit there is only this report and port-ownership.tsv
(results/). 5c9a's was the first clean bar, so it lands before the 6g stack (sa-port-172), which rebases onto it.

## The bar (sa-port-174/bar-5c9a on 5122f71)
1. **Suite by id against 5c8's rows:** 5,992 passed, 126 failed, 23 skipped, 18 xfailed, 6,159 ids. New 0, gone 0,
   changed outcome 0. Passed splits as 5,991 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`).
   S's standing: S's gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz, plus loop, zero and cert:** answers and state MATCH, and every control MATCHes. Answers unchanged:
   dev 31cd0945c07f02a6 (1,985 q), fuzz 173502b6ef285ad6 (3,000 q), loop 09238b2537e54383 (420 q), zero d9ed3534a2093027
   (854 q), cert 6a09c059eb266747 (61 q). The Rust runs made 0 Python solvers. The registry's snapshot digest is equal at the
   switch on all five (below).
3. **Plants:** 7 of 8 caught (table below), counting memo_check and the suite files; the bar's live comparison alone catches
   173, 175 and 176. 177 is void, as expected.
4. **Quiet handlers in the suite:** 39 rows in 2 tests, the same multiset as 5c8's:
   - `_consistent` AttributeError: 34 on `_ok` and 4 on `_rb_clauses` (the named needs-internals case);
   - `Engine._build_context` "Already mutably borrowed": 1, in `test_protocol_on_fuzz` (the 46-stub cause).

   The `caught` rows per id match base. TermFault 0 in the suite log. The 12 live handler files have 0 rows. Among the
   plant handler files, only `memo-set-relspecs`'s have rows (dev 2, fuzz 315: `_consistent` Unsupported, "... is out of
   scope (relation)"), the plant's own effect (no adapter specs, so relations are out of scope); the other 14 have 0.
5. **Known differences in answers or read state:** none. Tests: 574 passed, 0 failed (5c8's list of 14 files).
   `relations_direct.py` exited 0.

## The switch digest (planner's state ruling, item 3)
`memo_check.py WL rust` on base Rust (3611952, a worktree) and on 5c9a Rust, on orion. The digest covers everything Python can
read from the registry that both have: per memo of `memos.PROCESS` and of the default engine's `Engine.memos` (native views
excepted, since base has none), (owner, name, key, len, stamp). **Answers and digest equal on all five workloads:**

| workload | queries | answers | digest | 5c9a: views == maps | empty after clear | rerun of 200 the same |
|---|--:|---|---|---|---|---|
| dev | 1,985 | c9cf2db177fb842d | fa58cc766d98d539 | yes (ENCLOSURES 1, SPEC_ROWS 2) | yes | yes |
| fuzz | 3,000 | 7b70c27d5415d320 | c322be409740fe5e | yes (1, 2) | yes | yes |
| loop | 420 | 157ced0aa6f9823f | c8fa633c2526d52e | yes (0, 0) | yes | yes |
| zero | 854 | 1c3f3090a3f172c6 | f409711365f18111 | yes (0, 2) | yes | yes |
| cert | 61 | c8e58c56d2ac2beb | 124879cd9aca401c | yes (1, 2) | yes | yes |

(memo_check's answer hash isn't live.py's, so these hashes differ from the bar's.) Rows: `~/sa-rust-ids-work/sa-port-174/mc/`.

## Plants
Fired = `rel:plant_fired`. For 173-176 that counter ticks at every setting read while the plant is on (`planted()` is
consulted before the setting's name), so it overcounts; the plant changes only its own setting's reads, which per dev pass
are transfer 35, uninterpreted 393, relation_specs 122, extensions 989 (fuzz 911, 5,564, 315, 2,938).
Caught by: V = registry view != Rust maps, C = not empty after `clear()`, S = registry digest, A = answers (memo_check,
against the same workload's unplanted 5c9a run), and D = the bar's plants/extra comparison (live.py, answers and state).

| plant | row | dev | fuzz | loop | zero | cert | caught by |
|---|---|---|---|---|---|---|---|
| memo-view-drop (170, **the registry-view plant**) | `memo_install` | 1 V C | 1 V C | 1 V | 1 V C | 1 V C | memo_check, every workload (bar's live: MATCH, it reads no registry) |
| memo-clear-skip (171) | `NativeTable.clear` | 2 C | 2 C | 2 | 2 | 2 C | memo_check dev, fuzz, cert |
| memo-restamp-no-stamp (172) | memos.rs `restamp` | 2,410 S | 15,536 S | 52 S | 2,360 S | 468 S | memo_check digest, every workload (bar's live: MATCH) |
| memo-set-transfer (173) | `setting` transfer | A S D | A S D | | A S D | | memo_check and the bar, dev, fuzz, zero |
| memo-set-uninterp (174) | `setting` uninterpreted | | | | | | **suite files: 18 tests** (below); no workload has an atom no theory interprets |
| memo-set-relspecs (175) | `setting` relation_specs | S D | S D | | S D | | memo_check and the bar, dev, fuzz, zero |
| memo-set-ext (176) | `setting` extensions | | | S D | | | loop (memo_check and the bar); suite files: 2 tests |
| memo-spec-unbounded (177) | `spec_row` bound | 0 | 0 | 0 | 0 | 0 | **void**: no workload or test makes 4,096 relation specs |

memo_check's fired counts (first three rows) are from a copy of memo_check.py with a counts epilogue,
`~/sa-rust-ids-work/sa-port-174/memo_check-counts.py` (kept out of the landing source, which the bar guards); rows in
`sa-port-174/pl/`. The bar's plant runs give the same picture (fired: view-drop 1 everywhere, restamp dev 2,360, fuzz 14,444;
clear-skip 0 there, since live.py never clears the registry).
**Suite files under the plant** (orion, rust_plugin, the 13 test files that set `uninterpreted=` or `extensions=`;
sa-port-174/sp/; not the bar's suiteplants phase): unplanted 4 failed (all in base's 126), memo-set-uninterp 22 (18 new:
test_extended_order 6, test_sympy_api 3, and one each in test_memos `test_uninterpreted_assumptions_are_remembered`,
test_invariant_repros (2), test_registry_versioning, test_relations (2), test_relevance, test_transfer, test_verify_integration),
memo-set-ext 6 (2 new: test_relevance `test_vocabulary_extension_is_not_split` and `..._on_derived_class_is_not_split`).

## Reached (memo counters on the unplanted 5c9a run, memo_check: one full pass plus the 200-query rerun)
| workload | `memo:setting` | `memo:restamp` | `memo:native_clear` | `memo:setting_prop` | `memo:native_items` | `memo:spec_full` |
|---|--:|--:|--:|--:|--:|--:|
| dev | 1,566 | 4 | 2 | 0 | 0 | 0 |
| fuzz | 10,417 | 4 | 2 | 0 | 0 | 0 |
| loop | 360 | 4 | 2 | 0 | 0 | 0 |
| zero | 2,888 | 4 | 2 | 0 | 0 | 0 |
| cert | 366 | 4 | 2 | 0 | 0 | 0 |

The moved items (`setting`, `restamp`) are reached by every workload. Counters shown to fire before quoting their zero
(sa-port-174/ctr/counters_fire.py): `memo:native_items` 4 after reading both views' `items()` and iterating them,
`memo:setting_prop` 1 after one query on an `Engine` subclass. **`memo:spec_full` is not shown to fire:** it needs 4,096
distinct live relation specs, and duplicating the real adapters' specs conflicts (two LRA adapters register the same
variable, ValueError); plant 177 is void for the same reason. `memo:native_clear` fires in the registry test
`test_process_memos_registered_and_cleared` (2).

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Share of all queries kept per reason, on the Rust run, against 5c8's bar.

| workload | queries | out-of-scope | refused | other named exceptions | base |
|---|--:|--:|--:|--:|---|
| dev | 1,985 | 24 (1.21%) | 0 | 0 | the same |
| fuzz | 3,000 | 0 | 0 | 0 | the same |
| zero | 854 | 0 | 0 | 0 | the same |
| cert | 61 | 0 | 0 | 0 | the same |
| loop | 420 | 0 | 0 | 0 | the same |

**No share rose.**

## State: each container 5c9a's rows touch (planner's state ruling, 8 Nov)
| container | decision | readers past 5c9a | inventory row |
|---|---|---|---|
| `memos.PROCESS` (the registry) | **kept a Python object, made able to hold Rust-native tables** (inventory: "the registry itself, made able to hold Rust-native tables") | public API reads `names/sizes/clear/items`; tests test_memos.py, test_p4_review.py; `_Mark` (slice wiring, parked); conversion `_formula` | INVENTORY-state.md :270-275; tsv "state: memos.PROCESS (registry)" |
| `Engine.memos` / `ENGINE_MEMOS` | kept Python: its tables are 5c9c's and 5c10's containers; listed through the registry view | `_Mark`, tests, `_drop_set_memos` (5c10) | :270-275; tsv "state: Engine.memos (ENGINE_MEMOS)" |
| relations_core `SPEC_ROWS` | Rust-native already; **now visible** to Python through a read-only view in `memos.PROCESS` | none in Python but the view (tests, inventory) | tsv "state: SPEC_ROWS" |
| constfield `ENCLOSURES` | Rust-native already; now visible through the view; new bound 100,000 | as SPEC_ROWS | tsv "state: ENCLOSURES" |
| Engine settings fields (`_extensions`, `_relation_specs`, `_transfer`, `_uninterpreted`) | kept Python (Engine's fields are 5c10's container); Rust reads them directly, **one counted crossing**, `memo:setting`, removed by 5c10 | conversion, public API | tsv engine.py Engine.* 1418-1522 |

**Snapshot digest at the switch: equal on all five workloads** (above). `memo_snapshot` (memos.rs, test-only) reads the
native maps; the views equal it on every workload.

## Registry tests on Rust
`tests/test_memos.py` (all 8, including its three registry ids) and
`tests/test_p4_review.py::test_every_adopted_memo_name_resolves`: **9 passed, unedited**, under rust_plugin
(sa-port-174/regtests; `caught` empty on every row). The native views are attached in that run: `test_process_memos_registered_and_cleared`
ticks `memo:native_clear` 2. None goes on the needs-internals list.

## Module count
**14 of 32, unchanged** (STATUS "Counted modules", 14 before this step). state/memos.py doesn't count: its Python still runs
per query from `_Mark` (`Memos.items`, slice wiring parked for the conversion pass) and from `_formula`'s restamp
(conversion). state/epoch.py's `bump` runs 0 per query (import time and registrations), but it isn't ported; not claimed.

## Owed-list additions
- `memo-spec-unbounded` (177) is void: no workload or test makes 4,096 relation specs. A test with a cheap stub adapter spec
  repeated 4,097 times would reach it.
- The settings plants' fire counter overcounts (it ticks at every setting read with the plant on); count by setting if a
  later step reuses them.

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
- the full suite under any 5c9a plant (SUITE_PLANTS empty); 174 and 176 ran on 13 suite files on orion instead;
- the switch digest on scope and budget (memo_check ran dev, fuzz, loop, zero, cert);
- `memo:spec_full` shown to fire (above).

Other notes:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
  This step doesn't touch it.
- Quiet catches at engine.py:1906: not counted separately in this bar; the suite's `caught` rows per id match base.
