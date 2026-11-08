# Step 5c10a: the fact caches Rust-native: `Engine.cache.store`, `Engine.custom_cache.store`, with `DictCache` (issue 323)

## What moved
Inventory part 5's 5c10a row (sa-port-147, INVENTORY-state.md :285-287; container row :197): containers `cache.store` and
`custom_cache.store`; rows `DictCache.*` (engine.py :188-277); the `_journaled_put` wiring goes. Work by sa-port-182 (64031f6),
bar read and landed by sa-port-183.
- **Moved to Rust-native state** (factcache.rs): `FactCache` is the whole `DictCache`: its store (node -> {pred: value}),
  `maxsize`, `_epoch`, `_settings`, and Python's `sync`, `facts`, `get`, `put` with their semantics exactly: lookup by the node's
  hash, then identity or `==` (`fc:key_eq`); insertion order kept (a Vec plus a hash index; no single deletes exist, so no order
  exception is needed); the store emptied when a new node finds it at `maxsize` (`fc:full`); `sync` emptying it on another epoch
  or other settings (`!=`, as Python).
- **Where caches come from:** `FactCache` is registered as `sa_solver.DictCache`. session_live `_install_factcache`
  (`SLICE_FACTCACHE`, default rust) binds it over Python's class in every loaded module (`ObjectCache` too, so
  `type(Engine().cache) is DictCache` holds) and gives Python's class a `__new__` that returns one, for a name bound before the
  install. So every `DictCache(...)` (the engine's default, a caller's shared cache, the harness's sized ones) is one, and a
  cache passed to several engines is one object they all write (`fc:new`).
- **The read-only view (public reads):** `store` is a `FactView`: a mapping over the Rust store (len, in, [], get, keys,
  values, items, iter, `==` with a dict), each value a fresh dict. Its only writer is `clear`, which the registry
  (`Engine.memos.clear()`, public) and `_settings_changed` call (`fc:clear`). Views are `native` and `moved`, so `_Mark` skips
  them and the registry digest still counts them.
- **Rollback:** `_Mark` (term_live.py :123-170) undid a refused query's puts by size plus `_journaled_put`'s journal. It now
  takes each native cache's `_fc_mark()` and calls `_fc_rollback(mark)` (`fc:rollback`). **`_journaled_put` is not installed
  on the Rust backend** (term_live.py, the condition near :940); it stays only for `SLICE_FACTCACHE=py`.
- **Python callers left, each a counted crossing:** `Engine.is_`, `is_many`, `_is_custom`, `_put_result` (`facts`, `put`,
  `fc:py_facts`/`fc:py_put`/`fc:py_key`; 5c10c), `_check_version` (`sync`, `fc:py_sync`; 5c10d), `_settings_changed`
  (`store.clear()`; 5c10d). No Rust code calls the caches yet.
- **Counters** (session.rs): `fc:py_facts`..`fc:py_key` 260-270 (NAMES is 271). **Plants** (relations_core.rs `rel_plant`):
  200-210, `_MEMO_PLANTS` in session_live.py.
- **New test:** test_factcache_core.py (13 passed), Python against Rust in separate processes, cases shared, engine, get,
  bound, epoch, custom, view, clear, rollback: Python == Rust on every case, every `fc:*` counter fires on Rust, both caches
  are Rust's there, and all 11 plants fire and are caught.
- **memo_check.py** records the fact stores (`FACTCACHES`, `factcache_rows`: sizes, contents, insertion order) and checks the
  view against `sa_solver.fc_snapshot` (test-only, reads the Rust store itself; `fc_view_bad`), and that they are empty after
  clear.

## SHAs
**Tested: 64031f6** (port/5c10a on rust-slice 2d12e81), all bar phases but seed1. Rows on pareto1:
`~/sp19/sa-rust-ids-work/sa-port-182/bar-5c10a/` (summary copied to `~/sa-rust-ids-work/sa-port-183/bar/`); `.so` sha256
9c6b62bc…. Base suite rows: 5c9c's (`sa-port-181/bar-5c9c/suite`).
**Landed:** the commit carrying this file, on rust-slice, rebased on 2d12e81 (unchanged since the bar started). **Incoming
diff: none** (2d12e81..2d12e81). Between 64031f6 and the landed commit there is only this report, the handoff file and
port-ownership.md/.tsv (results/); the landing guard saw no source difference.

## The bar (sa-port-182/bar-5c10a on 64031f6)
1. **Suite by id against 5c9c's rows:** 5,991 passed, 127 failed, 23 skipped, 18 xfailed, 6,159 ids. New 0, gone 0,
   **changed outcome 1**: `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`,
   passed -> failed, **explained below: the test's planted memo keys on `id(self)`; it already fails on base under Rust 5 of 10
   runs.** Passed splits as 5,990 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`).
   S's standing: S's gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz, plus loop, zero, cert and scope:** answers and state MATCH, and every control MATCHes. Answers
   unchanged: dev 31cd0945c07f02a6 (1,985 q), fuzz 173502b6ef285ad6 (3,000 q), loop 09238b2537e54383 (420 q), zero
   d9ed3534a2093027 (854 q), cert 6a09c059eb266747 (61 q), scope 12e06b0586faee40 (169 q), all equal to 5c9c's. The Rust runs
   made 0 Python solvers, reentry 0. The snapshot digest is equal at the switch on all six (below).
3. **Plants:** 11 of 11 caught (table below), counting memo_check, the suite and test_factcache_core.py. The bar's live
   comparison alone catches 201 (dev, fuzz, cert) and 204 (dev, fuzz); the suite catches 200 (**the inventory's planted bug, a
   put lost on a shared DictCache**: 2 tests), 203, 205, 208 and 210. Void on every workload: 200, 203, 205, 206, 209. Caught by
   the test only: 202, 206, 209.
4. **Quiet handlers in the suite:** 39 rows in 2 tests, the same multiset as 5c9c's:
   - `_consistent` AttributeError: 34 on `_ok` and 4 on `_rb_clauses` (the named needs-internals case);
   - `Engine._build_context` "Already mutably borrowed": 1, in `test_protocol_on_fuzz` (the 46-stub cause).

   The `caught` rows per id match base (0 ids differ). TermFault 0 in the suite log. The 12 live handler files and the 4
   extra-workload handler files have 0 rows, and so do all 22 plant handler files. The 7 suite-plant runs give the same 39-row
   multiset and 0 `caught` differences.
5. **Known differences in answers or read state:** none. The one changed suite outcome is the id-reuse artifact (below), not a
   value. Tests: 604 passed, 0 failed (5c9c's 16 files plus test_factcache_core.py). `relations_direct.py` exited 0.

## The changed outcome: `test_public_comparison_catches_a_planted_history_dependence` (bar item 1)
**Cause: the test's planted memo keys on `id(self)`, and CPython reuses a dead engine's address. A test artifact, not a Rust
difference, and it already fails on base under Rust.** Evidence: `~/sa-rust-ids-work/sa-port-183/idreuse/` (evidence.txt,
rates.txt, and the scripts), on orion.
- The test (tests/test_public_incremental.py:185-204) patches `Engine.ask` with a memo keyed `(id(self), proposition)`, and
  `run_stream` (:134-141) builds a fresh engine for each op and drops it. The leak should give 2 differences (op 1: warm True,
  fresh False; op 3: warm None, fresh True).
- **Fresh engines' ids** (pytest with a logging plugin that wraps `_fresh_engine`): on 64031f6 under Rust, op 1's fresh engine
  gets op 0's dead engine's address and op 3's gets op 2's, so those fresh engines read the memo's earlier answer and match the
  warm engine: 0 differences in that run. The bar's run had 1 (one of the two reuses).
- **Base 2d12e81 under Rust fails it too:** the same reuse (op 3's fresh engine at op 2's address) gave 1 difference.
  **Over 10 runs each: base Rust failed 5 of 10** (differences 2 1 1 2 2 2 2 1 1 1), 64031f6 Rust failed 10 of 10 (0 or 1).
  Python passed 10 of 10 on both trees (on 64031f6 Python, op 3's fresh engine did reuse op 1's address, but its proposition
  differs, so the key misses). Base's bar row passed by chance. The same 64031f6 source passed it under plant 203's suite run
  (`failed -> passed` against this bar's plain suite): the outcome moves with allocation, not with the code under test.
- **With every fresh engine held alive** (no address can be reused), all four (64031f6 and 2d12e81, Rust and Python) give
  exactly 2 differences with the same values, `[(1, True, False), (3, None, True)]`. So the comparison itself catches the plant
  on Rust, as on Python.
- **Why the rate rose:** the engine is freed promptly on all four (a weakref is dead on `del`, with gc disabled; no cycle).
  What changed is allocation: on base `cache` and `custom_cache` are Python `DictCache` instances, `__basicsize__` 16 like
  `Engine`'s, so they share its allocator size class; on 64031f6 they are `sa_solver.DictCache`, `__basicsize__` 160, in another
  class. So which freed slot the next `Engine` takes changed, and it now more often takes the dead engine's.
- No fix and no bar rerun: nothing in the crate gives a different value. The test isn't edited (state rule, item 4). For the
  backend PR list: the test is flaky on base under Rust already (5 of 10); it would need a key that isn't an address (e.g. a
  per-engine token) to be stable, and that is a test change for Tilo's call, not this step's.

## The switch digest (planner's state ruling, item 3)
`memo_check.py WL rust` at PYTHONHASHSEED=0 on base Rust (2d12e81, a worktree with its own build,
`~/sa-rust-ids-work/sa-port-182/base`, with this step's memo_check.py copied in) and on 5c10a Rust (18d2bb6, a fresh build;
the code memo_check runs is unchanged to 64031f6, which adds only the `fc:py_key` counter), on orion. On base the two stores are
Python dicts in Python `DictCache`s; on 5c10a they are `FactView`s. **`memo_check --cmp` gives MATCH on all six workloads**:
answers, registry digest, the 5c9c memos, and the two fact stores' sizes, contents and insertion order. The answers and
digests equal 5c9c's table (port-5c9c.md). Fact stores at the end:

| workload | `cache.store` | `custom_cache.store` | views == `fc_snapshot` | empty after clear |
|---|--:|--:|---|---|
| dev | 16 | 0 | yes | yes |
| fuzz | 7 | 5 | yes | yes |
| loop | 12 | 0 | yes | yes |
| zero | 1 | 0 | yes | yes |
| cert | 26 | 0 | yes | yes |
| scope | 1 | 0 | yes | yes |

Rows: `~/sa-rust-ids-work/sa-port-182/mc/{base,new}`.

## Plants
Fired = `rel:plant_fired` (memo_check, one full pass plus the 200-query rerun, 64031f6 build). Caught by: C = not empty after
`clear()`, S = registry digest, E = the stores' sizes/contents/order, V = view against `fc_snapshot`, T = test_factcache_core.py,
D = the bar's plants/extra comparison (live.py, answers and state). Rows: `~/sa-rust-ids-work/sa-port-182/mc/pl-*`,
table `mc/plants-table.txt`.

| plant | row | dev | fuzz | loop | zero | cert | scope | suite (fired, changed) | caught by |
|---|---|---|---|---|---|---|---|---|---|
| fc-shared-sync-is (200, **the inventory's planted bug: a put lost on a shared DictCache**) | `sync` on a shared cache | 0 | 0 | 0 | 0 | 0 | 0 | 152, 2 | **the suite** (`test_shared_cache_with_the_same_settings_shares_hits`, `test_shared_cache_created_before_a_registration`), T; void on every workload (none shares a cache) |
| fc-put-new-drop (201) | `put` of a new node | 418 S E D | 750 S E D | 15 S E | 13 S E | 121 S E D | 13 S E | not run | memo_check every workload, the bar on dev, fuzz, cert, T |
| fc-new-no-maxsize (202) | `DictCache(maxsize)` | 2 | 2 | 2 | 2 | 2 | 2 | not run | **T only** (the default maxsize is what every workload builds) |
| fc-sync-no-clear (203) | `sync` on a new epoch | 0 | 0 | 0 | 0 | 0 | 0 | 365, 16 | the suite (test_history R2/R4, test_registry_versioning), T; void on every workload (no registry change) |
| fc-facts-first (204) | `facts` lookup | 378 S D | 666 S D | 36 | 0 | 95 | 0 | not run | memo_check and the bar, dev and fuzz; fires but changes nothing read on loop and cert; T |
| fc-get-no-default (205) | `get` default | 0 | 0 | 0 | 0 | 0 | 0 | 15, 12 | the suite (test_engine, test_registry_versioning, ...), T; void on every workload (no `get`) |
| fc-no-bound (206) | `maxsize` bound | 0 | 0 | 0 | 0 | 0 | 0 | 0, 0 | **T only**; nothing in the workloads or the suite fills a cache to its bound |
| fc-custom-put-drop (207) | `custom_cache` `put` | 65 | 102 S E | 15 | 13 | 26 | 13 | not run | memo_check on fuzz (the only workload with custom predicates), T |
| fc-view-drop-last (208) | the view | 8 S E V | 8 S E V | 8 S E V | 8 S E V | 8 S E V | 8 S E V | 146, 11 | memo_check every workload, the suite, T (live.py reads no view: fired 0 there) |
| fc-rollback-skip (209) | `_fc_rollback` | 0 | 0 | 0 | 0 | 0 | 0 | 696, 0 | **T only**; void on every workload (refused 0); fires in the suite and changes no outcome |
| fc-clear-skip (210) | `store.clear()` | 2 C | 2 C | 2 C | 2 C | 2 C | 2 C | 106, 8 | memo_check every workload, the suite, T (live.py never clears: fired 0 there) |

Fired counts per workload are memo_check's; the bar's plant runs (live.py, dev and fuzz, and extra on loop, zero, cert, scope)
give the same picture on one pass, except that on scope every plant read 0 fired in the bar's extra runs (memo_check fires 201,
202, 207, 208, 210 there), so the bar's scope plant column is void and memo_check carries scope. **Void on every workload: 200,
203, 205, 206, 209** (no shared cache, no epoch change, no `get`, no bound, refused 0). **Caught by the test only: 202, 206,
209.** No plant is void overall. The suite ran under the five void plants plus 208 and 210 (SUITE_PLANTS=`zero`): 206 doesn't
fire there and 209 fires 696 times without moving an outcome; the other five are caught.

## Reached (counters on the unplanted 5c10a run, memo_check: one full pass plus the 200-query rerun)
| workload | `fc:py_facts` | `fc:py_put` | `fc:py_key` | `fc:key_eq` | `fc:py_sync` | `fc:view` | `fc:clear` | `fc:new` | `fc:py_get` | `fc:full` | `fc:rollback` |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| dev | 435 | 65 | 441 | 8 | 2 | 8 | 2 | 2 | 0 | 0 | 0 |
| fuzz | 789 | 102 | 838 | 10 | 2 | 8 | 2 | 2 | 0 | 0 | 0 |
| loop | 140 | 15 | 144 | 0 | 2 | 8 | 2 | 2 | 0 | 0 | 0 |
| zero | 2 | 13 | 7 | 0 | 2 | 8 | 2 | 2 | 0 | 0 | 0 |
| cert | 121 | 26 | 125 | 0 | 2 | 8 | 2 | 2 | 0 | 0 | 0 |
| scope | 5 | 13 | 11 | 0 | 2 | 8 | 2 | 2 | 0 | 0 | 0 |

`fc:new` 2 is the engine's two caches; `fc:view`, `fc:clear` and `fc:py_sync` are memo_check's own reads and clears plus the
engine's `_check_version`. Rows: `~/sa-rust-ids-work/sa-port-182/mc/new2`.

**Which moved items are reached, and by what:** `cache.store` (`facts`, `put`, `sync`, the view, `clear`) by every workload;
`custom_cache.store` filled only by fuzz (5 entries; the only workload with custom predicates), its `facts`/`put` path reached
everywhere (plant 207 fires on all six); `get`, the `maxsize` bound (`fc:full`), an epoch change in `sync` (plant 203), a shared
cache (plant 200) and the rollback (`fc:rollback`; refused 0 on every workload) only by test_factcache_core.py. Counters shown to
fire before quoting their zero: every `fc:*` in test_factcache_core.py's Rust run (`test_counters_fire` asserts each).

`fc:key_eq` counts the key `==` a lookup runs when identity doesn't settle it; the keys are SymPy objects, so it is a callback
into Python, as Python's dict makes the same call. It goes when the keys are Rust term ids (conversion pass).

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Share of all queries kept per reason, on the Rust run, against 5c9c's bar.

| workload | queries | out-of-scope | refused | other named exceptions | base |
|---|--:|--:|--:|--:|---|
| dev | 1,985 | 24 (1.21%) | 0 | 0 | the same |
| fuzz | 3,000 | 0 | 0 | 0 | the same |
| zero | 854 | 0 | 0 | 0 | the same |
| cert | 61 | 0 | 0 | 0 | the same |
| loop | 420 | 0 | 0 | 0 | the same |
| scope | 169 | 0 | 0 | 0 | the same |

**No share rose.**

## State: each container 5c10a's rows touch (planner's state ruling, 8 Nov)
| container | decision | readers past 5c10a | inventory row |
|---|---|---|---|
| `Engine.cache.store` | **moved to Rust-native** (factcache.rs `FactCache`, registered as `sa_solver.DictCache`; insertion order kept, `maxsize` 200,000 as Python, `fc:full`); public reads through the read-only `FactView`; a cache shared by several engines (engine.py:98, public) is one Rust object | `is_`, `is_many`, `_put_result` (`facts`/`put`), 5c10c; `_check_version` (`sync`), `_settings_changed` (`store.clear()`), `Engine.__init__`, 5c10d; the registry's `Engine.memos` (view, public); tests read the view | INVENTORY-state.md :197, :285-287; tsv "state: Engine.cache.store" |
| `Engine.custom_cache.store` | **moved to Rust-native** (the same class) | `_is_custom` (`facts`/`put`), 5c10c; as above for 5c10d | :197, :285-287; tsv "state: Engine.custom_cache.store" |
| `_journaled_put` (term_live wiring) | **removed on the Rust backend**: `_Mark` rolls the native caches back by their own mark | `SLICE_FACTCACHE=py` only | :230; tsv "wiring: _journaled_put" |

**Snapshot digest at the switch: equal on all six workloads** (above). `fc_snapshot` (factcache.rs, test-only) reads each store
itself; the views equal it on every workload (`fc_view_bad` empty).

## The cache tests (the inventory's 39 + 9 test reads)
On orion (Rust, sa-port-182 `t1/`): the 9 cache-reading test files gave 127 passed and 3 failed, the same 3 as base
(`NotImplementedError: no provenance` x2, `_cowner`). In the bar's suite: tests/test_registry_versioning.py 50 passed, tests/test_memos.py 8, tests/test_p2_review.py 4, tests/test_engine.py 12,
tests/test_extensibility.py 9, tests/test_lazy_atoms.py 2, tests/test_history.py 136 passed (15 skipped, 1 xfailed), all unedited;
tests/test_writeback_provenance.py 30 passed, 3 failed, the same 3 as on base. No test reads these stores in a way the
view breaks, so none goes on the needs-internals list.

## Module count
**14 of 32, unchanged** (STATUS "Counted modules"). engine.py doesn't count whole; this step moves state and one class.

## Owed-list additions
- `fc:key_eq` is a callback into SymPy's `__eq__` from the fact caches' lookups (fuzz 10 a pass). It goes with the keys
  becoming Rust term ids (conversion pass).
- `fc:rollback`, `fc:full`, `fc:py_get`, the epoch path in `sync` and a shared cache are reached only by test_factcache_core.py,
  no workload: plants 200, 203, 205, 206 and 209 are void on every workload and caught by the test only.
- `test_public_comparison_catches_a_planted_history_dependence` is flaky under Rust on base already (5 of 10) and fails 10 of
  10 here, from id reuse (above). The test is unedited; a stable form keys the planted memo on something other than `id()`.

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
- a workload reaching `get`, the `maxsize` bound, an epoch change, a shared cache or a rollback (test_factcache_core.py covers
  all five);
- the full suite under plants 201, 202, 204 and 207 (SUITE_PLANTS was `zero`: the five void ones plus 208 and 210, which fire
  0 in live.py).

Other notes:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals
  (failed on this bar as on base). This step doesn't touch it.
- Quiet catches at engine.py:1906: not counted separately in this bar; the suite's `caught` rows per id are compared above (0 ids differ).
- The stub-spec test for plant 177 (5c9a) and `em:foreign`'s firing check (5c9c) stay on the owed list.
