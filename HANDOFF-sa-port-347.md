# HANDOFF sa-port-347: rebased, S1 read (the landing rule FAILS on dev and fuzz), the gate started and NOT READ, the bar not started; NOTHING IS LANDED

Stopped at the context budget, on the architect's word, with a question open to the planner (report 25f6298: A land
as is, B take the budget half of item (1) out, C a cheaper test as a new step). Branch port/witness-bounds (pushed),
worktree ~/sa-rust-ids-work/sa-port-346/wt in clone ~/dev/sa-port-5, rebased onto rust-slice 2030cdc6. Tested source
180e501 (43e3ee8 before the rebase, the same diff); the commits after it are results and tools only.

## Done

- Rebase onto origin/rust-slice 2030cdc6 (345's landing): 4c69d9c (1), 1e496f7 (2), 180e501 (3), no conflict.
- tools347 (results/tools347): the gate's jobs (stage347.sh, go347.sh, job347.sh, pre347.sh, jobb347.sh, bs347.py),
  S1's (gos1347.sh, onlease347.sh, time347.sh, arm347.py, med347.py, tab347.py, s1-med.txt), the bar's (gobar347.sh,
  job347bar.sh; written, never run).
- (5) S1 read and written: results/witness-bounds.md "(5) S1". In short, head on against 345 on: dev +2.4% (py and
  rust), fuzz +5.2% / +6.9%, beyond the spread; budget -71.0% / -78.5%, wiring -12.6% / -11.3%. The cause is item
  (1)'s budget test (head on against the check-first arm: fuzz +4.5% / +6.1%). The bound stays 2500 (the sum of the
  four is 3.6% / 3.7% lower than at 8400, beyond the spread).

## Running when I stopped

The gate on pareto0, shared lease 3ca5f4f4, detached from orion (setsid): `tools347/go347.sh 180e501 2030cdc6 01e8ca74`.
End marker ~/sa-rust-ids-work/sa-port-347/go-end.txt on orion, written by go347.sh:18 (its last line), expected about
21:20Z 19 Nov. Its first half (job347.sh: suites, pre, iv) ended on pareto0 at 19:46Z; jobb347.sh was running.
My waiter shell on it is stopped. Nothing else of mine runs; pareto1's lease is released.

## Not done, in order

