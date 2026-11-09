# HANDOFF sa-port-197 (state step, part 1: lra_live `_memoized` on the Rust adapter, issue 323)
Branch port/state-memoized, from rust-slice 9529850, pushed. Not barred, not landed. Handed off at the architect's request
(160k context, wait of over 2 hours for the 6g c6-c9 stack to land).

## Passed so far
- Fuzz quick runs at d1d9728 (`~/sa-rust-ids-work/sa-port-195/q2*`): q2 MATCH (answers 173502b6ef285ad6, lra_diff 0,
  stats_diff 0); ad-lra-pair-swap DIFFER (answer_diff 217); ad-lra-slot-stale fired 59,037 and moved nothing: void by
  construction (Python's `_INTERPRETED` is cross-query, keyed by atom and flag), named in test_lra_slot.py ELSEWHERE (f7ea3d3).
- test_lra_slot.py at f7ea3d3 (orion, -n 4): 6 passed, 1 skipped (slot-stale). Switch digest a2fa4c14a0805a07, 1,484 entries.
- ad:cb_memoized: dev 5,508 -> 33 (all ad:cbm_noquery = kept:out-of-scope), fuzz 164,954 -> 0 (ad:lra_native 164,954;
  ad:lra_term_id_py 64,424, ad:lra_relation 100,449).
- Group-D AFTER at f7ea3d3: `~/sa-rust-ids-work/sa-port-195/gd/run-f7ea3d3/SUMMARY.md`; table in the report
  (LRA path dev 5.3% -> 3.0%, fuzz 11.7% -> 5.8%; adapters' C API on fuzz 1.7% -> 3.7%, getattr guards). Digests equal.
- lra_adapter.py readers per workload (pycalls.py, `~/sa-rust-ids-work/sa-port-197/pyc/`): on converted queries only
  `relation` (all but loop) and `integer_form` 4 on scope (ad:cbm_noid via glue link_objects); dev's 141 kept calls named.
- test_term_live.py's 2 failures (`_Mark` has no `facts`) are on base 9529850 too (`sa-port-197/base-term_live.log`).

## Next
1. When the 6g c6-c9 stack has landed: `git fetch; git rebase origin/rust-slice` (expect results/port-ownership.* conflicts:
   keep both sides' rows), `sh rust-spike/slice/build_solver.sh`, rerun test_lra_slot.py, push the branch (-f, own branch).
2. Bar: `scp rust-spike/slice/p1/bar.sh pareto1:sp19/bar-sa-port-197.sh; scp ~/sa-rust-ids-work/sa-port-197/bar/run-bar.sh
   pareto1:sp19/sa-rust-ids-work/sa-port-197/run-bar.sh`, then detached on orion:
   `setsid nohup machine run pareto1 --shared --wait 4h -r "sa-port-NNN state-memoized bar on SHA" -- bash
   ~/sp19/sa-rust-ids-work/sa-port-197/run-bar.sh BASE_SUITE > LOG 2>&1 < /dev/null &` (BASE_SUITE = the 6g bar's
   `~/sp19/sa-rust-ids-work/sa-port-194/bar-6g-c6c9/suite`, else sa-port-193/bar-5c10d-r2/suite). run-bar.sh sets PLANTS
   (the 5), WLS, SUITE_PLANTS=zero, TESTS (5c10d's + test_lra_slot.py test_adapters_core.py), DIRECT, N=6, OUT
   `~/sp19/sa-rust-ids-work/sa-port-197/bar-state-memoized`, end marker `end.txt` there. Edit its OUT/name if you rename.
3. Read sum.txt; `python3 ~/sa-rust-ids-work/sa-port-197/bar/adcounts.py BAR_DIR` (copy the bar's live/ and extra/ back first)
   gives the slot counters per workload for "which moved items are reached".
4. Fill the PENDING sections of results/port-state-memoized.md; change the TSV's two "NOT LANDED" owners to "landed
   state-memoized (port-state-memoized.md)"; add an "Updated by" paragraph and the line :125 change in port-ownership.md.
5. `agent usage` < 90% -> `PUSH=1 sh rust-spike/slice/p1/bar.sh land TESTED_SHA`; agent report.

## FILE:LINE MAP (at the head carrying this file)
- rust-spike/slice/solver_rs/src/adapters.rs: LraAdapter.callback :100, memoized :105-170 (plants 251-254 at :120, :132, :139),
  top_query :258, Reader :300-440 (rel, id, obj, pairs with plant 255 :358, interpret :375, order_sides :395, integer_form :420).
- rust-spike/slice/solver_rs/src/session.rs: counters 327-336, NAMES 337. relations_core.rs: plants 251-255.
- rust-spike/slice/test_lra_slot.py: PLANTS :24, ELSEWHERE :26 (slot-stale void reason), plant test at the end.
- rust-spike/slice/pycalls.py: PYCALLS_FILE, state() (term_live stack top), by_state / by_name_state.
- rust-spike/slice/results/port-state-memoized.md: the report draft (PENDING: SHAs, bar, reached, kept, not run).
- rust-spike/slice/results/port-ownership.tsv: row 768 `_memoized`, new row "state: LraAdapter slot" after the state rows.
- satassume/theories/lra/lra_adapter.py: relation :155, integer_form :400, `_INTERPRETED` :425-433, `_memoized` :439.
- rust-spike/slice/lra_live.py: memoized :192-196 (converted queries skip `_INTERPRETED`), integer_form :165 (on_python :169).
- rust-spike/slice/term_live.py: glue_objects :715-718 (non-eq atom -> Python relations.glue_objects).
