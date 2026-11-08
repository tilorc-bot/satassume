# HANDOFF sa-port-173 (step 5c9a, memo registry), 8 Nov 2026

Branch port/5c9a, from origin/rust-slice 3611952. Head: the commit carrying this file (WIP code at a3226b9). Built on orion
and run on dev only. **No bar run yet. Not landed.** The 6g stack (sa-port-172, 0643e9c) started its bar at about 14:10 UTC
and is expected on rust-slice at about 17:10. 5c9a lands at its own bar (architect, 14:2x): rebase per the rule when it moves.

## Step 1: classification (traced, dev 1,985 q x 2 passes, py and rust; fuzz rust 1 pass)
Tool: `rust-spike/slice/memo_trace.py WL MODE --passes P`. Rows: ~/sa-rust-ids-work/sa-port-173/trace-{dev-rust,dev-py,fuzz-rust}.txt.
Per dev pass on Rust (pass 2 = pass 1):
- **Called back from Rust, per query (moved in this step):** `Engine.extensions` 989 and `Engine.relation_specs` 122
  (relevance.rs), `Engine.uninterpreted` 393 and `Engine.transfer` 35 (relations_core.rs), `Table.restamp` 2 (relevance.rs
  `keys_rel` on `_KEYS`/`_CONST`). After the change these run in Rust (memos.rs `setting`, `restamp`); rerun memo_trace to
  show 0 callbacks.
- **Python callers, conversion (stay):** `Engine.relation_specs` from convert.py `convert` 1,221 and `_engine_ask` 1,090;
  `Engine.relevance` from `_ask_general` 989; `Engine.discovery_budget` from convert.py `default_engine_settings` 1,221;
  `Table.restamp` from `_formula` 1 (`_FORMULAS`, conversion layer).
- **Slice wiring, per query:** `Memos.items` from term_live.py `_Mark.__init__` 27,660-29,304 and `_Mark.add` 14,652 (with
  `_path`/getters under it). `_Mark`'s per-query snapshot is parked for the conversion pass (state ruling); this step leaves
  it, except that `_Mark._note` now skips native views (term_live.py:145).
- **Import-time or once (stay out):** `Memos.__init__`, `Memos.adopt`, `adopt`, `_module_attr`, `owner_memos`(+getter) once
  per Engine, `Memos.table`, `Table.__init__`. `epoch.bump`: 2 per process on py (registry `deco` at import), 0 per query.
  `load_owners`, `module_locations`, `__getattr__`: harness and tests (one `__getattr__` via `_compat`). `Table.put`: 0 per
  query on dev (rules `_DEF_IMPL`; check fuzz).
- Fuzz rust rows: trace-fuzz-rust.txt (21 lines), not yet read.

## What's built (a3226b9)
- `solver_rs/src/memos.rs` (new): `TABLES` :43 (two Rust-native process memos Python never saw: relations_core `SPEC_ROWS`,
  constfield `ENCLOSURES`), `NativeTable` read-only view pyclass, `memo_install` :139 / `memo_uninstall` attach the views to
  `memos.PROCESS`, `memo_snapshot` :161 (test-only export from the maps), `restamp` :167, `setting` :180 (field read when
  type is exactly `Engine`, else the property, counted `memo:setting_prop`).
- Call sites: relevance.rs :385-386 (restamp), :599, :679, :731 (settings); relations_core.rs :1409, :1991, :2063.
- Bounds: `SPEC_ROWS_SIZE` relations_core.rs:2381 (was the literal 4096), `ENCLOSURES_SIZE` constfield.rs:189 (new bound
  100,000: ENCLOSURES had none; a behaviour change for a memo only, name it in the report).
- Counters session.rs:277-287: 230 `memo:native_clear`, 231 `memo:native_items`, 232 `memo:restamp`, 233 `memo:setting`
  (the crossing into Engine's fields, 5c10's container, removed by 5c10), 234 `memo:setting_prop`, 235 `memo:spec_full`
  (MEMO_FULL). NAMES/COUNTS grown to 236; 200-229 are "reserved:NNN" fillers (session.rs:54), skipped by `session_counts`.
  When the 6g stack lands, check whether it took any of 200-229 and merge.
- Plants relations_core.rs:212-227 and names :376-383, in session_live.py `_MEMO_PLANTS` :789: 170 memo-view-drop (the
  registry-view plant: SPEC_ROWS left out), 171 memo-clear-skip (ENCLOSURES' view doesn't empty), 172
  memo-restamp-no-stamp, 173 memo-set-transfer, 174 memo-set-uninterp, 175 memo-set-relspecs, 176 memo-set-ext, 177
  memo-spec-unbounded (expected void: nothing makes 4,096 specs; say so).
- Python: satassume/state/memos.py `Memos._native` :101, `attach` :121, `detach` :130; items/names/clear/`__repr__`
  include natives. Empty on the Python backend. session_live.py `_install_memos` :793, `SLICE_MEMOS=py` :919 skips it.
- `rust-spike/slice/memo_check.py WL MODE OUT.json` and `--cmp A B`: answers hash, registry digest (non-native tables of
  PROCESS and Engine.memos: name, key, len, stamp), view vs snapshot, empty after clear, rerun of 200 the same.

## Results so far (~/sa-rust-ids-work/sa-port-173/mc/)
- dev rust: view == snapshot (ENCLOSURES 1, SPEC_ROWS 2), cleared [], rerun_same true; answers equal py's.
- Registry digest py vs rust differs (_SPLIT, templates `_CACHE`, registry `_clauses_cache`/`_mro_cache`, `_UNDER_APPS`,
  euf `_class_ok`): the backends fill different tables, so this is not the switch. **The switch digest is base Rust
  (3611952) vs 5c9a Rust**: base tree is a worktree at ~/sa-rust-ids-work/sa-port-173/base-tree, build started detached
  (end marker ../base-build.done, log ../base-build.log), memo_check.py copied in. Run `memo_check.py dev rust` there with
  PYTHONPATH=base-tree:$W/sympy:$W/shim and cmp the `digest` with mc/dev-rust.json (answers and digest must be equal).
  Remove the worktree after (`git worktree remove`).

## Next
1. Base-vs-5c9a digest on dev, fuzz, loop, zero, cert (memo_check). Rerun memo_trace dev rust: settings/restamp from C = 0.
2. Plants: each with SLICE_SESSION_PLANT=NAME through memo_check (and live where answers move); 170-172 should show in
   view_ok/cleared/digest, 173-176 in answers (transfer only 35/pass on dev: may need fuzz or a workload; 176 ext None may
   only change relevance). Check counters fire (FALSE ZEROS).
3. Registry tests on Rust: tests/test_memos.py (all, incl. the three ids) and
   tests/test_p4_review.py::test_every_adopted_memo_name_resolves, under the rust plugin (see run_suite.sh for how).
   Note test_p4_review asserts `adopted <= PROCESS.items() names`: natives only add names, fine.
4. Bar per port-5c8.md; report results/port-5c9a.md; port-ownership.md/.tsv rows (state/memos.py 22, epoch 1, engine.py
   settings and engine_memos) with the classification above; STATUS module count (14 of 32 before).
