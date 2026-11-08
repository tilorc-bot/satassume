# Step 5c9c: the engine memos Rust works on, Rust-native: `_kids`, `_qcones`, `_glue_adapters`, `_xbasis`, `splits`, with `_query_cone` (issue 323)

## What moved
Inventory part 5's 5c9c row (sa-port-147, INVENTORY-state.md :281-284; container rows `_kids` :28, `_qcones` :55,
`_glue_adapters` :65, `splits` :193, `_xbasis` :196): containers `_kids`, `_qcones`, `_glue_adapters`, `_xbasis`, `splits`;
row `_query_cone` (5c7-move ruling) and the relations_core memo paths that fill `_glue_adapters`/`_xbasis`. Classified from the
code (HANDOFF-sa-port-179.md), then:
- **Already Rust before this step, the memos still Python objects:** relations_core `number_basis` (`_xbasis`) and
  `guarded_adapters` (`_glue_adapters`), relevance.rs `part_consistent`/`relevant` (`splits`, 5c8, through the AnswerMemo's
  methods, `rv:cb_memo`). `_query_cone` was a callback from budget.rs (`bud:cb_query_cone`).
- **Moved to Rust-native state** (engmemo.rs): `EngineMemo`, an insertion-ordered map with Python's dict lookup (the key's
  hash, then identity or `==`, `em:key_eq`) and AnswerMemo's `maxsize`/`put`. Order is kept exactly (Vec plus hash index; no
  single deletes exist), so no order exception is needed. A `MemoSlot` data descriptor on `Engine` for each of the five names
  converts whatever is assigned (dict or AnswerMemo, keeping `maxsize`) into an `EngineMemo` (`em:slot_set`), so
  `Engine.__init__` (Python, 5c10d) and harness/state.py:91's reassignment of `eng.splits` need no edit. `_qcones` is emptied
  at 50,000, as Python (`em:full`). Installed by session_live `_install_engmemos` (`SLICE_ENGMEMOS`, default rust).
- **Rust readers go native:** `number_basis` and `guarded_adapters` (relations_core.rs) and `part_consistent`/`relevant`
  (relevance.rs) read and write through `engmemo::get/set/put/first`; the `rv:cb_memo` ticks for `splits` are gone. A memo
  that isn't an `EngineMemo` (ref.py's engine, a test's own dict) goes through its Python methods (`em:foreign`, 0 on every
  workload).
