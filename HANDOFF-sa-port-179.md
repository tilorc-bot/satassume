# HANDOFF sa-port-179: step 5c9c (issue 323), the engine memos `_kids`, `_qcones`, `_glue_adapters`, `_xbasis`, `splits`

Branch port/5c9c from rust-slice 2553a68 (5c9b landed). One WIP commit: `rust-spike/slice/solver_rs/src/engmemo.rs`
(written, **not yet compiled or wired**) plus this file. No bar run, no build yet. The planner kept the stack cap (architect,
8 Nov ~16:00): 5c9c lands at its own bar, not stacked with sa-port-175's 6g stack; the later of the two rebases.

## Classification (step 1, read from the code; trace counts still owed)
| container | Python today | Rust today | decision |
|---|---|---|---|
| `_kids` | `Engine._struct` engine.py:1621-1636 (get/len/clear/setitem), `_drop_cones` :1604 | none (budget.rs `struct_weight` calls `_struct` back, `bud:cb_struct`) | move; `_struct` stays Python (5c10c) and works on the map through its Python methods: crossing `em:py_kids` |
| `_qcones` | `Engine._query_cone` :1726-1757, `_drop_cones` :1606 | none (budget.rs:93 `query_cone` calls it back, `bud:cb_query_cone`) | move, with `_query_cone` ported (5c7-move ruling) |
| `_glue_adapters` | passed as `memo` by `_struct` :1632 and `_query_cone` :1746; `_drop_cones` :1607 | relations_core.rs:2731 `guarded_adapters` get/set through the C API | move; Rust reads natively; `_struct`'s pass-through is a crossing (5c10c) |
| `_xbasis` | `_drop_set_memos` :1600 (5c10d); relations.py:711 (Python backend only) | relations_core.rs:2496 `number_basis` get/set | move |
| `splits` | `_drop_set_memos` :1597 (5c10d); harness/state.py:91 **reassigns** `eng.splits = AnswerMemo(n)`; harness/checker.py:523 | relevance.rs:643-672 `part_consistent`/`relevant` get/put (`rv:cb_memo`) | move |

## Design (engmemo.rs, read its header)
- `EngineMemo` pyclass: an insertion-ordered map with Python dict lookup (hash, then `is`/`==`, `em:key_eq`), `maxsize`
  (AnswerMemo `put`). Order kept exactly (Vec + hash index; no single deletes exist), so no order exception is needed.
  Python methods (get, put, `[]`, `[]=`, in, len, bool, clear, items, keys, values, iter) each tick `em:py_<container>`.
  `native`/`moved` getters: `_Mark` skips it, memo_check counts it.
- `MemoSlot(slot)` data descriptor on `Engine` for each of the 5 names: `__set__` converts the assigned dict/AnswerMemo
  (keeps `maxsize`) into an `EngineMemo` in `inst.__dict__` (`em:slot_set`); `__get__` converts a pre-install dict on first
  read. So Engine.__init__ (Python, 5c10d) and the harness's reassignment need no edit.
- Rust helpers `engmemo::{get,set,put,len,clear}`: native when `EngineMemo`, else the container's Python methods (`em:foreign`,
  e.g. ref.py's engine, a test's dict).
- `em_snapshot(memo)`: test-only export from the map itself.

