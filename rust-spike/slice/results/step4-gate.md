# Step 4 gate: settled items (issue 323)

**The gate is not decided.** Live mutant columns, 7 fuzz history runs and the harness compare were still running at 04:32 UTC, 7 Nov. See `HANDOFF-sa-rust-18.md`.

## The planner's three numbers
Run 5: real crate (`sa_solver.so` sha 44577e02), shuffled order, 3 workers, orion. An unshuffled run on the probe build gave the same counts.

| | tests |
|---|---:|
| 1. Ran on Rust and passed | 5,960 |
| 2. Kept on Python, needs internals (all pass on Python) | 77 |
| 3. Failed | 46, all with the borrow RuntimeError from a test stub |
| Skipped / xfailed, same on both | 23 / 18 |

Python on the same run: 6,083 passed, 0 failed. Python solvers made in the Rust run: 0.
- **Not "passes the full suite".** Number 2 and 3 are real. Of the 5,960, 2,822 made a Rust solver inside the test; 3,138 didn't, so they say little or nothing about Rust.
- Change from sa-rust-17 (5,949 / 77 / 57): the 11 failing on both now pass on both.
- By-name lists: `step4-lists.md`. Full report: `step4-suite-run5.md`.

## The 11 failing on both: environment, fixed
The tests set `PYTHONPATH` to the repo root, or run `python -I`, so their subprocesses lost sympy, which was on `PYTHONPATH` only. Added `~/sa-rust-ids-work/venv/lib/python3.12/site-packages/sa_rust_sympy.pth`, outside the clone. Their 5 files: 137 of 137 pass on both backends. **These 11 count in number 1 but aren't evidence about Rust:** they do their work in subprocesses, which don't get the patch.

## Re-entry: only a test stub
Every borrow RuntimeError found raises at `tests/theory_harness.py:242`, in `Recorder.check`, which audits the solver from inside a hook. This covers the 5 that showed only a Hypothesis frame: read from their sub-exceptions, and the text of all 5 in run 5 names line 242.
- **Adapters:** `LRATheory`, `EUFTheory` and `TransferTheory`, the objects that get hooks, hold no solver reference (rg for `self._solver` and the like hits only `lra_adapter.py` and `euf_adapter.py`, whose objects aren't attached as theories). Read, and consistent with the runs below; not a proof over every path.
- **Audit off (`SLICE_AUDIT_OFF=1`, 10 theory files, Rust):** 0 borrow errors in 928 tests.
- **Control:** the same patch on pure Python. Every Rust failure that isn't a missing attribute fails on Python with the same message (hiding the solver breaks the harness's level checks). No test fails on Python and passes on Rust except where Python's failure comes after the attribute Rust lacks.
- **`SLICE_AUDIT_OFF=2`** also drops `check_protocol`: of the 18 such tests, 17 pass on both backends, so their answer comparisons ran on Rust. The other, `test_protocol_on_fuzz`, needs the counts that patch removes, and fails the same on both.
- Of the 46, 44 pass on Rust with the audit off. The other 2: `test_protocol_on_fuzz`, and `test_real_theories_match_fresh_solvers[both]`, which then reads `_trail_lim`.
- **They stay failures in number 3.** Audit-off is reported apart and isn't part of the numbers. Hook-audit limit: an exception swallowed by `except` inside a hook wouldn't show here.

**One open oddity:** `test_lra_fuzz.py::test_fuzz_entails_and_implied` hit its 120 s guard during data generation in 2 of 5 audit-on Rust runs, after the audit had already failed it. Python passes it, and it passes on Rust in the audit-off-2 run with no timeout. That reads as Hypothesis shrinking a failure under load, but the cause isn't shown.

## "Needs internals": resolved test by test
All 77 raise in `tests/`, none in `satassume/` or `harness/`, and all pass on Python.

| Handoff mismatch | Finding | Verdict |
|---|---|---|
| `test_verify_integration.py:95` | Reads `solver._trail_lim`, then `_held`, `_backtrack`, on `sess.solver`. It gets the solver from the engine, so sa-rust-16's by-name search couldn't list it | In class: listed private attribute |
| `test_writeback_provenance.py:29` | `s.owner = "B"` raises the provenance NotImplementedError | In class: named by the ruling |
| `test_writeback_provenance.py:60` | `s.provenance(1, {})`, same | In class |
| `test_writeback_provenance.py:212` | `sv.owner is BOTTOM` passes, then `_cowner` raises | In class. **Lines 213 to 216 don't run on Rust** |
| `test_lra_integers` on the handoff, none kept | Its private reads are on the theory (`t._int_lits`, `t._lo`), not the solver; `Solver()` use is public. 808 pass on Rust with 1,481 solvers | The handoff's entry was wrong |

So the list is right and the handoff's was incomplete: no real failure was hiding in those 5. **Limit:** a kept test stops at its first private read, so anything after it isn't run on Rust. That includes `test_incremental_matches_fresh` and its family in `test_solver_incremental`, the suite's own differential tests of incremental against fresh. 20 of the 22 kept for a read inside the harness pass with the audit off.
**For the planner:** `_n_conflicts` is a read-only view of public `stats()` in `rust_plugin.py`, which moved 64 tests to Rust. I read it as not a port; it's their ruling.

## Mutants 27, 29, 30, 31: caught, nested column
`step4-mutants-nested.md`, 500 seeds, base row "no" (278 nested-in-hook sessions). Each was read for its reason:

| # | Caught by | First difference |
|---|---|---|
| 27 | `odd`, seed 5 | Python goes on to `prop`; the mutant raises RuntimeError from `solve`. **Only on the constructed `(0, model)` input**; `odd` was written to reach it |
| 29 | `in-check`, seed 1 | `outer.a check` goes to `inner.a` |
| 30 | `in-check`, seed 1 | payload `outer.b.5` arrives as `outer.a.5` |
| 31 | `in-check`, seed 1 | 0 alive after drop on Python, 6 on the mutant |

With the API columns, all 25 boundary mutants (10 to 34) are now caught by at least one column. Not caught by nested, all caught by API: 11, 12, 23, 26, 33, 34. Batch flush order: the crate has no batching layer, so 10 to 12 mutate the batches it has.

## Reach, suite on the probe build
| Path | Suite hits | With theories | Tests |
|---|---:|---:|---:|
| restart | 22 | 9 | 8 |
| `reduce_db` | 11 | 4 | 3 |
| mutant 2, 2+ pending blocks | 1,571 | 80 | 94 |
| mutants 5, 6, 7, 9 | **0** | 0 | 0 |

The audit-off-2 run on the theory files added nothing for 5, 6, 7, 9. **Those 4 paths rest on the API fuzzer alone**, with stub theories. Kept tests stop early on Rust, so they may reach these paths on Python only.

## B to E
None occurred: no panic in the run 5 or probe logs, and none in any failure's text. Unfixed.

## History so far
`step4-history-interim.md`: all 14 dev runs and the 3 finished fuzz pairs match: 0 answers, 0 end states, 0 streams differ. Query 873's state moves with order on both backends, as the plan requires. **Interim: 5 fuzz rows aren't finished.** `test_history.py` in shuffled order: 135 passed, 15 skipped, 1 xfailed on both; 4,253 Rust solvers.

## Run 6
No `static` or `thread_local` in the crate. The 3 `'static` are lifetimes: `solver.rs:2318` (`dump`'s names), `lib.rs:24` (`py()`), `lib.rs:89` (`PyProps`). Dropped against created: finished rows read 0/0; not yet final for fuzz.
