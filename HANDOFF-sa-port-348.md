# HANDOFF sa-port-348: ruling B applied (82d4ddf), its gate read and clean, the bar RUNNING and not read; NOTHING IS LANDED

Stopped at the context mark, on the architect's word (22:29Z 19 Nov). Branch port/witness-bounds (pushed), worktree
~/sa-rust-ids-work/sa-port-346/wt in clone ~/dev/sa-port-5, on rust-slice 2030cdc6. Tested source **82d4ddf**; the
commits after it are results, tools and this file only. What is left is land-only.

## Done

- (4) b2c929e: the gate on 180e501 read, results/witness-bounds.md (4). Clean.
- (5b) 82d4ddf: ruling B. `witness.witnesses` asks `Engine._known_inconsistent(assumptions)` (a `_verdict` read);
  `_ends_without_session` and its budget half are gone; plant 758 keeps the INCONSISTENT read as its site; the comment
  at `WORK` says how 2500 was chosen. Tests by id: removed
  `tests/test_witness.py::test_a_query_over_the_budget_is_the_engines_as_with_the_switch_off[0]`, `[1]`, `[2]`; in
  their place `::test_a_query_over_the_budget_still_answers_none[0]`, `[1]`, `[2]` (None off and on; off counts budget
  limited, on certified). No other test touched. This replacement is 348's reading of condition 3 and is named in the
  report for the planner.
- Condition 1: the gate on a frozen 82d4ddf against 2030cdc6 (tools348/stage348.sh, go348.sh; pareto0 lease 1758122d,
  END 0 at 22:47Z): witness-bounds.md (5b). Clean: answers equal on against off (dev, fuzz 424242, seeds 0/1/2/42
  under four hash seeds, 20 workloads, py and rust), iv 0 runs differ, suite by id 0 outcomes differ (Rust 127 known
  base ids in on, off and base; Python 0 failed), budget's 15 over-budget rows equal on against off. The arm at 8400
  was not rerun on 82d4ddf (not in condition 1; (4) reads it on 180e501).
- Conditions 2 and 3 and the report's lines (the dev exception and its cause, certified at 2500 against 8400, the
  OWED trigger): witness-bounds.md (5b) and "Owed, named here".

## Running when I stopped

The bar on pareto0, shared lease 9d4bce81, started 22:48:51Z 19 Nov, detached from orion (setsid):
`~/sa-rust-ids-work/sa-port-348/tools/gobar348.sh 82d4ddf cad764d46471b1c6` (job348bar.sh on pareto0), on the frozen
branch origin/bar/witness-bounds-82d4ddf. Rows witness:on, witness:check-first, witness:skip-work, as workload and as
suite rows; BASE sa-port-344's bar suite on pareto0. **End marker ~/sa-rust-ids-work/sa-port-348/gobar-end.txt on
orion, written by gobar348.sh:20 (its last line)**; "END 0 END 0 ..." is a clean run. About 90 minutes by 345's bar.
No waiter shell of mine is on it. Nothing else of mine runs.

## Not done, in order

1. Read the bar once gobar-end.txt exists: ~/sa-rust-ids-work/sa-port-348/bar (copied back without jsonl rows),
   bar-end.txt, bar.log, env-summary.txt, launcher-env.txt. As 345 read its bar (witness-reasons.md (7), :405): the
   sum, the suite against BASE by id, the plain rows (switch unset: the default path), the three witness rows on the
   workloads and as suite rows with each row's WALL TIME (the planner asks for it), fired from counter 740 for
   check-first and skip-work (a zero shows nothing: check it fired), so-loaded.txt cad764d46471b1c6, source 82d4ddf.
   Expected: witness:check-first is caught by its suite row only (tests/test_witness.py's INCONSISTENT-set test); no
   workload differs under it. witness:skip-work: wiring certified 231, not 215, answers equal; caught by two tests.
   Whether the state comparison of witness:on reads `_known_inconsistent`'s version check is the owed look of
   witness-bounds.md "Owed".
2. Write it as section (6) of results/witness-bounds.md, fix the title line and the state paragraph, commit.
3. `git fetch`; if origin/rust-slice is still 2030cdc6: in the worktree `bash rust-spike/slice/p1/bar.sh land 82d4ddf`
   (reads the guard), then `PUSH=1 bash rust-spike/slice/p1/bar.sh land 82d4ddf`; rule [91]. If rust-slice moved, the
   LANDING ORDER block says what to do. Report the landed SHA; OWED [153] settles; tell the architect.
4. If the bar is not clean: no landing; report what differs.

## FILE:LINE MAP (82d4ddf)

- satassume/engine.py: `_within_budget` :1814, `_known_inconsistent` :1860, `_over_budget` :1876.
- satassume/witness.py: CAP :102, WORK :113 (comment :104-112), the plants' list :114-121, FIRED :124, `_Query.spend`
  :565 (759's site :570), `witnesses` :825 (the INCONSISTENT read and 758's site :854).
- tests/test_witness.py: :636 over-budget still None, :656 INCONSISTENT set, the work-bound tests after it.
- rust-spike/slice/p1/bar.sh: land :50-77, penv :100.
- rust-spike/slice/results/witness-bounds.md: (4) gate of 180e501, (5) S1, (5b) ruling B and the gate of 82d4ddf,
  Owed. results/tools348 (stage348.sh, go348.sh, jobb348.sh, gobar348.sh, job348bar.sh); tools347; witness-reasons.md
  :405 (345's bar, the model for (6)).
- orion ~/sa-rust-ids-work/sa-port-348: job-82d4ddf, jobb-82d4ddf (the gate), so/, tools/, orion/ (local test logs,
  ki348.py), gobar.out, bar-launch.log, then bar/ and gobar-end.txt. pareto0 ~/sp19/sa-rust-ids-work/sa-port-348.

## Must stay in every report

Tested source 82d4ddf (180e501 before ruling B: its gate is evidence, section (4)); .so: pareto venv cad764d46471b1c6
(gates, bar), bench 0982a28074215658 (S1, on 180e501), orion a956b03496066671; no Rust change. SLICE_WITNESS off by
default and the unchanged path the default. No SymPy construction or evaluation at query time. Certifications before
-> after at cap 32: dev 173 -> 173, fuzz 1284 -> 1284, wiring 231 -> 215, 20 workloads 1844 -> 1828. S1 wall times
from the quiet lease 9e0c7e81 only (witness-bounds.md (5)); no S1 on 82d4ddf, by the ruling (the cf arm is read as
its time; the remaining read is 0.1% of a pass on orion, not S1). The named exception: dev on, +0.9% py / +1.2% rust
against 345 on, cause the work count of item (2). Known base rows by id: Rust 127 (witness-bounds.md (4)), iv
test_transfer.py's two, the planted-history id()-reuse test. Quiet catches recorded: Rust 49 in 9 ids, Python 10 in 7
ids, on, off and base. The Rust port of the per-call compile and pools is not started. OWED [153] open until landed.
New OWED item named: a cheaper budget test for the check, trigger a workload with an over-budget query that is
certified slowly.
