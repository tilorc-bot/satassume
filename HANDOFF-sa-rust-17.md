# Handoff sa-rust-17: S step 4 is half done (issue 323, branch rust-slice)

Handed off at the context note, 03:26 UTC, 7 Nov. Item 1 (suite) has its numbers. Items 2 and 3 aren't finished. The gate has not been decided. Step 4 finishes first, and then step 5.

## Done: the planner's three numbers
Full table and lists: `rust-spike/slice/results/step4-suite.md`. Crate unchanged (`sa_solver.so` sha 44577e02). Orion, seed 0, 4 workers, one run.

| | tests |
|---|---:|
| 1. Ran on Rust and passed | 5,949 |
| 2. Kept on Python, needs internals (all pass on Python) | 77 |
| 3. Failed | 57: 46 re-entry, 11 failing the same way on pure Python |
| Skipped / xfailed, same on both | 23 / 18 |

- **Don't describe this as "passes the full suite".** 3,129 of the 5,949 made no solver inside the test, so only 2,820 are evidence about Rust (shared fixtures may add a few). Python solvers made in the Rust run: 0.
- **19 files**, not about 14: 19 in `tests/` import `Solver` by name, plus `harness/invariants.py`.
- **Plugin size:** the ruling's item 1 took a small plugin, `rust_plugin.py`, so no Status: question. It adds `_to_int` and `_to_ext` (stateless) and a read-only `_n_conflicts` from public `stats()`. That view moved 64 tests in `test_stress_wide` and `test_wide_derived` onto Rust. **The planner should look at it**, since they ruled out porting private attributes; I read it as not a port.
- **The list does not match the handoff's.** Extra, raising outside sa-rust-16's files: `test_verify_integration.py:95` `_trail_lim`, `test_writeback_provenance.py:212` `_cowner`, `:29` and `:60` provenance (4 tests). `test_lra_integers` is on the handoff's list but has none. The first two extras were read at their lines; `:29` and `:60` were classed by their error text. Reported as a mismatch, not resolved.
- **Hand-classed:** the 3 `test_solver.py` rule-block tests that count `_CountingSolver._rb_reason`, as subclassing, by node id in `suite_report.py`'s `SUBCLASS`. All other kept tests are classed by the failure's own text.
- **Re-entry:** 41 of 46 raise at `tests/theory_harness.py:242`, the `Recorder.check` audit, a test stub. **The other 5 show only a hypothesis decorator frame** (`test_euf_fuzz.py:555,574`, `test_lra_fuzz.py:200,212`, `test_theory_hooks.py:217`), so their site isn't confirmed. Confirm before saying "only test stubs". Nothing was fixed.
- **The 11 failing on both** are subprocess tests (`test_compiled_rows` 2, `test_layering` 6, `test_memos`, `test_sympy_boundary`, `test_trig_rows`). The one message read in full is `No module named sympy`; the cause looks like this environment (sympy on PYTHONPATH only), not confirmed for all 11. They give no evidence for either backend.
- **A one-off:** in the first Rust run, `test_lra_fuzz::test_fuzz_entails_and_implied` hit its 120 s timeout while generating data, at load about 20. In the rerun it failed with re-entry instead. So it didn't recur, but load wasn't shown to be the cause.
- Two timing tests failed on Python under load and passed on Rust. That says nothing about speed.
- B to E: not checked under the suite yet.

## Done: boundary mutants, API columns only
`rust-spike/slice/results/step4-mutants-api.md`, M indexes 10 to 34 (25 mutants), unmutated row "no" throughout.
21 of 25 caught by the API fuzzer. **Not caught so far: 27 (`conflict_of` falsy), 29 and 30 (stale handles), 31 (`__traverse__` leak).** This table alone doesn't meet the pass rule. "Batch flush order": the crate has no batching layer, so 10 to 12 mutate the batches it has (pending trail, `add_clauses`, `add_internal`). Say so.

## Not done, in order
Tools are at this head. **Except where a line says otherwise, none has finished a run**, so check their output before trusting it.
1. **History 1 to 4:** `run_history.sh WORK 3`, WORK = `~/sa-rust-ids-work/slice/step4/hist`. 14 of 56 runs were done at handoff, and the job was started from this session, so it may die with it. If `finished.txt` is missing and nothing is running, rerun: it skips finished runs. Then `historycmp.py WORK`.
2. **Audit-off run:** `$W/suite-audit-off` was in flight (`SLICE_AUDIT_OFF=1`, 7 theory files). It puts the real-theory fuzz tests on Rust with the harness's internal audit off. Report it apart from the three numbers. If `exit.txt` is missing, rerun it with the command in `run_suite.sh`'s header style: `SLICE_AUDIT_OFF=1 PYTEST_N="-n 3" bash rust-spike/slice/run_suite.sh DIR rust FILES`. A `mark` level check may fail with the solver hidden: read those as harness limits, one by one.
3. **Nested column:** `mutate_boundary.py $W/mut-api $W/mut-nested --jobs 3 --seeds 500`. `boundary.py` ran clean on the unmutated build (100 seeds, 66 nested-in-hook counts). The scorer's only run was stopped in its first minute. Delete `$W/mut-nested` first. **First add an "odd" kind to `boundary.py`**: `check` returns `(0, model)` for `(True, model)` and `assert_lit` returns `(None, [x])` for None. Without it nothing can catch mutant 27; my edit for this was never applied. Python tests `is False`.
4. **Live columns:** `mutate_live.py WORK REF --only 10,...,34 --jobs 5 --timeout 1500`. REF needs `dev-py.jsonl` and `fuzz-py.jsonl`: symlink them to `hist/recorded-*-py.jsonl`. Step 3's REF wasn't kept.
5. **Run 5:** `SLICE_SUITE_SHUFFLE=1` suite on both backends, and `harness_rust.py rust|python OUT fuzz --seeds 0-3 --config all`, compared. Check its last line shows Rust solvers made. Avoid `--confirm` and `hashseed`: their subprocesses don't get the patch.
6. **Run 6:** dropped against created from `historycmp.py`, and `rg static` in the crate.
7. **Reach:** `$W/probe/sa_solver.so` is built (`probe_build.py`). Run the suite with `SLICE_SO=$W/probe PROBE_FILE=FILE` and count by name: restarts, `reduce_db`, mutants 2, 5, 6, 7, 9.
8. Optional: `mutate_boundary.py --suite FILES`, for whether the suite itself catches callback bugs.
9. Write `results/step4-*.md`, commit, push, report.

Don't use `pkill -f` on a pattern that also appears in the same command: it killed my own shell once.

## For step 5
- `rust-spike/slice/run-slice.sh` still names `/work/src/base-9bafaa5` and runs `qtime.py`. It needs the current source and the Rust backend. Not touched here.
- **Crossing counts (step 3, measured):** hook calls 34,788 on dev and 1,241,630 on fuzz.
- **Plan section 2 correction:** its "80k on dev, 2.67M on fuzz" counted internal calls too. Real crossings are 44% and 46% of that, so the callback part of the estimate is about 2.2 times too high. Use the measured counts.
- Report full API and abi3 both (plan section 4).

## Running the tools
As in `HANDOFF-sa-rust-16.md`: from ~/dev/sa-rust, `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH SA_EVAL_DATA PYTHONHASHSEED`. `W=~/sa-rust-ids-work/slice/step4`. Suite: `run_suite.sh WORK rust|python [args]`, about 15 minutes; `suite_report.py RUST PYTHON` (`$W/suite-rust2`, `$W/suite-python`). Orion's load was 15 to 20 from all sessions, so keep jobs modest.
