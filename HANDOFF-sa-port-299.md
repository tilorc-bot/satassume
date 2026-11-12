# HANDOFF sa-port-299 (rk_key step, issue 323): bar read, NOT landed; one test file not exit 0, question with the planner

Branch port/rk-key, head = the commit adding this file. Landing source 0bd82e4 (unchanged). rust-slice still 63d5632.
Worktree ~/sa-rust-ids-work/sa-port-296/wt (in ~/dev/sa-port-7). Scratch ~/sa-rust-ids-work/sa-port-299/ (orion) and
pareto0 ~/sp19/sa-rust-ids-work/sa-port-299/. Results: rust-spike/slice/results/rk-key-step.md (bar, the failure, probe).

## DONE
1. Bar on bfe7a87 (source 0bd82e4, .so f7e18b93; pareto0, END 0 08:27Z) read: equal to base (sa-port-294/bar) on suite
   (new 0, gone 0, changed 0), live 8/8 and extra 30/30 MATCH, quiet failures 39 = base, kept reasons, fm rows (0 differ; 4 and
   3 under the plants), plant table (425 rows, fired and verdict equal), suite plants. NOT clean on tests: 69 of 70 exit 0;
   test_lazy_reads.py::test_stock_term_plant_is_caught[finite-stock_finite] failed (test_lazy_reads.py:237, assert 0 > 0).
2. That failure classified, nothing fixed: 3/40 on the landing tree, 3/40 on base 1d22f9a, 8/40 on 86845aa; with SymPy's
   `_assumptions_rng` seeded 0-59 (twice each), the same 10 seeds fail on landing and base. It follows SymPy's shuffled
   assumption-check order (sympy/core/assumptions.py:596), not this step.
3. Probe on the candidate (pc299.sh): 40 jobs exit 0, 180 cells and all function/state keys equal sa-port-294/pc; 21 of 32.
   The bar's 442 knowledge.json files equal 294's.
4. `bar.sh land 0bd82e4` without PUSH: rebase is a no-op, guard clean (only HANDOFF and results/ differ from tested).

## OPEN (planner): does the bar count as clean with this one failure?
The 299 ruling says a bar that isn't clean is handed off with the diff and nothing fixed; the 281 gate (2) lets a failure pass
as known only on a known signature. This one is new to the list, so it wasn't landed on.

## NEXT (after the planner's answer)
- If yes: in the worktree `PUSH=1 bash rust-spike/slice/p1/bar.sh land 0bd82e4` (check `git log origin/rust-slice` is still
  63d5632 first), change the Status paragraph of results/rk-key-step.md to the landed SHA, push, report done. The probe needs
  no rerun: the landed tree adds results/HANDOFF files only.
- If the test is to be fixed first: test_lazy_reads.py:226-237 (seed `sympy.core.random._assumptions_rng`, or assert over
  several seeds); a test-only change under rust-spike/slice/ still trips the push guard, so the tests phase (at least) reruns
  on the new SHA per the planner.

## FILE:LINE MAP (on 0bd82e4, rust-spike/slice/)
- test_lazy_reads.py: eager() :96, planted() :115, evaluations() :204, stock_finite :221, the test :226, the assertion :237.
- SymPy (pareto0 ~/sp19/sa-rust-ids-work/sympy): sympy/core/assumptions.py:596 shuffle; sympy/core/random.py:45 `_assumptions_rng`.
- solver_rs/src/relkeys.rs: is_basic :42, is_joinable :55, rk_key :83. session_glue.rs + session_live.py: ded9d0b.
- test_rk_key_targets.py, test_guard_method.py:43, test_entry_frame.py.
- p1/bar.sh land mode (:3, :46-66); p1/one_test.sh.
- Scripts (orion ~/sa-rust-ids-work/sa-port-299/): lz299.sh (repeat), lzseed299.sh (by seed), pc299.sh (probe), pccmp299.py
  (probe compare). Rows on pareto0 ~/sp19/sa-rust-ids-work/sa-port-299/: lz/sum.txt, lzseed/sum.txt, pc/, pccmp.txt.
- Bar rows: pareto0 ~/sp19/sa-rust-ids-work/sa-port-298/bar (sum.txt, tests.txt:37, tests/test_lazy_reads.py.log).
