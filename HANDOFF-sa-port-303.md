# HANDOFF sa-port-303: the convert step, the bfac1a4 differential read and clean, the bar running, nothing landed (issue 323)

Handed off at an item boundary: the differential is read and committed, the bar started 04:34Z 17 Nov and takes
about 4 hours, and my context passed 100k (~/README.md: hand off before a wait of over an hour).
port/convert head: this commit, on 82518dc (the bar's tested SHA; source bfac1a4), from rust-slice 899d354.
Numbers: rust-spike/slice/results/convert-step.md ("The bfac1a4 differential, read").

## Done

- The bfac1a4 differential (pareto1): 69256 inputs (workloads 29361, suite 39895), 0 differences, 1781733 terms,
  14253807 reads compared, slow 1 (suite, `Q.lt(x, sin(exp(exp(exp(5))))) | Q.positive(x)`, read `complex` of term 3),
  reread 59 (all rootof, all `finite`; the first run had 84), `exit 0`. test_convert_walk.py 14 passed there.
- Answers: 60 rows, 60 MATCH (20 workloads, three pairs each). rootof's three rows MATCH: no final answer differs
  on the [131] inputs between the three runs.
- Plants 670-674 under the whole-run differential (dev and fuzz, 4219 inputs): each caught, `exit 1`
  (4195 / 4195 / 3610 / 4195 / 2992 differences).
- The differential's suite: 132 failed, base's 127 plus five, all caused by the harness (planner's ruling (4)), each
  run alone on pareto1 (~/sp19/sa-rust-ids-work/sa-port-303/extra5; script orion ~/sa-rust-ids-work/sa-port-303/extra5.sh):
  test_lra_constants.py::test_constants_evalf_cannot_bound_rigorously_are_not_read (wall < 5 s: plain 0.03 s with
  either walker; 30.14 s under the differential, which is the read limit on the slow row's read; 2.10 s and passing
  with SLICE_CONVERT_DIFF_READ_SECONDS=2) and test_wide_derived.py::test_wide_derived_or_against_or_is_fast[or-or],
  [or-nor], [nor-or], [nor-nor] (wall < 2.0 s: plain 0.03 to 0.04 s; 1.25 to 1.42 s alone under the differential;
  2.5 to 3.0 s in its -n 6 suite). They stay in the differential's run (their inputs are part of it) and are left out
  of its failed set only; the differential's code is unchanged.
- For the planner's ruling (2) (not this step's task): the plain `ask` of the slow input does not hang. It answers
  None in 0.03 s with either walker; only the harness, which asks every lazy read of every term, reaches the
  `complex` read that never ends. Whether any query asks that read is the owed item's question.
- The bar: barq302.sh started detached on orion 04:34:24Z 17 Nov; it checked the differential (exit 0, 60 MATCH, 5
  plants) and started pareto0 ~/sp19/bar302.sh under shared lease 3ef07bff. Tested SHA 82518dc, .so b6177184.

## Open, in order

1. Wait for the bar: orion ~/sa-rust-ids-work/sa-port-302/bar/bar-launch-end.txt (`END 0 ...`), pareto0
   ~/sp19/sa-rust-ids-work/sa-port-302/bar/bar-end.txt. Expected about 08:30Z to 09:00Z 17 Nov (sa-port-298's bar took
   3 h 15 min; convdiff adds about an hour). Nothing of mine waits on it.
2. Read it: sum.txt, the item-5 verdict list, convdiff/total.txt (0 differences, `exit 0`, 60 MATCH; slow 1, the same
   input), convdiff-plants.txt (5 rows, `exit 1`), convdiff/suite-exit.txt (its failed set may hold the five above and
   nothing else beyond base's). The plain suite must equal base's failed set (127; the five must pass there).
3. `bar.sh land 82518dc` in the worktree without PUSH, read the incoming diff, then PUSH=1 (p1/bar.sh :44-:70; the
   push guard compares source with the tested SHA; this handoff commit and results/ don't count). rust-slice was at
   899d354 at 04:30Z 17 Nov.
4. The probe on the landed SHA against 21 of 32 (pareto0 ~/sp19/sa-rust-ids-work/pc299.sh is the last one: copy it
   to a pc303.sh with its own clone and output directory), results/convert-step.md, the report (Status: done).

## File:line map

Unchanged from HANDOFF-sa-port-302.md (rust-spike/slice/: convert_diff.py, test_convert_walk.py,
solver_rs/src/term/walk.rs, convert.py, p1/convert_diff.sh, p1/bar.sh land :44-:70, phase convdiff :179). New:
results/convert-step.md "The bfac1a4 differential, read" (after "Item 6, continued"); orion
~/sa-rust-ids-work/sa-port-303/ (extra5.sh, base-failed.txt, diff-bfac1a4-failed.txt, diff-5c7db78-failed.txt);
orion ~/sa-rust-ids-work/sa-port-302/bar/ (bar-launched.txt, p0-bar.txt, diff-read.txt, bar-p0.log).

## Notes

- Plants 670-674 used, next free 675; counters 706-719 free, none used.
- Known, by id: test_lazy_reads.py::test_stock_term_plant_is_caught[finite-stock_finite] (~3/40, base too);
  tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence (id() reuse).
- Not run by me: no new livecmp beyond the differential's 60 rows (the bar's live phase repeats it on 82518dc).