- **`_query_cone` ported** (budget.rs `query_cone`, in Python's order: objs, link, sums, union, zero_args), called natively by
  `within_budget` (`bud:query_cone`); `bud:cb_query_cone` is 0 on every workload. Python's `_query_cone` (engine.py:1726)
  stays for PY_BUDGET and the pure-Python default (`'_query_cone'` is in session_live `_BUDGET_METHODS`).
- **Python readers left (crossings, counted and named):** `Engine._struct` reads and writes `_kids` through the view
  (`em:py_kids`) and passes `_glue_adapters` as `memo` (Rust then reads it natively), and `_drop_cones` clears `_kids`,
  `_qcones`, `_glue_adapters`: both 5c10c. `Engine.__init__` assigns all five (`em:slot_set`), and `_settings_changed`,
  `_check_version` and `_drop_set_memos` clear `_xbasis`/`splits`: 5c10d. harness/state.py:91 reassigns `splits` (tooling,
  `em:slot_set`). The views are the `Engine` attributes themselves, so `Engine.memos` (names, sizes, items, clear) reads
  Rust's maps. `_Mark` skips native views, so it no longer rolls these five back on a fault; their entries are pure functions
  of (object, settings, epoch).
- **Counters** (session.rs): `em:py_kids`..`em:key_eq` 250-258, `bud:query_cone` 259 (NAMES is 260). `BUD_CB_QUERY_CONE` (160)
  is retired. **Plants** (relations_core.rs `rel_plant`): 190-198, `_MEMO_PLANTS` in session_live.py.
- **New test:** test_engmemo_core.py (11 passed), Python against Rust in separate processes, cases cert, settings, xbasis,
  sums, kids, splits: Python == Rust on every case, the counters fire, and all 9 plants fire and are caught.
- **memo_check.py** records the five memos (`em_sizes`, `em_content` sorted, `em_order` under one PYTHONHASHSEED,
  `em_view_bad` from `sa_solver.em_snapshot`, test-only) and checks them empty after clear. 0f8af2c fixes its key repr: `splits`
  keys hold a bare `object()` sentinel whose repr carries an address, which made dev's and zero's `splits` content differ
  between any two processes; it is now written `<object>`.

## SHAs
**Tested: 0f8af2c** (port/5c9c on rust-slice 2553a68), all bar phases but seed1. Rows on pareto1:
`~/sp19/sa-rust-ids-work/sa-port-181/bar-5c9c/`; `.so` sha256 6d726e49…. Base suite rows: 5c9b's (`sa-port-177/bar-5c9b/suite`).
**Landed:** the commit carrying this file, on rust-slice, rebased on 2553a68 (unchanged since the bar started). **Incoming
diff: none** (2553a68..2553a68). Between 0f8af2c and the landed commit there is only this report and port-ownership.md/.tsv
(results/); the landing guard saw no source difference. 5c9c's is the first clean bar of the two queued, so it lands before
the 6g c3-c5 stack (sa-port-175), which rebases onto it.

## The bar (sa-port-181/bar-5c9c on 0f8af2c)
1. **Suite by id against 5c9b's rows:** 5,992 passed, 126 failed, 23 skipped, 18 xfailed, 6,159 ids. New 0, gone 0,
   changed outcome 0. Passed splits as 5,991 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`).
   S's standing: S's gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz, plus loop, zero, cert and scope:** answers and state MATCH, and every control MATCHes. Answers
   unchanged: dev 31cd0945c07f02a6 (1,985 q), fuzz 173502b6ef285ad6 (3,000 q), loop 09238b2537e54383 (420 q), zero
   d9ed3534a2093027 (854 q), cert 6a09c059eb266747 (61 q), scope 12e06b0586faee40 (169 q). The Rust runs made 0 Python
   solvers, reentry 0. The snapshot digest is equal at the switch on all six (below).
3. **Plants:** 9 of 9 caught (table below), counting memo_check and test_engmemo_core.py; the bar's live comparison alone
   catches 193 (dev, fuzz: answers) and 198 (dev: session count). 194 is void on every workload and 197 fires but is caught
   only by the test (T).
4. **Quiet handlers in the suite:** 39 rows in 2 tests, the same multiset as 5c9b's:
   - `_consistent` AttributeError: 34 on `_ok` and 4 on `_rb_clauses` (the named needs-internals case);
   - `Engine._build_context` "Already mutably borrowed": 1, in `test_protocol_on_fuzz` (the 46-stub cause).

   The `caught` rows per id match base (0 ids differ). TermFault 0 in the suite log. The 12 live handler files and the 4
   extra-workload handler files have 0 rows, and so do all 18 plant handler files.
5. **Known differences in answers or read state:** none new. 5c9b's `_SPLIT` len difference Python vs Rust stands
   (port-5c9b.md, knowledge_live's per-call `Pattern`). Tests: 591 passed, 0 failed (5c9b's 15 files plus
   test_engmemo_core.py). `relations_direct.py` exited 0.

## The switch digest (planner's state ruling, item 3)
`memo_check.py WL rust` at PYTHONHASHSEED=0 on base Rust (2553a68, a worktree with its own build,
`~/sa-rust-ids-work/sa-port-180/base`, with this step's memo_check.py copied in) and on 5c9c Rust (0f8af2c's source, a fresh
build), on orion. On base the five are Python dicts and an AnswerMemo on the engine; on 5c9c they are the `EngineMemo` views.
**`memo_check --cmp` gives MATCH on all six workloads**: answers, registry digest, and the five memos' sizes, contents and
insertion order:

| workload | queries | answers | digest | `_kids` | `_qcones` | `_glue_adapters` | `_xbasis` | `splits` | views == maps | empty after clear | rerun of 200 the same |
|---|--:|---|---|--:|--:|--:|--:|--:|---|---|---|
| dev | 1,985 | c9cf2db177fb842d | fa58cc766d98d539 | 271 | 615 | 1 | 2 | 145 | yes | yes | yes |
| fuzz | 3,000 | 7b70c27d5415d320 | c322be409740fe5e | 2,732 | 8,621 | 1 | 6 | 1,766 | yes | yes | yes |
| loop | 420 | 157ced0aa6f9823f | c8fa633c2526d52e | 49 | 149 | 0 | 0 | 10 | yes | yes | yes |
| zero | 854 | 1c3f3090a3f172c6 | f409711365f18111 | 76 | 277 | 1 | 1 | 77 | yes | yes | yes |
| cert | 61 | c8e58c56d2ac2beb | 124879cd9aca401c | 104 | 184 | 1 | 0 | 31 | yes | yes | yes |
| scope | 169 | f2fd056234f29d49 | 170d770cf3b65109 | 53 | 125 | 1 | 2 | 27 | yes | yes | yes |

Answers and digests are equal to 5c9b's own (port-5c9b.md). (memo_check's answer hash isn't live.py's.) Rows:
`~/sa-rust-ids-work/sa-port-181/mc/`.

## Plants
Fired = `rel:plant_fired` (memo_check counts copy, `~/sa-rust-ids-work/sa-port-181/memo_check-counts.py`, kept out of the
landing source). Caught by: C = not empty after `clear()`, S = registry digest, E = the five memos' sizes/contents/order,
A = answers (memo_check, against the same workload's unplanted 5c9c run), T = test_engmemo_core.py, D = the bar's
plants/extra comparison (live.py, answers and state). Rows: `sa-port-181/pl/`.

| plant | row | dev | fuzz | loop | zero | cert | scope | caught by |
|---|---|---|---|---|---|---|---|---|
| em-qcones-clear-skip (190, **the inventory's planted bug: `_drop_cones` not clearing `_qcones`**) | `_qcones` clear | 2 C | 2 C | 2 C | 2 C | 2 C | 2 C | memo_check every workload, T (`settings:budget`, the settings change); bar's live: fired 1, MATCH (live.py never reads `_qcones` after the clear) |
| em-kids-set-drop (191) | `_kids` store | 965 S E | 35,822 S E | 170 S E | 445 S E | 1,026 S E | 480 S E | memo_check every workload, T |
| em-glue-no-store (192) | `guarded_adapters` memo | 226 S E | 12,608 S E | 0 | 387 S E | 482 S E | 146 S E | memo_check every workload but loop (no adapters there), T |
| em-xbasis-first (193) | `number_basis` memo | 44 S A D | 1,057 S E A D | 0 | 641 | 0 | 40 | memo_check and the bar, dev and fuzz; fires but changes nothing read on zero and scope; T |
| em-splits-no-bound (194) | `splits` `put` bound | 0 | 0 | 0 | 0 | 0 | 0 | **T only**; the workloads' AnswerMemo never fills |
| em-qcone-no-sums (195) | `query_cone` sums | 635 E | 9,343 S E | 226 E | 358 S E | 368 | 250 E | memo_check every workload but cert (fires, nothing read changes), T |
| em-qcone-key-f (196) | `query_cone` key | 3,314 S E | 12,634 S E | 1,440 E | 3,574 S E | 488 S E | 1,328 S E | memo_check every workload, T |
| em-slot-no-maxsize (197) | `MemoSlot` conversion | 5 | 5 | 5 | 5 | 5 | 5 | **T only** (the harness form, AnswerMemo(4)); no workload fills `splits` to its bound |
| em-splits-put-drop (198) | `splits` `put` | 1,010 S E | 3,136 S E | 360 S E | 922 S E | 122 S E | 332 S E | memo_check every workload, the bar on dev (session count), T |

Fired counts are memo_check's (one full pass plus the 200-query rerun); the bar's plant runs give the same picture on one
pass. **Void on every workload: 194.** Caught by the test only: 194 and 197. No plant is void overall. The full suite didn't run
under any 5c9c plant. The `_qcones` bound (50,000, `em:full`) has no plant of its own; no workload reaches it.

## Reached (counters on the unplanted 5c9c run, memo_check: one full pass plus the 200-query rerun)
| workload | `bud:query_cone` | `bud:cb_query_cone` | `bud:within_budget` | `em:py_kids` | `em:key_eq` | `em:slot_set` | `em:foreign` | `em:full` |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| dev | 3,314 | 0 | 862 | 1,545 | 2,932 | 5 | 0 | 0 |
| fuzz | 12,634 | 0 | 3,358 | 41,978 | 7,379 | 5 | 0 | 0 |
| loop | 1,440 | 0 | 360 | 324 | 1,214 | 5 | 0 | 0 |
| zero | 3,574 | 0 | 909 | 661 | 3,225 | 5 | 0 | 0 |
| cert | 488 | 0 | 122 | 1,448 | 120 | 5 | 0 | 0 |
| scope | 1,328 | 0 | 332 | 698 | 1,138 | 5 | 0 | 0 |

`em:py_glue` and `em:py_qcones` are 6 and `em:py_xbasis` and `em:py_splits` 5 on every workload: memo_check's own view reads
(items, clear, the empty checks), plus one clear on the first two (`_drop_cones`, not attributed separately). `em:py_kids`
includes the same 5 reads; the rest is `_struct`'s crossing. `em:slot_set` 5 is `Engine.__init__` assigning the five.

**Which moved items are reached, and by what:** `_kids`, `_qcones`, `splits` and `_query_cone` by every workload;
`_glue_adapters` by every workload but loop; `_xbasis` by dev, fuzz, zero and scope (plant 193 fires there), not loop or cert;
`splits`' bound, the `MemoSlot` maxsize path and `_qcones`' bound (`em:full`) only by test_engmemo_core.py.
Counters shown to fire before quoting their zero: `em:full`, `em:slot_set`, `em:py_*` and `bud:query_cone` in
test_engmemo_core.py's Rust run (it asserts each fires). **`em:foreign` is not shown to fire anywhere**, so its 0 proves
nothing yet. `bud:cb_query_cone` is retired and its zero is by construction (no call site left).

`em:key_eq` counts the key `==` a lookup runs when identity doesn't settle it; the keys are SymPy and `P` objects, so it is a
callback into Python, as Python's dicts make the same call. It goes when the keys are Rust term ids (conversion pass).

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Share of all queries kept per reason, on the Rust run, against 5c9b's bar.

| workload | queries | out-of-scope | refused | other named exceptions | base |
|---|--:|--:|--:|--:|---|
| dev | 1,985 | 24 (1.21%) | 0 | 0 | the same |
| fuzz | 3,000 | 0 | 0 | 0 | the same |
| zero | 854 | 0 | 0 | 0 | the same |
| cert | 61 | 0 | 0 | 0 | the same |
| loop | 420 | 0 | 0 | 0 | the same |
| scope | 169 | 0 | 0 | 0 | the same |

**No share rose.**

## State: each container 5c9c's rows touch (planner's state ruling, 8 Nov)
| container | decision | readers past 5c9c | inventory row |
|---|---|---|---|
| `Engine._kids` | **moved to Rust-native** (engmemo.rs slot `_kids`); the view is the `Engine` attribute | `_struct` (`em:py_kids`) and `_drop_cones`, 5c10c; `Engine.__init__` (`em:slot_set`), 5c10d; tests/test_writeback_provenance.py:453 writes through the view (passes) | INVENTORY-state.md :28, :281-284; tsv "state: Engine._kids" |
| `Engine._qcones` | **moved to Rust-native** (slot `_qcones`, emptied at 50,000) with `_query_cone` (row moved) | `_drop_cones`, 5c10c; `Engine.__init__`, 5c10d | :55, :281-284; tsv "state: Engine._qcones", "Engine._query_cone" |
| `Engine._glue_adapters` | **moved to Rust-native** (slot `_glue_adapters`); `guarded_adapters` reads it natively | `_struct`'s pass-through and `_drop_cones`, 5c10c; `Engine.__init__`, 5c10d | :65, :281-284; tsv "state: Engine._glue_adapters" |
| `Engine._xbasis` | **moved to Rust-native** (slot `_xbasis`); `number_basis` reads it natively | `_settings_changed`, `_check_version`, `_drop_set_memos`, `Engine.__init__`, 5c10d; relations.py:711 on the Python backend only; ref.py's engine keeps its own dict (`em:foreign`) | :196, :281-284; tsv "state: Engine._xbasis" (new row) |
| `Engine.splits` | **moved to Rust-native** (slot `splits`, AnswerMemo `maxsize` kept); relevance.rs reads it natively | `_settings_changed`/`_drop_set_memos`, `Engine.__init__`, 5c10d; harness/state.py:91 reassigns it (converted by the descriptor; tooling); harness/checker.py:523 | :193, :281-284; tsv "state: Engine.splits" |

**Snapshot digest at the switch: equal on all six workloads** (above). `em_snapshot` (engmemo.rs, test-only) reads each map
itself; the views equal it on every workload (`em_view_bad` empty). No test reads these containers' internals in a way the
views break, so none goes on the needs-internals list.

## Registry tests on Rust
From the bar's suite (rust_plugin, handler_count; tree is the bar's clone): `tests/test_memos.py` 8 passed and
`tests/test_p4_review.py` 2 passed, including `test_every_adopted_memo_name_resolves`: **10 passed, unedited**. 5c8's `splits`
readers' tests, `tests/test_relevance.py`: 77 passed, unedited. `tests/test_registry_versioning.py` 50 passed.
`tests/test_writeback_provenance.py` 30 passed, 3 failed, the same 3 as on base (`NotImplementedError: no provenance` x2,
`_cowner`).

## Module count
**14 of 32, unchanged** (STATUS "Counted modules"). engine.py, relations.py and relevance don't count whole; this step moves
state and one function.

## Owed-list additions
- `em:key_eq` is a callback into SymPy's and `P`'s `__eq__` from the moved memos' lookups (fuzz 7,379 a pass). It goes with the
  keys becoming Rust term ids (conversion pass).
- `_qcones`' 50,000 bound has no plant; only test_engmemo_core.py reaches it (`em:full` fires there), no workload does.
- `em:foreign` has never been shown to fire (FALSE ZEROS): a test running Rust's `number_basis` on a plain-dict engine owes it.
- ref.py's engine keeps a Python `_xbasis` dict, read by Rust's `number_basis` through its methods (`em:foreign`, 0 on every
  workload).

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
- the full suite under any 5c9c plant (SUITE_PLANTS empty);
- the switch digest on budget (memo_check ran dev, fuzz, loop, zero, cert, scope);
- a workload reaching `splits`' bound, the `MemoSlot` maxsize path or `_qcones`' bound (test_engmemo_core.py covers all
  three);
- a firing check for `em:foreign`.

Other notes:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals
  (failed on this bar as on base). This step doesn't touch it.
- Quiet catches at engine.py:1906: not counted separately in this bar; the suite's `caught` rows per id match base.
- The stub-spec test for plant 177 (5c9a) stays on the owed list.
