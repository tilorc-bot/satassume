# PR 328 on `rust-slice`: checks (issue 323)

2d00bea applies PR 328 (head 68c86b5, same patch-id; open, held for Tilo, not merged). **The checks ran after that commit reached origin:** a push of a document commit from another session in this clone published it at 06:42 UTC, before any check. The architect ruled that it stays. All runs: orion, source at 2d00bea, `tree.txt` in each directory confirming the import path. Crate unchanged, `sa_solver.so` sha 44577e02, as in step 4. Results under `~/sa-rust-ids-work/port-census/pr328-check/`.

## Rust against Python, and before against after

`run_live.sh`, hash seed 0: every comparison reads MATCH.

| Workload | Queries | Sessions | Answers differ, Rust and Python | End states differ | Call streams differ | Answers differ from before PR 328 (Python, Rust) |
|---|---:|---:|---:|---:|---:|---|
| dev | 1,985 | 918 | 0 | 0 | 0 | 0, 0 |
| fuzz | 3,000 | 3,133 | 0 | 0 | 0 | 0, 0 |

"Before" is step 4's `hist/recorded-*`, source identical to 2c195c4 under `satassume/` and `tests/`. `answers_sha` on dev is 31cd0945c07f02a6 on all of them. Fresh engine per query (`seed_state.py`): 0 answer differences before and after, on dev and fuzz. PR 328 does move state, as intended: 26 of 1,985 dev and 845 of 3,000 fuzz queries at seed 0, Python.

## Hash seeds, Python, in the source this time

`seed_state.py`: fresh engine, memos cleared, digest of each session's solver at query end.

| Workload | Without PR 328 (2c195c4), seeds 0-1 | With PR 328 (this tree) | Seed pairs | Answers or session counts differ |
|---|---:|---:|---|---:|
| dev, 1,985 | 39 | **0** | 0-1, 0-2, 0-3 | 0 |
| fuzz 424242, 3,000 | 131 | **0** | 0-1, 0-2 | 0 |
| corpus, 2,863 | not rerun (13 in section 5) | **0** | 0-1 | 0 |

Same as section 5's result, which was from outside the source. Still a sample of orders, over 2 to 4 seeds, and the digest covers the solver dump only.

## History runs, `run_history.sh` and `historycmp.py`

**Dev: finished.** Recorded, two shuffles, fork, twice, seeds 1 and 2: 7 of 7 pairs, 0 differences in answers, end state, stream or session count. Against recorded, seeds move no state on either backend, and shuffles and fork move the same counts on both (335, 358, 1,549).

**Fuzz: still running when this was written, so not a result.** See the report for its final state.

## The suite's three numbers

`run_suite.sh`, both backends, `SLICE_SUITE_SHUFFLE=1`, 3 workers, as step 4's run 5.

| | Before | With PR 328 |
|---|---:|---:|
| 1. Ran on Rust and passed | 5,960 | **5,961** |
| 2. Kept on Python, needs internals | 77 | **77** |
| 3. Failed: stub re-entry, one cause | 46 | **46** |
| Skipped / xfailed | 23 / 18 | 23 / 18 |

**The change:** +1 is the test PR 328 adds, `tests/test_history.py::test_clause_sequence_does_not_depend_on_the_hash_seed`. It's among the tests that made no Rust solver in the test (3,138 to 3,139; those that did stay 2,822). Compared by test id with run 5: 1 new, none gone, 0 outcomes changed on Rust, so the 46 are the same 46.

**S's standing:** its gate is met except for the 46 named stub failures, one cause. This isn't "passes the full suite". The `_n_conflicts` view in `rust_plugin.py` is a test-plugin shim, not a port; it moved 64 tests.

**One Python failure, not in the three numbers:** `tests/test_solver.py::test_performance_smoke_300_vars`, 6.11 s against its `assert dt < 5.0`, in the Python run (6,083 passed, 1 failed); passed on Rust and in run 5. Call: wall-clock under load, not PR 328. It's a pure-solver test, PR 328 doesn't change `sat/solver.py` or this test, and orion's load was about 14-16 against 12 cores. Rerun at that load: through pytest on this tree, passed 1 of 3; called directly, 4 of 4 on each of 2c195c4 and this tree. Not run: pytest on 2c195c4, or anything on a quiet machine, so this is the likely cause, not a shown one.

## Not run or not changed

- `harness_rust.py`, the mutants, and the boundary suite column: not rerun. Mutants 2, 5, 6, 7, 9 rest on the API fuzzer alone, 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- **`lra/port/src/lra.rs` still has the CPython set copy (`PySet`, for `_dirty`).** It isn't connected to anything yet, and changing it is port work, so it's left for step 1a. Nothing here tests Rust's `_dirty` order: LRA still runs on Python.
- The solver crate needed no change.

## Tool fix

`run_live.sh`, `run_history.sh` and `run_suite.sh` took their source from `env.sh` or `cd ~/dev/sa-rust`, whichever clone they sat in. Run from this clone they'd have tested the source without PR 328. They now use the tree holding the script and write `tree.txt`. `run5_harness.sh`, `run-audit.sh` and `run6_counts.sh` still use the old path; none was run here.
