# HANDOFF sa-port-202 (state step part 2, (ii) transfer sites; (iii) not started), issue 323

Branch port/state-relations at 19d5d04 (pushed), on rust-slice c3d0999. Not through the bar, not landed.

## Done
- (ii) code at 19d5d04. SessionCore (session.rs) holds `solver` (copied at TableView.bind: session_live.py `c.set_solver`),
  `session_xfer` (Session.xfer) and `xfer: Vec<RelX>` (each Relations' xfer/xfer_sel/_xadapter, independent fields as on Python).
  Rust readers moved: relations_core.rs `Cx::solver` (all Cx users) and `Cx::xfer()`, engage_transfer (one `xfer_engage` call
  replaces the four setattrs), transfer_terms, xswitch, sync_transfer, congruent, rel_process (4 `xfer` checks); query.rs head and
  context.rs complete_check read s.xfer from the core (`session::session_xfer`); session_glue.rs's 5 xfer_sel reads use
  `core_of(s).xfer_obj(rel, XSEL)`; session_glue init no longer writes s.xfer; rel_init no longer sets xfer/xfer_sel/_xadapter.
  Python: session_live.py `S.xfer` property (`_xfer_get`/`_xfer_set`), `Relations` views `_rel_xview` for `_REL_XVIEWS`,
  installed in `install()` (so SLICE_REL=py writes go to the core too); core-less sessions (ref.py) keep `__dict__`.
  `__traverse__`/`__clear__` on SessionCore cover the new refs.
- Counters 338-343: xf:solver_core, xf:engage_core, xf:read_core, xf:session_view, xf:rel_view, xf:record (all fire in
  test_xfer_core.py's clean run; an xf:clear counter was dropped: it can't be shown firing, GC clears another cycle member).
- Plants 257-262: xf-session-none, xf-sel-none, xf-rel-any, xf-solver-fresh, xf-rel-view-none, xf-traverse-skip.
  test_xfer_core.py (new) catches all but xf-solver-fresh directly (xf-rel-any and xf-traverse-skip are reached by no workload:
  two Relations on one session, a cycle through the record). xf-solver-fresh is claimed caught by test_relations_core.py and fuzz:
  NOT YET SHOWN, check on the bar's plant phase.
- Quick checks, on the build before the last two edits (removal of the init write and of xf:clear; rebuilt since, untested):
  dev MATCH (31cd0945c07f02a6); dev counts: rel:engage_transfer 35, sync 173, xswitch 90, xf:engage_core 35, xf:read_core 4,315,
  xf:solver_core 239, xf:session_view 0, xf:rel_view 0 (no Python reader of the views on dev), xf:record 918 (now 0 expected).
  Fuzz Rust finished; fuzz Python was still running in ~/sa-rust-ids-work/sa-port-202/q2 (compare with livecmp.py).
  test_relations_core.py + tests/test_transfer.py + tests/test_relations.py: 166 passed, 3 failed, all 3 base failures with the
  same crash (test_protocol_on_fuzz "Already mutably borrowed", test_models_respect_transfer Solver._solve,
  test_equality_sharing_is_needed_and_works, needs-internals).
- Group-D BEFORE on c3d0999 done: ~/sa-rust-ids-work/sa-port-202/gd/run-c3d0999/SUMMARY-rel.md (tools/sum202.py). Relations path
  (a)+(b)+(c)+(d): dev 530/7,620 = 7.0%, fuzz 2,969/19,348 = 15.3%. Digests 31cd0945c07f02a6 on every dev row.
  AFTER: `bash tools/go195.sh SHA` (from gd/, repo path already sa-port-24), wait for run-SHA/DONE-JOB on pareto1, then the post
  steps by hand (post195.sh's nm step: `mkdir -p run-SHA/nm; cp nm/*.nm run-SHA/sa_solver.so.nm run-SHA/nm/`, ana195.py per
  workload with GD_NM, then `python3 tools/sum202.py ../run-SHA`).

## Next
1. Rebuild, rerun test_xfer_core.py + the three test files, dev+fuzz quick MATCH, check xf:record 0 on workloads.
2. Bar for (ii) alone (allowed per sub-part): copy ~/sa-rust-ids-work/sa-port-200/bar/run-bar.sh to sa-port-202/bar, OUT
   .../sa-port-202/bar-state-relations-ii, PLANTS = the six xf-* plus sa-port-200's list, TESTS += test_xfer_core.py, base rows
   ~/sp19/sa-rust-ids-work/sa-port-200/bar-state-relations-i/suite. Bar took ~33 min for sa-port-200. Week rule: `agent usage`
   before `PUSH=1 bar.sh land`; was 87% at 11:40, 90% due between 22:29 9 Nov and 00:49 10 Nov.
3. (iii): not started. Relations' ~40 fields in rel_init (relations_core.rs ~:2040 on), term_live `_relation_atom` (:389),
   `_under_apps` (:548), session_live `_rel_m`/`_rel_process`. Planner ruling 11:40 9 Nov: relations.py is off the counted list;
   (iii) owns it; it rejoins only on a module-wide per-query probe (every function in relations.py, all workloads).
4. Not done: per-call getattr guards count (this part adds none in adapters slots; session_glue's xfer_sel reads now do one
   `core_of` = s.table property + .core per call), report section, TSV owners, port-ownership.md.
