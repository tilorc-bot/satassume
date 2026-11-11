# HANDOFF sa-port-294 (A, part 3 follow-up; issue 323)

Branch port/part3-followup at 1d22f9a (Rust source as at 5bf9c47), on rust-slice 15c62a7 (still its head at 20:25Z).
Nothing landed. Handed off at the context budget, between items: the three rulings and the cheap part of (4) are done;
the batch bar and the re-probe are RUNNING detached on pareto0. I ran no speed measurement.

## Done (each its own commit)
- c4701f4 rulings (1)-(2) on 293's deviations.
  (1) ses_cont.rs `Seen` (doc at the struct): a memo row's key is the address of the object that row holds strongly, so it
  is identity on a held object, never an address alone (plant 616 drops the hold; test_ses_keys.py catches it).
  (2) Contexts are built per query (engine.py `_fresh_session`; context.rs stores a session in `_context_sessions` only
  under plant 222). So no session crosses queries, and the memo isn't cleared at a query boundary. Gauges: 701
  `sc:ses_live` (SesCont alive now) and 702 `sc:memo_peak` (largest one-dict memo), in `session_counts`. Kept test
  test_ses_keys.py `test_no_session_outlives_its_query`: 6 public asks, gc.collect(), live 0 after each (6 sessions,
  peak 3). Control `test_a_kept_session_is_seen_between_queries`: plant 222 gives 1,2,2,2,3,3 with the same answers.
- 13955e0 + a6cae7e ruling (3). A bound EntMethod was named `ent_ask`. session_glue.rs `renamed_entry` now gives each entry
  its own builtin over the same C entry point (ml_name, ml_doc, `__self__` = Engine so `__qualname__` is Engine.<name>,
  m_module). The call is unchanged, still with no Python frame. a6cae7e: every GuardMethod (58), and the class-level
  EntMethod, had `__doc__` '' (PyType_FromSpec writes the type's own doc after the getsets). The getter is now `_method_doc`,
  and session_live `_method_docs` puts it under `__doc__`. GuardMethod's name, qualname and doc come from PY_X[key].
  Kept tests: test_entry_frame.py `test_a_bound_entry_method_looks_like_the_python_method` (+ class_looks; control: no
  class/module gives `ent_ask`), test_guard_method.py `test_a_bound_guard_method_looks_like_the_python_method` (failed on
  13955e0 with doc ''). Footnote: GuardMethod `__module__` stays sa_solver; the ruling names three attributes.
- 06ce200 (4) query.rs `ses_query_literal` takes the def's signature (assumptions=(), search=True; explicit None passes
  through), so `_frameless` installs Session.query_literal as a GuardMethod. Kept test test_query_core.py
  `test_query_literal_defaults_are_the_defs`.
- 5bf9c47 (4) compile_loop.rs `view_core`: `_flush`/`_compile_patterns` read new_custom/new_nodes/base_of on the
  TableView's own core (any other table goes by attribute, as before). These were the bulk of TableView 667,978 and
  _BaseOf 241,845 (fuzz new_nodes 133,977, new_custom 108,970, _BaseOf.get 33,395). Plant 620 `cl-view-nodes-drop`, caught
  by test_compile_loop_core.py (PLANTS) and test_discovery_core.py test_same_as_python. **compile_loop.rs is outside
  A's four files** (named; formula's step is closed, and the rulings list it as also the part 3 follow-up's).
- 1d22f9a fm_again_split.py dumps the `sc:` counters, `sc:memo_peak`, and sessions alive at each top-level ask's end
  (no gc), for ruling (2)'s per-workload rows.
- On orion, 321 passed (11 related files, at 5bf9c47). The full suite and all tests run in the bar.

