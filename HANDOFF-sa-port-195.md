# HANDOFF sa-port-195 (state step, part 1: lra_live `_memoized` on the Rust adapter, issue 323)
Head: d1d9728 on port/state-memoized (pushed), from rust-slice 9529850. Not barred, not landed.

## Done
- adapters.rs: `LraAdapter.memoized` answers on a per-query slot (`LraQuery`: the query's table, ids, objects; memo keyed
  (kind, arg identity, GENERIC_CONSTANTS) -> result; replaced when term_live's stack top changes). `Reader` = lra_live's
  interpret/order_sides/integer_form line for line, calling the table's lra_* readers natively (term/py.rs made pub(crate),
  `n_input_rows`). Callback `_memoized` left only by reason (counters below). `ad_lra_live(cfg|None)` registered by
  lra_live._install / cleared by undo; `ad_lra_export(on)` = test-only snapshot export (every slot entry as stored).
- Counters session.rs 327-336: ad:lra_native, ad:lra_hit, ad:lra_relation, ad:lra_term_id_py, ad:lra_scaffold,
  ad:cbm_noquery, ad:cbm_noid, ad:cbm_check, ad:cbm_patched, ad:cbm_off (ad:cb_memoized 144 = sum of the cbm_*).
- Plants relations_core.rs 251-255 (u8 space now full): ad-lra-kind-key, ad-lra-slot-stale, ad-lra-flag-key,
  ad-lra-patch-guard, ad-lra-pair-swap; session_live.py `_LRA_SLOT_PLANTS`.
- test_lra_slot.py: answers py vs rust; snapshot export vs lra_live's own function per entry, digest equal (1,484 entries,
  digest a2fa4c14a0805a07 at d1d9728 on orion); flag guard and patch guard direct. 5 of 7 pass; kind-key now records the
  raised answer (should pass, rerun); slot-stale fires but moves nothing here -> needs a workload catch (q2-stale below),
  then put it in ELSEWHERE with that catch, or find a case.
- Quick dev on orion (q1): MATCH (answers_sha 31cd0945c07f02a6, lra_diff 0, stats_diff 0); ad:cb_memoized 5,508 -> 33
  (all ad:cbm_noquery); ad:lra_native 5,475, hit 1,749, relation 3,212, term_id_py 1,825, scaffold 20; rel:plant_fired 0.
- Group-D BEFORE (9529850, 146's method, subagent): ~/sa-rust-ids-work/sa-port-195/gd/RESULTS.md and run-9529850/SUMMARY.md.
  dev 10,364 samples: (a) D in adapters/term::py/term::lra_read 256 (2.5%); (b) callbacks at lra_live memoized 290 (2.8%);
  (c) SymPy under memoized 30 (0.3%). fuzz 27,744: (a) 782 (2.8%), (b) 2,479 (8.9%), (c) 328 (1.2%). Digests = 146's.

## Running (detached on orion, end marker DONE in summary.txt)
~/sa-rust-ids-work/sa-port-195/q2 (fuzz rust, no plant), q2-stale (ad-lra-slot-stale), q2-swap (ad-lra-pair-swap); fuzz py rows
reused from q1. q1's fuzz rust died at 1,891 (SIGBUS from my .so rebuild under it), not a finding.

## Next
1. Read q2*/summary.txt (q2 must MATCH; plants should DIFFER). Run test_lra_slot.py again (orion, -n 4).
2. Commit with a subject starting "state-memoized:" then AFTER samples: gd/RUN-AFTER.md (go195.sh SHA; post195.sh SHA).
   sum195.py now also prints (b') = relation/term_id/scaffold/_fault entered directly from adapters.
3. Wait for the 6g c6-c9 stack (sa-port-196, bar ends ~06:30Z) to land; rebase; its diff runs code -> full bar on the rebased
   head, base rows = the 6g bar's suite (else sa-port-193/bar-5c10d-r2/suite). Config as 5c10d's
   (~/sp19/sa-rust-ids-work/sa-port-193/bar-5c10d-r2/config.txt) with PLANTS = the 5 above, TESTS += test_lra_slot.py
   test_adapters_core.py, WLS=loop zero cert scope budget, SUITE_PLANTS=zero.
4. Report results/port-state-memoized.md in port-5c10d.md's form; TSV row 768 `_memoized` -> Rust (adapters.rs LraQuery) +
   a state row for the slot; port-ownership.md line.

## Notes for the report
- Element class: the table hands back a number's cached Python Element once Python's `constant` path attached one, else Rust's
  PyElem; a slot hit returns the class from first read. Same value; both forms accepted since Element._new; dev lra_diff 0.
- test_term_live.py: 2 failures `'_Mark' object has no attribute 'facts'` in term_live._Mark.rollback (untouched here; the file
  isn't on 5c10d's TESTS) -> pre-existing; confirm on base if cheap.
- Module count (STATUS 14 of 32): lra_adapter.py still runs Python per query: `relation` (conversion, by lra_live's note; not
  a ruling I found), `_memoized`+Python reads on kept/no-table queries (dev 33), constant_bounds callback (0 on dev/fuzz). Ask
  the planner whether that counts with footnotes; not claimed.
