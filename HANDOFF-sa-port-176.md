# HANDOFF sa-port-176: step 5c9b, built and short-checked, no bar yet (issue 323)

Branch port/5c9b from origin/rust-slice e0ec542 (unchanged at handoff). Clone /home/tilo/dev/sa-port-7. Built on orion
(`sh rust-spike/slice/build_solver.sh`, clean, 13 warnings, all old ones).

## Done
1. **Classification (step 1), by `rust-spike/slice/proc_memo_trace.py WL py|rust`** on orion, rows in
   `~/sa-rust-ids-work/sa-port-176/trace/{dev,fuzz,loop,scope,zero,cert}-{py,rust}.txt` (base e0ec542 .so):
   - On Rust, **0 Python calls** of `want_of`, `_split`, `neighbourhood`, `closed_units`, `with_closed_units`, `sympy_atom`:
     every call is Rust's (session_live `_LOOP_FUNCS`/`_REL_FUNCS` switch the module functions). Rust counts equal Python's
     call counts, e.g. dev `ses:want_of` 5,257 = 2,362+597+2,298 py; `ses:split` 8,127; `rel:sympy_atom` 2,093; fuzz 51,089 /
     79,164 / 66,365; `rel:closed_units` dev 2,704, fuzz 16,727.
   - `neighbourhood`/`_NEIGH`: **0 on every workload, both backends**; its only caller is tests/test_engine.py:195-201.
   - Python readers of the containers past 5c9b: none in engine or wiring; registry (`memos.PROCESS` names/sizes/items/clear),
     `_Mark` (term_live.py:145, skips native views, so it now drops these tables, as the inventory says), tests:
     tests/test_engine.py:195 (neighbourhood), tests/test_p4_review.py:67-73 (swaps `PROCESS._adopted[..._SPLIT]` and restores:
     works with the view), rust-spike/slice/test_relations_core.py:1054-1072 (reads the *module* attributes `relations._SYMPY_ATOMS`
     /`_CLOSED`, which stay Python's, for Python's own functions: unaffected).
   - **Found, pre-existing (since 5c2): `_SPLIT`'s len differs Python vs Rust** (dev 743 vs 783, fuzz 1,718 vs 1,733, cert 64
     vs 65, loop 267/278, scope 106/112, zero 149/153); the other four sizes are equal. Rust's compile loop hands `_split` some
     distinct list objects Python doesn't. Only the registry's len reads it. 5c9a's switch digest compared Rust vs Rust for this
     reason; do the same (base Rust e0ec542 vs 5c9b Rust). Name it in the report as a known read-state difference, cause stated.
2. **Code (step 2-3), uncommitted before this handoff, now in the WIP commit:**
   - `solver_rs/src/procmemo.rs` (new): thread-local Rust maps WANT/SPLIT/NEIGH/CLOSED/ATOMS with Python-dict lookup semantics
     (`PyKeyMap`: hash, then identity or `==`); `_SPLIT` keyed (id(clauses), hash(want)) with `r[0] is clauses` check (:200, :229);
     bounds as Python's (SPLIT 100,000, CLOSED 4,096, ATOMS 100,000; WANT/NEIGH none); `pm_neighbourhood` pyfunction (:327).
   - Callers switched: compile_loop.rs:39 (want_of), :46/:89 (split); relations_core.rs:2582/2601 (sympy_atom), :2842/:2877
     (closed_units).
   - memos.rs: TABLES 2 -> 7 (:43-68, `ATTACHED` = 2), the five under **Python's own registry names**; `NativeTable.moved`
     (:89), `get`/`__contains__`, size `Option` (None for WANT/NEIGH); `procmemo_views()` (:182); `memo_snapshot` covers all 7.
   - session_live.py `_install_procmemos` (:809), called from `_install_memos`: puts each view where Python's container sits in
     `memos.PROCESS` (`_tables` for relations', `_adopted` getter for engine's), switches `engine.neighbourhood`; undo restores.
     Module attributes stay Python's containers (Python backend's).
   - memo_check.py `registry_rows`: native views with `moved` now count in the digest (so the digest covers the 5 tables on
     both sides).
   - Counters (session.rs :291-301, NAMES 236 -> 245, 236-239 reserved): `pm:neigh` 240, `pm:cb_rules` 241, `pm:full` 242,
     `pm:key_eq` 243, `pm:key_hash` 244.
   - Plants (relations_core.rs :227-243, names in `rel_plant` and session_live `_MEMO_PLANTS` :792): 180 `pm-split-no-full-clear`
     and 181 `pm-split-clear-skip` (the inventory's `_SPLIT` bug: Python's `_SPLIT` is **not** cleared on epoch bump, nothing
     bumps-and-clears process memos; the registry's clear is the other clear, so 181 stands for "on epoch bump"); 182
     `pm-want-key-len`; 183 `pm-neigh-no-self`; 184 `pm-neigh-memo-first`; 185 `pm-closed-hit-none`; 186 `pm-atoms-key-expr`;
     187 `pm-view-drop` (`_SPLIT`'s view not put in the registry).
3. **Short check:** `memo_check.py dev rust --limit 400` (`~/sa-rust-ids-work/sa-port-176/chk/`): view_ok true, cleared [],
   rerun_same true; answers f7d91f230eaf27c8. Rust `neighbourhood('even')` = [2,3,5,9,11,13]. **Not yet compared against base.**

## Next
1. Base Rust worktree at e0ec542 (as sa-port-174 did, `sa-port-174/mc/`), run `memo_check.py WL rust` on base and 5c9b for dev,
   fuzz, loop, zero, cert (+scope): answers and digest equal = the switch digest. If the digest differs on `_SPLIT`/`_CLOSED`
   lens, suspect `_Mark` no longer rolling these back (term_live.py:145): check whether rollback runs on that workload.
2. Plants: 180 needs >100,000 `_SPLIT` entries (no workload): add a slice test calling `sa_solver.ses_split` on 100,001 fresh
   lists and checking len resets (and `pm:full` fires); 181 caught by memo_check `cleared`; 182/185/186 by answers (memo_check
   and the bar); 187 by memo_check view_ok and digest; 183/184: tests/test_engine.py:195 imports `neighbourhood` at import
   time, so it may hold Python's: check under rust_plugin, else add a slice test calling `engine.neighbourhood` after install.
   Show each new counter fires before quoting a zero.
3. Registry tests: tests/test_memos.py + tests/test_p4_review.py::test_every_adopted_memo_name_resolves under rust_plugin.
4. The bar: `PUSH=1 sh rust-spike/slice/bar.sh land TESTED_SHA`, base rows pareto1 ~/sp19/sa-rust-ids-work/sa-port-174/bar-5c9a/suite;
   launch as in port-5c9a.md. Add the 5c9b plants to the bar's plant list (check how bar.sh picks plants: `_MEMO_PLANTS`).
5. Report results/port-5c9b.md in port-5c9a.md's form; port-ownership.md and TSV (rows: neighbourhood; state rows for the 5).