## Owner table (session_live.py converted calls, 20 workloads; baseline 2439bac, pareto0 sa-port-291/pc)
All owner A (session_live is A's). Baseline: TableView 667,978; _rel_m 317,337; _BaseOf 241,845; _q 210,338; _ses_ensure
187,617; _ses_discover 99,320; _ent 77,795; _ses_custom 56,682; _ses_query_literal 55,202; _table_get 50,059;
_ses_incomplete 39,032; _Custom 35,966; eight per-session ones 27,882 each (_core_rules, _table_set, _ses_solver_set,
_Slots, _ses_solver_get, _Base, _ses_init, _base_set); _node 25,966; _g 23,315; _ses_assumption_lits 23,259; _rust_call
20,775; _compile_formula 17,457; total 2,445,317 (orion ~/sa-rust-ids-work/sa-port-294/slfn-base.md). _rel_m/_q/
_ses_ensure/_ses_discover/_ent/_ses_custom/_g are 293's GuardMethod/EntMethod wrappers (gone since e41642f/f4afbab).
_ses_query_literal and most of TableView/_BaseOf are gone from 06ce200/5bf9c47 on. What's left, Python per converted query:
TableView.__len__ (from _rel_process and sympy_api), _table_get (from `_node`, `_rust_call`), `_node`, `_rel_process`,
`_ses_incomplete`, `_Custom.__contains__`, the per-session setup (`_ses_init`, `_table_set`, TableView.bind, ...).
Next cheap one: `_node` as a Rust entry (core.base_get, `_compile_pending` by name, core.visit), which also removes
_table_get from it.
**After**: `scp ~/sa-rust-ids-work/sa-port-294/scripts/slfn.py pareto0:sp19/sa-rust-ids-work/slfn294.py` (already there),
then `ssh pareto0 'cd ~/sp19/sa-rust-ids-work && python3 slfn294.py sa-port-291/pc sa-port-294/pc'` gives before/after.

## Running (detached on pareto0, shared leases; read the end markers)
- Bar: ~/sp19/bar294.sh (291's config + plants 614-620; BASE sa-port-291/bar/suite; phases tests suite live plants seed1
  extra suiteplants fmrows sum). Out ~/sp19/sa-rust-ids-work/sa-port-294/bar, end marker bar/bar-end.txt (291's took
  2h36m; started 20:25Z). Tested source 1d22f9a, .so 2cc2e09f (built on pareto1, OUT=sa-port-294/build).
- Probe: ~/sp19/sa-rust-ids-work/pc294.sh (pc291 recipe + fm_again_split), out sa-port-294/pc, end pc/end.txt. Then pcsum.py
  (sa-port-291/pcsum.py NEW OLD) for the module-wide probe vs 21/32, and fa/*.json for fm:again within an ask, sc:key_hash
  per query, sc:memo_peak per workload, and sessions alive at ask ends.

## Left
1. Read the bar (sum.txt, tests.txt, plants incl. 614-620, fm rows, suite vs BASE). Planted-history: run the test about 20
   times on 15c62a7 and on the head and give the pass rate (ruling (2)). Quiet failures: count them.
2. Speed (S1): pinned wall time, dev and fuzz, base 15c62a7 vs head, plus per-function inclusive time. Quiet lease on
   pareto1 via bench-container. Not started.
3. bar.sh land 1d22f9a (rebase; PUSH=1 if the guard is clean), report.

## FILE:LINE MAP (on 1d22f9a, rust-spike/slice/)
- solver_rs/src/ses_cont.rs:74 LIVE (701), :80 gauges(), :143 Drop, :213 PEAK update (702); `Seen` doc (ruling 1) above `struct Seen`.
- solver_rs/src/session.rs:566 sc:ses_live/sc:memo_peak in session_counts; :745 A_PLANTS (614-620).
- solver_rs/src/session_glue.rs:501/:621 `_method_doc` getters, :512 renamed_entry, :603 plant 619, :606 GuardMethod.
- solver_rs/src/compile_loop.rs:124 plant 620, :130 view_core, :142 flush, :298 compile_patterns.
- solver_rs/src/query.rs:347 ses_query_literal (signature above it).
- session_live.py:1099 _SB_PLANTS, :1111 _ent, :1124 _method_docs, :1179 _frameless (:1206 PY_X names), :398 _node,
  :1438 _rust_call, :124 TableView, :180 _table_get.
- Tests: test_ses_keys.py:176/:182, test_entry_frame.py:95, test_guard_method.py:107, test_query_core.py:217,
  test_compile_loop_core.py PLANTS (620).
- Ranges: plants 614-620 used (621, 668 free); counters 700-702 used (703-719 free).
- Logs: orion ~/sa-rust-ids-work/sa-port-294/ (build*.log, t*.log, slfn-base.md, scripts/).