1. Read the gate once go-end.txt exists ("END 0 ..."). Everything is copied to ~/sa-rust-ids-work/sa-port-347:
   - job-180e501/suite-cmp.txt (the suite by id, on/off/base, py and rust; known base rows: witness-reasons.md (5)),
     job-180e501/iv-cmp.txt (iv: no moved id), job-180e501/pre/ (dig/dig.jsonl: dev and fuzz digests off, on and under
     each plant incl. check-first and skip-work; tw/*.log: test_witness.py per backend, switch and plant;
     rep/rep-sum.txt: the planted-history repeat, a28c548's method).
   - jobb-180e501/gate-180e501/answers.txt and xans.txt (20 workloads, on against off, and against 343's rows of
     01e8ca74, whose tree differs from 2030cdc6 in harness/state.py's inventory only); gate-180e501-w8400 and
     xans-w8400.txt (the same at SLICE_WITNESS_WORK=8400); bs.txt (bs347.py: Engine.stats, last_budget_limited and
     moved ids on budget's over-budget rows, on against off; also the check-first row gate-180e501-cf and the base);
     fz.txt and fz8400.txt (fuzz seeds 0 1 2 42 under four hash seeds). Count the quiet catches (rc.txt, *.err).
   - Known already: budget has 15 over-budget queries by the engine's counter (7 reach the check), and on 343's rows
     of 01e8ca74 every row's stats and last_budget_limited were equal on against off BEFORE this step; so bs.txt
     cannot tell the head from the base on this workload. The kept test (tests/test_witness.py:636) is what does.
   Write it as section (4) of results/witness-bounds.md.
2. Apply the planner's answer to report 25f6298 (the architect appends it to the NEXT brief):
   - (A) land as is: comment at witness.py:104-107 saying 2500 was chosen by S1 (sum of dev, fuzz, budget, wiring
     3.6% py / 3.7% rust lower than 8400, 12 of 12 rounds, lease 9e0c7e81) at the price of wiring's 16
     certifications; that is a source change, so the tested SHA moves: rerun the suite part of the gate or rely on
     the bar on the new SHA, as the planner says.
   - (B) the budget half of item (1) out: in witness.witnesses (witness.py:849) ask only the set's memoized
     INCONSISTENT (a `_verdict` read) and not `_within_budget`; rework `Engine._ends_without_session`
     (engine.py:1860), the kept over-budget test (tests/test_witness.py:636) and what plant 758 takes out; new SHA,
     then the gate (go347.sh NEW 2030cdc6 01e8ca74 after stage347.sh NEW 2030cdc6) and S1 again
     (gos1347.sh NEW 2030cdc6; onlease347.sh refuses if s1/timing-s1 exists on pareto1, so move the old rows or
     change the directory). Expected from the cf arm: fuzz within the spread of 345, dev about +1%.
   - (C) a new step: hand back.
3. (6) the bar: push the tested SHA as origin/bar/witness-bounds-SHA; copy 344's .so
   (~/sa-rust-ids-work/sa-port-344/so/sa_solver-bfceccc9.so, cad764d46471b1c6; the crate is unchanged) to
   ~/sa-rust-ids-work/sa-port-347/so/sa_solver-SHA.so with a so-SHA.txt beside it; then
   `setsid bash tools/gobar347.sh SHA cad764d46471b1c6` (stage347.sh puts tools347 in sa-port-347/tools; run it again
   after any tools change). Rows witness:on, witness:check-first, witness:skip-work; BASE is 344's bar suite on
   pareto0. End marker sa-port-347/gobar-end.txt (gobar347.sh's last line). Then `bar.sh land SHA`, PUSH=1.

## FILE:LINE MAP (180e501)

- satassume/engine.py: `_within_budget` :1814, `_ends_without_session` :1860, `_over_budget` :1876, `ask` :2219.
- satassume/witness.py: CAP :102, WORK :107 (comment :104-106), the plants' list :108-115, FIRED :118, `_Query.spend`
  :559 (759's site :564), `_roots` :707, `_pools` :744, `witnesses` :819 (the engine's test and 758's site :846-849).
- satassume/sympy_api.py: the check's call :1136. tests/test_witness.py: :636 over-budget, :658 INCONSISTENT set,
  :683, :693, :710, :721, :741. harness/state.py :290.
- rust-spike/slice/p1/bar.sh: land :50-77, penv :100. rust-spike/slice/live.py:505-508 (the eng rows bs347.py reads).
- rust-spike/slice/results/witness-bounds.md ((1)-(3) 346's, (5) S1); results/tools347; results/tools346.
- orion ~/sa-rust-ids-work/sa-port-347: s1/ (timing-s1, timing-bw, med.txt, tab.md), tools/, report-q1.txt.
  pareto0 ~/sp19/sa-rust-ids-work/sa-port-347 (s1/bench-180e501, bench-2030cdc6, job-180e501, jobb-180e501).
  pareto1 ~/sa-rust-ids-work/sa-port-347/s1 (common, bench-*, timing-s1, timing-bw).

## Must stay in every report

Tested source 180e501; .so: pareto venv cad764d46471b1c6 (gate, bar), bench 0982a28074215658 (S1), orion
a956b03496066671; no Rust change. SLICE_WITNESS off by default and the unchanged path the default. No SymPy
construction or evaluation at query time. Certifications before -> after at cap 32: dev 173 -> 173, fuzz 1284 -> 1284,
wiring 231 -> 215, 20 workloads 1844 -> 1828. S1 wall times from the quiet lease 9e0c7e81 only (witness-bounds.md
(5)). Known base rows by id: from the gate's suite-cmp.txt, not read yet. The Rust port of the per-call compile and
pools is not started. OWED [153] open.
