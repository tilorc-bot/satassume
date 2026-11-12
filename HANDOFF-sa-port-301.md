# HANDOFF sa-port-301: the convert step, items 1-6 committed, differential not clean yet, nothing landed (issue 323)

Handed off at the context budget, inside item 6's run (its code is committed; its full run has not given 0).
port/convert head: this commit, on 9cdbb4f; from rust-slice 899d354. Numbers: rust-spike/slice/results/convert-step.md.

## Done

- Items 1-5 cut, one commit each: 682e141 enc, 87f86ca klass, e204e5a term_row, 8363e8a walk, eb10c7d enc_int (the
  last equals d4af871's files). Each builds and passes test_convert_walk.py for its items (4/6/8/10/12 passed).
  Per-commit suites on pareto1: equal to base in the 7 runs read; 3 rows unread (below).
- Item 6 code: 4784f4e convert_diff.py + SLICE_CONVERT_DIFF in convert.from_env + p1/convert_diff.sh; 9cdbb4f p1/bar.sh
  (`convert:NAME` plants, phase `convdiff`); this commit adds SLICE_CONVERT_DIFF_CONTROL (Python against Python).
- S1 done (one quiet lease, 4 arms, 7 rounds): Rust walker dev 0.760 -> 0.646 s (-15.0%), fuzz 6.364 -> 5.908 s
  (-7.2%), inside item 0's estimate; table in results/convert-step.md.

## Open, in order

1. **The differential is not clean: 39 differences in 29168 inputs (partial), all in rootof, all `read finite 2` +
   `counts` on `Q.positive(x*CRootOf(...))`.** The control shows the same differences with Python's walker on both
   sides (14 in 2184 inputs, partial), so they come from asking `finite` of one CRootOf object twice, not from Rust.
   To do: make `convert_diff.diff`'s lazy-read comparison independent of who asks first. Suggested: in `both`
   (convert_diff.py install), when `diff` returns only `read ...`/`counts` names, convert twice more (Python, then
   Rust) and compare those; count the input under `first-read` (reported, not a difference) when the second pair
   agrees, and under `differences` when it doesn't. Then show plants 670-674 are still caught (their differences are
   in tables, so they should be), rerun p1/convert_diff.sh (20 workloads + suite + answers, then the 5 plants), and
   put the counts into results/convert-step.md. If the planner wants another rule for these inputs, that is a question
   for the planner: the gate says zero differences.
2. Read what the first full run left on pareto1, ~/sp19/sa-rust-ids-work/sa-port-301/diff-4784f4e: all/total.txt,
   all/suite-exit.txt, all/answers.txt (60 rows, MATCH expected), plants.txt (each plant: differences > 0, exit 1),
   end.txt. And cut/rows.txt's last three rows (8363e8a rust, eb10c7d py and rust) against base's failed set
   (orion ~/sa-rust-ids-work/sa-port-301/cutcmp/base.txt).
3. The bar: orion ~/sa-rust-ids-work/sa-port-301/barq301.sh starts pareto0 ~/sp19/bar300.sh only on a clean
   differential; with the 39 it writes `NOT LAUNCHED` to ~/sa-rust-ids-work/sa-port-301/bar/bar-launch-end.txt. After
   item 1 above: rebuild nothing (no Rust change) unless walk.rs changes, point barq301.sh's P1 at the new run's
   directory, start it detached. Bar end marker: pareto0 ~/sp19/sa-rust-ids-work/sa-port-301/bar/bar-end.txt; launcher
   end: orion ~/sa-rust-ids-work/sa-port-301/bar/bar-launch-end.txt. bar300.sh exports SLICE_CONVERT=rust for every
   Rust-backend run, adds convert:NAME to PLANTS and SUITE_PLANTS, runs `convdiff` with CONVERT_PLANTS; BASE is
   sa-port-298's suite. The tested SHA is port/convert's head when the bar starts.
4. Then `bar.sh land`, land on rust-slice, the probe against 21 of 32 (pc299.sh), the report.

## File:line map (rust-spike/slice/)

- solver_rs/src/term/walk.rs: as HANDOFF-sa-port-300.md's map (PLANT :57, WalkCtx :75, Walk :179, W :202, dispatchers
  :309-:327, enc_native :346, enc_int_native :404, walk_native :432, klass_native :499, term_row_native :629,
  pymethods :721).
- convert.py: RUST_ITEMS :392, WALK :394, rust_walk :398, use_rust :440, WALK_PLANTS :446, from_env :450 (the
  SLICE_CONVERT_DIFF lines at its end), `_Walk.read` in :123-:388 (the lazy reads; `finite` is one of convert.READS).
- convert_diff.py: diff :28 (the read loop near its end), outcome, install (`both`, `write`), total, `__main__`.
- test_convert_walk.py: imports convert_diff.diff; inputs, differences, the two tests, the script entry.
- p1/convert_diff.sh (OUT [PLANT]); p1/bar.sh: penv :87, phase convdiff :179.
- Orion ~/sa-rust-ids-work/sa-port-301/: mk_commits.py + commits.log (the cut), cut301.sh, diff301.sh (pareto1 jobs),
  cutcmp/, ctl/ (the control: ctl.sh, out.txt), bar300.sh, barq301.sh, bar/, gd/ (S1: go301.sh, med-r1.md,
  timing-r1/, run-ARM/, split-ARM/tab.txt, tools280/time301.sh and onlease301.sh with the SHA+rust arm).
- pareto1 ~/sp19/dev/sa-port-301 (clone, x86-64 .so of 4784f4e's Rust), ~/sp19/sa-rust-ids-work/sa-port-301/{cut,diff-4784f4e}.

## Notes

- livecmp.py prints very long lines: read it with `tail -n 1 | cut -c1-80`.
- Plants 670-674 used, next free 675; counters 706-719 free, none used.
- Known, by id: test_lazy_reads.py::test_stock_term_plant_is_caught[finite-stock_finite] (~3/40, base too);
  tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence (id() reuse).
