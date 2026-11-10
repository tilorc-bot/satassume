# HANDOFF sa-port-227: state part 3. _rows ruling done, sub-part 3 readers measured, 4 written; 1, 3 (code), 5, 6 open

Branch port/state-part3 (from rust-slice c822173), head e1e4729 + this handoff. Unbarred, unlanded; landing waits for (iii)
(sa-port-225), a rebase and a full bar on the merged tree. Results: rust-spike/slice/results/port-state-part3.md.

## Done
- _rows ruling (planner ~06:47 10 Nov): 0 calls on the seven workloads (pre and post); suite pre: `_rows.generator` 717 calls in
  177 tests, `constant_value` 14,708 in 4, `rules` 95 in 50, all from test files. Fix 11af121: module `__getattr__` onto
  `wiring` (tests import the names from `_rows`, so it can't be deleted); test_rows_names_resolve_at_call_time; _rows left
  NAMED_HOLDERS. Suite pre = post: 127 failed / 5991 passed, same ids. Plants 424 (+32) and 425 (+2) caught pre; slot plants
  426/427 catch +139/+22 pre and +171/+23 post (call-time lookup shown). Probe rows_probe.py (counters 550-554).
- Sub-part 3 measurement: session_readers.py on the seven workloads. Every Python reader of `Session.solver` on converted
  queries is session_live wiring passing `s.solver` to Rust per call (`_rel_*` dominate: _rel_interpret 323k), plus engine.py
  `_gave_up` 13,915 and `_exhausted` 4,733. OWED [100]'s relations.py/engine.py sites don't appear.
- Sub-part 4: table in the results.

## Open
1. Sub-part 1 inventory: Session containers, engine.py:304-376 (solver :311, table, base, frontier, pending, pending_c, demand,
   deferred, verdict, literals, defvars, _dv, _dv_node, sel, truncated :376); session_live.install() :1201 makes
   table/base/xfer properties onto SessionCore. Mark each row's overlap with (iii) (Relations views `_REL_XVIEWS`/`_REL_CVIEWS`).
3. Session.solver code: the `_ses_*`, `_q`, `_ent`, `_compile_formula`, `_formula_literal`, `_context_session` wrappers in
   session_live.py can use the core's copy (`TableView.bind` :127 `set_solver`) instead of `s.solver`. The `_rel_*` wrappers go into
   relations_core.rs: condition (2), so ask forward-chain-3b (Status: question) before touching them. Read `_gave_up`/`_exhausted`
   (engine.py, rg 'def _gave_up|def _exhausted') first.
5. SessionCore shape: after (iii) incl. 225 lands; rebase.
6. Readouts [108] + rk:intern:engine per workload.
- Bar: not run. Note rust_plugin and rows_probe both used `rows.PID.jsonl` in the suite dir in my runs (fixed 7f7c822:
  rowsprobe.PID.jsonl); my suite dirs are not bar rows.

## Outputs
pareto0:~/sp19/sa-rust-ids-work/sa-port-227/rows-probe-p0 (suites, workloads, summary.txt); pareto1:~/sp19/sa-rust-ids-work/
sa-port-227/rows-probe/pre/suite-none and sreaders/summary.txt. Scripts: ~/sa-rust-ids-work/sa-port-227/ on orion.
