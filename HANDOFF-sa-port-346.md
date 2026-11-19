# HANDOFF sa-port-346: (1), (2), (3) committed and pushed; the gate (4), S1 (5) and the bar (6) NOT STARTED; NOTHING IS LANDED

Stopped at the context budget. Branch port/witness-bounds (pushed), worktree ~/sa-rust-ids-work/sa-port-346/wt in
clone ~/dev/sa-port-5, from bfceccc9. Not rebased: rust-slice was 29c5a0db and sa-port-345 was still queued at
17:40Z 19 Nov. No job of mine is running.

## Commits

- 49b1efc (1) the engine's exits before any point: `Engine._ends_without_session`, asked by `witness.witnesses`
  after the compile; two kept tests.
- 50d8b77 (2) the work bound, SLICE_WITNESS_WORK default 2500; harness/state.py; three kept tests.
- 43e3ee8 (3) plants 758 `check-first`, 759 `skip-work`.
- then results/witness-bounds.md, tools346 and this file.

Checked on orion only (.so a956b03496066671, no Rust change): tests/test_witness.py 157 passed with the switch off
and on (py) and on under rust_plugin; test_module_state_inventory_is_classified passed; digests on dev, fuzz, budget
and wiring equal 344's, py and rust. The whole suite has not been run.

## Not done, in order

1. Rebase onto origin/rust-slice once 345 has landed (no source conflict expected: 345 lands bfceccc9 plus results).
2. (4) the gate: tools343/go343.sh, job342.sh and jobb343.sh are the pattern (pareto0, --shared): suite by id, iv,
   20 workloads and fuzz seeds, switch on. Add: `Engine.stats` and `last_budget_limited` on budget, on against off.
3. (5) S1, pareto1 quiet lease, 12 rounds: tools343/onlease343.sh and tools342/time342.sh, med342.py are the
   pattern. Arms worth one lease: 345's SHA off and on; the head off and on; the head on with
   SLICE_WITNESS_PLANT=check-first (item (1) taken out) and with SLICE_WITNESS_WORK=8400 (no certification lost);
   py and rust. Two rules are at risk, see witness-bounds.md (1) and (2): fuzz against on at 345's SHA (the budget
   test is new cost for 1284 certified calls) and wiring on against off. A loss is Status: question, with the arms.
4. (6) the bar with rows `witness:on witness:check-first witness:skip-work` (bar.sh penv :100 takes any
   `witness:NAME`), then land.

## FILE:LINE MAP (43e3ee8)

- satassume/engine.py: `_within_budget` :1814, `_ends_without_session` :1860, `_over_budget` :1876, `ask` :2219.
- satassume/witness.py: CAP :102, WORK :107, the plants' list :104-115, `_Query.spend` :559 (759's site :564),
  `_roots` :707, `_pools` :744, `witnesses` :819 (the engine's test and 758's site :849).
- satassume/sympy_api.py: the check's call :1136 (unchanged).
- tests/test_witness.py: :636 over-budget, :658 INCONSISTENT set, :683 `work`, :693 `_spent`, :710, :721, :741.
- harness/state.py :290.
- rust-spike/slice/results/witness-bounds.md; tools346: pc346.py (per-call rows with size, work, the test's time),
  pcrun346.sh, ana346.py, wk346.py, ex346.py (which exit), env346.sh, wk-20wl.md, wk-fuzz-seeds-0-1-2-42.md,
  pc1-sum.txt. Rows on orion: ~/sa-rust-ids-work/sa-port-346/pc0, pc20, pcseeds (no bound), pc1 (the head).

## Must stay in every report

Tested SHA 43e3ee8 (source), orion .so a956b03496066671; pareto .so not built for this branch. SLICE_WITNESS off by
default and the unchanged path the default. No SymPy construction or evaluation at query time. Certifications
before -> after at cap 32: dev 173 -> 173, fuzz 1284 -> 1284, wiring 231 -> 215, 20 workloads 1844 -> 1828. S1
wall times: none yet (nothing here is from a quiet lease). Known base rows by id: witness-reasons.md section (5).
The Rust port of the per-call compile and pools is not started. OWED [153] open.
