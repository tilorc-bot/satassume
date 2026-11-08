# Step 5c10c: cones and construction in Rust; `_cones`, `_constructing` Rust-native (issue 323)

## What moved
Inventory part 5's 5c10c row (sa-port-147, INVENTORY-state.md): containers `_cones` and `_constructing`; rows `_struct`,
`_cone_info`, `_drop_cones` (engine.py :1603-1676), which the planner's follow-up (8 Nov ~06:17) held back from 5c7 and 5c9
until every container they touch is Rust-native. Work by sa-port-188 (770f7be); rebase, bar, ownership rows and landing by
sa-port-189.
- **The three rows run in budget.rs**, step for step as engine.py: `struct_` (`_struct`, :77), `cone_info` (`_cone_info`,
  :203), `drop_cones` (`_drop_cones`, :273), with pyfunctions `bud_struct`, `bud_cone_info`, `bud_drop_cones` (:287-305)
  bound in session_live's `_BUDGET_METHODS`. `union` calls `cone_info` and `struct_` directly, so 5c7's callbacks
  `bud:cb_struct` and `bud:cb_cone_info` are now 0. `budget_of` returns None past 2**60 (Python's fallback keeps `budget + 1`
  exact).
- **Moved to Rust-native state:** `_cones` (engmemo.rs slot 8, a map) and `_constructing` (slot 9, a set held as a map to None;
  `EngineMemo::remove`, Python `add`/`discard`/`update`; `set_add`/`set_discard`/`contains` for Rust). compile_loop.rs
  `core_visit` uses them natively. Both have 5c9c's `EngineMemo` view at the same Engine attribute (`_Mark` skips native views;
  the registry digest counts them). `cones_native()` (session_live.py :814; `SLICE_CONES=py` is the control).
