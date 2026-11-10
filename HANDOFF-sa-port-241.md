# HANDOFF sa-port-241: state part 3. Rebased onto 0192b35; slice-5b read and fixed; sub-part 5's containers moved; BEFORE probe run; digest, plant tests, results, bar open

Branch port/state-part3, rebased onto origin/rust-slice 0192b35 (docs only on (iii) 3203cb4). Unbarred, unlanded.
Old head before this rebase: 0377452 (local branch backup/state-part3-0377452). After the rebase, sub-part 5's first part
is 0414c4f (was ebdf52e) and sa-port-230's handoff commit is 1f093cb.

## Done (sa-port-241)
- **Rebase** onto 0192b35: no conflict; incoming diff 3203cb4..0192b35 is 4 files, +479/-2, docs only (HANDOFF-sa-port-237.md,
  results/port-ownership.md/.tsv, results/port-state-relations.md), so no rebuild was needed for it.
- **slice-5b read** (orion:~/sa-rust-ids-work/sa-port-230/slice-5b, 50 files in one pytest run on ebdf52e's tree): exit 1,
  8 failed, 1257 passed, 10 skipped, 34 errors. By cause, each rerun one file a process
  (orion:~/sa-rust-ids-work/sa-port-241/slice-5c/summary.txt):
  - **One real change from sub-part 5's first part**, test_catch_count.py::test_complete_check_route_into_1906: Rust reads
    the core's copy of the solver (`solver_of`), so a write to `Session.solver` after `TableView.bind` no longer reached Rust.
    Fixed in 02354d4: `Session.solver` is a property whose setter records into the core (`set_solver`); the value stays in the
    instance dict, so Python's reads are unchanged. test_session_boundary.py has a `solver-write` row on both backends
    (test_solver_write_reaches_rust; it fails without the fix).
  - test_glue_plain.py::test_default_engine_rewrapped contradicted install()'s refusal (it builds the default engine, then
    installs). Now test_install_after_a_default_engine_is_refused: asserts the refusal and that the engine keeps Python's.
  - test_term_live.py, 2 tests: they build a `_Mark` by `__new__` without the `facts` dict step 5c10a added; the same on the
    base (the base's test has no `m.facts`). One-line test fix, a sibling's test file (term_live), named here.
  - test_relevance_core.py, 34 errors: install() refused after another file's Engine in the shared process. 34 passed alone.
  - test_catch_count.py (2 more) and test_handler_count.py (2): need `-p rust_plugin -p handler_count` and SLICE_SUITE_OUT;
    5 passed that way after the solver fix.
  - test_session_boundary.py 13 passed (test_rust_repeats included); test_install_order.py 198 passed, its install list still
    191 entries: the list is of replaced module-level names, and the `Session` properties are class attributes looked up at
    call time, so there is no entry to add for them.
  - **Slice files must run one process per file** (or at least not with files that build an Engine before another's
    install); bar.sh's TESTS is one pytest run, so choose TESTS with that in mind or run the others as DIRECT.
- **Containers, 7a18df2**: `frontier`, `deferred` (sequences of nodes) and `pending`, `pending_c`, `demand`, `literals`,
  `_groups` (insertion-ordered maps keyed by RelKeys ids through `rk_key`) are in `SessionCore` (new file ses_cont.rs: record
  `SesCont`, field `sc`). Rust sites use them natively through `Ses` (discovery.rs, compile_loop.rs, session_glue.rs,
  query.rs: no `s.getattr("<container>")` is left except in `Ses::Py`, the no-core session, counted `sb:attr`). Python reads
  `Session.<name>` through `SesDictView`/`SesSeqView` (session_live `_ses_cview`, `_SES_CVIEWS`); an assignment replaces the
  content through `sc_dict_replace`/`sc_seq_replace`. session_glue.rs `init` no longer writes them for a core session.
  `_groups`' keys None and True take two reserved keys and are never interned, so `rk:intern:engine` does not rise for them.
  Origins: the four node/formula dicts count `rk:intern:input`, other `_groups` keys `rk:intern:engine`.
  Counters 565-567 `sc:core`, `sc:view`, `sc:record` (NAMES/COUNTS are 568). Plants 439-445 `sc-frontier-drop`,
  `sc-pending-drop`, `sc-pending_c-drop`, `sc-demand-drop`, `sc-deferred-drop`, `sc-literals-drop`, `sc-groups-drop`
  (`sb_plant`; session_live `_SB_PLANTS`): **they exist and are not yet tested**.
  Condition 2: no RelKeys or Relations field changed and relations_core.rs is untouched. relkeys.rs got one method,
  `OrdMap::pop_last` (dict.popitem); ses_cont.rs reads `relkeys.objs` (as `rd_items` does) and calls `rk_key`.
  Nothing stopped on under condition 2; no question sent.
  Checked on 7a18df2 (orion:~/sa-rust-ids-work/sa-port-241/slice-5d): test_session_boundary 14, test_discovery_core 10,
  test_query_core 14, test_session_limits 242, test_install_order 198, test_theory_flags 4, test_compile_loop_core 13,
  test_glue_plain 4, test_rd_core 17, all passed. Nothing wider was run on it.
- **session_live module-wide probe, BEFORE** (d8f9146 = e90a0d1 rebased; pycalls.py, PYCALLS_FILE=rust-spike/slice/session_live.py,
  seven workloads, Rust, --check plain, all exit 0; orion:~/sa-rust-ids-work/sa-port-241/pyc/before/summary.txt). Python calls
  into session_live.py on converted queries, total (per query), then the four wrappers `_rel_interpret` / `_rel_link` /
  `_rel_share_guard` / `_ses_visit`:

  | workload | queries | converted calls (per query) | wrappers |
  |---|---|---|---|
  | fuzz | 3000 | 3,009,742 (1003.2) | 36,397 / 9,405 / 4,890 / 16,537 |
  | dev | 1985 | 201,983 (101.8) | 1,494 / 373 / 274 / 2,476 |
  | zero | 854 | 593,181 (694.6) | 6,278 / 1,733 / 2,028 / 2,804 |
  | loop | 420 | 58,863 (140.2) | 0 / 0 / 0 / 2,284 |
  | scope | 169 | 69,286 (410.0) | 701 / 174 / 12 / 490 |
  | budget | 28 | 20,333 (726.2) | 0 / 0 / 0 / 1,961 |
  | cert | 61 | 36,798 (603.2) | 374 / 81 / 20 / 223 |

  The largest name everywhere is `_table_get` (fuzz 2,079,683; dev 120,618; zero 418,024): the `Session.table` property, run
  each time Rust's `core_of(s)` does `s.getattr("table")`. **`Ses::of(s)` calls `core_of` too**, so AFTER will show
  `_table_get` higher unless `core_of` stops going through the property (for example reading the instance dict's
  `_table_view` natively). That is the first thing to look at in the AFTER numbers and in the memo-cost timing.
- **AFTER probe started detached at 7a18df2**, not read: end marker orion:~/sa-rust-ids-work/sa-port-241/pyc/after/end.txt,
  then `python ~/sa-rust-ids-work/sa-port-241/pyc/sum.py after` (it also prints the sb:*/sc:* counts it finds in
  <wl>.session.json or <wl>.out; **check it finds them**, the BEFORE summary printed none, so sb:attr and sb:fwd_named per
  workload are still owed). Rerun it at the final sub-part 5 head if the source changes again:
  `~/sa-rust-ids-work/sa-port-241/pyc/probe.sh after <sha>` (own clone and build under pyc/).

## Not done
1. Tests for the containers: rows in test_session_boundary.py comparing each container's content (keys and values, in
   order) on Python and Rust after `_build_context` and each `_ask`; `sc_snapshot()` equals the views; plants 439-445 each
   fired and caught; `sc:core`/`sc:view`/`sc:record` fire. A view under SLICE_DISC=py / SLICE_LOOP=py / SLICE_GLUE=py (Python's
   own methods over the core's containers) has not been run at all.
2. Read the AFTER probe; give sb:* and sc:* per workload beside it; decide on `core_of`/`_table_get` (above).
3. `relations`' reference held by the core (inventory row): not started.
4. Digest: cherry-pick digest/split-order 0e41490 (on c931c16), extend per the planner's (A)/(B) rulings (the seven containers
   above belong in it too: `sc_snapshot()`), add twin to WLS, rk-class-split to PLANTS, test_moved_digest.py to TESTS.
   **Not taken yet: the architect and sa-port-234 have not been told**; tell them when you take it.
