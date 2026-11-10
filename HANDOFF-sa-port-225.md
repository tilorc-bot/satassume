# HANDOFF sa-port-225 (state step part 2, rest of (iii)(b) and (iii)(c)): code DONE at 1a6d38a, BAR RUNNING. Issue 323

## Done, on port/state-relations-iii (pushed; rust-slice still c822173 at 06:47Z)
- **The 1 failure fixed** (test_same_core_python_methods_match, 19 cases): relations.py:949 `top, self.top = self.top, {}`.
  Under the core, `top` is a view of the core's dict, so the rebind (record method set_rd) emptied the held `top` too. Now
  relations.py:951-952 `top = list(self.top); self.top.clear()`, which is the same for a plain dict (shared-file change, name it
  in the report). Grep: no other `x = self.<dict>` followed by a rebind in relations.py.
- **15 dicts checked:** test_rd_core.py 17 passed (orion ~/sa-rust-ids-work/sa-port-225/rd2): digest equal at the switch
  (469 queries, items in insertion order; adapters compared by class name because default specs hold the Rust adapters, per
  RelKeys ruling (3)); record method; **all 15 rd-<dict>-drop plants (390-404) move it, none void**. rd plants are now in
  `_REL_STATE_PLANTS`. Rust rd counts: rd:core transfer:7:60 25,729 / transfer2 22,293 / fuzz:200 61,686 / scope 14,161;
  rd:view and rd:record are 0 on workloads (views only in tests).
- **4 lists Rust-native:** queue, _pending_links, _xextra, _xpend are `Vec<Py<PyAny>>` in `RelS.l` (session.rs RL_NAMES :713,
  counters 523-525 rl:core/view/record :497; rl_field/set_rl/rl_snapshot :1611-1640), relkeys.rs RL_PLANT0=405 :633
  (`rl-<list>-drop` 405-408, the push a no-op), `RList` :676 (Rust sites), `RelListView` :751 (Python). Sites:
  relations_core.rs rel_init `plist`, `_xextra` push and drain, `_xpend` push/iterate/replace, queue push (rel_enqueue) and pop
  (process), `_pending_links` push/pop; query.rs :273 queue truth. session_live.py `_rel_lview` :302, installed :1298.
  **specs stays Python's list. Decision: configuration** (the default specs or a user's, never written after `__init__`, read
  only by iteration at relations_core.rs :1250/:1365/:1717).
- test_rl_core.py: lists sampled at every `_interpret`/`_link` call and at the end, with dicts and sets. **Digest equal at the
  switch 74b52f3903b5236b** (469 queries; each list seen non-empty: queue 2,864, _pending_links 2,265, _xextra 369, _xpend
  619). Record method OK; the 4 rl plants each move it (rl-queue-drop checked by hand: digest ecbc2bfdd9d2ccb6).
- Focused check on orion (~/sa-rust-ids-work/sa-port-225/t1): rl/rd/rs core, test_relations_core, test_relc_core,
  test_query_core, tests/test_scope.py: 153 passed, 1 failed (rl-queue-drop: the child crashed in its record section because the
  plant was still on. Fixed in 1a6d38a by `rel_plant(None)` before that section, and rechecked by hand).
- **Readers:** engine.py :1086-1129 use only `len`, `in` and `.get` on link_sel/num_sel/atom_sel/status. engine.py :1177 and
  ref.py :416 test `rel.queue` for truth; ref.py :409 and engine.py :726 call `rel.enqueue` (Rust's rel_enqueue). So all are
  read-only through the views. Suite tests that read internals (test_relations.py:209 `adapters.values()`,
  test_switched_glue.py:136-138 `link_sel[..]`, test_verify_integration.py:72 `adapters[name]`) go through RelDictView. None
  was added to needs-internals. The bar's suite confirms.
- **(iii)(c) module-wide relations.py probe, on the tested source 1a6d38a** (orion ~/sa-rust-ids-work/sa-port-225/pyc/all1,
  summ.py): **converted 0 on all seven** (dev, fuzz, zero, loop, cert, budget, scope). The only calls are noquery 4 (import
  time: `<module>`, AdapterSpec, Uninterpreted, Relations) and dev kept:out-of-scope 110. Scope's 385 relation_atom calls go
  to the installed wrapper (term_live.py:991 rebinds relations.relation_atom; scope_wl imports after install since the harness
  fix db7130a). rel:cb_relation_atom is 180 on scope, as at e025aa5. A name imported before install still dispatches
  (test_term_ids.py::test_a_name_imported_before_install_dispatches). **Rerun it on the landed SHA** (run.sh all1 -> a new
  dir) unless the landed source equals 1a6d38a's.

## Running (detached; read the end markers)
- **Bar** on tested 1a6d38a: pareto1 `~/sp19/sa-rust-ids-work/sa-port-225/bar-iii-b/end.txt` (sum.txt). Config
  run-bar-iii-b.sh next to it: 45 plants (the 17 old ones, 9 rs, 15 rd, 4 rl), WLS loop zero cert scope budget,
  SUITE_PLANTS zero. TESTS adds test_rs_core, test_rd_core and test_rl_core. BASE = sa-port-217's bar suite (the tested tree of
  c822173). Started 06:47Z under `machine run` (launcher pid in ~/sa-rust-ids-work/sa-port-225/bar-launch.pid, log
  bar-launch.log).
- **Group-D**, before c822173 and after 1a6d38a: logs ~/sa-rust-ids-work/sa-port-225/gd/run-{c822173,1a6d38a}.log ("END
  exit N"). Then, for each SHA, `bash ~/sa-rust-ids-work/sa-port-225/gd/tools/post195.sh SHA`, then
  `python3 tools/sum202.py gd/run-SHA > gd/run-SHA/SUMMARY-rel.md`. Compare with port-state-relations.md :237-246.

## Not done
1. Read the bar's five items. Land with `bar.sh land 1a6d38a` (rust-spike/slice/p1/bar.sh). If rust-slice moved (the 6i(b)+(c)
   stack, sa-port-224), follow the rebase rule.
2. TSV and port-ownership.md: results/port-ownership.tsv :372 glue_objects owner -> "landed C1 63e085d + (iii) part 1 cac82a9
   (glue_objects_plain)". Add state rows for Relations' 9 sets, 15 dicts and 4 lists (Rust-native, this step), plus specs
   (configuration). Add the relations.py count line from the probe.
3. results/port-state-relations.md: the (iii)(a)+(b) section header :329 still says UNBARRED/UNLANDED; it LANDED c822173
   (5a3c218). Append a section for this step with every MUST-STAY item.
4. agent report, push.