- **5c9c's one temporary crossing is gone:** Python's `_struct` and `_drop_cones` read and wrote `_kids`/`_qcones`/
  `_glue_adapters` through their Rust views (the planner's follow-up, 8 Nov ~06:17); both now run in Rust on the slots.
  5c9c's plants `em-kids-set-drop` and `em-qcones-clear-skip` moved onto Rust's own writes (`store_kids`, `drop_cones`).
- **Callbacks into Python left, counted:** `struct_` reads the template rows (`bud:cb_templates`) and the ext reads
  (`bud:cb_ext`), removed by the state step with session_live.
- **Counters** (session.rs :379-397): 288-300 (NAMES is 301): `em:py_cones`, `em:py_constructing`, `bud:struct`,
  `bud:cone_info`, `bud:drop_cones`, `bud:cb_templates`, `bud:cb_ext`, `bud:struct_wide`, `bud:kids_hit`, `bud:cones_hit`,
  `bud:py_struct`, `bud:py_cone_info`, `bud:py_drop_cones`. **Plants** (relations_core.rs :313-327): 223-230, `_CONE_PLANTS`
  in session_live.py :835. The 6g stack added no numeric counters or plants, so there's no collision after the rebase.
- **New test:** test_cones_core.py, Python against Rust: 10 passed (every plant fires and moves a case; the two bound plants
  228, 229 are driven directly).
- **memo_check.py** records `_cones` and `_constructing` in `em_sizes`/`em_content`/`em_order` (`CONEMEMOS`) and checks their
  views against `em_snapshot`; it still runs on base trees.
- **Doc step (the planner's go, item 2), done by sa-port-188:** INVENTORY-state.md :302-312 records the five reader sites that
  keep Session.solver/xfer/truncated on Python, checked at 4215655: none moved. Function names were corrected against report
  7a65a8b: relations.py :1689 `_engage_transfer` (writes `s.xfer`), :1812 `sync_transfer`, :1851 `_xswitch`; engine.py :2145
  `_put_result`, :2248 `_note_budget`.

## SHAs
**Tested: XX** (port/5c10c on rust-slice eac4537, the 6g c3-c5 stack), XX. Rows on pareto1:
`~/sp19/sa-rust-ids-work/sa-port-189/bar-5c10c/` (end marker `end.txt`, written by the job); `.so` sha256 32cbde57….
Base suite rows: the stack's landing bar (`sa-port-187/bar-6g-c3c5r3/suite`); kept-share base its `extra/` and `live/`.
**Incoming diff before the bar** (4215655..eac4537, the 6g stack): knowledge_common_live.py, knowledge_core_live.py,
term/rows_tpl.rs, test_knowledge_core_shapes.py, results/port-6g.md; no file this step touches. Rebased without conflict,
rebuilt on orion, test_cones_core.py 10 passed.
**Landed:** XX

## The bar (sa-port-189/bar-5c10c on XX)
XX

## Plants
XX

## The switch digest (planner's state ruling, item 3)
`memo_check.py WL rust` at PYTHONHASHSEED=0 on base Rust (4215655, a worktree with its own build,
`~/sa-rust-ids-work/sa-port-188/base`) and on 5c10c Rust (this step before the rebase, same source as 770f7be; the rebase brought
no file this step or memo_check reads), on orion, from a copy of this step's memo_check.py (`sa-port-188/bin/`). On base the
two containers are a Python dict and set; on 5c10c they are `EngineMemo` views. **`memo_check --cmp` gives MATCH on all six
workloads** (rerun by sa-port-189, `~/sa-rust-ids-work/sa-port-189/mc/cmp-base-new.txt`): answers, registry digest, the 5c9c
memos, the fact stores, 5c10b's three, and `_cones`/`_constructing`' sizes, contents and insertion order. Views equal
`em_snapshot` on every workload (`em_view_bad` empty), every memo is empty after clear, and the 200-query rerun gives the same
answers.

| workload | queries | answers | digest | `_cones` | `_constructing` |
|---|--:|---|---|--:|--:|
| dev | 1,985 | c9cf2db177fb842d | fa58cc766d98d539 | 222 | 0 |
| fuzz | 3,000 | 7b70c27d5415d320 | c322be409740fe5e | 2,690 | 0 |
| loop | 420 | 157ced0aa6f9823f | c8fa633c2526d52e | 27 | 0 |
| zero | 854 | 1c3f3090a3f172c6 | f409711365f18111 | 56 | 0 |
| cert | 61 | c8e58c56d2ac2beb | 124879cd9aca401c | 103 | 0 |
| scope | 169 | f2fd056234f29d49 | 170d770cf3b65109 | 50 | 0 |

Base and 5c10c give the same row on every workload; every answers and digest value equals 5c10b's table (port-5c10b.md).
`_constructing` is empty at the end of every query on both, as Python. Rows: `~/sa-rust-ids-work/sa-port-188/mc/{base,new}`.

## Reached (counters on the unplanted 5c10c run, memo_check: one full pass plus the 200-query rerun)
| workload | `struct` | `cone_info` | `drop_cones` | `kids_hit` | `cones_hit` | `struct_wide` | `cb_templates` | `cb_ext` | `py_struct`/`py_cone_info`/`py_drop_cones` | `em:py_cones` | `em:py_constructing` |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| dev | 936 | 900 | 1 | 665 | 678 | 0 | 222 | 6 | 0 / 0 / 0 | 438 | 1,657 |
| fuzz | 33,036 | 24,181 | 1 | 30,304 | 21,491 | 0 | 190 | 0 | 0 / 0 / 0 | 749 | 3,745 |
| loop | 120 | 172 | 1 | 71 | 145 | 0 | 49 | 49 | 0 / 0 / 0 | 145 | 527 |
| zero | 337 | 854 | 1 | 261 | 798 | 0 | 63 | 0 | 0 / 0 / 0 | 6 | 744 |
| cert | 513 | 528 | 1 | 409 | 425 | 0 | 32 | 0 | 0 / 0 / 0 | 126 | 185 |
| scope | 240 | 212 | 1 | 187 | 162 | 0 | 28 | 12 | 0 / 0 / 0 | 8 | 175 |

`py_*` count the Python rows (PY_BUDGET and the pure-Python default only): 0 on the default Rust backend. `em:py_cones` and
`em:py_constructing` are Python's reads through the views: `is_` :1998/:2001 and `is_many` :2047/:2049 (5c10d), and `_Mark`
on `_constructing` (term_live.py :156, :189-190; the state step). Rows: `~/sa-rust-ids-work/sa-port-188/mc/new`.

**Which moved items are reached, and by what:** `_struct`, `_cone_info` and `_cones` by every workload (sizes above);
`_drop_cones` once per pass on every workload (memo_check's clear; with `_cones` empty there, so plant 226 MATCHes);
`_constructing` written and emptied in every query on every workload (`em:py_constructing` above). Not reached by any
workload: `_struct`'s wide-sum path (`struct_wide` 0, no sum wider than the default budget) and `_cone_info`'s over-budget fit
(plant 225 fires 0); both are reached by test_cones_core.py (budgets 3 and 6, wide sums). The bounds of `_kids` and `_cones`
(228, 229) are reached only by test_cones_core.py, driven directly. XX suite counts.

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
XX

## State: each container 5c10c's rows touch (planner's state ruling, 8 Nov)
| container | decision | readers past 5c10c | inventory row |
|---|---|---|---|
| `Engine._cones` | **moved to Rust-native** (engmemo.rs slot 8) | `is_` :2001, `is_many` :2049 through the view, counted `em:py_cones` (5c10d); the registry's `Engine.memos` (view, public); tests/test_writeback_provenance.py :444-454 read it through the view, unedited | INVENTORY-state.md part 5, 5c10c row; tsv "state: Engine._cones" |
| `Engine._constructing` | **moved to Rust-native** (slot 9, a set) | `is_` :1998, `is_many` :2047 through the view, counted `em:py_constructing` (5c10d); wiring: term_live.py `_Mark.add` :156 and `rollback` :189-190 (the state step); compile_loop.rs `core_visit` natively | the same; tsv "state: Engine._constructing" |
| `Engine._kids`, `_qcones`, `_glue_adapters` | Rust-native since 5c9c; **their crossing from Python's `_struct`/`_drop_cones` is gone** | as 5c9c's rows, less the two Python writers | tsv "state: Engine._kids", `_qcones`, `_glue_adapters` (crossing texts updated) |
| Session.solver, Session.xfer, Session.truncated | **kept Python to the named state step**, as the state rule and the planner's go (item 2) say; this step doesn't touch them | the five reader sites in INVENTORY-state.md :302-312 (above) | :302-312; tsv "state: Session.*" |

**Snapshot digest at the switch: equal on all six workloads** (above). `em_snapshot` (engmemo.rs, test-only) reads each map
itself; the views equal it on every workload.

## Module count
**14 of 32, unchanged** (STATUS "Counted modules"). engine.py doesn't count whole; 5c10d remains.

## Owed-list additions
- Plants 225 (`_cone_info` over-budget fit) and 230 (`_struct`'s wide-sum path) fire 0 on every workload; test_cones_core.py
  catches them. A workload with a sum wider than the default budget would reach them.
- Plants 228 and 229 (the `_kids`/`_cones` bounds) are test-only, driven directly in test_cones_core.py.
- `bud:cb_templates`/`bud:cb_ext`: `struct_`'s reads of the template rows and ext through Python, removed with session_live in
  the state step.
- TSV rows 10-15 (DictCache) and `state: Engine.cache.store`/`custom_cache.store` still name `is_`/`is_many`/`_is_custom`/
  `_put_result` as "5c10c" callers, from before 5c10 was split; by the current split those rows are 5c10d's. Left as they are
  for 5c10d to confirm when it reads them.

## Not run
XX
