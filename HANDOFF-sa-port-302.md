# HANDOFF sa-port-302: the convert step, item 6's comparison redone, its full run and the bar under way, nothing landed (issue 323)

Handed off at the context budget, between the comparison's commits and the reading of their full run.
port/convert head: this commit, on bfac1a4 (source), from rust-slice 899d354. Numbers: rust-spike/slice/results/convert-step.md.

## Done

- Gate (a): rust-spike/slice/finite_history_repro.py, pure SymPy. `is_finite` of `x*ComplexRootOf._new(reducible poly, i)`
  raises KeyError or answers True by SymPy's assumptions shuffle and by who asked before. The VALUE differs. Cause:
  SymPy's state, not `_Walk`'s memo, not the walk order.
- Gate (c): 5c7db78 convert_diff.py makes each walker's reads in its own forked child (values, counts, `raised` all
  compared; `reread` lists pure-Python second-ask differences). bfac1a4 gives each read 30 s of CPU and compares what
  was read before a stop (`slow` lists the input; stops at different reads are a difference; `reads` counts reads compared).
- Gate (b): rootof whole run 39 -> 0 differences. First fresh-state run (5c7db78): 69245 inputs, 1 difference, which is
  the never-ending read bfac1a4 handles; reread 84, all rootof `finite`. Answer rows not read.
- test_convert_walk.py: 14 passed (plants 670-674 caught, the two new tests), orion and pareto1.
- Per-commit suites: all 10 runs equal base's failed set (127).
- Stopped, superseded: sa-port-301's 4784f4e run (stuck 90 minutes in the suite) and barq301.sh; my 5c7db78 run.

## Open, in order

1. Read the bfac1a4 differential: pareto1 ~/sp19/sa-rust-ids-work/sa-port-302/diff-bfac1a4/end.txt (end marker), then
   all/total.txt (line 1: inputs, differences, reads, slow, reread; `grep -v '^REREAD'`; last lines `exit 0` and
   `answer rows 60, MATCH 60`), all/suite-exit.txt, plants.txt (5 rows, each `differences` > 0 and `exit 1`).
   Expected: 0 differences, 1 slow (`Q.lt(x, sin(exp(exp(exp(5)))))`), reread about 84 in rootof. Launched 11:33Z;
   the 5c7db78 run took 42 minutes for the workloads and 13 for the suite. Put the counts into results/convert-step.md.
   A new difference: read its DIFF line, don't relax the comparison; a ruling on inputs is the planner's.
2. The bar starts by itself: orion ~/sa-rust-ids-work/sa-port-302/barq302.sh (running, detached) waits for that
   end.txt, checks `exit 0`, 60 MATCH and 5 caught plants, then starts pareto0 ~/sp19/bar302.sh. Launcher's files:
   orion ~/sa-rust-ids-work/sa-port-302/bar/ (diff-read.txt, bar-launched.txt with the tested SHA, bar-launch-end.txt:
   `NOT LAUNCHED: why` or `END code time`). Bar end marker: pareto0 ~/sp19/sa-rust-ids-work/sa-port-302/bar/bar-end.txt;
   sa-port-298's bar took 3 h 15 min, and this one adds the convdiff phase (about an hour more).
   The tested SHA is origin/port/convert's head when barq302.sh checks it out (this handoff commit: source = bfac1a4).
3. Read the bar (sum.txt, the item-5 verdict list, convdiff/total.txt and convdiff-plants.txt), then `bar.sh land`,
   land on rust-slice, the probe against 21 of 32 (pareto0 ~/sp19/sa-rust-ids-work/pc299.sh), the report.
4. For the planner (in my report): the `slow` rule is my decision, not a ruling; gate (d)'s owed item.

## File:line map (rust-spike/slice/)

- convert_diff.py: READ_SECONDS :42, fresh :54, _fork :62, _collect :87, reads :99, diff :116 (the read part from
  `fa, fb = fresh(`), outcome :165, install :177 (`both` :185, `write` :212), total :226, `__main__` after it.
- test_convert_walk.py: inputs :79, differences :122, test_reads_are_compared_in_fresh_state :152,
  test_a_read_past_its_time_stops_both_children_alike :174, test_plant_is_caught :201.
- finite_history_repro.py: the gate (a) repro (`python finite_history_repro.py [--rootof] [SEEDS]`).
- solver_rs/src/term/walk.rs, convert.py, p1/convert_diff.sh, p1/bar.sh: unchanged, as HANDOFF-sa-port-301.md's map.
- Orion ~/sa-rust-ids-work/sa-port-302/: diff302.sh (the pareto1 job), barq302.sh, bar302.sh, bar/, a/ (repro drafts),
  b/ (gate (b): gate_b.py, rows.K.jsonl), cut-*.txt (per-commit failed sets), first-suite.txt.
- pareto1: clone ~/sp19/dev/sa-port-302 (x86-64 .so b6177184, sa-port-301's build of 4784f4e's Rust; no Rust change
  since); ~/sp19/sa-rust-ids-work/sa-port-302/diff-5c7db78 (first run) and diff-bfac1a4.

## Notes

- Plants 670-674 used, next free 675; counters 706-719 free, none used.
- Known, by id: test_lazy_reads.py::test_stock_term_plant_is_caught[finite-stock_finite] (~3/40, base too);
  tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence (id() reuse).
- Under the differential only (not the plain suite): test_lra_constants.py::test_constants_evalf_cannot_bound_rigorously_are_not_read
  and test_wide_derived.py::test_wide_derived_or_against_or_is_fast[or-nor], [or-or] failed in the 5c7db78 run.
- test_convert_walk.py takes about 2 minutes on a loaded orion (15 s on pareto1): two forks per comparison.
