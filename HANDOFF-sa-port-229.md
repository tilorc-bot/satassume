# HANDOFF sa-port-229: state part 3. Sub-parts 1, 3 (engine.py readers), 6 done; 5 waits for (iii); then bar and landing

Branch port/state-part3 (from rust-slice c822173), head = this commit. Unbarred, unlanded. (iii) (sa-port-225's 1a6d38a,
land-only sa-port-228; bar pareto1:~/sp19/sa-rust-ids-work/sa-port-225/bar-iii-b/end.txt) had not landed at 07:30 10 Nov.
Results: rust-spike/slice/results/port-state-part3.md (sub-parts 1-4, 6; OWED [100] site table).

## Done (sa-port-229)
- 042598c: engine.py `_gave_up`/`_exhausted` read in Rust from SessionCore's solver (theory_flags.rs; counters 555-558,
  plants 428-430 via its own `th_plant`; context.rs/entry.rs call it; lra_py.rs `flags()`). test_theory_flags.py: equal on
  12 sessions, all 3 plants caught. Workloads: engine.py Session readers 0; answers A (1a6d38a) = B (042598c) on seven.
- Sub-part 1 inventory table with (iii) overlap per row; OWED [100] five sites with reasons (3 gone, 2 `truncated` open ->
  sub-part 5); sub-part 6 readouts (rk:* per workload on 1a6d38a, scope fallback unchanged 33/64, memo cost = timing, not run).

## Next
1. Wait for (iii) on origin/rust-slice; rebase port/state-part3 (expect conflicts: session.rs NAMES array, 225 pads to 526 with
   "reserved:N" -> keep its entries, pad 526..554, then th:* at 555-558, sizes 559; session_live.py plant lists).
2. Sub-part 5 (planner's Session.solver ruling, addenda/sa-port-session-solver-ruling.txt): REMOVE the forwarding `_rel_*`
   wrappers and `_ses_visit` (Rust calls relations_core directly, solver from the core); list any wrapper that does more than
   forward; unruled callback -> question to forward-chain-3b. Session.solver Rust readers onto `solver_direct`
   (relations_core.rs :1048/:1070/:1093/:1207, compile_loop.rs :98/:383, session_glue.rs, entry.rs:802, context.rs:265,
   query.rs:109/:116). Move `truncated`, `verdict`, `sel`, `n_hold` (and frontier/pending/pending_c/demand/deferred per the
   inventory) into SessionCore; drop session_glue.rs's dead writes of defvars/_dv/_dv_node/_neg_shared. Module-wide probe
   count for session_live before/after (pycalls.py / count7.py).
3. Full bar on the merged tree (suite by id vs base, dev/fuzz MATCH + plants incl. 428-430, handler rows), land, report.

## FILE:LINE MAP (at this head)
- rust-spike/slice/solver_rs/src/theory_flags.rs (new); context.rs `theory_flag` calls (~:200, ~:290); entry.rs ~:821
- rust-spike/slice/solver_rs/src/session.rs:17 NAMES[559], :480-483 TH_* consts, :634 core_of, :674 solver_direct
- rust-spike/slice/session_live.py `_TH_PLANTS` after `_RULE_BLOCK_PLANTS` (~:921), from_env plant dispatch (~:1290);
  install() ~:1203; wrappers: rg 'def _rel_|def _ses_'
- rust-spike/slice/test_theory_flags.py; test_install_order.py
- satassume/engine.py:2292 _gave_up, :2300 _exhausted (kept for Python/tests)
- Outputs: pareto1:~/sp19/sa-rust-ids-work/sa-port-229/{readouts,inv,summary.txt,inv_summary.txt}; scripts on orion
  ~/sa-rust-ids-work/sa-port-229/
