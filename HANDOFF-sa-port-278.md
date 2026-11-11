# HANDOFF sa-port-278: formula step (issue 323), eighteenth part

Branch `port/formula`, head = this commit, on rust-slice **9151316**; source last changed at **212a7d6** (later commits are
results/handoff only). **Unbarred, unlanded.** Handed off at the context note, during bar prep (gate item 4).

## Done (one commit each)
- **4ef002c, 4j**: `link:second` 3 is a miss in `term_of`'s link memo (relations_core.rs:777), answered by Python's own
  `term_id`: one line in test_relations_core.py (:1007) and results; no known row (cls 138 of 2,085 link calls; scope 0).
- **50e6fa4, 4f**: p1/one_test.sh runs test_handler_count.py / test_catch_count.py with `-p rust_plugin -p handler_count`
  (fresh SLICE_SUITE_OUT) and test_cf_diff.py as a script (exit 1 unless `MISMATCHES 0`); bar.sh tests phase uses it in
  both TESTS_SPLIT modes. Orion: 2 pass, 3 pass, MISMATCHES 0.
- **7c69d1b, 4i**: moved_digest.py `_CACHE` row = `[content, order, count, keys]`; livecmp.py compares it at every point
  (no skip) and counts `moved_cache_points`, `moved_cache_key_diff`, `moved_cache_value_diff` (in the verdict). Kept test
  test_moved_digest.py `test_cache_row_keys_and_values_apart` (4 pass). Orion wiring: plain MATCH, 261 points, 0/0;
  plant 666: DIFFER, answers 40 (q4264 False vs True), key diffs 91 -> 666 is **caught by answers on wiring**.
- **212a7d6, bar prep**: bar.sh `penv`: a PLANTS / SUITE_PLANTS / FM_PLANTS entry `term:NAME` goes in as SLICE_TERM_PLANT.

## Bar prep state (gate item 4)
- pareto1, lease 968a24f1, `~/sp19/prep278.sh` (copy: orion `~/sa-rust-ids-work/sa-port-278/prep278.sh`), out
  `~/sp19/sa-rust-ids-work/sa-port-278/bar`: build done (.so 802adb75), tests done (62 files exit 0), then suite (N=8),
  then 20 workloads py/rust `--check entry` + cls/zero py2/rust2, livecmp -> `wl/verdicts.txt` (incl. "twice" lines = the
  seed-fix check). **End marker `bar/prep-end.txt`.** Read: suite against base (BASE for bar_sum should be
  `~/sp19/sa-rust-ids-work/sa-port-247/bar-part3/suite`, the last landed bar, not the default sa-port-91), verdicts, then
  `python3 ~/sa-rust-ids-work/sa-port-278/rows278.py WL AUX` (copy `bar/wl` to orion first) for the per-workload rows.
- Aux (pareto0, done): see results/port-formula.md "Bar prep". Open item: knowledge_live.py `_Store._nt_mark` (noquery)
  raises the module count base -> head; say so in the report (per entry, not per converted query).
- Group D: sampler job on head 212a7d6 started on pareto1 (shared), tools copied/adapted in orion
  `~/sa-rust-ids-work/sa-port-278/gd/tools` (go195.sh, job195.sh), log `gd/run-212a7d6.log` (END line), results pareto1
  `~/sa-rust-ids-work/sa-port-278/gd/run-212a7d6` (SUMMARY.md). Base = bench-f252daf (copied to pareto1
  `~/sa-rust-ids-work/sa-port-278/gd/bench-f252daf`; f252daf source == 9151316). Still to do: pinned timing under a
  **quiet** lease: adapt `gd/tools262/time262.sh` (S="f252daf 212a7d6") + sa-port-262's onlease262.sh / med262.py /
  dmods.py (orion `~/sa-rust-ids-work/sa-port-262/gdt/`), paths to sa-port-278/gd. A quiet lease can't coexist with a
  shared bar on pareto1: plan was the full bar on **pareto0** (copy the .so; skip `build`; same `$B` layout) and Group D
  on pareto1 meanwhile.
- Bar config planned: PLANTS="fm-atoms-drop-last fm-atoms-merge-pred fm-args-drop-last fm-implies-swap fm-not-drop
  ad-lra-class-is class-is ad-lra-atom-object fm-hand-no-give fm-hand-kept rows-product-verdict-flip
  atom-symbol-key-names term:mark-skips-native term:mark-wrong-pattern term:mark-leaves-entry";
  SUITE_PLANTS="zero fm-ite-swap same-is dispatch-keeps-memo fm-hand-instrument-by-name fm-hand-patched-direct"
  (term plants read fired 0 in bar.sh's `fired`, so `zero` picks them too); WLS = 247's 14 + cls; FM_WLS = the 20;
  FM_PLANTS="fm-atoms-merge-pred fm-args-drop-last"; TESTS=all TESTS_SPLIT=1; DIRECT="relations_direct.py 300 0"; N=6.

## File:line map (this head)
- p1/bar.sh: `penv` :85, suite() :96, tests phase :108 (one_test.sh :114, :119-:121), plants :132, extra :148, fmrows :164.
- p1/one_test.sh (whole file, 20 lines). livecmp.py: `_CACHE` counters :101-:111, init :25. moved_digest.py `_CACHE`
  row :417-:422. test_moved_digest.py: new test at the end. test_relations_core.py join asserts :1000-:1012.
- term_live.py: `_Mark` :188-:235, `_wrong_pattern` :360. knowledge_live.py `_Store._nt_mark` :263.
- Earlier map: HANDOFF-sa-port-277.md.
No plant or counter taken.