5. results/port-state-part3.md sub-part 5 section (first part, the `_neg_shared` correction, OWED [100]'s two truncated
   sites closed by 0414c4f, the solver view, the containers, the probe before/after). Not written.
6. Full bar on the merged tree, memo-cost timing on a quiet pareto1 lease, Group D in seconds if this lands before formula,
   land (`bar.sh land`, no PUSH first), report. Plants 446-449 and counters 568-579 remain.

## FILE:LINE MAP (at this head)
- rust-spike/slice/solver_rs/src/ses_cont.rs (new): SD_NAMES/SQ_NAMES and indices at the top; SD_PLANT/SQ_PLANT; `key_of`
  (reserved None/True keys); `impl SessionCore` sd_*/sq_*; `enum Ses` (of, d_contains, d_get, d_item, d_set, d_del, d_popitem,
  d_truthy, q_push, q_popleft, q_pop, q_truthy, q_items, frontier_reset); SesDictView; SesSeqView; dict_replace, seq_replace,
  snapshot
- session.rs: :17 NAMES[568]; :717 SB_FWD_SKIP_LINK; :720 sb_planted; :730 sb_plant (SB_PLANTS has 15 names, 431 + index);
  :743 solver_of; :834 named; :919 core_of; :1781 sc_dict (sc_seq, sc_dict_replace, sc_seq_replace, sc_snapshot follow);
  :1807 ses_snapshot
- relkeys.rs: `rk_key` :123; `OrdMap` :362 (pop_last added)
- discovery.rs (rewritten on `Ses`); compile_loop.rs `rg 'ses\.|Ses::of'`; session_glue.rs init ~:46 (no-core writes only),
  `_groups` sites `rg SD_GROUPS`; query.rs literal_of `rg SD_LITERALS`
- rust-spike/slice/session_live.py: :225 _ses_cview; :247 _SES_CVIEWS; :258 _ses_solver_set; :1075 _SB_PLANTS; :1358 install()
  (:1368 solver property, :1372 container views)
- rust-spike/slice/test_session_boundary.py (rows in CHILD; `solver-write`), test_glue_plain.py, test_install_order.py,
  pycalls.py, p1/bar.sh
- satassume/engine.py:304 class Session (:320-328 the containers, :350 _groups), :772-850 ensure/discover/escalate
- OWED: ~/dev/architect/OWED-satassume-rust.md [100], [108], [109], [110]
- Outputs: orion:~/sa-rust-ids-work/sa-port-241/{slice-5c,slice-5d,pyc/before,pyc/after}; 230's and 229's as before