## What's left, in order
1. **Constants.** session.rs:17 NAMES is `[&str; 245]` and COUNTS `[...; 245]` (:309): add "reserved:245".."reserved:249"
   then 250 `em:py_kids`, 251 `em:py_qcones`, 252 `em:py_glue`, 253 `em:py_xbasis`, 254 `em:py_splits`, 255 `em:slot_set`,
   256 `em:foreign`, 257 `em:full`, 258 `em:key_eq`, 259 `bud:query_cone`; size 260; `pub(crate) const EM_*`/`BUD_QUERY_CONE`
   after :299. Plants in relations_core.rs after :243 (u8) and in `rel_plant` (~:406) and `_MEMO_PLANTS` (session_live.py:786):
   190 `em-qcones-clear-skip` (EM_QCONES_CLEAR_SKIP, **the inventory's planted bug**), 191 `em-kids-set-drop`,
   192 `em-glue-no-store`, 193 `em-xbasis-first` (a `_xbasis` lookup answers the first entry: wrong value), 194
   `em-splits-no-bound` (test only, 20,000), 195 `em-qcone-no-sums`, 196 `em-qcone-key-f` (memo key ignores `link`),
   197 `em-slot-no-maxsize` (test only), 198 `em-splits-put-drop`. engmemo.rs already uses 190, 191, 194, 197.
   6g stack (origin/port/stack-6g-c3c5) has NAMES 200 and no plants >= 170: no clash.
2. **lib.rs**: `mod engmemo;` and `engmemo::register(m)?` beside memos.rs's register.
3. **budget.rs**: replace `query_cone` (:93-96, the callback) with the port of engine.py:1726-1757: key `(f, link)` (plant
   196: key `f`), `_qcones` via `engmemo::get/set`, bound 50,000 (`engmemo::clear`, tick EM_FULL), objs = set of
   `_kid(a)` over `glue_atoms(atoms)` if `eng._relation_specs` truthy else `atoms` (module globals via `global()`, as
   :98), with `link`: `link_objects(a.expr, specs, eng._glue_adapters)` for atoms with `pred in PRED_INDEX`; `sums`
   frozenset (plant 195: empty); `union(eng, objs, budget)` + `(sums, zero_args(atoms))`. Build `objs` as a PySet in
   Python's insertion order (union's weight is order-dependent). Add `#[pyfunction] bud_query_cone(eng, f, link)` with
   `py_method` fallback when the budget isn't an int; `within_budget` passes `budget` to it. session_live.py:732 add
   `'_query_cone': 'bud_query_cone'` (PY_BUDGET keeps Python's).
4. **relations_core.rs**: :2500-2501/:2563 `number_basis` -> `engmemo::get/set` (plant 193); :2743/:2747
   `guarded_adapters` -> `engmemo::get/set` (plant 192: skip the set). Update the comment at :2230.
5. **relevance.rs** :650-658, :665-671 -> `engmemo::get/put` (plant 198 on put); drop the `RV_CB_MEMO` ticks for
   `splits` (keep them for `_KEYS`/`_CONST`); update header :7-9.
6. **session_live.py**: `_install_engmemos()` setting `engine.Engine.<name> = sa_solver.MemoSlot(i)` for
   `engmemo::SLOTS` order (`_kids`, `_qcones`, `_glue_adapters`, `_xbasis`, `splits`), undo deletes them; call it from
   `_install_memos` (:796) under `SLICE_ENGMEMOS` (default rust). Update the 5c7/5c8 comments at :725 and :763.
7. **memo_check.py**: for the 5 names add a content row (`_canon`: sets sorted by repr, `Split` by its getters, adapters
   by type name) and, on Rust, `view == em_snapshot`; switch digest base Rust (a 2553a68 worktree with its own build) vs
   5c9c Rust on dev, fuzz, loop, zero, cert, scope.
8. **test_engmemo_core.py** (pattern: test_procmemo_core.py, Python vs Rust in separate processes): a settings change
   between queries (discovery_budget / relations) with `_qcones` cleared (plant 190 caught), `splits` bound 20,000 (194),
   harness `EngineConfig.make()` keeps `maxsize` (197), the tests' writes (`e._xbasis[S(5)] = ...`, `eng2._kids[...]`).
9. Build (`sh rust-spike/slice/build_solver.sh`), run the registry tests (tests/test_memos.py,
   tests/test_p4_review.py), tests/test_registry_versioning.py (reads `eng.splits[a].consistent`),
   test_relevance_core.py, test_relations_core.py, under rust_plugin, PYTEST_N="-n 4".
10. Plant screen, counters shown to fire, the bar as port-5c9b.md, report results/port-5c9c.md, port-ownership.md/.tsv.

## Open points to state in the report
- `_Mark` stops rolling back these five (as 5c9b's): a fault-time rollback leaves Rust's entries; they're pure functions of
  (object, settings, epoch).
- ref.py's engine keeps its own `_xbasis` dict (`em:foreign` when Rust's `_number_basis` runs on it).
- Crossings past 5c9c: `_struct` (`em:py_kids`, `em:py_glue` pass-through) and `_drop_cones` (5c10c); `_drop_set_memos`,
  `__init__` via `em:slot_set` (5c10d); the harness reassignment (`em:slot_set`, tooling).
